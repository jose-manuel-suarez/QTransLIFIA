"""Lógica específica de AWS Braket: cargador nativo y generador de scripts.

El parser nativo de Braket (``Circuit.from_ir``) es un intérprete de OpenQASM
propio, no un parser completo: reconoce un subconjunto de compuertas. Antes de
``Circuit.from_ir`` el OpenQASM se normaliza con ``_normalize_for_braket``, que
elimina los ``include "stdgates.inc"``/``"qelib1.inc"`` (que el parser nativo no
resuelve en disco, pues sus compuertas estándar ya están soportadas por el SDK)
y traduce las compuertas que Braket no define a sus equivalentes exactos.
"""

import re

from .qasm_utils import (
    _angle_to_expr,
    _sanitize_gate_name,
    _unquote_parameters,
)


# Include de librería estándar que el parser nativo de Braket no resuelve en disco
# (sus gates estándar ya están soportados por el SDK, así que la línea se elimina).
_STD_INCLUDE_RE = re.compile(r'^\s*include\s+"(?:stdgates\.inc|qelib1\.inc)"\s*;\s*$', re.I | re.M)


def _split_arguments(text):
    """Separa los argumentos de una llamada separando por comas de primer nivel.

    Parámetros:
        - text (str): contenido entre paréntesis (sin los paréntesis).

    Retorna:
        - list[str]: argumentos normalizados (sin espacios sobrantes).
    """
    arguments = []
    depth = 0
    current = ''
    for character in text:
        if character == '(':
            depth += 1
        elif character == ')':
            depth -= 1
        if character == ',' and depth == 0:
            arguments.append(current.strip())
            current = ''
        else:
            current += character
    if current.strip():
        arguments.append(current.strip())
    return arguments


def _rewrite_calls(text, name, build):
    """Reescribe las llamadas ``name(argumentos)`` de un código OpenQASM.

    Parámetros:
        - text (str): código OpenQASM.
        - name (str): nombre de la compuerta a reescribir.
        - build (callable): recibe la lista de argumentos y devuelve el texto
          sustituto, o ``None`` para dejar la llamada intacta.

    Retorna:
        - str: el código con las llamadas reescritas.
    """
    pattern = re.compile(rf'(?<![\w.]){re.escape(name)}\s*\(')
    pieces = []
    index = 0
    while True:
        match = pattern.search(text, index)
        if match is None:
            pieces.append(text[index:])
            break
        open_paren = text.index('(', match.start(), match.end())
        depth = 0
        close_paren = None
        for position in range(open_paren, len(text)):
            character = text[position]
            if character == '(':
                depth += 1
            elif character == ')':
                depth -= 1
                if depth == 0:
                    close_paren = position
                    break
        if close_paren is None:
            pieces.append(text[index:])
            break
        arguments = _split_arguments(text[open_paren + 1:close_paren])
        replacement = build(arguments)
        pieces.append(text[index:match.start()])
        pieces.append(
            text[match.start():close_paren + 1] if replacement is None else replacement
        )
        index = close_paren + 1
    return ''.join(pieces)


def _normalize_for_braket(qasm_str):
    """Adapta el OpenQASM al subconjunto de compuertas que entiende Braket.

    Traducciones aplicadas (todas equivalencias exactas):

    - ``p(theta)`` → ``U(0, theta, 0)``: la puerta de fase de OpenQASM es
      ``diag(1, e^{i·theta})`` y ``U(0, phi, 0)`` es esa misma matriz.
    - ``cx a, b`` → ``cnot a, b`` y ``u1/u2/u3`` → ``U(...)``: nombres de
      OpenQASM 2.0 que Braket no define.

    Los ``include`` de la librería estándar se eliminan (sus compuertas ya
    están soportadas por el SDK). Las declaraciones ``gate`` se conservan: el
    parser nativo de Braket las *expande* en línea, por lo que el circuito
    obtenido es equivalente pero no conserva la estructura de compuerta
    custom.

    Parámetros:
        - qasm_str (str): código OpenQASM (2.0 o 3.0).

    Retorna:
        - str: el código OpenQASM adaptado al parser nativo de Braket.
    """
    text = _STD_INCLUDE_RE.sub('', qasm_str)
    text = _rewrite_calls(
        text, 'u1', lambda args: f'U(0,0,{args[0]})' if len(args) == 1 else None
    )
    text = _rewrite_calls(
        text, 'u2', lambda args: f'U(pi/2,{args[0]},{args[1]})' if len(args) == 2 else None
    )
    text = _rewrite_calls(
        text, 'u3', lambda args: f'U({args[0]},{args[1]},{args[2]})' if len(args) == 3 else None
    )
    text = _rewrite_calls(
        text, 'p', lambda args: f'U(0,{args[0]},0)' if len(args) == 1 else None
    )
    return re.sub(r'(?<![\w.])cx(?=\s)', 'cnot', text)


def _braket_python_source(parsed_circuit, preserve_custom_gates=False,
                          custom_gate_definitions=None):
    """Genera el script Python (SDK Amazon Braket) que reconstruye el circuito.

    Las mediciones se difieren al final; si un qubit se mide más de una vez
    (p. ej. post-selección ``ps[i]`` y lectura final ``c[i]``) se emite una
    sola, porque Braket sólo admite una medición por qubit.

    Parámetros:
        - parsed_circuit (qiskit.QuantumCircuit): circuito de referencia parseado.
        - preserve_custom_gates (bool): si True, cada compuerta custom se define
          una sola vez como función local; si False se expande en línea.
        - custom_gate_definitions (list | None): pares (nombre, operación) de
          compuertas custom declaradas en el OpenQASM que el parser descartó por
          no usarse en el circuito; si ``preserve_custom_gates`` es True se
          definen igualmente como funciones locales (exhaustividad).

    Retorna:
        - str: código Python ejecutable que construye la variable ``circuit``
          (``braket.circuits.Circuit``).
    """
    instructions = []
    measurements = []
    measurement_qubits = set()
    repeated_measures = set()
    custom_functions = {}
    custom_scope = []

    def define_custom(name, operation):
        """Registra (una sola vez) la función local de una compuerta custom."""
        if name in custom_functions:
            return
        definition = operation.definition
        params = [f'w{index}' for index in range(len(definition.qubits))]
        qubit_positions = {bit: index for index, bit in enumerate(definition.qubits)}
        clbit_positions = {bit: index for index, bit in enumerate(definition.clbits)}
        before = len(instructions)
        custom_scope.append(name)
        try:
            for sub_item in definition.data:
                emit(
                    sub_item.operation,
                    [params[qubit_positions[bit]] for bit in sub_item.qubits],
                    [f'cl{clbit_positions[bit]}' for bit in sub_item.clbits],
                    1,
                )
        finally:
            custom_scope.pop()
        body = _unquote_parameters(instructions[before:], params)
        del instructions[before:]
        custom_functions[name] = (params, body)

    def custom_function(operation, qubits):
        """Define (una sola vez) una función local y emite su llamada."""
        base = _sanitize_gate_name(operation.name, 'custom_gate')
        # Las compuertas anidadas se nombran con el prefijo de la compuerta
        # que las contiene: si no, dos compuertas custom distintas que
        # compartan una operación interna (p. ej. ``mcphase``) reutilizarían
        # el cuerpo de la primera y perderían sus propios parámetros.
        name = f'{custom_scope[-1]}__{base}' if custom_scope else base
        define_custom(name, operation)
        arguments = ['circuit'] + [str(qubit) for qubit in qubits]
        instructions.append(f"{name}({', '.join(arguments)})")

    def emit(operation, qubits, clbits, depth=0):
        parameters = [_angle_to_expr(parameter) for parameter in operation.params]

        if operation.name == 'measure':
            qubit = qubits[0]
            if qubit in measurement_qubits:
                # Braket sólo admite una medición por qubit. Como este
                # generador difiere todas las mediciones al final del circuito,
                # una medición repetida del mismo qubit lee el mismo valor
                # (p. ej. la post-selección ``ps[i]`` y la lectura ``c[i]``),
                # así que se descarta y se deja una sola.
                repeated_measures.add(qubit)
                return
            measurement_qubits.add(qubit)
            measurements.append((clbits[0], qubit))
            return

        if (
            getattr(operation, 'base_gate', None) is not None
            and operation.base_gate.name
            in {'p', 'u1', 'u2', 'u3', 'u', 'swap', 'h', 'rx', 'ry', 'rz', 'x', 'y', 'z'}
        ):
            control_count = operation.num_ctrl_qubits
            controls = qubits[:control_count]
            targets = qubits[control_count:]
            base_name = operation.base_gate.name
            control_state = operation.ctrl_state
            control_args = (
                f', control_state={control_state}'
                if control_state != (1 << control_count) - 1
                else ''
            )

            if base_name == 'p':
                instructions.append(
                    f'circuit.cphaseshift({controls!r}, {targets[0]}, {parameters[0]})'
                )
            elif base_name == 'u1':
                arguments = [str(targets[0]), parameters[0], f'control={controls!r}']
                if control_state != (1 << control_count) - 1:
                    arguments.append(f'control_state={control_state}')
                instructions.append(f"circuit.phaseshift({', '.join(arguments)})")
            elif base_name in {'u2', 'u3', 'u'}:
                rotation_parameters = (
                    ['math.pi/2'] + parameters
                    if base_name == 'u2'
                    else parameters
                )
                arguments = [str(targets[0])] + rotation_parameters + [f'control={controls!r}']
                if control_state != (1 << control_count) - 1:
                    arguments.append(f'control_state={control_state}')
                instructions.append(f"circuit.u({', '.join(arguments)})")
            elif base_name == 'swap':
                instructions.append(
                    f'circuit.swap({targets[0]}, {targets[1]}, '
                    f'control={controls!r}{control_args})'
                )
            elif base_name in {'h', 'rx', 'ry', 'rz', 'x', 'y', 'z'}:
                arguments = [str(targets[0])] + parameters + [f'control={controls!r}']
                if control_state != (1 << control_count) - 1:
                    arguments.append(f'control_state={control_state}')
                instructions.append(f"circuit.{base_name}({', '.join(arguments)})")
            else:
                raise ValueError(f'Puerta Braket controlada no soportada: {operation.name}')
            return

        if operation.name == 'swap':
            instructions.append(f'circuit.swap({qubits[0]}, {qubits[1]})')
        elif operation.name == 'u1':
            instructions.append(f'circuit.phaseshift({qubits[0]}, {parameters[0]})')
        elif operation.name == 'u2':
            instructions.append(
                f'circuit.u({qubits[0]}, math.pi/2, {parameters[0]}, {parameters[1]})'
            )
        elif operation.name in {'u3', 'u'}:
            instructions.append(
                f'circuit.u({qubits[0]}, {parameters[0]}, {parameters[1]}, {parameters[2]})'
            )
        elif operation.name in {'h', 'rx', 'ry', 'rz', 'x', 'y', 'z'}:
            arguments = [str(qubits[0])] + parameters
            instructions.append(f"circuit.{operation.name}({', '.join(arguments)})")
        elif operation.definition is not None and depth < 10:
            # Custom gate declarado en OpenQASM (o controlado sin equivalencia
            # directa): se conserva como función local o se expande en línea.
            if preserve_custom_gates:
                custom_function(operation, qubits)
                return
            definition = operation.definition
            qubit_positions = {bit: index for index, bit in enumerate(definition.qubits)}
            clbit_positions = {bit: index for index, bit in enumerate(definition.clbits)}
            for sub_item in definition.data:
                emit(
                    sub_item.operation,
                    [qubits[qubit_positions[bit]] for bit in sub_item.qubits],
                    [clbits[clbit_positions[bit]] for bit in sub_item.clbits],
                    depth + 1,
                )
        else:
            raise ValueError(f'Puerta Braket no soportada: {operation.name}')

    for item in parsed_circuit.data:
        emit(
            item.operation,
            [parsed_circuit.find_bit(bit).index for bit in item.qubits],
            [parsed_circuit.find_bit(bit).index for bit in item.clbits],
        )

    # Compuertas custom declaradas en el OpenQASM pero no usadas en el
    # circuito: el parser las descartó, así que se recuperan aparte para que
    # el script sea exhaustivo con la biblioteca de compuertas del original.
    if preserve_custom_gates:
        for name, operation in (custom_gate_definitions or []):
            define_custom(_sanitize_gate_name(name, 'custom_gate'), operation)

    python_lines = [
        '# Importación de paquetes requeridos',
        'import math',
        'from braket.circuits import Circuit',
    ]
    if custom_functions:
        python_lines.extend(['', '# Compuertas personalizadas (funciones locales)'])
        for name, (params, body) in custom_functions.items():
            python_lines.append(f"def {name}(circuit, {', '.join(params)}):")
            python_lines.extend(f'    {line}' for line in body)
            python_lines.append('')
        if python_lines[-1] == '':
            python_lines.pop()
    python_lines.extend([
        '',
        '# Creación del circuito AWS Braket',
        'circuit = Circuit()',
        '',
        '# Puertas migradas desde OpenQASM',
        *instructions,
    ])
    if measurements:
        python_lines.append('')
        python_lines.append('# Mediciones en orden clásico, diferidas al final')
        if repeated_measures:
            listed = ', '.join(str(qubit) for qubit in sorted(repeated_measures))
            python_lines.append(
                f'# Qubit(s) {listed} medido(s) más de una vez en OpenQASM: '
                'Braket admite una sola medición por qubit'
            )
        python_lines.extend(
            f'circuit.measure([{qubit}])'
            for _, qubit in sorted(measurements)
        )
    return '\n'.join(python_lines) + '\n'


def _load_braket_native(qasm_str):
    """Parsea OpenQASM a un Circuit de Braket con su parser nativo.

    Normaliza antes el código (ver ``_normalize_for_braket``): elimina los
    ``include "stdgates.inc"``/``"qelib1.inc"`` y traduce las compuertas que el
    parser nativo de Braket no define (``p``, ``cx``, ``u1/u2/u3``).

    Parámetros:
        - qasm_str (str): código OpenQASM (2.0 o 3.0).

    Retorna:
        - braket.circuits.Circuit: el circuito parseado.
    """
    from braket.circuits import Circuit

    return Circuit.from_ir(_normalize_for_braket(qasm_str))


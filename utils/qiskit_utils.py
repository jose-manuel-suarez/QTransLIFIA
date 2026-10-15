"""Lógica específica de Qiskit (IBM): cargador nativo y generador de scripts.

El dispatch público sigue en ``utils.qutils.provider_python_source``; este módulo
expone el parser nativo (``_load_qiskit_native``) y la generación de código Qiskit
(``_qiskit_python_source``) junto a sus helpers (``_native_gate_for_u``).
"""

import re

from utils.qutils import (
    _angle_to_expr,
    _sanitize_gate_name,
    _unquote_parameters,
)


_HALF_PI = 1.5707963267948966
_PI = 3.141592653589793


def _native_gate_for_u(theta, phi, lam):
    """Devuelve la puerta nativa de Qiskit equivalente a un gate U(θ, φ, λ).

    Parámetros:
        - theta (float): ángulo θ en radianes.
        - phi (float): ángulo φ en radianes.
        - lam (float): ángulo λ en radianes.

    Retorna:
        - str | None: nombre de la puerta nativa (h/x/y/z/s/sdg/t/tdg/sx/id)
          si los ángulos coinciden con un caso conocido; None en caso contrario.
    """
    targets = {
        'h': (_HALF_PI, 0.0, _PI),
        'x': (_PI, 0.0, _PI),
        'y': (_PI, _HALF_PI, _HALF_PI),
        'z': (0.0, 0.0, _PI),
        's': (0.0, 0.0, _HALF_PI),
        'sdg': (0.0, 0.0, -_HALF_PI),
        't': (0.0, 0.0, _PI / 4.0),
        'tdg': (0.0, 0.0, -_PI / 4.0),
        'sx': (_HALF_PI, 0.0, 0.0),
        'id': (0.0, 0.0, 0.0),
    }
    for name, angles in targets.items():
        if all(abs(a - b) < 1e-9 for a, b in zip((theta, phi, lam), angles)):
            return name
    return None


def _qiskit_python_source(parsed_circuit, preserve_custom_gates=False):
    """Genera el script Python (SDK Qiskit) que reconstruye el circuito parseado.

    Parámetros:
        - parsed_circuit (qiskit.QuantumCircuit): circuito ya parseado con
          ``qasm2.loads``/``qasm3.loads``.
        - preserve_custom_gates (bool): si True, cada compuerta custom/nativa se
          define una sola vez como función local; si False se expande en línea.

    Retorna:
        - str: código Python ejecutable que construye la variable ``circuit``.
    """
    gate_classes = {
        'h': 'HGate', 'swap': 'SwapGate', 'x': 'XGate', 'y': 'YGate', 'z': 'ZGate',
    }
    register_variables = []
    register_declarations = []
    qubit_references = {}
    clbit_references = {}

    for register in parsed_circuit.qregs:
        variable = f"qreg_{re.sub(r'\\W', '_', register.name)}"
        register_variables.append(variable)
        register_declarations.append(
            f'{variable} = QuantumRegister({len(register)}, {register.name!r})'
        )
        for index, bit in enumerate(register):
            qubit_references[bit] = f'{variable}[{index}]'

    for register in parsed_circuit.cregs:
        variable = f"creg_{re.sub(r'\\W', '_', register.name)}"
        register_variables.append(variable)
        register_declarations.append(
            f'{variable} = ClassicalRegister({len(register)}, {register.name!r})'
        )
        for index, bit in enumerate(register):
            clbit_references[bit] = f'{variable}[{index}]'

    gate_imports = set()
    instructions = []
    custom_functions = {}

    def custom_function(operation, qubits):
        """Define (una sola vez) una función local y emite su llamada."""
        name = _sanitize_gate_name(operation.name, 'custom_gate')
        if name not in custom_functions:
            definition = operation.definition
            params = [f'w{index}' for index in range(len(definition.qubits))]
            qubit_positions = {bit: index for index, bit in enumerate(definition.qubits)}
            clbit_positions = {bit: index for index, bit in enumerate(definition.clbits)}
            before = len(instructions)
            for sub_item in definition.data:
                emit(
                    sub_item.operation,
                    [params[qubit_positions[bit]] for bit in sub_item.qubits],
                    [f'cl{clbit_positions[bit]}' for bit in sub_item.clbits],
                    1,
                )
            body = _unquote_parameters(instructions[before:], params)
            del instructions[before:]
            custom_functions[name] = (params, body)
        arguments = ['circuit'] + [str(qubit) for qubit in qubits]
        instructions.append(f"{name}({', '.join(arguments)})")

    def emit(operation, qubits, clbits, depth=0):
        raw_params = list(operation.params)
        parameters = [_angle_to_expr(parameter) for parameter in raw_params]

        if operation.name in {'u1', 'u2', 'u3', 'u'}:
            theta, phi, lam = 0.0, 0.0, 0.0
            if operation.name in {'u3', 'u'}:
                theta, phi, lam = raw_params
            elif operation.name == 'u2':
                theta = _HALF_PI
                phi, lam = raw_params[0], raw_params[1]
            else:
                lam = raw_params[0]
            native = _native_gate_for_u(theta, phi, lam)
            if native == 'id':
                return
            if native:
                instructions.append(f'circuit.{native}({qubits[0]})')
            elif operation.name == 'u1':
                instructions.append(f'circuit.p({parameters[0]}, {qubits[0]})')
            elif operation.name == 'u2':
                instructions.append(
                    f'circuit.u(math.pi/2, {parameters[0]}, {parameters[1]}, {qubits[0]})'
                )
            else:
                instructions.append(
                    f'circuit.u({parameters[0]}, {parameters[1]}, {parameters[2]}, {qubits[0]})'
                )
        elif operation.name == 'mcx':
            controls = qubits[:-1]
            control_state = operation.ctrl_state
            control_arg = (
                f', ctrl_state={control_state}'
                if control_state != (1 << len(controls)) - 1
                else ''
            )
            instructions.append(
                f"circuit.mcx([{', '.join(controls)}], {qubits[-1]}{control_arg})"
            )
        elif hasattr(parsed_circuit, operation.name):
            arguments = parameters + qubits + clbits
            instructions.append(f"circuit.{operation.name}({', '.join(arguments)})")
        elif (
            getattr(operation, 'base_gate', None) is not None
            and operation.base_gate.name in gate_classes
        ):
            base_name = operation.base_gate.name
            gate_class = gate_classes[base_name]
            gate_imports.add(gate_class)
            control_state = operation.ctrl_state
            control_count = operation.num_ctrl_qubits
            control_args = (
                f', ctrl_state={control_state}'
                if control_state != (1 << control_count) - 1
                else ''
            )
            gate_expression = f'{gate_class}().control({control_count}{control_args})'
            instructions.append(f"circuit.append({gate_expression}, [{', '.join(qubits)}])")
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
            raise ValueError(f'Puerta Qiskit no soportada: {operation.name}')

    for item in parsed_circuit.data:
        emit(
            item.operation,
            [qubit_references[bit] for bit in item.qubits],
            [clbit_references[bit] for bit in item.clbits],
        )

    imports = [
        '# Importación de paquetes requeridos',
        'import math',
        'from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister',
    ]
    if gate_imports:
        imports.append(
            f"from qiskit.circuit.library import {', '.join(sorted(gate_imports))}"
        )

    python_lines = imports + ['', '# Generación de registros cuánticos y clásicos']
    python_lines.extend(register_declarations)
    if custom_functions:
        python_lines.extend(['', '# Compuertas personalizadas (funciones locales)'])
        for name, (params, body) in custom_functions.items():
            python_lines.append(f"def {name}(circuit, {', '.join(params)}):")
            python_lines.extend(f'    {line}' for line in body)
            python_lines.append('')
        if python_lines[-1] == '':
            python_lines.pop()
    python_lines.extend(['', '# Creación del circuito cuántico'])
    python_lines.append(f"circuit = QuantumCircuit({', '.join(register_variables)})")
    python_lines.extend([''] + instructions)
    return '\n'.join(python_lines) + '\n'


def _load_qiskit_native(qasm_str, qasm_version, fallback=True):
    """Parsea OpenQASM a un QuantumCircuit con el parser nativo de Qiskit.

    Parámetros:
        - qasm_str (str): código OpenQASM (2.0 o 3.0).
        - qasm_version (str): '2.0' o '3.0' (parser a usar).
        - fallback (bool): si True, ante un error reintenta con el parser
          opuesto y re-lanza el error original si también falla.

    Retorna:
        - qiskit.QuantumCircuit: el circuito parseado.
    """
    from qiskit import qasm2, qasm3

    loaders = {'2.0': qasm2.loads, '3.0': qasm3.loads}
    try:
        return loaders[qasm_version](qasm_str)
    except Exception as primary_error:
        if not fallback:
            raise
        # Cabecera ausente o inconsistente: se intenta el parser opuesto y se
        # reporta siempre el error de la versión esperada.
        try:
            return loaders['3.0' if qasm_version == '2.0' else '2.0'](qasm_str)
        except Exception:
            raise primary_error


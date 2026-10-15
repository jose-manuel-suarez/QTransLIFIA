"""Lógica específica de AWS Braket: cargador nativo y generador de scripts.

El parser nativo de Braket no resuelve ``include "stdgates.inc"`` en disco (sus
gates estándar ya están soportados por el SDK), por lo que la línea se elimina
antes de ``Circuit.from_ir``.
"""

import re

from utils.qutils import (
    _angle_to_expr,
    _sanitize_gate_name,
    _unquote_parameters,
)


# Include de librería estándar que el parser nativo de Braket no resuelve en disco
# (sus gates estándar ya están soportados por el SDK, así que la línea se elimina).
_STD_INCLUDE_RE = re.compile(r'^\s*include\s+"(?:stdgates\.inc|qelib1\.inc)"\s*;\s*$', re.I | re.M)


def _braket_python_source(parsed_circuit, preserve_custom_gates=False):
    """Genera el script Python (SDK Amazon Braket) que reconstruye el circuito.

    Parámetros:
        - parsed_circuit (qiskit.QuantumCircuit): circuito de referencia parseado.
        - preserve_custom_gates (bool): si True, cada compuerta custom se define
          una sola vez como función local; si False se expande en línea.

    Retorna:
        - str: código Python ejecutable que construye la variable ``circuit``
          (``braket.circuits.Circuit``).
    """
    instructions = []
    measurements = []
    measurement_qubits = set()
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
        parameters = [_angle_to_expr(parameter) for parameter in operation.params]

        if operation.name == 'measure':
            qubit = qubits[0]
            if qubit in measurement_qubits:
                raise ValueError(f'Braket no permite medir más de una vez el qubit {qubit}')
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
        python_lines.extend(
            f'circuit.measure([{qubit}])'
            for _, qubit in sorted(measurements)
        )
    return '\n'.join(python_lines) + '\n'


def _load_braket_native(qasm_str):
    """Parsea OpenQASM a un Circuit de Braket con su parser nativo.

    Elimina los ``include "stdgates.inc"``/``"qelib1.inc"`` (que el parser nativo
    no resuelve en disco) antes de llamar a ``Circuit.from_ir``.

    Parámetros:
        - qasm_str (str): código OpenQASM (2.0 o 3.0).

    Retorna:
        - braket.circuits.Circuit: el circuito parseado.
    """
    from braket.circuits import Circuit

    return Circuit.from_ir(_STD_INCLUDE_RE.sub('', qasm_str))


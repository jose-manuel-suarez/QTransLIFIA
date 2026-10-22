"""Lógica específica de Xanadu PennyLane: generador de scripts (QNode).

PennyLane no usa parser nativo en este proyecto: ``qml.from_qasm`` exige el plugin
``pennylane-qiskit`` y ``qml.from_qasm3`` no acepta los registros ``qreg``
indexados, por lo que el circuito se materializa siempre vía script migrado.
"""

from .qasm_utils import (
    _angle_to_expr,
    _sanitize_gate_name,
    _unquote_parameters,
)


def _pennylane_python_source(parsed_circuit, shots=1000, preserve_custom_gates=False):
    """Genera el script Python (PennyLane) que reconstruye el circuito como QNode.

    Parámetros:
        - parsed_circuit (qiskit.QuantumCircuit): circuito de referencia parseado.
        - shots (int): disparos del device de PennyLane.
        - preserve_custom_gates (bool): si True, cada compuerta custom se define
          una sola vez como función local (sin parámetro circuit); si False se
          expande en línea.

    Retorna:
        - str: código Python ejecutable que construye la variable ``circuit``
          (``pennylane.QNode``).
    """
    pennylane_gates = {
        'h': 'Hadamard', 'p': 'PhaseShift', 'rx': 'RX', 'ry': 'RY',
        'rz': 'RZ', 'swap': 'SWAP', 'x': 'PauliX', 'y': 'PauliY', 'z': 'PauliZ',
        'u1': 'PhaseShift', 'u2': 'U3', 'u3': 'U3', 'u': 'U3',
    }

    def gate_parameters(operation_name, parameters):
        if operation_name == 'u2':
            return ['math.pi/2'] + parameters
        if operation_name in {'u3', 'u'}:
            return parameters
        if operation_name == 'u1':
            return parameters
        return parameters

    instructions = []
    measurement_variables = {}
    measurement_count = 0
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
        instructions.append(f"{name}({', '.join(str(qubit) for qubit in qubits)})")

    def emit(operation, qubits, clbits, depth=0):
        nonlocal measurement_count
        parameters = [_angle_to_expr(parameter) for parameter in operation.params]

        if operation.name == 'measure':
            classical_index = clbits[0]
            variable = f'measurement_{classical_index}_{measurement_count}'
            measurement_count += 1
            measurement_variables[classical_index] = variable
            instructions.append(f'{variable} = qml.measure(wires={qubits[0]})')
            return

        if (
            getattr(operation, 'base_gate', None) is not None
            and pennylane_gates.get(operation.base_gate.name) is not None
        ):
            control_count = operation.num_ctrl_qubits
            controls = qubits[:control_count]
            targets = qubits[control_count:]
            base_name = operation.base_gate.name
            gate_name = pennylane_gates.get(base_name)

            control_values = ''
            if operation.ctrl_state != (1 << control_count) - 1:
                values = tuple(
                    int(value)
                    for value in f'{operation.ctrl_state:0{control_count}b}'
                )
                control_values = f', control_values={values!r}'
            gate_call = f'qml.ctrl(qml.{gate_name}, control={controls!r}{control_values})'
            if base_name == 'swap':
                arguments = [f'wires={targets!r}']
            else:
                arguments = gate_parameters(base_name, parameters) + [f'wires={targets[0]}']
            instructions.append(f"{gate_call}({', '.join(arguments)})")
            return

        gate_name = pennylane_gates.get(operation.name)
        if gate_name is None:
            if operation.definition is not None and depth < 10:
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
                return
            raise ValueError(f'Puerta PennyLane no soportada: {operation.name}')
        if operation.name == 'swap':
            arguments = [f'wires={qubits!r}']
        else:
            arguments = gate_parameters(operation.name, parameters) + [f'wires={qubits[0]}']
        instructions.append(f"qml.{gate_name}({', '.join(arguments)})")

    for item in parsed_circuit.data:
        emit(
            item.operation,
            [parsed_circuit.find_bit(bit).index for bit in item.qubits],
            [parsed_circuit.find_bit(bit).index for bit in item.clbits],
        )

    measured_classical_bits = sorted(measurement_variables)
    device_shots = shots if measured_classical_bits else None
    python_lines = [
        '# Importación de paquetes requeridos',
        'import math',
        'import pennylane as qml',
    ]
    if custom_functions:
        python_lines.append('')
        python_lines.append('# Compuertas personalizadas (funciones locales)')
        for name, (params, body) in custom_functions.items():
            python_lines.append(f"def {name}({', '.join(params)}):")
            python_lines.extend(f'    {line}' for line in body)
            python_lines.append('')
        if python_lines[-1] == '':
            python_lines.pop()
    python_lines.extend([
        '',
        f"device = qml.device('default.qubit', wires={parsed_circuit.num_qubits}, shots={device_shots!r})",
        '',
        '@qml.qnode(device)',
        'def circuit():',
        *[f'    {instruction}' for instruction in instructions],
    ])

    if measured_classical_bits:
        python_lines.append('    return (')
        python_lines.extend(
            f'        qml.sample({measurement_variables[classical_index]}),'
            for classical_index in measured_classical_bits
        )
        python_lines.append('    )')
    else:
        python_lines.append('    return qml.state()')
    return '\n'.join(python_lines) + '\n'


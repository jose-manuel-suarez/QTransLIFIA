"""Grafo ZX (PyZX) de QTransLIFIA.

Fase de verificación ZX del pipeline: construcción de los grafos directamente desde
la fuente Quirk (``quirk_to_zx_graph``) y desde el OpenQASM generado
(``qasm_to_zx_graph``), más los helpers ``_zx_*`` que las sustentan.

Los helpers compartidos con la traducción Quirk→OpenQASM (``_build_gate_map``,
``_column_extent``, ``_matrix_to_rows``, ``_qft_token``) viven en ``utils.quirk_utils``
y el parseo de URLs de Quirk (``parse_quirk_url``) en ``utils.url_utils``.
"""

import ast
import cmath
import itertools
import math
import re
import threading
from fractions import Fraction
from .quirk_utils import (
    _CONTROL_GATES,
    _build_gate_map,
    _column_extent,
    _cycle_token,
    _gate_height,
    _initial_state_gates,
    _is_control,
    _matrix_to_rows,
    _project_unitary,
    _qft_token,
    _resolve_gate_names,
)
from .url_utils import parse_quirk_url


def _zx_phase(angle):
    """Convierte un ángulo en radianes a Fraction (múltiplo de π) para PyZX.

    Parámetros:
        - angle (float): ángulo en radianes.

    Retorna:
        - Fraction: ángulo normalizado como fracción con denominador ≤ 1e6.
    """
    return Fraction(angle / math.pi).limit_denominator(1_000_000)


def _zx_append_phase_on_ones(circuit, qubits, angle):
    """Agrega una fase condicionada a que todos los qubits de control valgan 1.

    Usa la descomposición por subconjuntos (inclusión-exclusión) con CNOTs y
    fases Z sobre el último qubit de cada subconjunto.

    Parámetros:
        - circuit (pyzx.Circuit): circuito PyZX en construcción.
        - qubits (list[int]): índices de los qubits de control.
        - angle (float): ángulo de fase en radianes.
    """
    if not qubits or abs(angle) < 1e-12:
        return

    denominator = 2 ** (len(qubits) - 1)
    for subset_size in range(1, len(qubits) + 1):
        sign = 1 if subset_size % 2 else -1
        for subset in itertools.combinations(qubits, subset_size):
            target = subset[-1]
            for control in subset[:-1]:
                circuit.add_gate('CNOT', control, target)
            phase = _zx_phase(sign * angle / denominator)
            if phase:
                circuit.add_gate('ZPhase', target, phase)
            for control in reversed(subset[:-1]):
                circuit.add_gate('CNOT', control, target)


def _zx_append_controlled_rz(circuit, controls, target, angle):
    """Aplica Rz(angle) sobre target controlada por controls (vía fases).

    Parámetros:
        - circuit (pyzx.Circuit): circuito PyZX en construcción.
        - controls (list[int]): índices de los qubits de control.
        - target (int): índice del qubit objetivo.
        - angle (float): ángulo de rotación en radianes.
    """
    _zx_append_phase_on_ones(circuit, controls, -angle / 2)
    _zx_append_phase_on_ones(circuit, controls + [target], angle)


def _zx_append_controlled_ry(circuit, controls, target, angle):
    """Aplica Ry(angle) sobre target controlada por controls (conjugación de Rz).

    Parámetros:
        - circuit (pyzx.Circuit): circuito PyZX en construcción.
        - controls (list[int]): índices de los qubits de control.
        - target (int): índice del qubit objetivo.
        - angle (float): ángulo de rotación en radianes.
    """
    circuit.add_gate('XPhase', target, Fraction(1, 2))
    _zx_append_controlled_rz(circuit, controls, target, angle)
    circuit.add_gate('XPhase', target, Fraction(-1, 2))


def _zx_decompose_unitary(matrix):
    """Descompone una matriz 2x2 en (fase global, β, γ, δ) para Z–Y–Z.

    Parámetros:
        - matrix: tupla de dos tuplas de dos complejos (matriz unitaria 2x2).

    Retorna:
        - tuple: (global_phase, beta, gamma, delta), todos float en radianes.
    """
    a, b = matrix[0]
    c, d = matrix[1]
    determinant = a * d - b * c
    global_phase = cmath.phase(determinant) / 2
    phase_factor = cmath.exp(-1j * global_phase)
    a *= phase_factor
    b *= phase_factor
    c *= phase_factor
    d *= phase_factor

    cosine = min(1.0, abs(a))
    sine = min(1.0, abs(c))
    gamma = 2 * math.atan2(sine, cosine)
    angle_sum = -2 * cmath.phase(a) if cosine > 1e-12 else 0.0
    angle_difference = -2 * cmath.phase(-b) if sine > 1e-12 else 0.0
    beta = (angle_sum + angle_difference) / 2
    delta = (angle_sum - angle_difference) / 2
    return global_phase, beta, gamma, delta


def _zx_append_controlled_unitary(circuit, controls, target, matrix):
    """Aplica una unitaria 2x2 sobre target controlada por controls en PyZX.

    Parámetros:
        - circuit (pyzx.Circuit): circuito PyZX en construcción.
        - controls (list[int]): índices de los qubits de control.
        - target (int): índice del qubit objetivo.
        - matrix: matriz unitaria 2x2 (tupla de tuplas de complejos).
    """
    global_phase, beta, gamma, delta = _zx_decompose_unitary(matrix)
    _zx_append_phase_on_ones(circuit, controls, global_phase)
    _zx_append_controlled_rz(circuit, controls, target, delta)
    _zx_append_controlled_ry(circuit, controls, target, gamma)
    _zx_append_controlled_rz(circuit, controls, target, beta)


def _zx_append_mcx(circuit, controls, target):
    """Agrega una compuerta X multiconta (MCX) con descomposición H + fases + H.

    Parámetros:
        - circuit (pyzx.Circuit): circuito PyZX en construcción.
        - controls (list[int]): índices de los qubits de control (puede ser vacío).
        - target (int): índice del qubit objetivo.
    """
    if not controls:
        circuit.add_gate('NOT', target)
        return
    circuit.add_gate('HAD', target)
    _zx_append_phase_on_ones(circuit, controls + [target], math.pi)
    circuit.add_gate('HAD', target)


def _zx_rotation_matrix(axis, angle):
    """Matriz 2x2 de rotación Rx/Ry/Rz en radianes (convención de Qiskit).

    Parámetros:
        - axis (str): 'x', 'y' o 'z'.
        - angle (float): ángulo de rotación en radianes.

    Retorna:
        - tuple: matriz 2x2 como tupla de tuplas de complejos.

    Lanza:
        - ValueError: si el eje no es 'x', 'y' ni 'z'.
    """
    cosine = math.cos(angle / 2)
    sine = math.sin(angle / 2)
    if axis == 'x':
        off_diagonal = -1j * sine
        return ((cosine, off_diagonal), (off_diagonal, cosine))
    if axis == 'y':
        return ((cosine, -sine), (sine, cosine))
    if axis == 'z':
        return ((cosine - 1j * sine, 0j), (0j, cosine + 1j * sine))
    raise ValueError(f'Eje de rotación no soportado: {axis}')


def _zx_parse_angle(expression):
    """Evalúa una expresión de ángulo de Quirk/OpenQASM a float.

    Soporta constantes, el nombre ``pi`` y los operadores + - * / ** (incluido
    el unario). Cualquier otra construcción lanza ValueError.

    Parámetros:
        - expression (str): expresión matemática del ángulo.

    Retorna:
        - float: el valor del ángulo en radianes.
    """
    operators = {
        ast.Add: lambda left, right: left + right,
        ast.Sub: lambda left, right: left - right,
        ast.Mult: lambda left, right: left * right,
        ast.Div: lambda left, right: left / right,
        ast.Pow: lambda left, right: left ** right,
    }

    def evaluate(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name) and node.id == 'pi':
            return math.pi
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = evaluate(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            return operators[type(node.op)](evaluate(node.left), evaluate(node.right))
        raise ValueError(f'Expresión de ángulo no soportada: {expression}')

    return float(evaluate(ast.parse(expression, mode='eval').body))


def _zx_gate_matrix(token, gate_map, time):
    """Matriz unitaria 2x2 de un token de gate para el grafo ZX.

    Soporta matrices personalizadas de Quirk, gates fijos (H/X/Y/Z), rotaciones
    X^½/Y^¼/…, fases Z^½/…, Rxft (snapshot temporal) y los parámetros
    rx/ry/rz/p/cp/cu1 y u1/u2/u3/u.

    Parámetros:
        - token (str): identificador de la celda (p. ej. 'H', 'rx(pi/2)').
        - gate_map (dict): mapa id/name -> definición de custom gates.
        - time (float): snapshot temporal de Quirk (para 'Rxft').

    Retorna:
        - tuple: matriz 2x2 como tupla de tuplas de complejos.
    """
    gate = gate_map.get(token.split(':', 1)[0], {})
    name = gate.get('name', token)

    matrix_rows = _matrix_to_rows(gate.get('matrix'))
    if matrix_rows is not None:
        if len(matrix_rows) != 2 or any(len(row) != 2 for row in matrix_rows):
            raise ValueError(f'Matriz no soportada en el grafo ZX (se esperaba 2x2): {name}')
        return (
            (matrix_rows[0][0], matrix_rows[0][1]),
            (matrix_rows[1][0], matrix_rows[1][1]),
        )

    if name == 'H':
        scale = 1 / math.sqrt(2)
        return ((scale, scale), (scale, -scale))
    if name == 'X':
        return ((0j, 1 + 0j), (1 + 0j, 0j))
    if name == 'Y':
        return ((0j, -1j), (1j, 0j))
    if name == 'Z':
        return ((1 + 0j, 0j), (0j, -1 + 0j))

    rotations = {
        'X^½': ('x', math.pi / 2), 'X^-½': ('x', -math.pi / 2),
        'X^¼': ('x', math.pi / 4), 'X^-¼': ('x', -math.pi / 4),
        'Y^½': ('y', math.pi / 2), 'Y^-½': ('y', -math.pi / 2),
        'Y^¼': ('y', math.pi / 4), 'Y^-¼': ('y', -math.pi / 4),
    }
    if name in rotations:
        axis, angle = rotations[name]
        return _zx_rotation_matrix(axis, angle)
    phases = {
        'Z^½': math.pi / 2, 'Z^-½': -math.pi / 2,
        'Z^¼': math.pi / 4, 'Z^-¼': -math.pi / 4,
    }
    if name in phases:
        angle = phases[name]
        return ((1 + 0j, 0j), (0j, cmath.exp(1j * angle)))
    if name == 'Rxft':
        normalized_time = 2 * time - 1
        return _zx_rotation_matrix('x', math.pi * normalized_time ** 2)

    match = re.fullmatch(r'(rx|ry|rz|p|cp|cu1)\((.+)\)', name, re.IGNORECASE)
    if match:
        operation, expression = match.groups()
        angle = _zx_parse_angle(expression)
        if operation.lower() in ('p', 'cp', 'cu1'):
            return ((1 + 0j, 0j), (0j, cmath.exp(1j * angle)))
        return _zx_rotation_matrix(operation.lower()[-1], angle)

    match = re.fullmatch(r'(u1|u2|u3|u)\((.+)\)', name, re.IGNORECASE)
    if match:
        operation, expression = match.groups()
        parameters = [_zx_parse_angle(value.strip()) for value in expression.split(',')]
        operation = operation.lower()
        if operation == 'u1' and len(parameters) == 1:
            theta, phi, lam = 0.0, 0.0, parameters[0]
        elif operation == 'u2' and len(parameters) == 2:
            theta, (phi, lam) = math.pi / 2, parameters
        elif operation in ('u3', 'u') and len(parameters) == 3:
            theta, phi, lam = parameters
        else:
            raise ValueError(f'Cantidad de parámetros inválida para {operation}: {expression}')

        cosine = math.cos(theta / 2)
        sine = math.sin(theta / 2)
        return (
            (cosine, -cmath.exp(1j * lam) * sine),
            (cmath.exp(1j * phi) * sine, cmath.exp(1j * (phi + lam)) * cosine),
        )

    if gate.get('circuit'):
        raise ValueError(f'Custom gate compuesto no soportado todavía: {name}')
    raise ValueError(f'Compuerta Quirk no soportada: {name}')


def _zx_append_unitary(circuit, target, matrix, controls=None):
    """Agrega una unitaria 2x2 sobre target (con o sin controles) al circuito.

    Parámetros:
        - circuit (pyzx.Circuit): circuito PyZX en construcción.
        - target (int): índice del qubit objetivo.
        - matrix: matriz unitaria 2x2 (tupla de tuplas de complejos).
        - controls (list[int] | None): qubits de control; None sin controles.
    """
    if controls:
        _zx_append_controlled_unitary(circuit, controls, target, matrix)
        return

    _, beta, gamma, delta = _zx_decompose_unitary(matrix)
    if delta:
        circuit.add_gate('ZPhase', target, _zx_phase(delta))
    if gamma:
        circuit.add_gate('YPhase', target, _zx_phase(gamma))
    if beta:
        circuit.add_gate('ZPhase', target, _zx_phase(beta))


def _zx_append_qft(circuit, base, span, inverse, controls=()):
    """Agrega una QFT (o su inversa) sobre un rango de qubits al circuito PyZX.

    Parámetros:
        - circuit (pyzx.Circuit): circuito PyZX en construcción.
        - base (int): índice del primer qubit del rango.
        - span (int): cantidad de qubits de la QFT.
        - inverse (bool): si True agrega la QFT inversa.
        - controls (tuple[int], optional): qubits de control adicionales.
    """
    controls = list(controls)
    args = [base + k for k in range(span)]
    hadamard = ((0.5 ** 0.5, 0.5 ** 0.5), (0.5 ** 0.5, -0.5 ** 0.5))

    def emit_h(qubit):
        _zx_append_unitary(circuit, qubit, hadamard, controls)

    def emit_cp(angle, control, target):
        matrix = ((1 + 0j, 0j), (0j, cmath.exp(1j * angle)))
        _zx_append_unitary(circuit, target, matrix, controls + [control])

    def emit_swap(first, second):
        if controls:
            _zx_append_mcx(circuit, controls + [first], second)
            _zx_append_mcx(circuit, controls + [second], first)
            _zx_append_mcx(circuit, controls + [first], second)
        else:
            circuit.add_gate('SWAP', first, second)

    if not inverse:
        for i in range(span - 1, -1, -1):
            emit_h(args[i])
            for j in range(i - 1, -1, -1):
                emit_cp(math.pi / (2 ** (i - j)), args[i], args[j])
        for k in range(span // 2):
            emit_swap(args[k], args[span - 1 - k])
    else:
        for k in range(span // 2):
            emit_swap(args[k], args[span - 1 - k])
        for i in range(span):
            for j in range(i):
                emit_cp(-math.pi / (2 ** (i - j)), args[i], args[j])
            emit_h(args[i])


def _zx_append_cycle(circuit, base, span, direction, controls=()):
    """Agrega un cycle shift de Quirk ('<<n'/'>>n') sobre un rango de qubits.

    '<<n' rota el contenido hacia abajo (wire i -> i+1) y '>>n' hacia arriba
    (wire i -> i-1), con wrap-around; se descompone en swaps adyacentes.  Con
    controles, cada swap se implementa como tres Toffoli controlados.

    Parámetros:
        - circuit (pyzx.Circuit): circuito PyZX en construcción.
        - base (int): índice del primer qubit del rango.
        - span (int): cantidad de qubits del cycle shift.
        - direction (str): '<<' o '>>'.
        - controls (tuple[int], optional): qubits de control adicionales.
    """
    controls = list(controls)
    pairs = (
        [(k, k + 1) for k in range(span - 2, -1, -1)]
        if direction == '<<'
        else [(k, k + 1) for k in range(span - 1)]
    )
    for first, second in pairs:
        a, b = base + first, base + second
        if controls:
            _zx_append_mcx(circuit, controls + [a], b)
            _zx_append_mcx(circuit, controls + [b], a)
            _zx_append_mcx(circuit, controls + [a], b)
        else:
            circuit.add_gate('SWAP', a, b)


def _zx_control_matrix(operation):
    """Matriz 2x2 de la rotación de base que usa un control X/Y de Quirk.

    Parámetros:
        - operation (str): operación del setup/cleanup ('h', 'rx(pi/2)', …).

    Retorna:
        - tuple: matriz 2x2 como tupla de tuplas de complejos.

    Lanza:
        - ValueError: si la rotación no está soportada.
    """
    if operation == 'h':
        scale = 1 / math.sqrt(2)
        return ((scale, scale), (scale, -scale))
    match = re.fullmatch(r'rx\((.+)\)', operation)
    if match:
        return _zx_rotation_matrix('x', _zx_parse_angle(match.group(1)))
    raise ValueError(f'Rotación de control no soportada en ZX: {operation}')


def _zx_custom_gate_matrix(gate, gate_map, time, depth, column=None):
    """Matriz unitaria de un custom gate compuesto de Quirk.

    Construye un circuito PyZX local con la definición ``circuit.cols`` del
    gate (o una sola columna si se indica ``column``) y extrae su matriz.

    Parámetros:
        - gate (dict): definición del custom gate.
        - gate_map (dict): mapa id/name -> definición de custom gates.
        - time (float): snapshot temporal de Quirk.
        - depth (int): profundidad de anidamiento actual.
        - column (int | None): índice de columna a aplanar; None usa todo el gate.

    Retorna:
        - numpy.ndarray: matriz unitaria de dimensión 2**n_qubits.

    Lanza:
        - ValueError: si la columna no existe o el gate no tiene altura válida.
    """
    import pyzx as zx

    columns = gate.get('circuit', {}).get('cols', [])
    if column is not None:
        if not 0 <= column < len(columns):
            raise ValueError(f'Columna {column} fuera de rango en el custom gate')
        columns = [columns[column]]
    n_qubits = _gate_height(gate, gate_map)
    if n_qubits < 1:
        raise ValueError('Custom gate compuesto sin qubits definidos')
    local = zx.Circuit(n_qubits)
    _zx_add_columns(local, columns, 0, gate_map, time, depth + 1)
    return local.to_matrix()


def _zx_reverse_matrix_qubits(matrix, n_qubits):
    """Invierte el orden de qubits de una matriz (PyZX <-> Qiskit).

    PyZX indexa la base con el qubit 0 como bit más significativo, mientras que
    Qiskit lo usa como bit menos significativo. La inversión de bits permuta
    filas y columnas; como la permutación es una involución, la misma función
    sirve en ambos sentidos.

    Parámetros:
        - matrix (numpy.ndarray): matriz unitaria de 2**n_qubits.
        - n_qubits (int): cantidad de qubits de la matriz.

    Retorna:
        - numpy.ndarray: la matriz reordenada para la convención opuesta.
    """
    import numpy as np

    indices = []
    for index in range(1 << n_qubits):
        reversed_index = 0
        value = index
        for _ in range(n_qubits):
            reversed_index = (reversed_index << 1) | (value & 1)
            value >>= 1
        indices.append(reversed_index)
    return np.asarray(matrix, dtype=complex)[np.ix_(indices, indices)]


def _zx_append_multi_unitary(circuit, targets, matrix, controls=None, matrix_order='pyzx'):
    """Aplana una unitaria de varios qubits a compuertas de 1 y 2 qubits.

    Usa la síntesis de Qiskit (``transpile`` a la base ``u``/``cx``) y agrega el
    resultado al circuito PyZX. Cuando hay controles externos se construye la
    unitaria controlada completa y se descompone como un bloque. La matriz se
    reordena a la convención de Qiskit (ver ``_zx_reverse_matrix_qubits``) para que
    el bloque quede aplicado sobre los qubits correctos.

    Parámetros:
        - circuit (pyzx.Circuit): circuito PyZX en construcción.
        - targets (list[int]): qubits objetivo en orden de la matriz (el
          primero es el bit más significativo para PyZX).
        - matrix (numpy.ndarray): matriz unitaria de 2**len(targets).
        - controls (list[int] | None): qubits de control externos.
        - matrix_order (str): ``'pyzx'`` si ``matrix`` ya usa el orden de PyZX
          (qubit 0 = MSB, p. ej. ``local.to_matrix()``) o ``'qiskit'`` si usa
          el orden de Quirk/Qiskit (qubit 0 = LSB, p. ej. una matriz de la URL).
    """
    import numpy as np
    from qiskit import QuantumCircuit, transpile
    from qiskit.circuit.library import UnitaryGate

    controls = list(controls or [])
    if len(targets) == 1:
        rows = np.asarray(matrix, dtype=complex)
        _zx_append_unitary(
            circuit,
            targets[0],
            ((rows[0, 0], rows[0, 1]), (rows[1, 0], rows[1, 1])),
            controls,
        )
        return

    target_matrix = np.asarray(
        _project_unitary(np.asarray(matrix, dtype=complex).tolist()),
        dtype=complex,
    )
    if matrix_order == 'qiskit':
        target_matrix = _zx_reverse_matrix_qubits(target_matrix, len(targets))

    if controls:
        block = 2 ** len(targets)
        full = np.eye(block * (2 ** len(controls)), dtype=complex)
        full[-block:, -block:] = target_matrix
        order = controls + list(targets)
    else:
        full = target_matrix
        order = list(targets)

    qiskit_circuit = QuantumCircuit(len(order))
    qiskit_circuit.append(
        UnitaryGate(_zx_reverse_matrix_qubits(full, len(order))),
        list(range(len(order))),
    )
    lowered = transpile(
        qiskit_circuit, basis_gates=['u', 'cx'], optimization_level=0
    )
    for instruction in lowered.data:
        operation = instruction.operation
        positions = [lowered.find_bit(q).index for q in instruction.qubits]
        if operation.name == 'u':
            theta, phi, lam = (float(value) for value in operation.params)
            _zx_append_unitary(
                circuit,
                order[positions[0]],
                _zx_gate_matrix(f'u({theta},{phi},{lam})', {}, 0.5),
            )
        elif operation.name == 'cx':
            circuit.add_gate('CNOT', order[positions[0]], order[positions[1]])
        else:
            raise ValueError(
                f'Compuerta inesperada al aplanar la unitaria: {operation.name}'
            )


def _zx_embed_block(block, targets, controls, n_qubits):
    """Incrusta una unitaria de bloque en el espacio de ``n_qubits``.

    La matriz ``block`` usa el orden de Qiskit (el primer target es el bit
    menos significativo del bloque). Los qubits de ``controls`` deben valer 1
    para que se aplique ``block``; en el resto de la base se aplica identidad.

    Parámetros:
        - block (numpy.ndarray): matriz unitaria de ``2**len(targets)``.
        - targets (list[int]): qubits objetivo, en orden little-endian.
        - controls (list[int]): qubits de control.
        - n_qubits (int): número total de qubits.

    Retorna:
        - numpy.ndarray: matriz unitaria de ``2**n_qubits``.
    """
    import numpy as np

    dimension = 1 << n_qubits
    full = np.zeros((dimension, dimension), dtype=complex)
    targets = list(targets)
    controls = list(controls)
    target_mask = sum(1 << qubit for qubit in targets)
    block_dimension = 1 << len(targets)
    for column in range(dimension):
        if any(not ((column >> qubit) & 1) for qubit in controls):
            full[column, column] = 1
            continue
        block_column = 0
        for position, qubit in enumerate(targets):
            block_column |= ((column >> qubit) & 1) << position
        base = column & ~target_mask
        for block_row in range(block_dimension):
            amplitude = block[block_row, block_column]
            if amplitude == 0:
                continue
            row = base
            for position, qubit in enumerate(targets):
                row |= ((block_row >> position) & 1) << qubit
            full[row, column] = amplitude
    return full


def _zx_append_custom_gate(circuit, targets, token, gate, gate_map, time, controls, depth):
    """Aplana un custom gate (compuesto o matriz ancha) y lo agrega al grafo.

    Un gate compuesto sin controles externos se expande columna a columna con
    ``_zx_add_columns`` (mismas compuertas que el OpenQASM); con controles, o si
    es una matriz ancha, se sintetiza como bloque unitario con Qiskit.

    Parámetros:
        - circuit (pyzx.Circuit): circuito PyZX en construcción.
        - targets (list[int]): qubits ocupados por el gate.
        - token (str): identificador usado en la columna (puede incluir ``:k``).
        - gate (dict): definición del custom gate.
        - gate_map (dict): mapa id/name -> definición de custom gates.
        - time (float): snapshot temporal de Quirk.
        - controls (list[int]): controles externos que afectan a todo el gate.
        - depth (int): profundidad de anidamiento actual.
    """
    import numpy as np

    if gate.get('circuit') is not None:
        columns = gate.get('circuit', {}).get('cols', [])
        column = None
        if ':' in str(token):
            try:
                column = int(str(token).split(':', 1)[1])
            except ValueError as exc:
                raise ValueError(f'Índice de columna inválido: {token}') from exc
        if not controls:
            if column is not None:
                if not 0 <= column < len(columns):
                    raise ValueError(
                        f'Columna {column} fuera de rango en el custom gate'
                    )
                columns = [columns[column]]
            _zx_add_columns(circuit, columns, targets[0], gate_map, time, depth + 1)
            return
        matrix = _zx_custom_gate_matrix(gate, gate_map, time, depth, column)
        matrix_order = 'pyzx'
    else:
        rows = _matrix_to_rows(gate.get('matrix'))
        if rows is None:
            raise ValueError(f"Custom gate sin 'circuit' ni 'matrix': {token}")
        matrix = np.asarray(rows, dtype=complex)
        matrix_order = 'qiskit'

    size = 2 ** len(targets)
    if matrix.shape != (size, size):
        raise ValueError(
            f'Matriz de {matrix.shape[0]}x{matrix.shape[1]} incompatible con '
            f'{len(targets)} qubits en el grafo ZX: {token}'
        )
    _zx_append_multi_unitary(
        circuit, targets, matrix, controls, matrix_order=matrix_order
    )


def _zx_add_columns(circuit, cols, offset, gate_map, time, depth=0):
    """Agrega columnas de Quirk a un ``pyzx.Circuit``.

    Aplana los custom gates compuestos y las matrices de más de un qubit para
    que el grafo ZX solo contenga operaciones nativas de 1 y 2 qubits.

    Parámetros:
        - circuit (pyzx.Circuit): circuito PyZX en construcción.
        - cols (list): columnas de Quirk.
        - offset (int): desplazamiento de índices qubit.
        - gate_map (dict): mapa id/name -> definición de custom gates.
        - time (float): snapshot temporal de Quirk.
        - depth (int): profundidad de anidamiento actual.

    Retorna:
        - bool: True si se aplanó algún custom gate; False si no hizo falta.

    Lanza:
        - ValueError: si el anidamiento supera 10 niveles.
    """
    if depth > 10:
        raise ValueError('Anidamiento de custom gates demasiado profundo (>10) en ZX')

    flattened = False
    for col in cols:
        control_cells = [
            (index + offset, value)
            for index, value in enumerate(col)
            if _is_control(value)
        ]
        controls = [index for index, _ in control_cells]
        # Setup de los controles: Quirk evalúa el mask sobre el estado ya girado
        # a la base del control, y los anti-control se implementan conjugando
        # por X (así quedan todos como controles positivos).
        for index, value in control_cells:
            for operation in _CONTROL_GATES[value]['setup']:
                _zx_append_unitary(circuit, index, _zx_control_matrix(operation))
        for index, value in control_cells:
            if _CONTROL_GATES[value]['negate']:
                circuit.add_gate('NOT', index)
        swap_indices = [
            index + offset for index, value in enumerate(col) if value == 'Swap'
        ]
        if swap_indices:
            if len(swap_indices) % 2:
                raise ValueError(f'Cantidad impar de extremos Swap en la columna: {col}')
            for pair_start in range(0, len(swap_indices), 2):
                first, second = swap_indices[pair_start:pair_start + 2]
                if controls:
                    _zx_append_mcx(circuit, controls + [first], second)
                    _zx_append_mcx(circuit, controls + [second], first)
                    _zx_append_mcx(circuit, controls + [first], second)
                else:
                    circuit.add_gate('SWAP', first, second)

        for index, token in enumerate(col):
            if token in (1, '1', None, 'Swap', 'Measure') or _is_control(token):
                continue
            qft_info = _qft_token(token)
            if qft_info is not None:
                _zx_append_qft(
                    circuit, index + offset, qft_info[0], qft_info[1], controls
                )
                continue
            cycle_info = _cycle_token(token)
            if cycle_info is not None:
                direction, span = cycle_info
                _zx_append_cycle(
                    circuit, index + offset, span, direction, controls
                )
                continue
            gate = gate_map.get(str(token).split(':', 1)[0], {})
            matrix_rows = _matrix_to_rows(gate.get('matrix'))
            is_composite = gate.get('circuit') is not None
            is_wide_matrix = matrix_rows is not None and len(matrix_rows) > 2
            if is_composite or is_wide_matrix:
                flattened = True
                height = _gate_height(gate, gate_map) or 1
                targets = [index + offset + row for row in range(height)]
                _zx_append_custom_gate(
                    circuit, targets, token, gate, gate_map, time, controls, depth
                )
                continue
            _zx_append_unitary(
                circuit,
                index + offset,
                _zx_gate_matrix(token, gate_map, time),
                controls,
            )

        # Cleanup de los controles: se deshace la conjugación por X y se
        # devuelve cada qubit de control a su base original.
        for index, value in control_cells:
            if _CONTROL_GATES[value]['negate']:
                circuit.add_gate('NOT', index)
        for index, value in control_cells:
            for operation in _CONTROL_GATES[value]['cleanup']:
                _zx_append_unitary(circuit, index, _zx_control_matrix(operation))

    return flattened


def _build_quirk_zx_circuit(circuit_data, offset=0, time=0.5):
    """Construye el ``pyzx.Circuit`` de un circuito Quirk ya parseado.

    Parámetros:
        - circuit_data (dict): JSON del circuito Quirk (``cols``/``gates``).
        - offset (int): desplazamiento de índices qubit.
        - time (float): snapshot temporal de Quirk.

    Retorna:
        - tuple[pyzx.Circuit, str]: circuito y método usado ('directo' o
          'aplanado').
    """
    try:
        import pyzx as zx
    except ImportError as exc:
        raise ImportError(
            'Instala PyZX con `pip install pyzx` para generar grafos ZX'
        ) from exc

    if not 0 <= time <= 1:
        raise ValueError('time debe estar entre 0 y 1, como el tiempo de Quirk')

    cols = circuit_data.get('cols', [])
    init_states = circuit_data.get('init') or []
    gate_map = _build_gate_map(circuit_data)
    n_qubits = max((_column_extent(col, gate_map) for col in cols), default=0) + offset
    if init_states:
        n_qubits = max(n_qubits, len(init_states) + offset)
    circuit = zx.Circuit(n_qubits)
    for index, value in enumerate(init_states):
        for operation in _initial_state_gates(value):
            token = operation.upper() if operation in ('x', 'y', 'z', 'h') else operation
            _zx_append_unitary(
                circuit, index + offset, _zx_gate_matrix(token, gate_map, time)
            )
    flattened = _zx_add_columns(circuit, cols, offset, gate_map, time)
    return circuit, ('aplanado' if flattened else 'directo')


def quirk_to_zx_graph(url, offset=0, time=0.5):
    """Construye el grafo ZX de PyZX directamente desde una URL de Quirk.

    Parámetros:
        - url (str): URL de Quirk con ``circuit=<JSON>``.
        - offset (int): desplazamiento de índices qubit.
        - time (float): snapshot temporal de Quirk (para gates como 'Rxft').

    Retorna:
        - pyzx.Graph: el grafo ZX equivalente al circuito Quirk.
    """
    graph, _ = quirk_to_zx_graph_with_method(url, offset, time)
    return graph


def quirk_to_zx_graph_with_method(url, offset=0, time=0.5):
    """Construye el grafo ZX de Quirk e indica el método de construcción.

    Parámetros:
        - url (str): URL de Quirk con ``circuit=<JSON>``.
        - offset (int): desplazamiento de índices qubit.
        - time (float): snapshot temporal de Quirk.

    Retorna:
        - tuple[pyzx.Graph, str]: grafo ZX y método usado ('directo' si no hubo
          que aplanar custom gates, 'aplanado' si se expandieron/decompusieron).
    """
    circuit_data = parse_quirk_url(url)
    circuit, method = _build_quirk_zx_circuit(circuit_data, offset, time)
    return circuit.to_graph(), method


def _zx_matrix_gate_names(url):
    """Nombres QASM de las declaraciones que provienen de compuertas ``matrix``.

    El grafo base usa la matriz cruda (con su fase global) para esas
    compuertas; el grafo QASM debe evaluar su cuerpo de forma exacta para que
    la comparación controlada no pierda esa fase.

    Parámetros:
        - url (str): URL de Quirk con ``circuit=<JSON>``.

    Retorna:
        - set[str]: identificadores QASM de las compuertas con ``matrix``.
    """
    circuit_data = parse_quirk_url(url)
    gate_map = _build_gate_map(circuit_data)
    names = _resolve_gate_names(gate_map)
    return {
        names[key]
        for key, gate in gate_map.items()
        if gate.get('matrix') is not None and gate.get('circuit') is None
    }


def qasm_to_zx_graph(qasm_code, matrix_gate_names=None):
    """Construye el grafo ZX de PyZX desde el OpenQASM generado por el proyecto.

    Admite versiones 2.0 (``qreg``) y 3.0 (``qubit``), gates con parámetros
    (rx/ry/rz/p/u1/u2/u3/u) y declaraciones ``gate`` (incl. QFT), resolviendo
    los operandos del cuerpo por el nombre declarado (p. ej. ``h_``).

    Parámetros:
        - qasm_code (str): código OpenQASM (2.0 o 3.0).
        - matrix_gate_names (set[str] | None): nombres de declaraciones que
          provienen de compuertas ``matrix``; su cuerpo se evalúa con matriz
          exacta (fase global incluida) cuando se aplican de forma controlada.

    Retorna:
        - pyzx.Graph: el grafo ZX equivalente al circuito OpenQASM.
    """
    try:
        import pyzx as zx
    except ImportError as exc:
        raise ImportError('Instala PyZX con `pip install pyzx` para generar grafos ZX') from exc
    import numpy as np

    register_match = re.search(r'\bqreg\s+(\w+)\s*\[\s*(\d+)\s*\]\s*;', qasm_code)
    if register_match is None:
        register_match = re.search(r'\bqubit\s*\[\s*(\d+)\s*\]\s*(\w+)\s*;', qasm_code)
        if register_match is None:
            raise ValueError('No se encontró una declaración qreg o qubit[n]')
        register_name, n_qubits = register_match.group(2), int(register_match.group(1))
    else:
        register_name, n_qubits = register_match.group(1), int(register_match.group(2))

    circuit = zx.Circuit(n_qubits)
    register = re.escape(register_name)
    operand_pattern = re.compile(rf'{register}\[(\d+)\](?:\s*,\s*{register}\[(\d+)\])*')
    statement_pattern = re.compile(
        r'(?P<modifiers>(?:ctrl\s*@\s*)*)(?P<gate>[A-Za-z_]\w*)'
        r'(?:\((?P<params>[^)]*)\))?\s+(?P<operands>[^;]+);',
        re.IGNORECASE,
    )
    measurement_pattern = re.compile(
        rf'(?:\w+\[\d+\]\s*=\s*)?measure\s+{register}\[\d+\]'
        rf'(?:\s*->\s*\w+\[\d+\])?\s*;',
        re.IGNORECASE,
    )

    # Extrae las declaraciones `gate <nombre> <params> { ... }` (submódulos
    # OpenQASM) y se queda solo con las sentencias del circuito.
    declarations = {}
    circuit_statements = []
    raw_lines = qasm_code.splitlines()
    index = 0
    while index < len(raw_lines):
        line = raw_lines[index].split('//', 1)[0].strip()
        declaration_match = re.match(
            r'gate\s+([A-Za-z_]\w*)\s+([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*\{$',
            line,
        )
        if declaration_match:
            declaration_name = declaration_match.group(1)
            parameter_names = [part.strip() for part in declaration_match.group(2).split(',')]
            body = []
            index += 1
            while index < len(raw_lines) and raw_lines[index].strip() != '}':
                body_line = raw_lines[index].split('//', 1)[0].strip()
                if body_line:
                    body.append(body_line)
                index += 1
            declarations[declaration_name] = (parameter_names, body)
            index += 1  # salta el '}'
            continue
        if line:
            circuit_statements.append((index + 1, line))
        index += 1

    def process(
        statement,
        line_number,
        mapping=None,
        extra_controls=(),
        depth=0,
        param_names=None,
        target_circuit=None,
        target_n_qubits=None,
    ):
        active_circuit = circuit if target_circuit is None else target_circuit
        active_n_qubits = n_qubits if target_n_qubits is None else target_n_qubits
        if statement.startswith(('OPENQASM', 'include', 'qreg', 'creg', 'qubit', 'bit')):
            return
        if measurement_pattern.fullmatch(statement):
            return

        match = statement_pattern.fullmatch(statement)
        if match is None:
            raise ValueError(
                f'Instrucción OpenQASM no reconocida en línea {line_number}: {statement}'
            )

        operands_text = match.group('operands').strip()
        if mapping is None:
            # Contexto principal: operandos con formato qreg[i].
            if not operand_pattern.fullmatch(operands_text):
                raise ValueError(
                    f'Operandos OpenQASM no reconocidos en línea {line_number}: {statement}'
                )
            qubits = [int(value) for value in re.findall(r'\[(\d+)\]', operands_text)]
        else:
            # Cuerpo de un custom gate: operandos son los nombres declarados
            # en la cabecera `gate` (a, b, … o alias como h_ que genera
            # primeras_letras para evitar nombres de puertas). Se resuelven
            # por posición en param_names; si no están declarados, se acepta
            # la letra simple a-z (legacy).
            qubits = []
            for token in operands_text.split(','):
                token = token.strip()
                if param_names is not None and token in param_names:
                    position = param_names.index(token)
                elif re.fullmatch(r'[a-z]', token):
                    position = ord(token) - ord('a')
                else:
                    position = -1
                if position < 0 or position >= len(mapping):
                    raise ValueError(
                        f'Operando de custom gate no reconocido en línea '
                        f'{line_number}: {statement}'
                    )
                qubits.append(mapping[position])
        if any(qubit >= active_n_qubits for qubit in qubits):
            raise ValueError(f'Índice de qubit fuera del registro en línea {line_number}: {statement}')

        gate_name = match.group('gate').lower()
        parameters = match.group('params')
        modifier_controls = match.group('modifiers').lower().count('ctrl')

        # Custom gate declarado: expandir su cuerpo con los qubits mapeados.
        # Sin controles externos basta con expandir cada sentencia; con
        # controles se calcula la unitaria del bloque y se aplica controlada.
        declaration = declarations.get(match.group('gate'))
        if declaration is not None:
            if depth >= 10:
                raise ValueError(
                    f'Custom gates anidados demasiado profundos en línea {line_number}'
                )
            if parameters is not None:
                raise ValueError(
                    f'Parámetros inesperados para el custom gate en línea {line_number}: {statement}'
                )
            parameter_names, body = declaration
            if len(qubits) != modifier_controls + len(parameter_names):
                raise ValueError(
                    f'Cantidad de qubits inválida para el custom gate en línea '
                    f'{line_number}: {statement}'
                )
            body_mapping = qubits[modifier_controls:]
            body_controls = tuple(extra_controls) + tuple(qubits[:modifier_controls])
            if body_controls:
                # Un custom gate controlado representa la unitaria controlada
                # del bloque completo, no el control de cada sentencia. Para
                # las compuertas definidas con 'matrix' el grafo base usa la
                # matriz cruda (con fase global), así que el cuerpo QASM se
                # evalúa de forma exacta; para los custom gates compuestos se
                # conserva la matriz local de PyZX (misma convención que el
                # grafo base).
                if matrix_gate_names is not None and match.group('gate') in matrix_gate_names:
                    matrix = body_matrix(body, parameter_names, len(body_mapping), depth + 1)
                    matrix_order = 'qiskit'
                else:
                    local = zx.Circuit(len(body_mapping))
                    local_mapping = list(range(len(body_mapping)))
                    for body_line in body:
                        process(
                            body_line,
                            line_number,
                            local_mapping,
                            (),
                            depth + 1,
                            parameter_names,
                            local,
                            len(body_mapping),
                        )
                    matrix = local.to_matrix()
                    matrix_order = 'pyzx'
                _zx_append_multi_unitary(
                    active_circuit,
                    list(body_mapping),
                    matrix,
                    list(body_controls),
                    matrix_order=matrix_order,
                )
            else:
                for body_line in body:
                    process(
                        body_line,
                        line_number,
                        body_mapping,
                        body_controls,
                        depth + 1,
                        parameter_names,
                        active_circuit,
                        active_n_qubits,
                    )
            return

        if gate_name == 'swap':
            if len(qubits) < 2 or len(qubits) != modifier_controls + 2:
                raise ValueError(f'Cantidad de qubits inválida para swap en línea {line_number}: {statement}')
            controls, targets = qubits[:-2], qubits[-2:]
            if len(controls) != modifier_controls:
                raise ValueError(f'Controles incompatibles en línea {line_number}: {statement}')
            controls = list(extra_controls) + controls
            if controls:
                first, second = targets
                _zx_append_mcx(active_circuit, controls + [first], second)
                _zx_append_mcx(active_circuit, controls + [second], first)
                _zx_append_mcx(active_circuit, controls + [first], second)
            else:
                active_circuit.add_gate('SWAP', *targets)
            return

        controlled_aliases = {
            'cx': 'x', 'cy': 'y', 'cz': 'z', 'ch': 'h',
            'ccx': 'x', 'mcx': 'x', 'mcy': 'y', 'mcz': 'z',
            'crx': 'rx', 'cry': 'ry', 'crz': 'rz', 'cp': 'p', 'cu1': 'p',
        }
        if gate_name in controlled_aliases:
            if modifier_controls:
                raise ValueError(f'No se admite combinar alias controlado y ctrl @ en línea {line_number}: {statement}')
            controls, target = qubits[:-1], qubits[-1]
            gate_name = controlled_aliases[gate_name]
        elif modifier_controls:
            if len(qubits) != modifier_controls + 1:
                raise ValueError(f'Cantidad de controles incompatible en línea {line_number}: {statement}')
            controls, target = qubits[:-1], qubits[-1]
        else:
            if len(qubits) != 1:
                raise ValueError(f'Cantidad de qubits inválida en línea {line_number}: {statement}')
            controls, target = [], qubits[0]
        controls = list(extra_controls) + controls

        if gate_name in ('rx', 'ry', 'rz', 'p', 'u1', 'u2', 'u3', 'u'):
            if parameters is None:
                raise ValueError(f'Falta el ángulo de {gate_name} en línea {line_number}: {statement}')
            gate_token = f'{gate_name}({parameters})'
        else:
            if parameters is not None:
                raise ValueError(f'Parámetros inesperados para {gate_name} en línea {line_number}: {statement}')
            gate_token = gate_name.upper()

        matrix = _zx_gate_matrix(gate_token, {}, time=0.5)
        _zx_append_unitary(active_circuit, target, matrix, controls)

    def body_matrix(body, parameter_names, body_n_qubits, depth=0):
        """Matriz exacta (orden Qiskit) del cuerpo de una declaración ``gate``.

        A diferencia de construir un ``zx.Circuit`` local, esta evaluación
        conserva la fase global de cada compuerta, necesaria cuando el bloque
        completo se aplica de forma controlada.

        Parámetros:
            - body (list[str]): sentencias del cuerpo de la declaración.
            - parameter_names (list[str]): nombres de los operandos declarados.
            - body_n_qubits (int): qubits de la declaración.
            - depth (int): profundidad de anidamiento actual.

        Retorna:
            - numpy.ndarray: matriz unitaria de ``2**body_n_qubits``.

        Lanza:
            - ValueError: si el cuerpo tiene una sentencia o un operando inválido.
        """
        if depth >= 10:
            raise ValueError('Anidamiento de custom gates demasiado profundo (>10) en ZX')
        operator = np.eye(1 << body_n_qubits, dtype=complex)
        for body_line in body:
            match = statement_pattern.fullmatch(body_line)
            if match is None:
                raise ValueError(
                    f'Instrucción OpenQASM no reconocida en cuerpo de custom gate: {body_line}'
                )
            operands_text = match.group('operands').strip()
            qubits = []
            for token in operands_text.split(','):
                token = token.strip()
                if token in parameter_names:
                    position = parameter_names.index(token)
                elif re.fullmatch(r'[a-z]', token):
                    position = ord(token) - ord('a')
                else:
                    position = -1
                if position < 0 or position >= body_n_qubits:
                    raise ValueError(
                        f'Operando de custom gate no reconocido en cuerpo: {body_line}'
                    )
                qubits.append(position)

            gate_token = match.group('gate')
            gate_name = gate_token.lower()
            parameters = match.group('params')
            modifier_controls = match.group('modifiers').lower().count('ctrl')
            declaration = declarations.get(gate_token)
            if declaration is not None:
                if parameters is not None:
                    raise ValueError(
                        f'Parámetros inesperados para el custom gate en cuerpo: {body_line}'
                    )
                sub_parameter_names, sub_body = declaration
                if len(qubits) != modifier_controls + len(sub_parameter_names):
                    raise ValueError(
                        f'Cantidad de qubits inválida para el custom gate en cuerpo: {body_line}'
                    )
                sub_mapping = qubits[modifier_controls:]
                sub_matrix = body_matrix(
                    sub_body, sub_parameter_names, len(sub_mapping), depth + 1
                )
                full = _zx_embed_block(
                    sub_matrix, sub_mapping, qubits[:modifier_controls], body_n_qubits
                )
            elif gate_name == 'swap':
                if len(qubits) != modifier_controls + 2:
                    raise ValueError(f'Cantidad de qubits inválida para swap en cuerpo: {body_line}')
                swap = np.array(
                    [
                        [1, 0, 0, 0],
                        [0, 0, 1, 0],
                        [0, 1, 0, 0],
                        [0, 0, 0, 1],
                    ],
                    dtype=complex,
                )
                full = _zx_embed_block(
                    swap, qubits[modifier_controls:], qubits[:modifier_controls], body_n_qubits
                )
            else:
                controlled_aliases = {
                    'cx': 'x', 'cy': 'y', 'cz': 'z', 'ch': 'h',
                    'ccx': 'x', 'mcx': 'x', 'mcy': 'y', 'mcz': 'z',
                    'crx': 'rx', 'cry': 'ry', 'crz': 'rz', 'cp': 'p', 'cu1': 'p',
                }
                if gate_name in controlled_aliases:
                    if modifier_controls:
                        raise ValueError(
                            f'No se admite combinar alias controlado y ctrl @ en cuerpo: {body_line}'
                        )
                    controls, target = qubits[:-1], qubits[-1]
                    gate_name = controlled_aliases[gate_name]
                elif modifier_controls:
                    if len(qubits) != modifier_controls + 1:
                        raise ValueError(
                            f'Cantidad de controles incompatible en cuerpo: {body_line}'
                        )
                    controls, target = qubits[:-1], qubits[-1]
                else:
                    if len(qubits) != 1:
                        raise ValueError(f'Cantidad de qubits inválida en cuerpo: {body_line}')
                    controls, target = [], qubits[0]

                if gate_name in ('rx', 'ry', 'rz', 'p', 'u1', 'u2', 'u3', 'u'):
                    if parameters is None:
                        raise ValueError(f'Falta el ángulo de {gate_name} en cuerpo: {body_line}')
                    gate_token = f'{gate_name}({parameters})'
                else:
                    if parameters is not None:
                        raise ValueError(
                            f'Parámetros inesperados para {gate_name} en cuerpo: {body_line}'
                        )
                    gate_token = gate_name.upper()

                matrix = np.array(
                    _zx_gate_matrix(gate_token, {}, time=0.5), dtype=complex
                )
                full = _zx_embed_block(matrix, [target], controls, body_n_qubits)
            operator = full @ operator
        return operator

    for line_number, statement in circuit_statements:
        process(statement, line_number)

    return circuit.to_graph()


def compare_zx_graphs(base_graph, qasm_graph):
    """Compara dos grafos ZX (PyZX) y devuelve el método y el veredicto.

    Punto único de la regla de equivalencia ZX, compartido por el pipeline CLI
    (``_zx_compare_once`` en ``qtrans/core.py``, con límite de tiempo) y por el
    cuaderno. Grafos con distinto número de qubits no son comparables; con más de
    10 qubits se usa la verificación de igualdad de circuitos (``verify_equality``)
    y, en caso contrario, la comparación de tensores tras reducir ambos grafos.

    Parámetros:
        - base_graph (pyzx.Graph): grafo ZX construido desde Quirk.
        - qasm_graph (pyzx.Graph): grafo ZX construido desde el OpenQASM generado.

    Retorna:
        - tuple[str, str]: ``(method, result)`` donde ``result`` es
          'EQUIVALENTES', 'NO EQUIVALENTES', 'NO DEMOSTRADO' o 'NO COMPARABLES'.
    """
    import pyzx as zx

    base_qubits = base_graph.num_inputs()
    qasm_qubits = qasm_graph.num_inputs()
    if base_qubits != qasm_qubits:
        return 'sin comparar', f'NO COMPARABLES ({base_qubits} vs. {qasm_qubits} qubits)'
    if base_qubits > 10:
        base_circuit = zx.Circuit.from_graph(base_graph)
        qasm_circuit = zx.Circuit.from_graph(qasm_graph)
        equivalent = base_circuit.verify_equality(qasm_circuit, up_to_global_phase=True)
        return 'verify_equality', ('EQUIVALENTES' if equivalent else 'NO DEMOSTRADO')
    zx.simplify.full_reduce(base_graph)
    zx.simplify.full_reduce(qasm_graph)
    equivalent = zx.compare_tensors(base_graph, qasm_graph, strategy='rw-greedy-linear')
    return (
        'compare_tensors (rw-greedy-linear)',
        ('EQUIVALENTES' if equivalent else 'NO EQUIVALENTES'),
    )


def reduce_and_draw_zx_svg(graph, output_path, figsize=None):
    """Reduce un grafo ZX (``full_reduce``) y lo dibuja en un archivo SVG.

    Punto único del renderizado de grafos ZX reducidos, compartido por el
    pipeline CLI y el cuaderno.

    Parámetros:
        - graph (pyzx.Graph): grafo ZX a reducir y dibujar (no se modifica).
        - output_path (str | Path): ruta del SVG de salida.
        - figsize (tuple[float, float] | None): tamaño de figura opcional.

    Retorna:
        - pyzx.Graph: la copia reducida del grafo (para métricas como el número
          de vértices restantes).
    """
    import matplotlib
    matplotlib.use('Agg', force=True)
    import matplotlib.pyplot as plt
    import pyzx as zx

    reduced_graph = graph.copy()
    zx.simplify.full_reduce(reduced_graph)
    if figsize is None:
        # Tamaño adaptado al grafo reducido (mismo criterio que el cuaderno).
        n_qubits = reduced_graph.num_inputs()
        vertices = reduced_graph.num_vertices()
        figsize = (
            max(12, min(24, vertices / 70)),
            max(5, min(12, n_qubits * 0.5)),
        )
    figure = zx.draw(reduced_graph, labels=True, figsize=figsize)
    figure.savefig(str(output_path), format='svg')
    plt.close(figure)
    return reduced_graph


_ZX_TIMEOUT = object()


def zx_run_with_timeout(target, timeout):
    """Ejecuta ``target`` en un hilo daemon con límite de tiempo.

    Devuelve el valor de retorno si termina antes del timeout, la centinela
    ``_ZX_TIMEOUT`` si se excede el límite y relanza la excepción del worker si
    falla. Un hilo que supera el límite queda ejecutándose en segundo plano
    hasta la salida del proceso, pero no bloquea al pipeline.

    Parámetros:
        - target (callable): función a ejecutar en el hilo.
        - timeout (int): límite de tiempo en segundos.

    Retorna:
        - object: el valor de ``target`` o la centinela ``_ZX_TIMEOUT``.

    Lanza:
        - Exception: la excepción propagada por el worker, si falla.
    """
    outcome = {}

    def worker():
        try:
            outcome["ok"] = True
            outcome["value"] = target()
        except Exception as exc:  # noqa: BLE001
            outcome["ok"] = False
            outcome["error"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        return _ZX_TIMEOUT
    if outcome.get("ok"):
        return outcome["value"]
    raise outcome["error"]


def zx_compare_once(base_graph, qasm_graph, timeout):
    """Compara dos grafos ZX con un límite de tiempo.

    La regla de equivalencia vive en ``compare_zx_graphs``; aquí solo se
    envuelve en un límite de tiempo porque la comparación puede ser
    computacionalmente intratable en circuitos con muchas compuertas
    multi-controladas; en ese caso se devuelve un resultado de "no demostrado"
    por timeout en lugar de colgar el pipeline.

    Parámetros:
        - base_graph (pyzx.PyZXGraph): grafo construido desde la fuente Quirk.
        - qasm_graph (pyzx.PyZXGraph): grafo construido desde el OpenQASM.
        - timeout (int): límite de tiempo en segundos.

    Retorna:
        - tuple[str, str]: método usado y veredicto de la comparación.
    """
    def worker():
        return compare_zx_graphs(base_graph, qasm_graph)

    result = zx_run_with_timeout(worker, timeout)
    if result is _ZX_TIMEOUT:
        return "timeout", f"NO DEMOSTRADO (timeout {timeout}s)"
    return result


ZX_STATUS_LEGEND = {
    "EQUIVALENTES": (
        "Los grafos ZX del circuito de Quirk y del OpenQASM generado son "
        "equivalentes (salvo fase global)."
    ),
    "NO EQUIVALENTES": (
        "Los grafos ZX son distintos: la traducción no conserva la acción "
        "unitaria del circuito original."
    ),
    "NO COMPARABLES": (
        "No se pudo establecer la equivalencia (el grafo ZX no es construible "
        "o la comparación no está definida); el motivo figura en la columna "
        "«Motivo»."
    ),
    "NO DEMOSTRADO": (
        "La comparación excedió el límite de tiempo configurado y no pudo "
        "completarse."
    ),
    "ERROR": (
        "Excepción durante la comparación; el motivo figura en la columna "
        "«Motivo»."
    ),
}


def _md_cell(value):
    """Escapa un valor para que no rompa una tabla Markdown.

    Parámetros:
        - value (str | int): valor de la celda.

    Retorna:
        - str: texto sin saltos de línea y con las barras verticales escapadas.
    """
    return str(value).replace("|", "\\|").replace("\n", " ")


def _zx_status(result):
    """Extrae el estado normalizado de un veredicto de comparación ZX.

    Parámetros:
        - result (str): veredicto devuelto por la comparación (p. ej.
          ``'EQUIVALENTES'`` o ``'NO DEMOSTRADO (timeout 120s)'``).

    Retorna:
        - str: estado normalizado (clave de :data:`ZX_STATUS_LEGEND`).
    """
    text = str(result)
    for status in ("EQUIVALENTES", "NO EQUIVALENTES", "NO COMPARABLES",
                   "NO DEMOSTRADO", "ERROR"):
        if text.startswith(status):
            return status
    return text.split(" ", 1)[0]


def _zx_qubit_count(record):
    """Calcula el número de cúbits de un registro para la tabla de comparación.

    Parámetros:
        - record (dict): registro del circuito (clave ``qasm_source``).

    Retorna:
        - int | str: número de cúbits si se puede determinar, ``'?'`` si no.
    """
    text = str(record.get("qasm_source", ""))
    for pattern in (r"qubit\s*\[\s*(\d+)\s*\]", r"qreg\s+\w+\s*\[\s*(\d+)\s*\]"):
        sizes = re.findall(pattern, text)
        if sizes:
            return int(sizes[0])
    return "?"

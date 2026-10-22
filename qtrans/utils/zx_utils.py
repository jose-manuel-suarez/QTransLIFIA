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
from pathlib import Path

from .pipeline_utils import algorithm_sort_key, log_stage, safe_print
from .quirk_utils import (
    _CONTROL_GATES,
    _build_gate_map,
    _column_extent,
    _is_control,
    _matrix_to_rows,
    _qft_token,
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


def quirk_to_zx_graph(url, offset=0, time=0.5):
    """Construye el grafo ZX de PyZX directamente desde una URL de Quirk.

    Parámetros:
        - url (str): URL de Quirk con ``circuit=<JSON>``.
        - offset (int): desplazamiento de índices qubit.
        - time (float): snapshot temporal de Quirk (para gates como 'Rxft').

    Retorna:
        - pyzx.Graph: el grafo ZX equivalente al circuito Quirk.
    """
    try:
        import pyzx as zx
    except ImportError as exc:
        raise ImportError('Instala PyZX con `pip install pyzx` para generar grafos ZX') from exc

    if not 0 <= time <= 1:
        raise ValueError('time debe estar entre 0 y 1, como el tiempo de Quirk')

    circuit_data = parse_quirk_url(url)
    cols = circuit_data.get('cols', [])
    gate_map = _build_gate_map(circuit_data)
    n_qubits = max((_column_extent(col, gate_map) for col in cols), default=0) + offset
    circuit = zx.Circuit(n_qubits)

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
        swap_indices = [index + offset for index, value in enumerate(col) if value == 'Swap']
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
                _zx_append_qft(circuit, index + offset, qft_info[0], qft_info[1], controls)
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

    return circuit.to_graph()


def qasm_to_zx_graph(qasm_code):
    """Construye el grafo ZX de PyZX desde el OpenQASM generado por el proyecto.

    Admite versiones 2.0 (``qreg``) y 3.0 (``qubit``), gates con parámetros
    (rx/ry/rz/p/u1/u2/u3/u) y declaraciones ``gate`` (incl. QFT), resolviendo
    los operandos del cuerpo por el nombre declarado (p. ej. ``h_``).

    Parámetros:
        - qasm_code (str): código OpenQASM (2.0 o 3.0).

    Retorna:
        - pyzx.Graph: el grafo ZX equivalente al circuito OpenQASM.
    """
    try:
        import pyzx as zx
    except ImportError as exc:
        raise ImportError('Instala PyZX con `pip install pyzx` para generar grafos ZX') from exc

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

    def process(statement, line_number, mapping=None, extra_controls=(), depth=0, param_names=None):
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
        if any(qubit >= n_qubits for qubit in qubits):
            raise ValueError(f'Índice de qubit fuera del registro en línea {line_number}: {statement}')

        gate_name = match.group('gate').lower()
        parameters = match.group('params')
        modifier_controls = match.group('modifiers').lower().count('ctrl')

        # Custom gate declarado: expandir su cuerpo con los qubits mapeados.
        # Los controles de la llamada aplican a cada sentencia del cuerpo
        # (c-(A·B) == (c-A)·(c-B)), y se suman a los controles heredados.
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
            for body_line in body:
                process(body_line, line_number, body_mapping, body_controls, depth + 1, parameter_names)
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
                _zx_append_mcx(circuit, controls + [first], second)
                _zx_append_mcx(circuit, controls + [second], first)
                _zx_append_mcx(circuit, controls + [first], second)
            else:
                circuit.add_gate('SWAP', *targets)
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
        _zx_append_unitary(circuit, target, matrix, controls)

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


def run_zx_workflow(records, zx_dir, zx_time, generate_images, verbose, zx_timeout):
    """Ejecuta la fase ZX completa: grafos base/QASM, comparación y SVG.

    Parámetros:
        - records (list[dict]): registros de los circuitos (claves ``name``,
          ``url``, ``offset`` y ``qasm_source``).
        - zx_dir (str | Path): carpeta raíz de la fase ZX.
        - zx_time (int): límite de tiempo (s) de la construcción de los grafos.
        - generate_images (bool): genera además los SVG reducidos.
        - verbose (bool): muestra el log de cada etapa.
        - zx_timeout (int): límite de tiempo (s) de cada comparación y reducción.

    Retorna:
        - dict: ``base_graphs``, ``qasm_graphs`` (recuentos), ``comparisons``
          (lista de dicts), ``comparison_path`` (ruta del Markdown),
          ``images`` (SVG generados) y ``errors``.
    """
    zx_dir = Path(zx_dir)
    base_dir = zx_dir / "algorithms_base"
    qasm_dir = zx_dir / "algorithms_qasm"
    graphs_dir = zx_dir / "graphs"
    base_dir.mkdir(parents=True, exist_ok=True)
    qasm_dir.mkdir(parents=True, exist_ok=True)
    if generate_images:
        graphs_dir.mkdir(parents=True, exist_ok=True)

    base_graphs = {}
    qasm_graphs = {}
    errors = []
    not_comparable = {}
    log_stage(
        verbose,
        "ZX",
        f"Iniciando generación de grafos para {len(records)} algoritmos.",
    )
    for record in records:
        name = record["name"]
        try:
            base_graph = quirk_to_zx_graph(
                record["url"], record["offset"], time=zx_time
            )
            qasm_graph = qasm_to_zx_graph(record["qasm_source"])
            base_path = base_dir / f"{name}.json"
            qasm_path = qasm_dir / f"{name}.json"
            base_path.write_text(base_graph.to_json(), encoding="utf-8")
            qasm_path.write_text(qasm_graph.to_json(), encoding="utf-8")
            base_graphs[name] = base_graph
            qasm_graphs[name] = qasm_graph
            log_stage(verbose, "Grafo ZX", f"Generados grafos base/QASM para {name}.")
        except Exception as exc:
            errors.append((f"Grafo ZX/{name}", exc))
            not_comparable[name] = {
                "Cúbits": _zx_qubit_count(record),
                "Método": "sin grafo",
                "Resultado": "NO COMPARABLES",
                "Motivo": str(exc),
            }
            safe_print(f"Error generando grafos ZX para {name}: {exc}")

    comparisons = []
    log_stage(
        verbose,
        "ZX",
        f"Iniciando comprobación Quirk vs OpenQASM para "
        f"{len(base_graphs.keys() & qasm_graphs.keys())} circuitos.",
    )
    for name in sorted(base_graphs.keys() & qasm_graphs.keys(), key=algorithm_sort_key):
        base_graph = base_graphs[name]
        qasm_graph = qasm_graphs[name]
        base_qubits = base_graph.num_inputs()
        qasm_qubits = qasm_graph.num_inputs()
        method = "sin comparar"
        result = "NO COMPARABLES"
        reason = "Los grafos no admiten una comparación directa."

        try:
            method, result = zx_compare_once(
                base_graph, qasm_graph, zx_timeout
            )
            reason = ""
        except Exception as exc:
            errors.append((f"Comparación ZX/{name}", exc))
            result = "ERROR"
            reason = f"{type(exc).__name__}: {exc}"
            safe_print(f"Error comparando grafos ZX para {name}: {exc}")

        comparisons.append(
            {
                "Nombre algoritmo": name,
                "Cúbits": base_qubits,
                "Método": method,
                "Resultado": result,
                "Motivo": reason,
            }
        )
        log_stage(
            verbose,
            "Comparación ZX",
            f"Quirk vs OpenQASM de {name}: {result} (método: {method}).",
        )

    for name in sorted(not_comparable, key=algorithm_sort_key):
        entry = not_comparable[name]
        comparisons.append({"Nombre algoritmo": name, **entry})
        log_stage(
            verbose,
            "Comparación ZX",
            f"Quirk vs OpenQASM de {name}: {entry['Resultado']} "
            f"(motivo: {entry['Motivo']}).",
        )

    comparisons.sort(key=lambda c: algorithm_sort_key(c["Nombre algoritmo"]))

    if verbose and comparisons:
        equivalent = sum(
            1 for c in comparisons if c["Resultado"].startswith("EQUIVALENTES")
        )
        not_demonstrated = sum(
            1 for c in comparisons if c["Resultado"].startswith("NO DEMOSTRADO")
        )
        not_comparable_count = sum(
            1 for c in comparisons if c["Resultado"].startswith("NO COMPARABLES")
        )
        safe_print(
            f"[Comparación ZX] Grafos reducidos Quirk vs OpenQASM: "
            f"{equivalent}/{len(comparisons)} circuitos EQUIVALENTES"
            + (f", {not_demonstrated} NO DEMOSTRADOS" if not_demonstrated else "")
            + (f", {not_comparable_count} NO COMPARABLES" if not_comparable_count else "")
            + "."
        )
        safe_print(
            f"[Comparación ZX] Listado de comparaciones ({len(comparisons)}):"
        )
        for index, comparison in enumerate(comparisons, start=1):
            motive = f" — {comparison['Motivo']}" if comparison["Motivo"] else ""
            safe_print(
                f"[Comparación ZX] {index:>2}. {comparison['Nombre algoritmo']} "
                f"({comparison['Cúbits']}q) -> {comparison['Resultado']}{motive}"
            )

    comparison_path = zx_dir / "comparison_results.md"
    status_counts = {}
    reason_counts = {}
    for comparison in comparisons:
        status = _zx_status(comparison["Resultado"])
        status_counts[status] = status_counts.get(status, 0) + 1
        if comparison["Motivo"]:
            reason_counts[comparison["Motivo"]] = (
                reason_counts.get(comparison["Motivo"], 0) + 1
            )
    comparable = sum(
        count for status, count in status_counts.items() if status != "NO COMPARABLES"
    )
    markdown_lines = [
        "# Resultados de equivalencia Quirk vs OpenQASM (ZX-Calculus)",
        "",
        f"Total de circuitos analizados: {len(comparisons)} "
        f"({comparable} comparados, {len(comparisons) - comparable} no comparables).",
        "",
        "| Nombre algoritmo | Cúbits | Método | Resultado | Motivo |",
        "| --- | :-: | --- | --- | --- |",
    ]
    for comparison in comparisons:
        markdown_lines.append(
            f"| {_md_cell(comparison['Nombre algoritmo'])} | "
            f"{_md_cell(comparison['Cúbits'])} | "
            f"{_md_cell(comparison['Método'])} | "
            f"{_md_cell(comparison['Resultado'])} | "
            f"{_md_cell(comparison['Motivo'])} |"
        )
    markdown_lines += ["", "## Leyenda", ""]
    markdown_lines += [
        "| Estado | Circuitos | Significado |",
        "| --- | :-: | --- |",
    ]
    for status, description in ZX_STATUS_LEGEND.items():
        markdown_lines.append(
            f"| {status} | {status_counts.get(status, 0)} | {description} |"
        )
    if reason_counts:
        markdown_lines += ["", "### Motivos de no comparabilidad", ""]
        markdown_lines += ["| Motivo | Circuitos |", "| --- | :-: |"]
        for reason, count in sorted(
            reason_counts.items(), key=lambda item: (-item[1], item[0])
        ):
            markdown_lines.append(f"| {_md_cell(reason)} | {count} |")
    comparison_path.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")

    generated_images = []
    if generate_images:
        for name, graph in base_graphs.items():
            image_path = graphs_dir / f"{name}.svg"
            try:
                def render_worker(graph=graph, path=image_path):
                    return reduce_and_draw_zx_svg(graph, path)

                if zx_run_with_timeout(render_worker, zx_timeout) is _ZX_TIMEOUT:
                    log_stage(
                        verbose,
                        "ZX SVG",
                        f"Reducción de {name} excedió {zx_timeout}s; se omite el SVG.",
                    )
                    continue
                generated_images.append(image_path)
                log_stage(verbose, "ZX SVG", f"Generado {image_path.name}.")
            except Exception as exc:
                errors.append((f"ZX SVG/{name}", exc))
                safe_print(f"Error generando SVG ZX para {name}: {exc}")

    return {
        "base_graphs": len(base_graphs),
        "qasm_graphs": len(qasm_graphs),
        "comparisons": comparisons,
        "comparison_path": comparison_path,
        "images": generated_images,
        "errors": errors,
    }

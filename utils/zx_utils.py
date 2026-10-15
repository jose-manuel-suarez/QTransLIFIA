"""Grafo ZX (PyZX) de QTransLIFIA.

Fase de verificación ZX del pipeline: construcción de los grafos directamente desde
la fuente Quirk (``quirk_to_zx_graph``) y desde el OpenQASM generado
(``qasm_to_zx_graph``), más los helpers ``_zx_*`` que las sustentan.

Los helpers compartidos con la traducción Quirk→OpenQASM (``_build_gate_map``,
``_column_extent``, ``_matrix_to_rows``, ``_qft_token``) viven en ``utils.qutils``
y el parseo de URLs de Quirk (``parse_quirk_url``) en ``utils.url_utils``.
"""

import ast
import cmath
import itertools
import math
import re
from fractions import Fraction

from utils.qutils import (
    _build_gate_map,
    _column_extent,
    _matrix_to_rows,
    _qft_token,
)
from utils.url_utils import parse_quirk_url


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
    n_qubits = max((_column_extent(col) for col in cols), default=0) + offset
    circuit = zx.Circuit(n_qubits)
    gate_map = _build_gate_map(circuit_data)

    for col in cols:
        controls = [index + offset for index, value in enumerate(col) if value == '•']
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
            if token in (1, '1', None, '•', 'Swap', 'Measure'):
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

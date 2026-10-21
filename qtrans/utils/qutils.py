import cmath
import math
import os
import re
import string
import sys

from .url_utils import canonicalize_quirk_url, parse_quirk_url


def _build_gate_map(circuito):
    """Construye un mapa id/name -> definición de gate a partir del campo 'gates'.

    Parámetros:
        - circuito (dict): el circuito Quirk parseado (con 'gates').

    Retorna:
        - dict: mapa de id y name del gate -> su definición.
    """
    gate_map = {}
    for g in circuito.get('gates', []):
        if 'id' in g and isinstance(g['id'], str):
            gate_map[g['id']] = g
            base = g['id'].split(':')[0]
            gate_map[base] = g
        if 'name' in g and isinstance(g['name'], str):
            if g['name'] not in gate_map:
                gate_map[g['name']] = g
    return gate_map


def _gate_height(gate):
    """Altura en qubits de un custom gate (por su 'circuit' o su 'matrix').

    Parámetros:
        - gate (dict): definición del custom gate.

    Retorna:
        - int: cantidad de qubits que ocupa el gate.
    """
    cols = gate.get('circuit', {}).get('cols', [])
    if cols:
        return max(len(c) for c in cols)
    matrix = gate.get('matrix')
    if isinstance(matrix, list):
        dimension = len(matrix)
    elif isinstance(matrix, str):
        depth = 0
        dimension = 0
        for char in matrix:
            if char == '{':
                depth += 1
                if depth == 2:
                    dimension += 1
            elif char == '}':
                depth -= 1
    else:
        return 0
    if dimension < 1 or dimension & (dimension - 1):
        return 0
    return dimension.bit_length() - 1


def _matrix_gate_operation(gate):
    """Operación QASM equivalente para las matrices de fase conocidas de Quirk.

    Parámetros:
        - gate (dict): definición del gate con 'matrix'.

    Retorna:
        - str | None: la operación (p. ej. 's', 't') o None si no es conocida.
    """
    operations = {
        'U(-pi/2)': 'p(-pi/2)',
        'U(-pi/4)': 'p(-pi/4)',
    }
    name = gate.get('name')
    if name in operations:
        return operations[name]
    match = re.fullmatch(r'(?:cu1|cp)\((.+)\)', name or '', re.IGNORECASE)
    if match and _gate_height(gate) == 1:
        return f'p({match.group(1)})'
    return None


def _unquote_parameters(lines, params):
    """Quita las comillas que un !r añadió alrededor de los placeholders wN.

    Parámetros:
        - lines (list[str]): líneas del cuerpo de la función personalizada.
        - params (list[str]): nombres de parámetros (placeholders wN).

    Retorna:
        - list[str]: las líneas con los placeholders sin comillas.
    """
    result = list(lines)
    for param in params:
        result = [
            line.replace(f"'{param}'", param).replace(f'"{param}"', param)
            for line in result
        ]
    return result


# Compuertas nativas QFT / QFT† de Quirk (familia de 1..16 cúbits).
_QFT_TOKEN_RE = re.compile(
    r'^QFT(?P<inv1>\u2020|\^\u2020)?(?P<span>\d+)(?P<inv2>\u2020|\^\u2020)?$'
)


def _qft_token(value):
    """Detecta si value es una compuerta nativa QFT de Quirk.

    Parámetros:
        - value: celda de la columna (str u otro tipo).

    Retorna:
        - tuple | None: (span, inverse) si es 'QFTn'/'QFTn†'; None si no.
    """
    if not isinstance(value, str):
        return None
    match = _QFT_TOKEN_RE.match(value)
    if match is None:
        return None
    span = int(match.group('span'))
    if span < 1:
        return None
    return span, bool(match.group('inv1') or match.group('inv2'))


def _qft_gate_name(span, inverse=False):
    """Nombre OpenQASM de la compuerta QFT de 'span' qubits.

    Parámetros:
        - span (int): cantidad de qubits de la QFT.
        - inverse (bool): si True devuelve la versión inversa (sufijo '_dg').

    Retorna:
        - str: p. ej. 'QFT3' o 'QFT3_dg'.
    """
    return f'QFT{span}_dg' if inverse else f'QFT{span}'


def _qft_qasm_body(span, inverse=False):
    """Cuerpo de la compuerta QFT (descomposición estándar H + fases + SWAP).

    Parámetros:
        - span (int): cantidad de qubits de la QFT.
        - inverse (bool): si True genera la QFT inversa.

    Retorna:
        - list[str]: líneas OpenQASM del cuerpo (sin terminador ';').
    """
    arg_list = primeras_letras(span).split(',')
    args = [a.strip() for a in arg_list]
    lines = []
    if not inverse:
        for i in range(span - 1, -1, -1):
            lines.append(f'h {args[i]};')
            for j in range(i - 1, -1, -1):
                lines.append(f'cp(pi / {2 ** (i - j)}) {args[i]}, {args[j]};')
        for k in range(span // 2):
            lines.append(f'swap {args[k]}, {args[span - 1 - k]};')
    else:
        for k in range(span // 2):
            lines.append(f'swap {args[k]}, {args[span - 1 - k]};')
        for i in range(span):
            for j in range(i):
                lines.append(f'cp(-pi / {2 ** (i - j)}) {args[i]}, {args[j]};')
            lines.append(f'h {args[i]};')
    return lines


def _qft_declarations(tokens):
    """Declaraciones 'gate QFTn ...' para los spans QFT usados en el circuito.

    Parámetros:
        - tokens (set[tuple]): pares (span, inverse) detectados.

    Retorna:
        - list[str]: líneas de declaración OpenQASM.
    """
    lines = []
    for span, inverse in sorted(tokens):
        name = _qft_gate_name(span, inverse)
        lines.append(f'gate {name} {primeras_letras(span)} {{')
        lines.extend(_qft_qasm_body(span, inverse))
        lines.append('}')
    return lines


def _column_extent(col, gate_map=None):
    """Altura efectiva de una columna, contando custom gates y QFT nativas.

    Parámetros:
        - col (list): columna del circuito.
        - gate_map (dict | None): mapa id/name -> definición de custom gates
          (para contar la altura de las celdas que referencian un gate).

    Retorna:
        - int: la máxima cantidad de qubits que toca la columna.
    """
    extent = len(col)
    for index, value in enumerate(col):
        info = _qft_token(value)
        if info is not None:
            extent = max(extent, index + info[0])
            continue
        if gate_map is not None and _is_gate_ref(value, gate_map):
            gate = gate_map.get(str(value).split(':')[0])
            height = _gate_height(gate) if gate is not None else 0
            extent = max(extent, index + (height or 1))
    return extent


# Gates estándar de OpenQASM 3 (stdgates.inc) utilizables en el sitio de uso.
_STANDARD_GATES = frozenset({
    'p', 'x', 'y', 'z', 'h', 's', 'sdg', 't', 'tdg', 'sx', 'rx', 'ry', 'rz',
    'u', 'cx', 'cy', 'cz', 'ch', 'cp', 'crx', 'cry', 'crz', 'cswap',
    'ccx', 'ccy', 'ccz', 'swap', 'id',
})
# Gates estándar que no llevan argumentos (name plano, p.ej. "X", "H").
_NO_ARGUMENT_GATES = frozenset({
    'x', 'y', 'z', 'h', 's', 'sdg', 't', 'tdg', 'sx', 'swap', 'id',
})
# Palabras reservadas de OpenQASM que no pueden usarse como nombre de gate.
_QASM_RESERVED_WORDS = frozenset({
    'gate', 'qreg', 'creg', 'include', 'OPENQASM', 'barrier', 'measure',
    'reset', 'ctrl', 'inv', 'pow', 'if', 'else', 'for', 'while', 'return',
    'break', 'continue', 'const', 'input', 'output', 'qubit', 'bit', 'let',
})


def _sanitize_gate_name(raw_name, fallback='custom_gate'):
    """Convierte un nombre de custom gate en un identificador QASM válido.

    Reemplaza caracteres no alfanuméricos, evita palabras reservadas y
    colisiones con gates estándar.

    Parámetros:
        - raw_name (str): nombre original del gate en Quirk.
        - fallback (str): nombre a usar si raw_name queda vacío.

    Retorna:
        - str: identificador OpenQASM seguro.
    """
    cleaned = re.sub(r'[^A-Za-z0-9_]+', '_', str(raw_name or ''))
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    if not cleaned:
        cleaned = re.sub(r'[^A-Za-z0-9_]+', '_', str(fallback or '')).strip('_')
    if not cleaned:
        cleaned = 'custom_gate'
    if not re.match(r'[A-Za-z_]', cleaned):
        cleaned = f'gate_{cleaned}'
    if cleaned in _QASM_RESERVED_WORDS or cleaned in _STANDARD_GATES:
        cleaned = f'{cleaned}_gate'
    return cleaned


def _resolve_gate_names(gate_map):
    """Asigna a cada custom gate un identificador QASM único por id y name.

    Se usa tanto en la declaración `gate ...` como en el sitio de uso para
    garantizar que ambas referencias coincidan siempre.

    Parámetros:
        - gate_map (dict): mapa id/name -> definición de custom gates.

    Retorna:
        - dict: mapa id/name -> identificador QASM único.
    """
    names = {}
    identifier_by_object = {}
    used = set()
    for key in sorted(gate_map):
        gate = gate_map[key]
        object_id = id(gate)
        if object_id not in identifier_by_object:
            raw = gate.get('name') or gate.get('id') or 'custom_gate'
            identifier = _sanitize_gate_name(raw)
            base = identifier
            suffix = 2
            while identifier in used:
                identifier = f'{base}_{suffix}'
                suffix += 1
            used.add(identifier)
            identifier_by_object[object_id] = identifier
        names[key] = identifier_by_object[object_id]
    return names


def _named_gate_operation(gate):
    """Operación QASM si el 'name' del gate es una llamada a un gate estándar.

    Parámetros:
        - gate (dict): definición del gate (con 'name').

    Retorna:
        - str | None: la operación equivalente o None si no aplica.
    """
    name = str(gate.get('name') or '').strip()
    if not name:
        return None
    match = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)\((.*)\)', name)
    if match:
        operator, arguments = match.group(1), match.group(2)
        if operator == 'U':
            operator = 'u' if len(arguments.split(',')) == 3 else None
            if operator is None:
                return None
        if operator == 'cu1':
            # cu1 no existe en stdgates.inc de QASM 3: p (1 qubit) o cp (2).
            operator = 'cp' if _gate_height(gate) == 2 else 'p'
        elif operator not in _STANDARD_GATES:
            return None
        elif operator == 'cp' and _gate_height(gate) == 1:
            operator = 'p'
        return f'{operator}({arguments})'
    lowered = name.lower()
    if lowered in _NO_ARGUMENT_GATES:
        return lowered
    return None


def _split_top_level(text):
    """Divide un texto por comas que no están anidadas dentro de llaves/corchetes.

    Parámetros:
        - text (str): texto a dividir (p. ej. el contenido de una matriz).

    Retorna:
        - list[str]: los fragmentos de nivel superior.
    """
    parts, depth, current = [], 0, []
    for char in text:
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
        if char == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(char)
    parts.append(''.join(current))
    return parts


def _to_complex(value):
    """Convierte un valor de matriz Quirk a complex.

    Acepta complex, int, float o string de Quirk con √½, √2, fracciones (½, ¼, ¾),
    signo menos Unicode y notación imaginaria con 'i'.

    Parámetros:
        - value: valor a convertir (número o str).

    Retorna:
        - complex: el valor complejo equivalente.
    """
    if isinstance(value, complex):
        return value
    if isinstance(value, (int, float)):
        return complex(value)
    text = str(value).strip()
    text = text.replace('√½', '0.7071067811865476')
    text = text.replace('√2', '1.4142135623730951')
    text = text.replace('½', '0.5').replace('¼', '0.25').replace('¾', '0.75')
    text = text.replace('−', '-')  # signo menos Unicode
    if 'i' in text and 'j' not in text:
        text = text.replace('i', 'j')  # notación compleja de Quirk: ...+0.006i
    return complex(text)


def _matrix_to_rows(matrix):
    """Normaliza 'matrix' (string de Quirk o lista) a filas de complex.

    Parámetros:
        - matrix: representación de la matriz (str de Quirk o lista de listas).

    Retorna:
        - list | None: filas de valores complex, o None si no se puede parsear.
    """
    try:
        if isinstance(matrix, str):
            text = matrix.strip()
            if not (text.startswith('{') and text.endswith('}')):
                return None
            rows = []
            for row_text in _split_top_level(text[1:-1]):
                row_text = row_text.strip()
                if not (row_text.startswith('{') and row_text.endswith('}')):
                    return None
                rows.append([_to_complex(entry) for entry in _split_top_level(row_text[1:-1])])
            return rows
        if isinstance(matrix, list):
            return [[_to_complex(entry) for entry in row] for row in matrix]
    except (ValueError, TypeError, IndexError):
        return None
    return None


def _diagonal_matrix_operation(gate):
    """Operación QASM equivalente a una matriz diagonal de fase conocida.

    Parámetros:
        - gate (dict): definición del gate con 'matrix' diagonal.

    Retorna:
        - str | None: la operación (p. ej. 's', 't') o None si no es conocida.
    """
    rows = _matrix_to_rows(gate.get('matrix'))
    if not rows or len(rows) != 2 or any(len(row) != 2 for row in rows):
        return None
    (a, b), (c, d) = rows
    if abs(b) > 1e-9 or abs(c) > 1e-9:
        return None
    if abs(a - 1) > 1e-6:  # fase global distinta de 1: no equivale a p()
        return None
    return f'p({cmath.phase(d)!r})'


def _resolve_matrix_operation(gate, gate_id):
    """Operación OpenQASM equivalente a un custom gate definido con 'matrix'.

    Se usa para construir el cuerpo de su declaración `gate ...` (y para
    validar que el gate es traducible antes de referenciarlo).

    Parámetros:
        - gate (dict): definición del custom gate (con 'matrix').
        - gate_id (str): id del gate (para los mensajes de error).

    Retorna:
        - str: la operación OpenQASM equivalente.

    Lanza:
        - ValueError: si la matriz no es convertible a OpenQASM.
    """
    for resolver in (
        _matrix_gate_operation,
        _named_gate_operation,
        _diagonal_matrix_operation,
    ):
        operation = resolver(gate)
        if operation:
            return operation
    raise ValueError(
        f"Custom gate {gate_id!r} (name={gate.get('name')!r}) definido solo con "
        "'matrix' no es convertible a OpenQASM: agrega un name con forma "
        "'op(args)' de stdgates.inc o una matriz de fase 2x2 {{1,0},{0,z}}"
    )


# Cantidad de qubits que ocupa cada gate estándar (para el cuerpo de la
# declaración `gate` de un custom gate definido con 'matrix').
_OPERATION_ARITIES = {
    'cx': 2, 'cy': 2, 'cz': 2, 'ch': 2, 'cp': 2, 'crx': 2, 'cry': 2,
    'crz': 2, 'cswap': 2, 'swap': 2,
    'ccx': 3, 'ccy': 3, 'ccz': 3,
}


def _operation_arity(operation, default):
    """Aritud de una operación OpenQASM según su nombre.

    Consulta la tabla _OPERATION_ARITIES y, para gates estándar, asume aritud 1.

    Parámetros:
        - operation (str): texto de la operación (usa solo el primer identificador).
        - default (int): aritud a devolver si el nombre no se reconoce.

    Retorna:
        - int: la aritud de la operación.
    """
    match = re.match(r'([A-Za-z_][A-Za-z0-9_]*)', operation)
    if not match:
        return default
    name = match.group(1).lower()
    if name in _OPERATION_ARITIES:
        return _OPERATION_ARITIES[name]
    if name in _STANDARD_GATES:
        return 1
    return default


def _gate_operation(gate, gate_id, gate_names):
    """Identificador OpenQASM para usar un custom gate en el sitio de uso.

    Todos los custom gates (con 'circuit.cols' o con 'matrix') se declaran
    arriba como submódulos `gate ...`; aquí se devuelve ese mismo identificador
    para que la declaración y la llamada coincidan siempre.

    Parámetros:
        - gate (dict): definición del custom gate.
        - gate_id (str): id del gate en el gate_map.
        - gate_names (dict): mapa id/name -> identificador QASM (de
          ``_resolve_gate_names``).

    Retorna:
        - str: el identificador del gate (declaración y llamada coinciden).

    Lanza:
        - ValueError: si el gate no define 'circuit' ni 'matrix' (no traducible).
    """
    base = str(gate_id).split(':')[0]
    identifier = (
        gate_names.get(base)
        or gate_names.get(gate_id)
        or _sanitize_gate_name(gate.get('name') or gate_id)
    )
    if gate.get('circuit', {}).get('cols'):
        return identifier
    if gate.get('matrix') is None:
        raise ValueError(
            f"Custom gate {gate_id!r} no define 'circuit' ni 'matrix': "
            "no hay forma de traducirlo a OpenQASM"
        )
    _resolve_matrix_operation(gate, gate_id)  # valida que sea traducible
    return identifier


def _is_gate_ref(entry, gate_map):
    """Indica si una celda es una referencia a un custom gate del mapa.

    Parámetros:
        - entry: celda de la columna (str u otro tipo).
        - gate_map (dict): mapa id/name -> definición de custom gates.

    Retorna:
        - bool: True si la base del id (antes de ':') está en el mapa.
    """
    if not isinstance(entry, str):
        return False
    base = entry.split(':')[0]
    return base in gate_map


# ---------------------------------------------------------------------------
# Compuertas escalares de Quirk (fase global ·I)
# ---------------------------------------------------------------------------
# Fase global (en radianes) asociada a cada compuerta escalar de Quirk:
# multiplican el estado por e^{i·theta}·I. Sin control son fase global
# (gphase); con control pasan a ser fase relativa (Sección: _SCALAR_*_RELS).
_SCALAR_GLOBAL_PHASES = {
    'NeGate': math.pi,
    'i': math.pi / 2,
    '-i': -math.pi / 2,
    '\u221ai': math.pi / 4,      # √i
    '\u221a-i': -math.pi / 4,    # √-i
}
# Compuerta no-op de Quirk: no afecta el estado (Spacer / elipsis).
_SCALAR_NOOP_GATES = frozenset({'\u2026'})
# Compuerta '0' de Quirk: ZeroGate, matriz nula (no unitaria, no traducible).
_SCALAR_NULL_GATES = frozenset({'0'})


def _scalar_gate_phase(value):
    """Fase global (rad) de una compuerta escalar de Quirk, o None si no aplica.

    Parámetros:
        - value: celda de la columna (str u otro tipo).

    Retorna:
        - float | None: la fase en radianes; None si la celda no es escalar.
    """
    if not isinstance(value, str):
        return None
    return _SCALAR_GLOBAL_PHASES.get(value)


def _scalar_relative_rz_angles(phase):
    """Ángulos de las rotaciones Z de una fase relativa equivalente a gphase.

    La secuencia ``rz(phi); rx(pi); rz(-phi); rx(-pi)`` sobre un qubit
    convierte la fase global e^{i·phi} en una fase relativa sobre ese qubit,
    de modo que ``ctrl @`` reproduce el efecto de una compuerta escalar
    controlada de Quirk.

    Parámetros:
        - phase (float): fase global en radianes.

    Retorna:
        - tuple[float, float]: los ángulos ``(phi, phi)`` de las dos rz.
    """
    return phase, phase


# Compuertas Quirk no traducibles (matriz no unitaria / desconocidas) ya
# reportadas en la corrida, para no repetir el mismo aviso cientos de veces.
_REPORTED_UNSUPPORTED_GATES = set()


def _report_unsupported_gate(value):
    """Registra en stderr un aviso por una celda Quirk no traducible.

    Se emite una sola vez por identificador. No interrumpe la traducción;
    el aviso permite detectar compuertas de Quirk no soportadas (p. ej. la
    ZeroGate '0', no unitaria) que de otro modo se perderían en silencio.

    Parámetros:
        - value: celda de la columna (identificador de la compuerta).
    """
    key = str(value)
    if key in _REPORTED_UNSUPPORTED_GATES:
        return
    _REPORTED_UNSUPPORTED_GATES.add(key)
    print(
        f'[advertencia] Compuerta Quirk {key!r} no es traducible a OpenQASM; '
        'se omite del circuito generado.',
        file=sys.stderr,
    )


def _angle_literal(radians):
    """Expresión OpenQASM para un ángulo en radianes múltiplo de pi/4.

    Parámetros:
        - radians (float): ángulo en radianes.

    Retorna:
        - str: literal OpenQASM (p. ej. 'pi', 'pi/2', '-pi/4', '0').
    """
    if radians == 0:
        return '0'
    units = round(radians / (math.pi / 4))  # unidades de pi/4
    if abs(radians - units * (math.pi / 4)) > 1e-9:
        return repr(radians)
    sign = '-' if units < 0 else ''
    numerator = abs(units)  # 1..4 → pi/4, pi/2, 3pi/4, pi
    divisor = math.gcd(numerator, 4)
    numerator, denominator = numerator // divisor, 4 // divisor
    if denominator == 1:
        return f'{sign}pi' if numerator == 1 else f'{sign}{numerator}*pi'
    return f'{sign}pi/{denominator}' if numerator == 1 else f'{sign}{numerator}*pi/{denominator}'


# Compuertas de post-selección nativas de Quirk (PostSelectionGates.js). Son
# proyectores NO unitarios: 'post-seleccionar' = medir en la base propia del
# proyector y descartar el shot si el resultado no coincide. OpenQASM no tiene
# primitiva de post-selección, así que se traducen como la rotación de base que
# define el proyector + una medición en el registro ``ps`` (post-select),
# dejando en comentario el cbit válido y la etiqueta de Quirk.
_POSTSELECT_GATES = {
    # id (JSON Quirk)   : (líneas de rotación de base, resultado esperado, etiqueta)
    '|0⟩⟨0|':           ([], 0, 'Postselect Off (|0>)'),
    '|1⟩⟨1|':           (['x'], 1, 'Postselect On (|1>)'),
    '|+⟩⟨+|':           (['h'], 0, 'Postselect X-Off (|+>)'),
    '|-⟩⟨-|':           (['h'], 1, 'Postselect X-On (|->)'),
    # La base Y se mide con S† y luego H (S†·H·Z·H·S = Y): el orden inverso
    # mediría la base X y el post-select no distinguiría |+i⟩ de |−i⟩.
    '|X⟩⟨X|':           (['sdg', 'h'], 0, 'Postselect Y-Off (|+i>)'),
    '|/⟩⟨/|':           (['sdg', 'h'], 1, 'Postselect Y-On (|-i>)'),
}


def _is_postselect(value):
    """Indica si una celda Quirk es una compuerta de post-selección.

    Parámetros:
        - value: celda de la columna (identificador de la compuerta).

    Retorna:
        - bool: True si ``value`` es un proyector de post-selección de Quirk.
    """
    return isinstance(value, str) and value in _POSTSELECT_GATES


def _postselect_lines(value, qubit_index, offset):
    """Traduce una compuerta de post-selección a sus líneas OpenQASM.

    Emite la rotación de base que define el proyector, la medición en el cbit
    del registro ``ps`` y un comentario con el resultado válido (los shots cuyo
    cbit no coincide deben descartarse). La post-selección no es un unitario y
    OpenQASM no la representa directamente.

    Parámetros:
        - value: identificador de la compuerta de post-selección.
        - qubit_index (int): índice lógico del qubit (sin offset).
        - offset (int): desplazamiento de los índices q[i].

    Retorna:
        - list[str]: líneas OpenQASM (sin terminador ';').
    """
    rotations, expected, label = _POSTSELECT_GATES[value]
    qi = qubit_index + offset
    lines = [f'{gate} q[{qi}];' for gate in rotations]
    lines.append(
        f'// {label}: post-selección (medición), conservar si ps[{qi}] == {expected}'
    )
    lines.append(f'ps[{qi}] = measure q[{qi}];')
    return lines


# Compuertas de control de Quirk (familia "Controls" del Toolbox). No son
# compuertas por sí mismas: condicionan la columna en la que aparecen.
#
# Cada entrada describe:
#   - 'setup'/'cleanup': rotaciones de base que Quirk aplica antes y después de
#     la operación de la columna. El mask de control se evalúa sobre el estado
#     ya girado por el setup, así que la traducción debe hacer lo mismo.
#   - 'negate': True si el control se satisface con el qubit en OFF
#     (anti-control). OpenQASM solo tiene controles positivos, así que se
#     implementa conjugando por X el qubit de control.
#
# OJO: para los controles X/Y el símbolo dibujado y el id serializado están
# intercambiados (src/gates/Controls.js: "The drawn +/- convention was
# changed, but the serialized id must stay the same"):
#   id '⊕' (dibujado '⊖') = X-Axis Anti-Control -> dispara con X eigen +1 (|+⟩)
#   id '⊖' (dibujado '⊕') = X-Axis Control      -> dispara con X eigen -1 (|−⟩)
#   id '⊗' (dibujado '(/)') = Y-Axis Anti-Control -> dispara con Y eigen +1 (|+i⟩)
#   id '(/)' (dibujado '⊗') = Y-Axis Control      -> dispara con Y eigen -1 (|−i⟩)
_CONTROL_GATES = {
    '•': {'setup': (), 'cleanup': (), 'negate': False},
    '◦': {'setup': (), 'cleanup': (), 'negate': True},
    '⊕': {'setup': ('h',), 'cleanup': ('h',), 'negate': True},
    '⊖': {'setup': ('h',), 'cleanup': ('h',), 'negate': False},
    '⊗': {'setup': ('rx(pi/2)',), 'cleanup': ('rx(-pi/2)',), 'negate': True},
    '(/)': {'setup': ('rx(pi/2)',), 'cleanup': ('rx(-pi/2)',), 'negate': False},
}


def _is_control(value):
    """Indica si una celda Quirk es una compuerta de control.

    Parámetros:
        - value: celda de la columna (identificador de la compuerta).

    Retorna:
        - bool: True si ``value`` es un control de Quirk ('•', '◦', '⊕', '⊖',
          '⊗' o '(/)').
    """
    return isinstance(value, str) and value in _CONTROL_GATES


def _control_setup_lines(control_cells, offset):
    """Rotaciones de base y negaciones previas a la operación de la columna.

    El setup lleva cada qubit de control a la base en la que Quirk evalúa la
    condición (X o Y); a continuación se conjugan por X los anti-control, de
    modo que la condición "el qubit está en OFF" se traduzca como un control
    positivo de OpenQASM.

    Parámetros:
        - control_cells (list): pares (índice, id) de los controles de la columna.
        - offset (int): desplazamiento de los índices q[i].

    Retorna:
        - list[str]: líneas OpenQASM (sin terminador ';').
    """
    lines = []
    for index, value in control_cells:
        for operation in _CONTROL_GATES[value]['setup']:
            lines.append(f'{operation} q[{index + offset}];')
    for index, value in control_cells:
        if _CONTROL_GATES[value]['negate']:
            lines.append(f'x q[{index + offset}];')
    return lines


def _control_cleanup_lines(control_cells, offset):
    """Deshace el marco de control tras la operación de la columna.

    Primero se deshace la conjugación por X de los anti-control y después se
    aplica el cleanup (rotación inversa del setup) de cada control.

    Parámetros:
        - control_cells (list): pares (índice, id) de los controles de la columna.
        - offset (int): desplazamiento de los índices q[i].

    Retorna:
        - list[str]: líneas OpenQASM (sin terminador ';').
    """
    lines = []
    for index, value in control_cells:
        if _CONTROL_GATES[value]['negate']:
            lines.append(f'x q[{index + offset}];')
    for index, value in control_cells:
        for operation in _CONTROL_GATES[value]['cleanup']:
            lines.append(f'{operation} q[{index + offset}];')
    return lines


# Expresiones OpenQASM de las compuertas simples de Quirk (una sola fila).
_BASIC_GATE_EXPRESSIONS = {
    'H': 'h', 'X': 'x', 'Y': 'y', 'Z': 'z',
    'X^½': 'rx(pi/2)', 'X^-½': 'rx(-pi/2)',
    'X^¼': 'rx(pi/4)', 'X^-¼': 'rx(-pi/4)',
    'Y^½': 'ry(pi/2)', 'Y^-½': 'ry(-pi/2)',
    'Y^¼': 'ry(pi/4)', 'Y^-¼': 'ry(-pi/4)',
    'Z^½': 'p(pi/2)', 'Z^-½': 'p(-pi/2)',
    'Z^¼': 'p(pi/4)', 'Z^-¼': 'p(-pi/4)',
}


def _quirk2_col_to_qasm(col, offset, gate_map, gate_names=None):
    """Traduce una columna Quirk a líneas OpenQASM 3.0 (wrapper con nombres).

    Resuelve los identificadores de custom gates (si no se pasan) y delega en
    ``_quirk2_col_to_qasm_core``.

    Parámetros:
        - col (list): columna del circuito (lista de celdas).
        - offset (int): desplazamiento de los índices q[i].
        - gate_map (dict): mapa id/name -> definición de custom gates.
        - gate_names (dict | None): identificadores QASM ya resueltos (opcional).

    Retorna:
        - list[str]: líneas OpenQASM sin terminador ';'.
    """
    if gate_names is None:
        gate_names = _resolve_gate_names(gate_map)
    return _quirk2_col_to_qasm_core(list(col), offset, gate_map, gate_names)


def _quirk2_col_to_qasm_core(col, offset, gate_map, gate_names=None):
    """Núcleo de la traducción de columna Quirk a OpenQASM 3.0.

    Maneja controles (eje Z con '•'/'◦' y ejes X/Y con '⊕'/'⊖'/'⊗'/(/)),
    Swap, QFT nativas, puertas con parámetros (rx/ry/rz/p, u1/u2/u3), matrices
    de fase, post-selecciones y referencias a custom gates.

    En Quirk el mask de control de una columna se evalúa sobre el estado tras
    aplicar el "setup" de cada control (rotación de base) y la columna se
    deshace con el "cleanup" correspondiente, de modo que aquí se emite el
    setup antes de la operación y el cleanup después.

    Parámetros:
        - col (list): columna del circuito (lista de celdas).
        - offset (int): desplazamiento de los índices q[i].
        - gate_map (dict): mapa id/name -> definición de custom gates.
        - gate_names (dict | None): identificadores QASM ya resueltos (opcional).

    Retorna:
        - list[str]: líneas OpenQASM sin terminador ';'.
    """
    lines = []
    if gate_names is None:
        gate_names = _resolve_gate_names(gate_map)
    control_cells = [
        (index, value) for index, value in enumerate(col) if _is_control(value)
    ]
    control_indices = [index for index, _ in control_cells]
    modifier = 'ctrl @ ' * len(control_indices)
    occupied = set(control_indices)
    body = []

    if 'Swap' in col:
        swap_indices = [i for i, value in enumerate(col) if value == 'Swap']
        if len(swap_indices) == 2:
            qubits = [f'q[{i + offset}]' for i in control_indices + swap_indices]
            body.append(f'{modifier}swap {", ".join(qubits)};')
        return (
            _control_setup_lines(control_cells, offset)
            + body
            + _control_cleanup_lines(control_cells, offset)
        )

    # Compuertas que ocupan varias filas: QFT nativas y custom gates.
    for index, value in enumerate(col):
        if index in occupied or value in (1, '1', None):
            continue
        qft_info = _qft_token(value)
        if qft_info is not None:
            span, inverse = qft_info
            qubits = [f'q[{i + offset}]' for i in control_indices]
            qubits.extend(f'q[{index + k + offset}]' for k in range(span))
            name = _qft_gate_name(span, inverse)
            body.append(f'{modifier}{name} {", ".join(qubits)};')
            occupied.update(range(index, index + span))
            continue
        if isinstance(value, str) and _is_gate_ref(value, gate_map):
            gate_id = value.split(':')[0]
            gate = gate_map[gate_id]
            operation = _gate_operation(gate, gate_id, gate_names)
            gate_height = _gate_height(gate) or 1
            qubits = [f'q[{i + offset}]' for i in control_indices]
            qubits.extend(f'q[{index + k + offset}]' for k in range(gate_height))
            body.append(f'{modifier}{operation} {", ".join(qubits)};')
            occupied.update(range(index, index + gate_height))

    # Compuertas de una sola fila.
    for index, value in enumerate(col):
        if index in occupied or value in (1, '1', None):
            continue
        if value == 'Measure':
            if control_cells:
                # Medir dentro de una columna controlada no es representable
                # en OpenQASM (no existe una medición condicionada).
                continue
            qi = index + offset
            body.append(f'c[{qi}] = measure q[{qi}];')
            continue
        scalar_phase = _scalar_gate_phase(value)
        if scalar_phase is not None:
            angle = _angle_literal(scalar_phase)
            if control_cells:
                # Escalar controlada de Quirk: el factor e^{i·phi}·I aparece solo
                # cuando TODOS los controles están en ON. Sobre esos qubits de
                # control la fase es una fase relativa condicionada:
                #   1 control  -> p(phi) sobre el control;
                #   k controles -> ctrl @ p(phi) sobre el primer control.
                control_wires = [f'q[{i + offset}]' for i in control_indices]
                if len(control_wires) == 1:
                    body.append(f'p({angle}) {control_wires[0]};')
                else:
                    modifier_inner = 'ctrl @ ' * (len(control_wires) - 1)
                    body.append(
                        f'{modifier_inner}p({angle}) '
                        f'{", ".join(control_wires)};'
                    )
            else:
                # Escalar sin control: fase global (gphase) de OpenQASM 3.0.
                body.append(f'gphase({angle});')
            continue
        if _is_postselect(value):
            if control_cells:
                # Una post-selección controlada no tiene traducción directa:
                # OpenQASM no permite medir dentro de una compuerta controlada.
                _report_unsupported_gate(value)
                continue
            body.extend(_postselect_lines(value, index, offset))
            continue
        expression = _BASIC_GATE_EXPRESSIONS.get(value)
        if expression is None:
            if value in _SCALAR_NOOP_GATES:
                body.append(
                    "// Spacer Quirk ('\u2026'): compuerta identidad (no-op), "
                    "no altera el estado."
                )
            elif value in _SCALAR_NULL_GATES:
                body.append(
                    "// ZeroGate Quirk ('0'): matriz nula idempotente (0\u00b70=0), "
                    "no unitaria; se omite del circuito."
                )
                _report_unsupported_gate(value)
            else:
                _report_unsupported_gate(value)
            continue
        qi = index + offset
        if control_cells:
            qubits = [f'q[{i + offset}]' for i in control_indices]
            qubits.append(f'q[{qi}]')
            body.append(f'{modifier}{expression} {", ".join(qubits)};')
        else:
            body.append(f'{expression} q[{qi}];')

    return (
        _control_setup_lines(control_cells, offset)
        + body
        + _control_cleanup_lines(control_cells, offset)
    )

# Borrar esta función, se reemplaza por _col_to_qasm_with_gates() o _quirk2_col_to_qasm()
def _quirk_col_to_qasm(col, offset):
    """Traduce una columna Quirk a OpenQASM (ruta legacy, sin custom gates).

    Soporta Swap, controles '•' con puertas fijas y puertas sin control.

    Parámetros:
        - col (list): columna del circuito (lista de celdas).
        - offset (int): desplazamiento de los índices q[i].

    Retorna:
        - list[str]: líneas OpenQASM sin terminador ';'.
    """
    lines = []

    if 'Swap' in col:
        swap_indices = [k for k, g in enumerate(col) if g == 'Swap']
        if len(swap_indices) == 2:
            lines.append(f'swap q[{swap_indices[0] + offset}], q[{swap_indices[1] + offset}];')
        return lines

    if '•' in col:
        control_indices = [k for k, g in enumerate(col) if g == '•']
        target_gate = None
        target_index = None
        # acá hay que construir un target con lo que no sea el control
        for g in ('X', 'Z', 'Y', 'X^½', 'X^-½', 'X^¼', 'X^-¼', 'Y^½', 'Y^-½', 'Y^¼', 'Y^-¼', 'Z^½', 'Z^-½', 'Z^¼', 'Z^-¼'):
            if g in col:
                target_gate = g
                target_index = col.index(g)
                break

        if target_gate is None:
            return lines

        n_controls = len(control_indices)

        ctrl_str = ', '.join(f'q[{i + offset}]' for i in control_indices)
        tgt_str = f'q[{target_index + offset}]'

        ctrl_rz = {
            'Z^½': 'pi/2', 'Z^-½': '-pi/2', 'Z^¼': 'pi/4', 'Z^-¼': '-pi/4',
        }
        ctrl_rx = {
            'X^½': 'pi/2', 'X^-½': '-pi/2', 'X^¼': 'pi/4', 'X^-¼': '-pi/4',
        }
        ctrl_ry = {
            'Y^½': 'pi/2', 'Y^-½': '-pi/2', 'Y^¼': 'pi/4', 'Y^-¼': '-pi/4',
        }

        if target_gate == 'X':
            if n_controls == 1:
                lines.append(f'cx {ctrl_str}, {tgt_str};')
            elif n_controls == 2:
                lines.append(f'ccx {ctrl_str}, {tgt_str};')
            else:
                lines.append(f'mcx {ctrl_str}, {tgt_str};')
        elif target_gate == 'Z':
            if n_controls <= 2:
                lines.append(f'cz {ctrl_str}, {tgt_str};')
            else:
                lines.append(f'mcz {ctrl_str}, {tgt_str};')
        elif target_gate == 'Y':
            if n_controls <= 2:
                lines.append(f'cy {ctrl_str}, {tgt_str};')
            else:
                lines.append(f'mcy {ctrl_str}, {tgt_str};')
        elif target_gate in ctrl_rz:
            lines.append(f'cp({ctrl_rz[target_gate]}) {ctrl_str}, {tgt_str};')
        elif target_gate in ctrl_rx:
            lines.append(f'crx({ctrl_rx[target_gate]}) {ctrl_str}, {tgt_str};')
        elif target_gate in ctrl_ry:
            lines.append(f'cry({ctrl_ry[target_gate]}) {ctrl_str}, {tgt_str};')

        return lines

    for i, gate in enumerate(col):
        if gate == 1 or gate == '1':
            continue
        qi = i + offset
        m = {
            'Measure': f'c[{qi}] = measure q[{qi}];',
            'H': f'h q[{qi}];',
            'X': f'x q[{qi}];',
            'Y': f'y q[{qi}];',
            'Z': f'z q[{qi}];',
            'X^½': f'rx(pi/2) q[{qi}];',
            'X^-½': f'rx(-pi/2) q[{qi}];',
            'X^¼': f'rx(pi/4) q[{qi}];',
            'X^-¼': f'rx(-pi/4) q[{qi}];',
            'Y^½': f'ry(pi/2) q[{qi}];',
            'Y^-½': f'ry(-pi/2) q[{qi}];',
            'Y^¼': f'ry(pi/4) q[{qi}];',
            'Y^-¼': f'ry(-pi/4) q[{qi}];',
            'Z^½': f's q[{qi}];',
            'Z^-½': f'sdg q[{qi}];',
            'Z^¼': f't q[{qi}];',
            'Z^-¼': f'tdg q[{qi}];',
        }
        if gate in m:
            lines.append(m[gate])

    return lines

# FLATEA los custom gates con 'circuit' que se expanden recursivamente. Esto se hace en _col_qasm_with_gates() y se llama desde quirk_to_qasm().
def _col_to_qasm_with_gates(col, offset, gate_map, depth=0):
    """Traduce una columna soportando custom gates anidados (profundidad ≤ 10).

    Parámetros:
        - col (list): columna del circuito.
        - offset (int): desplazamiento de los índices q[i].
        - gate_map (dict): mapa id/name -> definición de custom gates.
        - depth (int): profundidad actual de recursión (interno).

    Retorna:
        - list[str]: líneas OpenQASM sin terminador ';'.
    """
    if depth > 10:
        return []
    has_gate = any(_is_gate_ref(v, gate_map) for v in col if isinstance(v, str))
    if not has_gate:
        return _quirk2_col_to_qasm(col, offset, gate_map)

    lines = []
    gate_names = _resolve_gate_names(gate_map)
    occupied = set()
    for idx, entry in enumerate(col):
        if not isinstance(entry, str):
            continue
        base = entry.split(':')[0]
        if base not in gate_map:
            continue
        gate = gate_map[base]
        gate_cols = gate.get('circuit', {}).get('cols', [])
        if not gate_cols:
            # Custom gate con 'matrix': se expande como una sola operación.
            operation = _gate_operation(gate, base, gate_names)
            gate_height = _gate_height(gate) or 1
            qubits = ', '.join(
                f'q[{i + offset}]' for i in range(idx, idx + gate_height)
            )
            lines.append(f'{operation} {qubits};')
            occupied.update(range(idx, idx + gate_height))
            continue
        if ':' in entry:
            try:
                rel = int(entry.split(':')[1])
            except ValueError:
                continue
            if 0 <= rel < len(gate_cols):
                gcol = gate_cols[rel]
                padded = [1] * idx + list(gcol)
                lines.extend(_col_to_qasm_with_gates(padded, offset, gate_map, depth + 1))
                for k in range(len(gcol)):
                    occupied.add(idx + k)
            continue
        for gcol in gate_cols:
            padded = [1] * idx + list(gcol)
            lines.extend(_col_to_qasm_with_gates(padded, offset, gate_map, depth + 1))
            for k in range(len(gcol)):
                occupied.add(idx + k)

    max_len = max(len(col), max(occupied) + 1 if occupied else 0)
    leftover_col = [1] * max_len
    has_leftover = False
    for i, v in enumerate(col):
        if isinstance(v, str) and v.split(':')[0] in gate_map:
            continue
        if i in occupied:
            continue
        if v == 1 or v == '1':
            continue
        if i < len(leftover_col):
            leftover_col[i] = v
            has_leftover = True
    if has_leftover:
        if any(isinstance(x, str) and _is_gate_ref(x, gate_map) for x in leftover_col):
            lines.extend(_col_to_qasm_with_gates(leftover_col, offset, gate_map, depth + 1))
        else:
            lines.extend(_quirk2_col_to_qasm(leftover_col, offset, gate_map))
    return lines

def primeras_letras(n):
    """Genera la lista de operandos 'a, b, c, ...' para una QFT de n qubits.

    Parámetros:
        - n (int): cantidad de qubits.

    Retorna:
        - str: los nombres de argumento separados por coma.
    """
    names = []
    i = 0
    base_chars = string.ascii_lowercase
    j = 0
    while len(names) < n and j < 200:
        c = base_chars[i % len(base_chars)]
        if i >= len(base_chars):
            c = base_chars[i % len(base_chars)] + str(i // len(base_chars))
        # avoid common gate names as params
        if c not in {'h', 's', 't', 'x', 'y', 'z', 'p', 'u', 'rx', 'ry', 'rz', 'cx', 'cp', 'swap', 'id'}:
            names.append(c)
        else:
            names.append(c + '_')
        i += 1
        j += 1
    return ','.join(names[:n])

def replace_params(lines):
    """Reemplaza los índices q[i] de un cuerpo de gate por letras minúsculas.

    Parámetros:
        - lines (list[str]): líneas con operandos ``q[i]`` (p. ej. 'h q[0];').

    Retorna:
        - list[str]: las mismas líneas con ``q[i]`` → 'a', 'b', … (in place).
    """
    if not lines:
        return []
    for index, line in enumerate(lines):
        if 'q[' in line:
            lines[index] = re.sub(r'q\[(\d+)\]', lambda m: string.ascii_lowercase[int(m.group(1))], line)
    return lines

def append_custom_gates(custom_gates_info, gate_map, gate_names=None):
    """Declaraciones `gate` (submódulos OpenQASM) de los custom gates.

    - Gates con 'circuit.cols': el cuerpo sale de sus columnas.
    - Gates con 'matrix': el cuerpo sale de la operación equivalente
      (name estándar o la matriz de fase misma).

    El identificador usado aquí es siempre el mismo que el que usan los
    llamados (``_gate_operation``), para que declaración y llamada coincidan.
    Las declaraciones se ordenan según sus referencias (se declara antes de usar).

    Parámetros:
        - custom_gates_info (list[dict]): custom gates usados en el circuito.
        - gate_map (dict): mapa id/name -> definición de custom gates.
        - gate_names (dict | None): identificadores ya resueltos (opcional).

    Retorna:
        - str: bloque de declaraciones (cadena vacía si no hay custom gates).
    """
    if gate_names is None:
        gate_names = _resolve_gate_names(gate_map)

    declarations = []
    for custom_gate_info in custom_gates_info:
        gate_id = str(custom_gate_info.get('id') or '').split(':')[0]
        name = gate_names.get(gate_id) or _sanitize_gate_name(
            custom_gate_info.get('name') or gate_id
        )
        cols = custom_gate_info.get("circuit_cols")
        if cols:
            n_qubits = (
                custom_gate_info.get('n_qubits')
                or _gate_height(custom_gate_info)
                or 1
            )
            body = []
            for col in cols:
                body.extend(replace_params(_quirk2_col_to_qasm(col, 0, gate_map, gate_names)))
        elif custom_gate_info.get('matrix') is not None:
            # Gates con 'matrix' (sin circuit): cuerpo = operación equivalente.
            operation = _resolve_matrix_operation(custom_gate_info, gate_id)
            n_qubits = (
                custom_gate_info.get('n_qubits')
                or _gate_height(custom_gate_info)
                or 1
            )
            letters = primeras_letras(n_qubits).split(',')
            arity = min(_operation_arity(operation, n_qubits), len(letters))
            body = [f'{operation} {", ".join(letters[:arity])};']
        else:
            # Sin 'circuit' ni 'matrix': no hay definición posible; solo se
            # falla si además se referencia en el circuito (_gate_operation).
            continue
        declarations.append({
            'id': gate_id,
            'name': name,
            'n_qubits': n_qubits,
            'body': body,
            'cols': cols or [],
        })

    # Ordena las declaraciones: primero las que no referencian a otras
    # pendientes (OpenQASM exige declarar antes de usar).
    declared_ids = {decl['id'] for decl in declarations}

    def refs_of(cols):
        found = set()
        for col in cols:
            for value in col:
                if isinstance(value, str) and _is_gate_ref(value, gate_map):
                    ref_id = value.split(':')[0]
                    if ref_id in declared_ids:
                        found.add(ref_id)
        return found

    ordered = []
    emitted = set()
    remaining = declarations
    while remaining:
        next_round = []
        for decl in remaining:
            pending = refs_of(decl['cols']) - emitted - {decl['id']}
            if pending:
                next_round.append(decl)
            else:
                ordered.append(decl)
                emitted.add(decl['id'])
        if len(next_round) == len(remaining):
            ordered.extend(next_round)  # referencia cíclica: orden original
            break
        remaining = next_round

    lines = []
    for decl in ordered:
        lines.append(f"gate {decl['name']} {primeras_letras(decl['n_qubits'])} {{")
        lines.extend(decl['body'])
        lines.append('}')
    return '\n'.join(lines)

def quirk_to_qasm(url, offset=0, qasm_version='3.0'):
    """Traduce una URL de Quirk a código OpenQASM completo.

    Genera las declaraciones de custom gates y QFT nativas, las operaciones por
    columna y, para la versión 2.0, transpila vía Qiskit a u1/u2/u3/cx.

    Parámetros:
        - url (str): URL de Quirk con ``circuit=<JSON>``.
        - offset (int): desplazamiento de todos los índices q[i].
        - qasm_version (str): '2.0' o '3.0' (por defecto '3.0').

    Retorna:
        - str: el código OpenQASM completo (cabecera incluida).
    """
    if qasm_version not in {'2.0', '3.0'}:
        raise ValueError("qasm_version debe ser '2.0' o '3.0'")
    info = quirk_circuit_info(url)
    lines = ['OPENQASM 3.0;', 'include "stdgates.inc";', '']
    custom_gates_info = info.get('custom_gates_info', [])

    circuito = parse_quirk_url(url)
    gate_map = _build_gate_map(circuito)
    gate_names = _resolve_gate_names(gate_map)
    cols = circuito.get('cols', [])
    qft_tokens = {
        info
        for col in cols
        for value in col
        for info in [_qft_token(value)]
        if info is not None
    }
    if qft_tokens:
        lines.extend(_qft_declarations(qft_tokens))
    if len(custom_gates_info) > 0:
        declarations = append_custom_gates(custom_gates_info, gate_map, gate_names)
        if declarations:
            lines.append(declarations)
    if not cols:
        n = offset
    else:
        n = max(_column_extent(c, gate_map) for c in cols) + offset
        r = max(
            (
                gate.get("n_qubits")
                for gate in custom_gates_info
                if gate.get("n_qubits") is not None
            ),
            default=0,
        ) + offset
        if r > n: n = r
        
    lines.extend([f'qreg q[{n}];', f'creg c[{n}];'])
    has_postselect = any(
        _is_postselect(value) for col in cols for value in col
    )
    if has_postselect:
        lines.append(f'creg ps[{n}];  // post-selección: descartar shots con ps != esperado')
    for col in cols:
        # algo=_col_to_qasm_with_gates(col, offset, gate_map)
        algo = _quirk2_col_to_qasm(col, offset, gate_map, gate_names)
        lines.extend(algo)
    qasm3_source = '\n'.join(lines)
    if qasm_version == '2.0':
        return qasm3_to_qasm2(qasm3_source)
    return qasm3_source


def qasm3_to_qasm2(qasm3_source):
    """Transpila OpenQASM 3.0 del proyecto a OpenQASM 2.0 vía Qiskit.

    OpenQASM 2.0 no tiene ``gphase``: las fases globales (compuertas escalares
    de Quirk como NeGate, i, -i, √i, √-i) no son representables y se descartan.
    Si el circuito las contiene, se emite un aviso por stderr ya que la
    equivalencia funcional del circuito baja a salvo de fase global.

    Parámetros:
        - qasm3_source (str): código OpenQASM 3.0.

    Retorna:
        - str: el código equivalente en OpenQASM 2.0 (u1/u2/u3/cx).
    """
    from qiskit import qasm2, qasm3, transpile

    circuit = qasm3.loads(qasm3_source)
    if abs(complex(circuit.global_phase)) > 1e-12 and re.search(r'\bgphase\s*\(', qasm3_source):
        _report_global_phase_dropped(circuit.global_phase)
    lowered_circuit = transpile(
        circuit,
        basis_gates=['u1', 'u2', 'u3', 'cx'],
        optimization_level=0,
    )
    source = qasm2.dumps(lowered_circuit)
    lines = source.split('\n')
    if len(lines) >= 2 and lines[1].startswith('include') and lines[2] != '':
        lines.insert(2, '')
    return '\n'.join(lines)


def _report_global_phase_dropped(phase):
    """Avisa por stderr que una fase global se pierde al bajar a OpenQASM 2.0.

    Se emite una sola vez, ya que OpenQASM 2.0 no soporta ``gphase``.

    Parámetros:
        - phase: fase global del circuito (radianes).
    """
    if 'gphase' in _REPORTED_UNSUPPORTED_GATES:
        return
    _REPORTED_UNSUPPORTED_GATES.add('gphase')
    print(
        f'[advertencia] El circuito incluye una fase global (gphase={phase!r}) '
        'que OpenQASM 2.0 no representa; se descarta en el código 2.0 '
        '(equivale al original salvo fase global).',
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Proveedores soportados (Qiskit / AWS Braket / PennyLane)
# ---------------------------------------------------------------------------
SUPPORTED_PROVIDERS = ('qiskit', 'braket', 'pennylane')

# Sinónimos admitidos en .env, CLI y cargar_circuito_qasm().
PROVIDER_ALIASES = {
    'qiskit': 'qiskit', 'ibm': 'qiskit', 'ibm_qiskit': 'qiskit',
    'braket': 'braket', 'aws': 'braket', 'aws_braket': 'braket',
    'pennylane': 'pennylane', 'xanadu': 'pennylane', 'xanadu_pennylane': 'pennylane',
}

# Subcarpeta de migrated_circuits/ por proveedor (coincide con qtrans/core.py y el README).
PROVIDER_DIRECTORY = {
    'qiskit': 'ibm_qiskit',
    'braket': 'aws_braket',
    'pennylane': 'xanadu_pennylane',
}


def normalize_provider(provider):
    """Normaliza un alias de proveedor a su nombre canónico.

    Parámetros:
        - provider (str): 'ibm', 'aws', 'xanadu', 'qiskit', 'braket' o 'pennylane'.

    Retorna:
        - str: 'qiskit', 'braket' o 'pennylane'.
    """
    key = str(provider).strip().casefold()
    normalized = PROVIDER_ALIASES.get(key)
    if normalized is None:
        raise ValueError(
            f'Provider no soportado: {provider!r}; opciones: '
            f'{", ".join(SUPPORTED_PROVIDERS)} (alias: ibm, aws, xanadu)'
        )
    return normalized


def parse_providers(value):
    """Convierte una lista separada por comas de proveedores a nombres canónicos.

    Parámetros:
        - value (str | None): p. ej. 'IBM, AWS, XANADU'.

    Retorna:
        - tuple[str]: nombres canónicos únicos (sin vacíos).
    """
    items = [value] if isinstance(value, str) else value
    providers = []
    for item in items:
        for token in str(item).split(','):
            if not token.strip():
                continue
            normalized = normalize_provider(token)
            if normalized not in providers:
                providers.append(normalized)
    if not providers:
        raise ValueError(
            f'providers debe contener al menos un provider; opciones: '
            f'{", ".join(SUPPORTED_PROVIDERS)}'
        )
    return tuple(providers)


def providers_from_env(getenv=None, default='qiskit'):
    """Lee los proveedores configurados desde las variables de entorno.

    Prefiere ``QTRANS_PROVIDERS``; si falta, usa la clave legada
    ``QTRANS_TARGET_PROVIDERS``; si ninguna está definida, devuelve ``default``.

    Parámetros:
        - getenv (callable | None): función tipo os.getenv (para tests; opcional).
        - default (str): valor si ninguna variable está definida.

    Retorna:
        - tuple[str]: nombres canónicos de proveedores.
    """
    if getenv is None:
        getenv = os.getenv
    configured = getenv('QTRANS_PROVIDERS') or getenv('QTRANS_TARGET_PROVIDERS') or default
    return parse_providers(configured)


def provider_python_source(qasm_source, provider, qasm_version='3.0', shots=1000,
                           preserve_custom_gates=False):
    """Devuelve el código Python ejecutable para el proveedor destino.

    Parsea el OpenQASM con el parser nativo de Qiskit y delega en el generador
    del proveedor (Qiskit, Braket o PennyLane).

    Parámetros:
        - qasm_source (str): código OpenQASM (2.0 o 3.0).
        - provider (str): nombre o alias del proveedor.
        - qasm_version (str): '2.0' o '3.0'.
        - shots (int): disparos (solo PennyLane).
        - preserve_custom_gates (bool): conserva custom gates como funciones.

    Retorna:
        - str: el código Python del script migrado.
    """
    # Import a nivel de función: los módulos de proveedor importan de este archivo
    # (_angle_to_expr y helpers), así que un import a nivel de módulo sería cíclico.
    from .braket_utils import _braket_python_source
    from .pennylane_utils import _pennylane_python_source
    from .qiskit_utils import _load_qiskit_native, _qiskit_python_source

    provider = normalize_provider(provider)
    if qasm_version not in {'2.0', '3.0'}:
        raise ValueError("qasm_version debe ser '2.0' o '3.0'")

    circuit = _load_qiskit_native(qasm_source, qasm_version, fallback=False)
    if provider == 'qiskit':
        return _qiskit_python_source(circuit, preserve_custom_gates=preserve_custom_gates)
    if provider == 'braket':
        return _braket_python_source(circuit, preserve_custom_gates=preserve_custom_gates)
    return _pennylane_python_source(
        circuit, shots=shots, preserve_custom_gates=preserve_custom_gates
    )


def _angle_to_expr(val):
    """Convierte un ángulo a expresión Python usando math.pi cuando es múltiplo.

    Parámetros:
        - val (float): ángulo en radianes.

    Retorna:
        - str: expresión Python (p. ej. 'math.pi/2', '3*math.pi/4') o repr(val).
    """
    if val == 0:
        return '0'
    sign = -1 if val < 0 else 1
    v = abs(val)
    for k in range(0, 25):
        denom = 2 ** k
        target = math.pi / denom
        if abs(v - target) < 1e-8:
            if k == 0:
                expr = 'math.pi'
            else:
                expr = f'math.pi/{denom}'
            return f'-{expr}' if sign < 0 else expr
    for n in range(1, 40):
        for k in range(0, 20):
            denom = 2 ** k
            target = math.pi * n / denom
            if abs(v - target) < 1e-8:
                if k == 0:
                    expr = 'math.pi' if n == 1 else f'{n}*math.pi'
                else:
                    expr = f'{n}*math.pi/{denom}'
                return f'-{expr}' if sign < 0 else expr
    return repr(val)


def quirk_circuit_info(url):
    """Información estructurada de un circuito Quirk (para testing/inspección).

    Parámetros:
        - url (str): URL de Quirk con ``circuit=<JSON>``.

    Retorna:
        - dict: claves n_qubits (efectivo), n_cols, gates, custom_gates,
          custom_gate_ids, custom_gate_names, n_custom_gates,
          custom_gates_gates y custom_gates_info.
    """
    circuito = parse_quirk_url(url)
    cols = circuito.get('cols', [])
    gates_defs = circuito.get('gates', [])
    # n_qubits efectivo: max de cols principales y altura de custom gates usados
    if cols:
        gate_map_eff = _build_gate_map(circuito)
        n_qubits = max(_column_extent(c, gate_map_eff) for c in cols) if cols else 0
        for col in cols:
            for idx, entry in enumerate(col):
                if not isinstance(entry, str):
                    continue
                base = entry.split(':')[0]
                if base not in gate_map_eff:
                    continue
                gate = gate_map_eff[base]
                if ':' in entry:
                    try:
                        rel = int(entry.split(':')[1])
                        gcol = gate.get('circuit', {}).get('cols', [])[rel]
                        needed = idx + len(gcol)
                        if needed > n_qubits:
                            n_qubits = needed
                    except Exception:
                        pass
                else:
                    h = _gate_height(gate)
                    needed = idx + h
                    if needed > n_qubits:
                        n_qubits = needed
        n_cols = len(cols)
    else:
        n_qubits = 0
        n_cols = 0

    gates = set()
    for col in cols:
        for g in col:
            if g not in (1, '1', None):
                gates.add(str(g))

    # Gates internos de los custom gates
    custom_gates_gates = set()
    for g in gates_defs:
        if 'circuit' in g:
            for c in g['circuit'].get('cols', []):
                for e in c:
                    if e not in (1, '1', None):
                        custom_gates_gates.add(str(e))

    custom_gate_ids = [g['id'] for g in gates_defs if isinstance(g.get('id'), str)]
    custom_gate_names = [g['name'] for g in gates_defs if isinstance(g.get('name'), str)]

    custom_gates_info = []
    for g in gates_defs:
        info = {
            'id': g.get('id'),
            'name': g.get('name'),
            'matrix': g.get('matrix'),
            'circuit_cols': g.get('circuit', {}).get('cols') if 'circuit' in g else None,
        }
        if 'circuit' in g:
            info['n_qubits'] = _gate_height(g)
            info['n_cols'] = len(g.get('circuit', {}).get('cols', []))
        else:
            # Gates con 'matrix': la altura sale de la dimensión de la matriz
            info['n_qubits'] = _gate_height(g) if g.get('matrix') is not None else None
            info['n_cols'] = None
        custom_gates_info.append(info)

    return {
        'n_qubits': n_qubits,
        'n_cols': n_cols,
        'gates': sorted(gates),
        'custom_gates': gates_defs,
        'custom_gate_ids': custom_gate_ids,
        'custom_gate_names': custom_gate_names,
        'n_custom_gates': len(gates_defs),
        'custom_gates_gates': sorted(custom_gates_gates),
        'custom_gates_info': custom_gates_info,
    }


def capture_quirk_circuit(url, output_path, timeout=15):
    """Captura la vista completa de un circuito Quirk en un archivo PNG.

    Abre la URL en Chromium headless (Selenium) y toma una captura del canvas.

    Parámetros:
        - url (str): URL de Quirk a capturar.
        - output_path (str | Path): ruta del PNG de salida.
        - timeout (int): límite en segundos para la carga de la página.

    Retorna:
        - bool: True si la captura se guardó; False si hubo error.
    """
    import base64
    from pathlib import Path

    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as exc:
        raise RuntimeError('Instala Selenium con `pip install selenium` para capturar circuitos Quirk') from exc

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Quirk solo reconoce la QFT inversa como 'QFT†n'; sin esta canonización,
    # las variantes 'QFTn†'/'QFT^†n' se capturan como compuerta "parse error".
    url = canonicalize_quirk_url(url)
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        wait = WebDriverWait(driver, timeout)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'canvas')))
        wait.until(lambda browser: browser.execute_script('return document.readyState') == 'complete')

        page_size = driver.execute_script("""
            const root = document.documentElement;
            const body = document.body;
            return {
                width: Math.max(root.scrollWidth, body.scrollWidth, root.clientWidth),
                height: Math.max(root.scrollHeight, body.scrollHeight, root.clientHeight)
            };
        """)
        screenshot = driver.execute_cdp_cmd('Page.captureScreenshot', {
            'format': 'png',
            'fromSurface': True,
            'captureBeyondViewport': True,
            'clip': {
                'x': 0,
                'y': 0,
                'width': page_size['width'],
                'height': page_size['height'],
                'scale': 1,
            },
        })
        output_path.write_bytes(base64.b64decode(screenshot['data']))
        return True
    except Exception as exc:
        print(f'Error capturando {url}: {exc}')
        return False
    finally:
        if driver is not None:
            driver.quit()


def detect_qasm_version(qasm_str, qasm_version=None):
    """Detecta la versión de OpenQASM (2.0 o 3.0) de un código fuente.

    Si qasm_version es '2.0' o '3.0' se devuelve tal cual; si no, se lee la
    cabecera 'OPENQASM x.y;' (default '3.0' si no hay cabecera).

    Parámetros:
        - qasm_str (str): código OpenQASM.
        - qasm_version (str | None): versión forzada (opcional).

    Retorna:
        - str: '2.0' o '3.0'.
    """
    if qasm_version in ('2.0', '3.0'):
        return qasm_version
    for line in (qasm_str or '').splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r'OPENQASM\s+([0-9]+(?:\.[0-9]+)?)', stripped, re.I)
        return match.group(1) if match else '3.0'
    return '3.0'


def load_qasm_circuit(qasm_str, qasm_version=None):
    """Carga un circuito Qiskit (``QuantumCircuit``) desde código OpenQASM 2.0 o 3.0.

    Punto único de carga de OpenQASM hacia Qiskit, compartido por la generación de
    imágenes, la celda de visualización del cuaderno y el pipeline CLI. La versión
    se determina con ``detect_qasm_version`` (cabecera ``OPENQASM x.y;`` salvo que
    se fuerce ``qasm_version``); si el parser 3.0 falla se reintenta con el parser
    2.0 como respaldo.

    Parámetros:
        - qasm_str (str): código OpenQASM (2.0 o 3.0).
        - qasm_version (str | None): '2.0' | '3.0' fuerza la versión; si es None se
          detecta desde la cabecera del código.

    Retorna:
        - qiskit.QuantumCircuit: circuito cargado.

    Lanza:
        - ValueError: si ``qasm_str`` está vacío.
    """
    from qiskit import QuantumCircuit, qasm2, qasm3

    text = (qasm_str or '').strip()
    if not text:
        raise ValueError('El contenido OpenQASM está vacío')
    version = detect_qasm_version(text, qasm_version)
    if version == '2.0':
        return qasm2.loads(text)
    try:
        return qasm3.loads(text)
    except Exception:
        return QuantumCircuit.from_qasm_str(text)


def render_qasm_image(qasm_code, qasm_version=None, style='bw', output_path=None):
    """Dibuja un circuito OpenQASM con Qiskit (matplotlib) como PNG.

    Punto único de dibujo de circuitos OpenQASM, compartido por las imágenes en
    base64 de la API de librería y por la generación de archivos del pipeline CLI
    y del cuaderno.

    Parámetros:
        - qasm_code (str): código OpenQASM (2.0 o 3.0).
        - qasm_version (str | None): versión forzada del parser (None = autodetectar).
        - style (str): estilo de dibujo de Qiskit ('bw' para QASM, 'iqp' para el
          estilo de IBM Quantum Composer).
        - output_path (str | Path | None): si se indica, guarda el PNG en esa ruta
          y devuelve un ``Path``; si es None, devuelve los bytes PNG.

    Retorna:
        - bytes | pathlib.Path: bytes PNG si ``output_path`` es None; el ``Path``
          del archivo guardado en caso contrario.
    """
    import io
    from pathlib import Path

    import matplotlib
    matplotlib.use('Agg', force=True)
    import matplotlib.pyplot as plt

    circuit = load_qasm_circuit(qasm_code, qasm_version)
    figure = None
    try:
        figure = circuit.draw(output='mpl', style=style)
        if output_path is not None:
            output_path = Path(output_path)
            figure.savefig(str(output_path), format='png', bbox_inches='tight')
            return output_path
        buffer = io.BytesIO()
        figure.savefig(buffer, format='png', bbox_inches='tight')
        return buffer.getvalue()
    finally:
        if figure is not None:
            plt.close(figure)


def _cargar_circuito_desde_codigo(qasm_str, provider, qasm_version, shots, preserve_custom_gates):
    """Materializa el circuito nativo del proveedor ejecutando su script migrado.

    Parámetros:
        - qasm_str (str): código OpenQASM.
        - provider (str): nombre canónico del proveedor.
        - qasm_version (str): '2.0' o '3.0'.
        - shots (int): disparos (solo PennyLane).
        - preserve_custom_gates (bool): conserva custom gates como funciones.

    Retorna:
        - object: el objeto 'circuit' del namespace (QuantumCircuit/Circuit/QNode).
    """
    source = provider_python_source(
        qasm_str,
        provider,
        qasm_version=qasm_version,
        shots=shots,
        preserve_custom_gates=preserve_custom_gates,
    )
    namespace = {}
    exec(compile(source, f'<cargar_circuito_qasm:{provider}>', 'exec'), namespace)
    return namespace['circuit']


def cargar_circuito_qasm(qasm_str: str, provider: str, qasm_version: str = None,
                         shots: int = 1000, preserve_custom_gates: bool = False,
                         native: bool = True):
    """Carga un circuito cuántico desde una cadena OpenQASM según el proveedor especificado.

    Parámetros:
        - qasm_str (str): código OpenQASM (2.0 o 3.0; si ``qasm_version`` no se indica,
          la versión se detecta de la cabecera ``OPENQASM x.y;``).
        - provider (str): 'qiskit'/'ibm', 'braket'/'aws' o 'pennylane'/'xanadu'
          (ver ``PROVIDER_ALIASES``).
        - qasm_version (str): '2.0' | '3.0'; fuerza la versión a usar en el parseo.
        - shots (int): disparos para el circuito PennyLane del respaldo por migración.
        - preserve_custom_gates (bool): conserva las puertas custom como funciones locales
          en el respaldo por migración.
        - native (bool): ``True`` usa el parser nativo del proveedor cuando existe
          (Qiskit siempre, Braket si reconoce el código); ``False`` materializa siempre
          el circuito vía ``provider_python_source``+``exec``.

    Funcionalidad:
        Parsea con la librería del proveedor. Qiskit y Braket usan su parser nativo;
        el de Braket se complementa con un respaldo porque no cubre todo el OpenQASM
        que genera este proyecto (p. ej. la puerta ``p`` o los ``include`` estándar).
        PennyLane se materializa siempre con su script migrado, porque su parser nativo
        tampoco sirve aquí: ``qml.from_qasm`` exige el plugin ``pennylane-qiskit`` y
        ``qml.from_qasm3`` no acepta los registros ``qreg`` indexados.

    Retorna:
        - qiskit -> ``qiskit.QuantumCircuit``; braket -> ``braket.circuits.Circuit``;
        - pennylane -> ``pennylane.QNode`` (circuito ejecutable).
    """
    from .braket_utils import _load_braket_native
    from .qiskit_utils import _load_qiskit_native

    canonical = normalize_provider(provider)
    if qasm_str is None or not str(qasm_str).strip():
        raise ValueError('qasm_str está vacío')
    version = detect_qasm_version(qasm_str, qasm_version)
    if version not in ('2.0', '3.0'):
        raise ValueError(f"Versión de OpenQASM no soportada: {version!r} (use '2.0' o '3.0')")

    if canonical == 'qiskit' and native:
        # Qiskit parsea todo lo que genera el proyecto; no necesita respaldo.
        return _load_qiskit_native(qasm_str, version)

    if canonical == 'pennylane':
        return _cargar_circuito_desde_codigo(
            qasm_str, canonical, version, shots, preserve_custom_gates
        )

    native_error = None
    if native:
        try:
            return _load_braket_native(qasm_str)
        except Exception as exc:
            native_error = exc

    try:
        return _cargar_circuito_desde_codigo(
            qasm_str, canonical, version, shots, preserve_custom_gates
        )
    except Exception as source_error:
        attempted = (
            f'parser nativo ({type(native_error).__name__}: {native_error}); '
            if native_error is not None
            else ''
        )
        raise ValueError(
            f'No se pudo cargar el circuito para {canonical!r}: {attempted}'
            f'migración ({type(source_error).__name__}: {source_error})'
        ) from source_error

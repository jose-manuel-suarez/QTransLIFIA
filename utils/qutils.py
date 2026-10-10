import ast
import cmath
import itertools
import math
import re
import string
from fractions import Fraction
from urllib.parse import unquote, quote, urlparse, urlunparse

def parse_quirk_url(url):
    return ast.literal_eval(unquote(url).split('circuit=')[1])

def encode_quirk_url(url):
    try:
        circuit_json = unquote(url).split('circuit=')[1]
        encoded = quote(circuit_json, safe='')
        return url.split('circuit=')[0] + 'circuit=' + encoded
    except Exception:
        return url

def _build_gate_map(circuito):
    """Construye un mapa id/name -> definición de gate."""
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
    """Altura en qubits de un custom gate con circuito o matriz."""
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
    """Devuelve la operación QASM para las matrices de fase conocidas."""
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
    """Convierte un nombre de custom gate en un identificador QASM válido."""
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
    """id/name del gate_map -> identificador QASM único por custom gate.

    Se usa tanto en la declaración `gate ...` como en el sitio de uso para
    garantizar que ambas referencias coincidan siempre.
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
    """Operación QASM si el `name` del gate es una llamada a un gate estándar."""
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
    """Divide un texto por comas que no estén anidadas dentro de llaves."""
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
    """Normaliza `matrix` (string de Quirk o lista) a filas de complex, o None."""
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
    """p(θ) para matrices de fase 2x2 {{1,0},{0,e^(iθ)}} sin name utilizable."""
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
    arriba como submódulos `gate ...`; aquí se devuelve ese mismo
    identificador para que la declaración y la llamada coincidan siempre.
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
    if not isinstance(entry, str):
        return False
    base = entry.split(':')[0]
    return base in gate_map


def _quirk2_col_to_qasm(col, offset, gate_map, gate_names=None):
    lines = []
    if gate_names is None:
        gate_names = _resolve_gate_names(gate_map)
    if '•' in col:
        control_indices = [i for i, value in enumerate(col) if value == '•']
        modifier = 'ctrl @ ' * len(control_indices)
        if 'Swap' in col:
            swap_indices = [i for i, value in enumerate(col) if value == 'Swap']
            if len(swap_indices) == 2:
                qubits = [f'q[{i + offset}]' for i in control_indices + swap_indices]
                lines.append(f'{modifier}swap {", ".join(qubits)};')
            return lines

        basic_gates = {
            'H': 'h', 'X': 'x', 'Y': 'y', 'Z': 'z',
            'X^½': 'rx(pi/2)', 'X^-½': 'rx(-pi/2)',
            'X^¼': 'rx(pi/4)', 'X^-¼': 'rx(-pi/4)',
            'Y^½': 'ry(pi/2)', 'Y^-½': 'ry(-pi/2)',
            'Y^¼': 'ry(pi/4)', 'Y^-¼': 'ry(-pi/4)',
            'Z^½': 'p(pi/2)', 'Z^-½': 'p(-pi/2)',
            'Z^¼': 'p(pi/4)', 'Z^-¼': 'p(-pi/4)',
        }
        occupied = set(control_indices)
        for index, value in enumerate(col):
            if index in occupied or value in (1, '1', None, 'Measure'):
                continue
            if isinstance(value, str) and _is_gate_ref(value, gate_map):
                gate_id = value.split(':')[0]
                gate = gate_map[gate_id]
                target = _gate_operation(gate, gate_id, gate_names)
                gate_height = _gate_height(gate) or 1
            else:
                target = basic_gates.get(value)
                gate_height = 1
            if target is None:
                continue
            target_indices = range(index, index + gate_height)
            qubits = [f'q[{i + offset}]' for i in control_indices]
            qubits.extend(f'q[{i + offset}]' for i in target_indices)
            lines.append(f'{modifier}{target} {", ".join(qubits)};')
            occupied.update(target_indices)
    else:
        if 'Swap' in col:
            swap_indices = [k for k, g in enumerate(col) if g == 'Swap']
            if len(swap_indices) == 2:
                lines.append(f'swap q[{swap_indices[0] + offset}], q[{swap_indices[1] + offset}];')
            return lines
        else:
            occupied = set()
            for index, value in enumerate(col):
                if index in occupied or value in (1, '1', None):
                    continue
                if not (isinstance(value, str) and _is_gate_ref(value, gate_map)):
                    continue
                gate_id = value.split(':')[0]
                gate = gate_map[gate_id]
                operation = _gate_operation(gate, gate_id, gate_names)
                gate_height = _gate_height(gate) or 1
                qubits = ', '.join(
                    f'q[{i + offset}]'
                    for i in range(index, index + gate_height)
                )
                lines.append(f'{operation} {qubits};')
                occupied.update(range(index, index + gate_height))
            basic_gates = {
                'Measure': f'c[{offset}] = measure q[{offset}];',
                'H': f'h q[{offset}];',
                'X': f'x q[{offset}];',
                'Y': f'y q[{offset}];',
                'Z': f'z q[{offset}];',
                'X^½': f'rx(pi/2) q[{offset}];',
                'X^-½': f'rx(-pi/2) q[{offset}];',
                'X^¼': f'rx(pi/4) q[{offset}];',
                'X^-¼': f'rx(-pi/4) q[{offset}];',
                'Y^½': f'ry(pi/2) q[{offset}];',
                'Y^-½': f'ry(-pi/2) q[{offset}];',
                'Y^¼': f'ry(pi/4) q[{offset}];',
                'Y^-¼': f'ry(-pi/4) q[{offset}];',
                'Z^½': f'p(pi/2) q[{offset}];',
                'Z^-½': f'p(-pi/2) q[{offset}];',
                'Z^¼': f'p(pi/4) q[{offset}];',
                'Z^-¼': f'p(-pi/4) q[{offset}];',
            }
            for index, value in enumerate(col):
                if index in occupied or value in (1, '1', None):
                    continue
                if isinstance(value, str) and _is_gate_ref(value, gate_map):
                    continue
                if value in basic_gates:
                    qi = index + offset
                    lines.append(
                        basic_gates[value].replace(
                            f'q[{offset}]', f'q[{qi}]'
                        ).replace(
                            f'c[{offset}]', f'c[{qi}]'
                        )
                    )
            return lines
    return lines
    
# Borrar esta función, se reemplaza por _col_to_qasm_with_gates() o _quirk2_col_to_qasm()
def _quirk_col_to_qasm(col, offset):
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
    """Version recursiva que expande custom gates con 'circuit'."""
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
    """Retorna las primeras n letras del abecedario separadas por coma."""
    return ','.join(string.ascii_lowercase[:n])

def replace_params(lines):
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
    llamados (_gate_operation), para que declaración y llamada coincidan.
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
    if qasm_version not in {'2.0', '3.0'}:
        raise ValueError("qasm_version debe ser '2.0' o '3.0'")
    info = quirk_circuit_info(url)
    lines = ['OPENQASM 3.0;', 'include "stdgates.inc";', '']
    custom_gates_info = info.get('custom_gates_info', [])

    circuito = parse_quirk_url(url)
    gate_map = _build_gate_map(circuito)
    gate_names = _resolve_gate_names(gate_map)
    cols = circuito.get('cols', [])
    if len(custom_gates_info) > 0:
        declarations = append_custom_gates(custom_gates_info, gate_map, gate_names)
        if declarations:
            lines.append(declarations)
    if not cols:
        n = offset
    else:
        n = max(len(c) for c in cols) + offset
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
    for col in cols:
        # algo=_col_to_qasm_with_gates(col, offset, gate_map)
        algo = _quirk2_col_to_qasm(col, offset, gate_map, gate_names)
        lines.extend(algo)
    qasm3_source = '\n'.join(lines)
    if qasm_version == '2.0':
        return qasm3_to_qasm2(qasm3_source)
    return qasm3_source


def qasm3_to_qasm2(qasm3_source):
    """Lower a supported OpenQASM 3.0 circuit to standard OpenQASM 2.0."""
    from qiskit import qasm2, qasm3, transpile

    circuit = qasm3.loads(qasm3_source)
    lowered_circuit = transpile(
        circuit,
        basis_gates=['u1', 'u2', 'u3', 'cx'],
        optimization_level=0,
    )
    return qasm2.dumps(lowered_circuit)


def provider_python_source(qasm_source, provider, qasm_version='3.0', shots=1000):
    """Return executable Python source for a supported quantum provider."""
    from qiskit import qasm2, qasm3

    providers = {'ibm_qiskit', 'aws_braket', 'pennylane'}
    if provider not in providers:
        raise ValueError(f'Provider no soportado: {provider!r}')
    if qasm_version not in {'2.0', '3.0'}:
        raise ValueError("qasm_version debe ser '2.0' o '3.0'")

    circuit = qasm2.loads(qasm_source) if qasm_version == '2.0' else qasm3.loads(qasm_source)
    if provider == 'ibm_qiskit':
        return _qiskit_python_source(circuit)
    if provider == 'aws_braket':
        return _braket_python_source(circuit)
    return _pennylane_python_source(circuit, shots=shots)


_HALF_PI = 1.5707963267948966
_PI = 3.141592653589793


def _native_gate_for_u(theta, phi, lam):
    """Return the native Qiskit gate name when (theta, phi, lam) is standard."""
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


def _qiskit_python_source(parsed_circuit):
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

    def emit(operation, qubits, clbits, depth=0):
        raw_params = list(operation.params)
        parameters = [repr(parameter) for parameter in raw_params]

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
                    f'circuit.u({repr(_HALF_PI)}, {parameters[0]}, {parameters[1]}, {qubits[0]})'
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
            # directa): se expande su cuerpo en línea respetando el orden.
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
        'from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister',
    ]
    if gate_imports:
        imports.append(
            f"from qiskit.circuit.library import {', '.join(sorted(gate_imports))}"
        )

    python_lines = imports + ['', '# Generación de registros cuánticos y clásicos']
    python_lines.extend(register_declarations)
    python_lines.extend(['', '# Creación del circuito cuántico'])
    python_lines.append(f"circuit = QuantumCircuit({', '.join(register_variables)})")
    python_lines.extend([''] + instructions)
    return '\n'.join(python_lines) + '\n'


def _braket_python_source(parsed_circuit):
    instructions = []
    measurements = []
    measurement_qubits = set()

    def emit(operation, qubits, clbits, depth=0):
        parameters = [repr(parameter) for parameter in operation.params]

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
                    ['1.5707963267948966'] + parameters
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
                f'circuit.u({qubits[0]}, 1.5707963267948966, {parameters[0]}, {parameters[1]})'
            )
        elif operation.name in {'u3', 'u'}:
            instructions.append(
                f'circuit.u({qubits[0]}, {parameters[0]}, {parameters[1]}, {parameters[2]})'
            )
        elif operation.name in {'h', 'rx', 'ry', 'rz', 'x', 'y', 'z'}:
            arguments = [str(qubits[0])] + parameters
            instructions.append(f"circuit.{operation.name}({', '.join(arguments)})")
        elif operation.definition is not None and depth < 10:
            # Custom gate declarado en OpenQASM: expandir su cuerpo en línea.
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
        'from braket.circuits import Circuit',
        '',
        '# Creación del circuito AWS Braket',
        'circuit = Circuit()',
        '',
        '# Puertas migradas desde OpenQASM',
        *instructions,
    ]
    if measurements:
        python_lines.append('')
        python_lines.append('# Mediciones en orden clásico, diferidas al final')
        python_lines.extend(
            f'circuit.measure([{qubit}])'
            for _, qubit in sorted(measurements)
        )
    return '\n'.join(python_lines) + '\n'


def _pennylane_python_source(parsed_circuit, shots=1000):
    pennylane_gates = {
        'h': 'Hadamard', 'p': 'PhaseShift', 'rx': 'RX', 'ry': 'RY',
        'rz': 'RZ', 'swap': 'SWAP', 'x': 'PauliX', 'y': 'PauliY', 'z': 'PauliZ',
        'u1': 'PhaseShift', 'u2': 'U3', 'u3': 'U3', 'u': 'U3',
    }

    def gate_parameters(operation_name, parameters):
        if operation_name == 'u2':
            return ['1.5707963267948966'] + parameters
        if operation_name in {'u3', 'u'}:
            return parameters
        if operation_name == 'u1':
            return parameters
        return parameters

    instructions = []
    measurement_variables = {}
    measurement_count = 0

    def emit(operation, qubits, clbits, depth=0):
        nonlocal measurement_count
        parameters = [repr(parameter) for parameter in operation.params]

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
                # Custom gate declarado en OpenQASM: expandir su cuerpo en línea.
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
        'import pennylane as qml',
        '',
        f"device = qml.device('default.qubit', wires={parsed_circuit.num_qubits}, shots={device_shots!r})",
        '',
        '@qml.qnode(device)',
        'def circuit():',
        *[f'    {instruction}' for instruction in instructions],
    ]

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


def quirk_circuit_info(url):
    circuito = parse_quirk_url(url)
    cols = circuito.get('cols', [])
    gates_defs = circuito.get('gates', [])
    # n_qubits efectivo: max de cols principales y altura de custom gates usados
    if cols:
        n_qubits = max(len(c) for c in cols) if cols else 0
        gate_map_eff = _build_gate_map(circuito)
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


def _zx_phase(angle):
    return Fraction(angle / math.pi).limit_denominator(1_000_000)


def _zx_append_phase_on_ones(circuit, qubits, angle):
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
    _zx_append_phase_on_ones(circuit, controls, -angle / 2)
    _zx_append_phase_on_ones(circuit, controls + [target], angle)


def _zx_append_controlled_ry(circuit, controls, target, angle):
    circuit.add_gate('XPhase', target, Fraction(1, 2))
    _zx_append_controlled_rz(circuit, controls, target, angle)
    circuit.add_gate('XPhase', target, Fraction(-1, 2))


def _zx_decompose_unitary(matrix):
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
    global_phase, beta, gamma, delta = _zx_decompose_unitary(matrix)
    _zx_append_phase_on_ones(circuit, controls, global_phase)
    _zx_append_controlled_rz(circuit, controls, target, delta)
    _zx_append_controlled_ry(circuit, controls, target, gamma)
    _zx_append_controlled_rz(circuit, controls, target, beta)


def _zx_append_mcx(circuit, controls, target):
    if not controls:
        circuit.add_gate('NOT', target)
        return
    circuit.add_gate('HAD', target)
    _zx_append_phase_on_ones(circuit, controls + [target], math.pi)
    circuit.add_gate('HAD', target)


def _zx_rotation_matrix(axis, angle):
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


def quirk_to_zx_graph(url, offset=0, time=0.5):
    """Convierte una URL Quirk a un grafo PyZX; time selecciona el snapshot [0, 1]."""
    try:
        import pyzx as zx
    except ImportError as exc:
        raise ImportError('Instala PyZX con `pip install pyzx` para generar grafos ZX') from exc

    if not 0 <= time <= 1:
        raise ValueError('time debe estar entre 0 y 1, como el tiempo de Quirk')

    circuit_data = parse_quirk_url(url)
    cols = circuit_data.get('cols', [])
    n_qubits = max((len(col) for col in cols), default=0) + offset
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
            _zx_append_unitary(
                circuit,
                index + offset,
                _zx_gate_matrix(token, gate_map, time),
                controls,
            )

    return circuit.to_graph()


def capture_quirk_circuit(url, output_path, timeout=15):
    """Captura la vista completa de un circuito Quirk en un archivo PNG."""
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


def qasm_to_zx_graph(qasm_code):
    """Importa el OpenQASM 3 generado por este proyecto y devuelve su grafo PyZX."""
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

    def process(statement, line_number, mapping=None, extra_controls=(), depth=0):
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
            # Cuerpo de un custom gate: operandos son letras (a, b, ...).
            qubits = []
            for token in operands_text.split(','):
                token = token.strip()
                if not re.fullmatch(r'[a-z]', token) or ord(token) - ord('a') >= len(mapping):
                    raise ValueError(
                        f'Operando de custom gate no reconocido en línea '
                        f'{line_number}: {statement}'
                    )
                qubits.append(mapping[ord(token) - ord('a')])
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
                process(body_line, line_number, body_mapping, body_controls, depth + 1)
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

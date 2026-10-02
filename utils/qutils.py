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


def _is_gate_ref(entry, gate_map):
    if not isinstance(entry, str):
        return False
    base = entry.split(':')[0]
    return base in gate_map


def _quirk2_col_to_qasm(col, offset, gate_map):
    lines = []
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
                target = _matrix_gate_operation(gate) or gate.get('name', gate_id)
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
            gate_index = next(
                (
                    index for index, value in enumerate(col)
                    if isinstance(value, str)
                    and _is_gate_ref(value, gate_map)
                ),
                None,
            )
            gate_reference = col[gate_index] if gate_index is not None else None
            gate_id = gate_reference.split(':')[0] if gate_reference else None
            gate = gate_map.get(gate_id) if gate_id is not None else None
            if gate is not None:
                gate_name = _matrix_gate_operation(gate) or gate.get('name', gate_id)
                gate_height = _gate_height(gate) or 1
                qubits = ', '.join(
                    f'q[{index + offset}]'
                    for index in range(gate_index, gate_index + gate_height)
                )
                return [f'{gate_name} {qubits};']
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
                if value in (1, '1'):
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
            lines.extend(_quirk2_col_to_qasm(leftover_col, offset))
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

def append_custom_gates(custom_gates_info, gate_map):
    lines = []
    for custom_gate_info in custom_gates_info:
     #print(f"Custom gate: {custom_gate['name']} (ID: {custom_gate['id']})")
        cols = custom_gate_info.get("circuit_cols")
        if cols is None:
            # Gates con matrix (no circuit) no son declarables en QASM
            continue
        lines.append(f'gate {custom_gate_info["name"]} {primeras_letras(custom_gate_info["n_qubits"])} {{')
        for col in cols:
            lines.extend(replace_params(_quirk2_col_to_qasm(col, 0, gate_map)))
        lines.append('}')
    return '\n'.join(lines)

def quirk_to_qasm(url, offset=0):
    info = quirk_circuit_info(url)
    lines = ['OPENQASM 3.0;', 'include "stdgates.inc";']
    custom_gates_info = info.get('custom_gates_info', [])

    circuito = parse_quirk_url(url)
    gate_map = _build_gate_map(circuito)
    cols = circuito.get('cols', [])
    if len(custom_gates_info) > 0:
        lines.append(append_custom_gates(custom_gates_info, gate_map))
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
        algo = _quirk2_col_to_qasm(col, offset, gate_map)
        lines.extend(algo)
    return '\n'.join(lines)


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
            info['n_qubits'] = None
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

    match = re.fullmatch(r'U\((.+)\)', name, re.IGNORECASE)
    if match:
        angle = _zx_parse_angle(match.group(1))
        return ((1 + 0j, 0j), (0j, cmath.exp(1j * angle)))

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

    for line_number, raw_line in enumerate(qasm_code.splitlines(), start=1):
        line = raw_line.split('//', 1)[0].strip()
        if not line or line.startswith(('OPENQASM', 'include', 'qreg', 'creg', 'qubit', 'bit')):
            continue
        if measurement_pattern.fullmatch(line):
            continue

        match = statement_pattern.fullmatch(line)
        if match is None:
            raise ValueError(f'Instrucción OpenQASM no reconocida en línea {line_number}: {line}')

        operands_text = match.group('operands').strip()
        if not operand_pattern.fullmatch(operands_text):
            raise ValueError(f'Operandos OpenQASM no reconocidos en línea {line_number}: {line}')
        qubits = [int(value) for value in re.findall(r'\[(\d+)\]', operands_text)]
        if any(qubit >= n_qubits for qubit in qubits):
            raise ValueError(f'Índice de qubit fuera del registro en línea {line_number}: {line}')

        gate_name = match.group('gate').lower()
        parameters = match.group('params')
        modifier_controls = match.group('modifiers').lower().count('ctrl')
        if gate_name == 'swap':
            if len(qubits) < 2 or len(qubits) != modifier_controls + 2:
                raise ValueError(f'Cantidad de qubits inválida para swap en línea {line_number}: {line}')
            controls, targets = qubits[:-2], qubits[-2:]
            if len(controls) != modifier_controls:
                raise ValueError(f'Controles incompatibles en línea {line_number}: {line}')
            if controls:
                first, second = targets
                _zx_append_mcx(circuit, controls + [first], second)
                _zx_append_mcx(circuit, controls + [second], first)
                _zx_append_mcx(circuit, controls + [first], second)
            else:
                circuit.add_gate('SWAP', *targets)
            continue

        controlled_aliases = {
            'cx': 'x', 'cy': 'y', 'cz': 'z', 'ch': 'h',
            'ccx': 'x', 'mcx': 'x', 'mcy': 'y', 'mcz': 'z',
            'crx': 'rx', 'cry': 'ry', 'crz': 'rz', 'cp': 'p', 'cu1': 'p',
        }
        if gate_name in controlled_aliases:
            if modifier_controls:
                raise ValueError(f'No se admite combinar alias controlado y ctrl @ en línea {line_number}: {line}')
            controls, target = qubits[:-1], qubits[-1]
            gate_name = controlled_aliases[gate_name]
        elif modifier_controls:
            if len(qubits) != modifier_controls + 1:
                raise ValueError(f'Cantidad de controles incompatible en línea {line_number}: {line}')
            controls, target = qubits[:-1], qubits[-1]
        else:
            if len(qubits) != 1:
                raise ValueError(f'Cantidad de qubits inválida en línea {line_number}: {line}')
            controls, target = [], qubits[0]

        if gate_name in ('rx', 'ry', 'rz', 'p'):
            if parameters is None:
                raise ValueError(f'Falta el ángulo de {gate_name} en línea {line_number}: {line}')
            gate_token = f'{gate_name}({parameters})'
        else:
            if parameters is not None:
                raise ValueError(f'Parámetros inesperados para {gate_name} en línea {line_number}: {line}')
            gate_token = gate_name.upper()

        matrix = _zx_gate_matrix(gate_token, {}, time=0.5)
        _zx_append_unitary(circuit, target, matrix, controls)

    return circuit.to_graph()

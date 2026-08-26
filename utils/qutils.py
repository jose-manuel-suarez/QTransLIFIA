import ast
import re
import string
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
    """Construye mapa id/name -> definicion de custom gate con 'circuit'.
    Solo gates con campo 'circuit' son expandibles; los de 'matrix' se ignoran."""
    gate_map = {}
    for g in circuito.get('gates', []):
        if 'circuit' not in g:
            continue
        if 'id' in g and isinstance(g['id'], str):
            gate_map[g['id']] = g
            base = g['id'].split(':')[0]
            gate_map[base] = g
        if 'name' in g and isinstance(g['name'], str):
            if g['name'] not in gate_map:
                gate_map[g['name']] = g
    return gate_map


def _gate_height(gate):
    """Altura (n qubits) del custom gate = max len de sus cols."""
    cols = gate.get('circuit', {}).get('cols', [])
    if not cols:
        return 0
    return max(len(c) for c in cols)


def _is_gate_ref(entry, gate_map):
    if not isinstance(entry, str):
        return False
    base = entry.split(':')[0]
    return base in gate_map


def _quirk2_col_to_qasm(col, offset, gate_map):
    lines = []
    if '•' in col:
        control_indices = [i for i, value in enumerate(col) if value == '•']
        target_col = [
            value for value in col
            if value != '•' and value not in (1, '1')
        ]
        if 'Swap' in target_col:
            target = 'swap'
        else:
            target = _quirk2_col_to_qasm(target_col, offset, gate_map)
            if isinstance(target, list):
                target = ''.join(target)
        target = target.rstrip(';')
        qubits = [f'q[{i + offset}]' for i in control_indices]
        qubits.extend(
            f'q[{i + offset}]'
            for i, value in enumerate(col)
            if value != '•' and value not in (1, '1')
        )
        lines.append(f'{"ctrl @ " * len(control_indices)}{target} {", ".join(qubits)};')
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
                gate_name = gate.get('name', gate_id)
                gate_height = _gate_height(gate)
                qubits = ', '.join(
                    f'q[{index + offset}]'
                    for index in range(gate_index, gate_index + gate_height)
                )
                return [f'{gate_name} {qubits};']
            return col[0]
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
    lines = ['OPENQASM 2.0;', 'include "qelib1.inc";']
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
        r = max(map(lambda gate: gate["n_qubits"], custom_gates_info), default=0) + offset
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

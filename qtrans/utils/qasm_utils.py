"""Utilidades de OpenQASM independientes del ecosistema de destino.

Concentra lo que el pipeline y los tres generadores de código (Qiskit, AWS
Braket y PennyLane) necesitan saber del *lenguaje* OpenQASM y no de un
proveedor concreto:

- tablas de compuertas estándar de ``stdgates.inc`` y palabras reservadas;
- saneado de nombres de compuerta custom y des-citado de placeholders;
- conversión de ángulos a expresiones Python (``math.pi/2``, ``3*math.pi/4``…);
- bajada de OpenQASM 3.0 a 2.0 (u1/u2/u3/cx) y detección de la versión;
- resumen de compuertas custom/nativas de un código QASM 3.0.

Es una *hoja* del grafo de importaciones: no depende de ningún otro módulo de
``qtrans.utils``, de modo que los módulos de proveedor pueden usarla sin ciclos.
"""

import math
import re
import sys


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
    # Constantes numéricas intrínsecas de OpenQASM 3 (p. ej. un gate 'pi').
    'pi', 'tau', 'euler',
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


# Compuertas Quirk no traducibles (matriz no unitaria / desconocidas) ya
# reportadas en la corrida, para no repetir el mismo aviso cientos de veces.
_REPORTED_UNSUPPORTED_GATES = set()


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


_QASM_DECL_RE = re.compile(r"^gate\s+([A-Za-z_][A-Za-z0-9_]*)")
_QASM_DECL_FULL_RE = re.compile(
    r"^gate\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s+(?P<params>[A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*))?\s*\{"
)
_QASM_MODIFIER_RE = re.compile(r"^(?:(?:ctrl|inv|pow\s*\([^)]*\))\s*@\s*)+")
_NON_OPERATION_PREFIXES = ("qreg", "creg", "qubit", "bit", "measure", "barrier", "reset")


def qasm_gate_summary(qasm3_source):
    """Resume las operaciones custom y nativas del código OpenQASM 3.0.

    Ignora cabeceras, declaraciones ``qreg``/``creg`` y los cuerpos de las
    declaraciones ``gate`` (incluidas QFTn); solo cuentan las líneas de
    operación a nivel de módulo. Una operación es *custom* si su nombre
    coincide con un gate declarado en el propio código; el resto es *nativa*.

    Parámetros:
        - qasm3_source (str): código OpenQASM 3.0 generado por ``quirk_to_qasm``.

    Retorna:
        - dict: ``{"custom": {"count": int, "names": [str, ...]},
          "native": {"count": int, "names": [str, ...]}}``; los nombres son
          únicos y quedan ordenados alfabéticamente.
    """
    custom_names = set()
    operations = []
    depth = 0
    for raw_line in qasm3_source.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("OPENQASM", "include", "//", "#")):
            continue
        if depth == 0:
            declaration_match = _QASM_DECL_RE.match(line)
            if declaration_match:
                custom_names.add(declaration_match.group(1))
            elif not line.startswith(_NON_OPERATION_PREFIXES) and line.endswith(";"):
                operations.append(line)
        depth += line.count("{") - line.count("}")
        if depth < 0:
            depth = 0

    custom_operations = []
    native_operations = []
    for operation in operations:
        token = _QASM_MODIFIER_RE.sub("", operation.rstrip(";").strip())
        if "=" in token:
            # Asignaciones de QASM 3.0 (``c[i] = measure q[j]``): la operación
            # es el lado derecho, no el registro clásico de destino.
            token = token.split("=", 1)[1].strip()
        name = re.split(r"[\s(]", token, maxsplit=1)[0]
        if name in custom_names:
            custom_operations.append(name)
        else:
            native_operations.append(name)
    return {
        "custom": {"count": len(custom_operations), "names": sorted(set(custom_operations))},
        "native": {"count": len(native_operations), "names": sorted(set(native_operations))},
    }


def qasm_gate_blocks(qasm_source):
    """Extrae las declaraciones ``gate`` completas del código OpenQASM.

    Devuelve el texto literal de cada declaración (cabecera y cuerpo), tal y
    como aparece en el código, para poder reutilizarla en otro documento
    OpenQASM (p. ej. para reconstruir una compuerta custom que el parser
    descarta por no usarse en el circuito).

    Parámetros:
        - qasm_source (str): código OpenQASM.

    Retorna:
        - list[tuple[str, int, str]]: triplets (nombre, número de qubits,
          bloque de texto de la declaración).
    """
    blocks = []
    lines = (qasm_source or '').splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        match = _QASM_DECL_FULL_RE.match(line)
        if match is None:
            index += 1
            continue
        chunk = [line]
        depth = line.count('{') - line.count('}')
        while depth > 0 and index + 1 < len(lines):
            index += 1
            chunk.append(lines[index])
            depth += lines[index].count('{') - lines[index].count('}')
        params = match.group('params')
        n_qubits = len(params.split(',')) if params else 0
        blocks.append((match.group('name'), n_qubits, '\n'.join(chunk)))
        index += 1
    return blocks


def qasm_custom_gate_operations(qasm_source):
    """Operaciones de todas las compuertas custom **declaradas** en el código.

    El parser de Qiskit solo conserva en el circuito las compuertas custom que
    se usan; las que se declaran pero no aparecen en el cuerpo se descartan.
    Esta función las recupera: reconstruye un OpenQASM sintético con las
    mismas declaraciones y una llamada por compuerta, lo parsea y devuelve las
    operaciones resultantes (con su ``definition``).

    Parámetros:
        - qasm_source (str): código OpenQASM 3.0.

    Retorna:
        - list[tuple[str, object]]: pares (nombre de la compuerta, operación
          de Qiskit). Lista vacía si no hay declaraciones o si el código no se
          puede parsear.
    """
    blocks = qasm_gate_blocks(qasm_source)
    if not blocks:
        return []
    total_qubits = sum(n_qubits for _, n_qubits, _ in blocks)
    if total_qubits == 0:
        return []
    synthetic = ['OPENQASM 3.0;', 'include "stdgates.inc";']
    synthetic.extend(block for _, _, block in blocks)
    synthetic.append(f'qubit[{total_qubits}] q;')
    offset = 0
    for name, n_qubits, _ in blocks:
        arguments = ', '.join(f'q[{offset + position}]' for position in range(n_qubits))
        synthetic.append(f'{name} {arguments};')
        offset += n_qubits
    try:
        from qiskit import qasm3

        circuit = qasm3.loads('\n'.join(synthetic))
    except Exception:  # noqa: BLE001 — mejor efforts: sin declaraciones extra
        return []
    operations = []
    for item, (name, _, _) in zip(circuit.data, blocks):
        operation = item.operation
        if operation.name != name:
            continue
        operations.append((name, operation))
    return operations

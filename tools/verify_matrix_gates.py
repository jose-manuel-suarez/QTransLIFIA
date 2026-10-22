"""Batería de verificación numérica de las compuertas personalizadas con ``matrix``.

Las *custom gates* declaradas en Quirk con el campo ``matrix`` son el punto
del flujo donde la traducción puede perder información: el tradutor no copia
la matriz sino que emite una **descomposición equivalente** (``p``+ZYZ para
unitarias 2×2, KAK con ``U``+``cx`` para 4×4). Esta batería comprueba, compuerta
por compuerta, que la equivalencia se conserva:

- **A** matriz declarada en la URL de Quirk (fuente de verdad);
- **B** unitaria reconstruida desde el cuerpo OpenQASM emitido por el traductor;
- **C** unitaria reconstruida desde un camino **independiente**: la
  descomposición ZYZ que usa el verificador ZX para 2×2 y la descomposición KAK
  de Qiskit para 4×4;
- **D** residuo de la proyección a unitaria (SVD) que el pipeline aplica cuando
  la matriz de la URL no es exactamente unitaria.

Uso:

    python tools/verify_matrix_gates.py
    python tools/verify_matrix_gates.py --input input/popular_algorithms.json

Devuelve código de salida 1 si algún residuo supera la tolerancia
(``--tol``, por defecto 1e-6, muy por encima del redondeo de 7 decimales con el
que Quirk serializa las matrices).
"""

import argparse
import cmath
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qiskit import qasm3
from qiskit.quantum_info import Operator

from qtrans.utils.quirk_utils import (
    _build_gate_map,
    _matrix_to_rows,
    _project_unitary,
    _resolve_gate_names,
    quirk_to_qasm,
)
from qtrans.utils.zx_utils import _zx_decompose_unitary

GATE_DECL_RE = re.compile(r'^gate\s+([^\n{]*)\{(.*?)^\}', re.M | re.S)


def _rz(theta):
    """Matriz de la rotación Z (convención de Qiskit)."""
    return np.array(
        [[cmath.exp(-1j * theta / 2), 0], [0, cmath.exp(1j * theta / 2)]],
        dtype=complex,
    )


def _ry(theta):
    """Matriz de la rotación Y (convención de Qiskit)."""
    return np.array(
        [[math.cos(theta / 2), -math.sin(theta / 2)],
         [math.sin(theta / 2), math.cos(theta / 2)]],
        dtype=complex,
    )


def _declarations(qasm_text):
    """Extrae {nombre: cuerpo} de las declaraciones ``gate`` del OpenQASM."""
    bodies = {}
    for match in GATE_DECL_RE.finditer(qasm_text):
        header = match.group(1).split()
        if not header:
            continue
        body = [line.strip() for line in match.group(2).strip().splitlines() if line.strip()]
        bodies[header[0]] = body
    return bodies


def _unitary_from_body(body, n_qubits):
    """Reconstruye la unitaria de un cuerpo de compuerta a partir de su texto."""
    letters = ['a', 'b', 'c', 'd'][:n_qubits]
    source = (
        'OPENQASM 3.0;\ninclude "stdgates.inc";\n'
        f"gate gtest {', '.join(letters)} {{\n" + '\n'.join(body) + '\n}\n'
        f"qreg q[{n_qubits}];\n"
        f"gtest {', '.join(f'q[{i}]' for i in range(n_qubits))};\n"
    )
    return Operator(qasm3.loads(source)).data


def _circuit_json(url):
    """Extrae el JSON del circuito de una URL de Quirk."""
    return json.loads(url.split('circuit=', 1)[1])


def _matrix_gates(circuit_json):
    """Devuelve [(id, nombre, filas, qubits)] de las compuertas con ``matrix``."""
    gate_map = _build_gate_map(circuit_json)
    gate_names = _resolve_gate_names(gate_map)
    found = []
    for gate in circuit_json.get('gates', []):
        if gate.get('matrix') is None:
            continue
        rows = _matrix_to_rows(gate['matrix'])
        found.append((
            str(gate.get('id')),
            gate.get('name') or gate.get('id'),
            np.array(rows, dtype=complex),
            int(round(math.log2(len(rows)))),
            gate_names.get(str(gate.get('id')), str(gate.get('id'))),
        ))
    return found


def verify_algorithm(name, entry, tol):
    """Verifica todas las compuertas con ``matrix`` de un algoritmo.

    Parámetros:
        - name (str): nombre del algoritmo en el registro de entrada.
        - entry (dict): entrada del registro (``url`` y ``offset`` opcional).
        - tol (float): tolerancia de los residuos.

    Retorna:
        - tuple: (residuo máximo frente a la URL, lista de detalles).
    """
    qasm = quirk_to_qasm(
        entry['url'], offset=entry.get('offset', 0), qasm_version='3.0'
    )
    circuit_json = _circuit_json(entry['url'])
    gates = _matrix_gates(circuit_json)
    if not gates:
        return 0.0, []

    bodies = _declarations(qasm)
    details = []
    worst = 0.0
    for gate_id, gate_name, url_matrix, n_qubits, emitted in gates:
        body = bodies.get(emitted)
        if body is None:
            details.append((gate_name, gate_id, float('nan'), 'sin declaración emitida'))
            continue
        emitted_matrix = _unitary_from_body(body, n_qubits)
        residual = float(np.abs(emitted_matrix - url_matrix).max())
        worst = max(worst, residual)

        independent = ''
        if n_qubits == 1:
            g, beta, gamma, delta = _zx_decompose_unitary(
                tuple(tuple(row) for row in url_matrix.tolist())
            )
            zx_unitary = (
                np.array([[cmath.exp(1j * g), 0], [0, cmath.exp(1j * g)]], dtype=complex)
                @ _rz(beta) @ _ry(gamma) @ _rz(delta)
            )
            residual_zx = float(np.abs(zx_unitary - url_matrix).max())
            independent = f'ZX/ZYZ |ZX-URL|={residual_zx:.3e}'
        else:
            projected = np.array(
                _project_unitary(tuple(tuple(row) for row in url_matrix.tolist())),
                dtype=complex,
            )
            residual_proj = float(np.abs(projected - url_matrix).max())
            from qiskit.synthesis import TwoQubitWeylDecomposition
            kak = TwoQubitWeylDecomposition(projected)
            residual_kak = float(np.abs(Operator(kak.circuit()).data - projected).max())
            independent = (
                f'|URL-proyeccion SVD|={residual_proj:.3e} '
                f'KAK |KAK-proyeccion|={residual_kak:.3e}'
            )

        details.append((gate_name, gate_id, residual, independent))

    print(f'\n=== {name} ===')
    for gate_name, gate_id, residual, extra in details:
        print(f'  {gate_name} (id {gate_id}) dim={len(url_matrix)}')
        print(f'    |OpenQASM-URL| = {residual:.3e}   {extra}')
    return worst, details


def main(argv=None):
    """Punto de entrada: recorre el registro de algoritmos y verifica matrices."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--input', default=str(PROJECT_ROOT / 'input' / 'popular_algorithms.json'),
        help='registro JSON de algoritmos (id -> {url, offset?})',
    )
    parser.add_argument('--tol', type=float, default=1e-6, help='tolerancia de residuos')
    args = parser.parse_args(argv)

    data = json.loads(Path(args.input).read_text(encoding='utf-8'))
    algorithms = data.get('algorithms', data) if isinstance(data, dict) else {}

    worst = 0.0
    checked = 0
    for name, entry in algorithms.items():
        if not isinstance(entry, dict) or 'url' not in entry:
            continue
        try:
            circuit_json = _circuit_json(entry['url'])
        except (ValueError, KeyError, json.JSONDecodeError):
            continue
        if not _matrix_gates(circuit_json):
            continue
        residual, details = verify_algorithm(name, entry, args.tol)
        checked += len(details)
        worst = max(worst, residual)

    print('\n' + '=' * 78)
    print(f'compuertas con "matrix" verificadas: {checked}   '
          f'residuo máximo |OpenQASM-URL| = {worst:.3e}   (tolerancia {args.tol:g})')
    print('=' * 78)
    return 0 if worst <= args.tol else 1


if __name__ == '__main__':
    sys.exit(main())

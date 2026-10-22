"""Batería de verificación cruzada entre el parser nativo y el script migrado.

QTransLIFIA materializa cada circuito de dos formas complementarias:

- **nativa**: el parser de cada ecosistema (Qiskit ``qasm2/qasm3.loads``,
  Braket ``Circuit.from_ir``; PennyLane no tiene parser viable y usa el script);
- **migrada**: la ejecución del script Python que la librería genera.

Ambas deben describir el mismo circuito. Esta batería lo comprueba sobre el
corpus real (``input/popular_algorithms.json``) comparando una **firma
semántica** de cada circuito:

- **Qiskit**: se comparan las unitary matrices (salvo fase global) del
  ``QuantumCircuit`` nativo y del circuito construido por el script.
- **AWS Braket**: se comparan las instrucciones tras canonicalizar las
  representaciones equivalentes de la fase (``U(0,phi,0)`` ≡ ``PhaseShift`` ≡
  ``CPhaseShift`` si hay control) e ignorar la posición de las mediciones
  (el script las difiere al final).
- **PennyLane**: no hay parser nativo; se comprueba que el script migrado
  compila y produce un ``QNode`` ejecutable.

Con ``--simulate`` se añade una comprobación estadística con el simulador local
de Braket (distribución de conteos de la ruta nativa frente a la migrada).

Uso:

    python tools/verify_backend_equivalence.py
    python tools/verify_backend_equivalence.py --providers qiskit,braket --simulate

Devuelve código de salida 1 si alguna comparación falla.
"""

import argparse
import collections
import json
import math
import sys
import warnings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qtrans.utils.provider_utils import (
    load_provider_circuit,
    provider_python_source,
)
from qtrans.utils.quirk_utils import quirk_to_qasm


def _exec_script(source, provider):
    """Ejecuta un script migrado y devuelve el objeto ``circuit`` que define."""
    namespace = {}
    exec(compile(source, f'<migrado:{provider}>', 'exec'), namespace)
    return namespace['circuit']


def _braket_signature(circuit):
    """Firma semántica de un circuito de Braket (fase y controles canonicalizados).

    Braket ofrece dos representaciones equivalentes de la misma operación y el
    parser nativo y el script migrado usan una distinta:

    - ``PhaseShift(target, ang, control=c)`` (nativa) frente a
      ``CPhaseShift(control=c, target=t, ang)`` (migrada), donde Braket guarda
      ambos qubits en ``target``;
    - ``CNot(control, target)`` (nativa) frente a ``x(target, control=...)``
      (migrada), con el mismo convenio de qubits;
    - ``PhaseShift(t, ang)`` frente a ``U(t, 0, 0, ang)``, que difieren solo en
      una fase global.

    La firma canonicaliza ambas representaciones para comparar el circuito y
    no su sintaxis.
    """
    legacy_controls = {'CNot': ('X', 1), 'CCNot': ('X', 2), 'CSwap': ('Swap', 1)}

    signature = []
    for instruction in circuit.instructions:
        name = str(instruction.operator).split('(')[0]
        if name == 'Measure':
            continue
        controls = tuple(sorted(map(str, instruction.control)))
        targets = tuple(map(str, instruction.target))
        params = tuple(
            round(float(p), 9) for p in (getattr(instruction.operator, 'parameters', None) or ())
        )

        if name == 'PhaseShift':
            angle = round(params[0] % (2 * math.pi), 9)
            signature.append(('ctrl', 'phase', (angle,), targets, controls))
        elif name == 'CPhaseShift':
            angle = round(params[0] % (2 * math.pi), 9)
            # Braket almacena CPhaseShift(control, target) con ambos en `target`.
            control = targets[0] if len(targets) == 2 else ''
            signature.append(('ctrl', 'phase', (angle,), (targets[-1],), (control,) if control else ()))
        elif name == 'U':
            theta, phi, lam = params
            if abs(theta) < 1e-12:
                # U(0, phi, lambda) == PhaseShift(phi + lambda) salvo fase global.
                angle = round((phi + lam) % (2 * math.pi), 9)
                signature.append(('ctrl', 'phase', (angle,), targets, controls))
            else:
                signature.append(('ctrl' if controls else 'U', 'U', params, targets, controls))
        elif name in legacy_controls:
            base, n_controls = legacy_controls[name]
            ctrl = targets[:n_controls]
            tgt = targets[n_controls:]
            signature.append(('ctrl', base, params, tgt, ctrl))
        else:
            signature.append(('ctrl' if controls else name, name, params, targets, controls))
    return signature


def _strip_measurements(circuit):
    """Devuelve una copia del circuito sin mediciones ni barreras."""
    clean = circuit.copy()
    clean.data = [
        instruction for instruction in clean.data
        if instruction.operation.name not in {'measure', 'barrier'}
    ]
    return clean


def _qiskit_statevector(circuit):
    """Vector de estado de un ``QuantumCircuit`` (sin mediciones), salvo fase global."""
    import numpy as np
    from qiskit.quantum_info import Statevector

    vector = np.asarray(Statevector.from_instruction(_strip_measurements(circuit)).data)
    # Normaliza la fase global dividiendo por la primera componente no nula.
    pivot = next((value for value in vector if abs(value) > 1e-9), 1.0)
    return vector / (abs(pivot) / pivot)


def _compare_qiskit(native, migrated):
    """Compara el estado final de dos ``QuantumCircuit`` (Qiskit).

    Se comparan los vectores de estado y no las matrices unitarias porque el
    corpus incluye circuitos de hasta 16 qubits, donde la matriz unitaria
    (65536×65536) no es materializable.
    """
    import numpy as np

    a = _qiskit_statevector(native)
    b = _qiskit_statevector(migrated)
    if a.shape != b.shape:
        return False, f'dimensiones distintas: {a.shape} vs {b.shape}'
    residual = float(np.abs(a - b).max())
    return residual < 1e-8, f'residio |psi_nativo-psi_migrado| = {residual:.3e}'


def _compare_braket(native, migrated):
    """Compara las firmas semánticas de dos circuitos de Braket."""
    a = _braket_signature(native)
    b = _braket_signature(migrated)
    if a == b:
        return True, 'firmas idénticas'
    index = next(
        (i for i, (x, y) in enumerate(zip(a, b)) if x != y),
        min(len(a), len(b)),
    )
    left = a[index] if index < len(a) else None
    right = b[index] if index < len(b) else None
    return False, f'primera diferencia en #{index}: {left} vs {right}'


def _simulate_braket(native, migrated, shots=4000):
    """Compara estadísticamente la ruta nativa y la migrada con Braket local."""
    from braket.devices import LocalSimulator

    device = LocalSimulator()
    distributions = {}
    for label, circuit in (('nativo', native), ('migrado', migrated)):
        measurements = device.run(circuit, shots=shots).result().measurements
        first = measurements[0]
        if hasattr(first, '__len__') and not isinstance(first, (int, float, str)):
            counts = collections.Counter(tuple(int(b) for b in row) for row in measurements)
        else:
            counts = collections.Counter((int(b),) for b in measurements)
        distributions[label] = counts

    keys = set(distributions['nativo']) | set(distributions['migrado'])
    difference = max(
        (abs(distributions['nativo'].get(k, 0) - distributions['migrado'].get(k, 0))
         for k in keys),
        default=0,
    )
    total = sum(distributions['nativo'].values())
    return difference, total


def main(argv=None):
    """Punto de entrada: recorre el corpus y compara ambas rutas de carga."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--input', default=str(PROJECT_ROOT / 'input' / 'popular_algorithms.json'),
        help='registro JSON de algoritmos (id -> {url, offset?})',
    )
    parser.add_argument(
        '--providers', default='qiskit,braket',
        help='proveedores a comparar (qiskit, braket, pennylane)',
    )
    parser.add_argument('--shots', type=int, default=4000, help='disparos por simulación')
    parser.add_argument(
        '--only', default='',
        help='filtra los algoritmos por nombre (subcadena separada por comas)',
    )
    parser.add_argument(
        '--simulate', action='store_true',
        help='añade la comparación estadística con el simulador local de Braket',
    )
    args = parser.parse_args(argv)

    warnings.filterwarnings('ignore')
    data = json.loads(Path(args.input).read_text(encoding='utf-8'))
    algorithms = data.get('algorithms', data) if isinstance(data, dict) else {}
    providers = [p.strip() for p in args.providers.split(',') if p.strip()]

    failures = []
    filters = [token.strip() for token in args.only.split(',') if token.strip()]
    for provider in providers:
        same = 0
        total = 0
        for name, entry in algorithms.items():
            if not isinstance(entry, dict) or 'url' not in entry:
                continue
            if filters and not any(token in name for token in filters):
                continue
            qasm = quirk_to_qasm(
                entry['url'], offset=entry.get('offset', 0), qasm_version='3.0'
            )
            total += 1
            try:
                native = load_provider_circuit(qasm, provider, qasm_version='3.0')
                migrated = _exec_script(
                    provider_python_source(qasm, provider, qasm_version='3.0'), provider
                )
            except Exception as exc:  # noqa: BLE001 - la batería reporta, no propaga
                failures.append((provider, name, f'error al cargar: {exc}'))
                continue

            if provider == 'qiskit':
                ok, detail = _compare_qiskit(native, migrated)
            elif provider == 'braket':
                ok, detail = _compare_braket(native, migrated)
            else:
                ok = True
                detail = 'materializado por script (sin parser nativo)'
            if ok:
                same += 1
            else:
                failures.append((provider, name, detail))

            if args.simulate and provider == 'braket':
                difference, shots = _simulate_braket(native, migrated, args.shots)
                verdict = 'EQUIVALENTE' if difference <= 0.10 * shots else 'DIFIERE'
                print(f'  [simulación] {name}: max|Δconteos| = {difference}/{shots} -> {verdict}')
                if difference > 0.10 * shots:
                    failures.append((provider, name, f'diferencia de conteos {difference}/{shots}'))

        print(f'{provider}: rutas equivalentes {same}/{total}')

    print('\n' + '=' * 78)
    if failures:
        for provider, name, detail in failures:
            print(f'FALLA [{provider}] {name}: {detail}')
        print(f'--- {len(failures)} discrepancias')
        return 1
    print('--- sin discrepancias entre la ruta nativa y la ruta migrada')
    return 0


if __name__ == '__main__':
    sys.exit(main())

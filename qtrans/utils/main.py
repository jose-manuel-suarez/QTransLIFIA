import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qtrans.core import translate_circuit

URL_COMPLEX_CUSTOM = (
    "https://algassert.com/quirk#circuit=%7B%22cols%22%3A%5B%5B%22H%22%2C%22H%22%5D%2C%5B%22~edqr%22%5D%2C%5B%22~cu10000%22%2C%22%E2%80%A2%22%5D%2C%5B%22%E2%80%A2%22%2C%22~cu10001%22%5D%2C%5B%22~ipt0%22%2C%22~pi31%22%5D%2C%5B%22Measure%22%2C%22Measure%22%5D%5D%2C%22gates%22%3A%5B%7B%22id%22%3A%22~cu10000%22%2C%22name%22%3A%22cu1%28pi%20%2F%20512%29%22%2C%22matrix%22%3A%22%7B%7B1%2C0%7D%2C%7B0%2C0.9999811753%2B0.006135884649i%7D%7D%22%7D%2C%7B%22id%22%3A%22~cu10001%22%2C%22name%22%3A%22cu1%28pi%20%2F%20256%29%22%2C%22matrix%22%3A%22%7B%7B1%2C0%7D%2C%7B0%2C0.9999247018%2B0.01227153829i%7D%7D%22%7D%2C%7B%22id%22%3A%22~edqr%22%2C%22name%22%3A%22mia%22%2C%22matrix%22%3A%22%7B%7B0.5341571-0.0812871i%2C-0.2911111%2B0.3243367i%2C0.2354813-0.5239272i%2C-0.3141007%2B0.2991959i%7D%2C%7B0.0922618-0.0590391i%2C0.1507841%2B0.3020887i%2C0.5312675%2B0.5239244i%2C0.3141036%2B0.4675529i%7D%2C%7B0.664025%2B0.1403262i%2C0.6640229-0.1403212i%2C-0.1403227%2B0.1403248i%2C-0.1403248-0.1403227i%7D%2C%7B0.3593634%2B0.3260492i%2C-0.3593634-0.3260492i%2C-0.2667888-0.0524325i%2C0.6329801%2B0.2334746i%7D%7D%22%7D%2C%7B%22id%22%3A%22~ipt0%22%2C%22name%22%3A%22jo%22%2C%22matrix%22%3A%22%7B%7B0.9512512%2B0.1677313i%2C0.0449435-0.254887i%7D%2C%7B0.0449435-0.254887i%2C0.9512512%2B0.1677313i%7D%7D%22%7D%2C%7B%22id%22%3A%22~rfnt%22%2C%22name%22%3A%22pi%22%2C%22matrix%22%3A%22%7B%7B0.9238795%2C-0.3826834i%7D%2C%7B-0.3826834i%2C0.9238795%7D%7D%22%7D%2C%7B%22id%22%3A%22~bkbo%22%2C%22name%22%3A%22prueba%22%2C%22matrix%22%3A%22%7B%7B0.9238795%2C-0.2705981-0.2705981i%7D%2C%7B0.2705981-0.2705981i%2C0.9238795%7D%7D%22%7D%2C%7B%22id%22%3A%22~pi31%22%2C%22name%22%3A%223ejes%22%2C%22matrix%22%3A%22%7B%7B0.9238795-0.2209424i%2C-0.2209424-0.2209424i%7D%2C%7B0.2209424-0.2209424i%2C0.9238795%2B0.2209424i%7D%7D%22%7D%2C%7B%22id%22%3A%22~f0b8%22%2C%22name%22%3A%22complex_rotation%22%2C%22matrix%22%3A%22%7B%7B0.6338146-0.3885086i%2C-0.4025149-0.5341553i%7D%2C%7B0.5341553-0.4025149i%2C0.5021742%2B0.5481615i%7D%7D%22%7D%5D%7D"
)

# Payload de translate_circuit con la estructura completa y valores por defecto.
payload_one_gate = {
    "input": {
        "url": URL_COMPLEX_CUSTOM,
        "offset": 0,
        "qasm_version": "3.0",
        "provider": "qiskit",
        "shots": 1000,
        "preserve_custom_gates": True,
        "zx": {"enabled": False, "time": 0.5, "timeout": 120},
        "images": {
            "quirk": False,
            "qasm": False,
            "composer": False,
            "capture_timeout": 15,
        },
        "comparison": False,
        "return_circuit": True,
    }
}

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

result = translate_circuit(payload_one_gate)
# Con return_circuit=True, output.circuits trae objetos vivos (QuantumCircuit,
# Circuit, QNode): se imprimen como texto y siguen disponibles en `result`.
print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

output = result["output"]

print("\n===== output.qasm.code =====")
print(output["qasm"]["code"])

print("\n===== output.migrated_code =====")
for provider, code in output["migrated_code"].items():
    print(f"\n--- {provider} ---")
    print(code)

print("\n===== output.circuits =====")
for provider, circuit in (output["circuits"] or {}).items():
    print(f"\n--- {provider} ---")
    print(circuit)

# Circuito nativo retornado por translate_circuit (requiere return_circuit=True).
circuitos = output["circuits"] or {}
circuito = circuitos.get("qiskit") or next(
    (c for c in circuitos.values() if c is not None), None
)


def _simular_qiskit(circuito, shots, seed):
    """Simula un ``QuantumCircuit`` de Qiskit con Aer y devuelve los conteos.

    Parámetros:
        - circuito (QuantumCircuit): circuito a simular.
        - shots (int): cantidad de ejecuciones.
        - seed (int): semilla reproducible.

    Retorna:
        - dict: conteos ``{bitstring: ocurrencias}``.
    """
    from qiskit import transpile

    # Sin mediciones no hay conteos: se añaden sobre una copia.
    if circuito.count_ops().get("measure", 0) == 0:
        circuito = circuito.measure_all(inplace=False)

    try:
        from qiskit_aer import AerSimulator
    except ImportError:
        from qiskit.primitives import StatevectorSampler

        sampler = StatevectorSampler(default_shots=shots, seed=seed)
        return sampler.run([circuito]).result()[0].join_data().get_counts()

    simulador = AerSimulator()
    compilado = transpile(circuito, simulador, seed_transpiler=seed)
    return simulador.run(
        compilado, shots=shots, seed_simulator=seed
    ).result().get_counts()


def _simular_braket(circuito, shots):
    """Simula un ``Circuit`` de Braket con su simulador local.

    Parámetros:
        - circuito (Circuit): circuito a simular.
        - shots (int): cantidad de ejecuciones.

    Retorna:
        - dict: conteos ``{bitstring: ocurrencias}``.
    """
    from braket.circuits.measure import Measure
    from braket.devices import LocalSimulator

    # Sin mediciones no hay conteos: se añaden sobre una copia.
    if not any(isinstance(i.operator, Measure) for i in circuito.instructions):
        circuito = circuito.copy()
        circuito.measure(range(circuito.qubit_count))
    resultado = LocalSimulator().run(circuito, shots=shots).result()
    return dict(resultado.measurement_counts)


def simular_circuito(circuito, shots=1024, seed=1234):
    """Ejecuta un circuito nativo en un simulador local y devuelve los conteos.

    Soporta ``QuantumCircuit`` de Qiskit (AerSimulator) y ``Circuit`` de Braket
    (LocalSimulator). Para PennyLane (``QNode``) no hay simulación genérica.

    Parámetros:
        - circuito: circuito nativo retornado por ``translate_circuit``.
        - shots (int): cantidad de ejecuciones simuladas.
        - seed (int): semilla reproducible (solo Qiskit/Aer).

    Retorna:
        - dict: conteos ``{bitstring: ocurrencias}``.

    Lanza:
        - RuntimeError: si no se recibió un circuito.
        - TypeError: si el tipo de circuito no es soportado.
    """
    if circuito is None:
        raise RuntimeError(
            'No hay circuito para simular: activa "return_circuit": True en el payload.'
        )
    modulo = type(circuito).__module__
    if modulo.startswith("braket"):
        return _simular_braket(circuito, shots)
    if modulo.startswith("qiskit"):
        return _simular_qiskit(circuito, shots, seed)
    raise TypeError(f"Circuito no soportado para simulación: {type(circuito)!r}")


def imprimir_conteos(conteos, shots):
    """Imprime los conteos ordenados por frecuencia y el total de shots.

    Parámetros:
        - conteos (dict): ``{bitstring: ocurrencias}``.
        - shots (int): total de ejecuciones (para los porcentajes).

    Retorna:
        - None
    """
    for estado, ocurrencias in sorted(
        conteos.items(), key=lambda kv: (-kv[1], kv[0])
    ):
        print(f"{estado}: {ocurrencias:5d}  ({100 * ocurrencias / shots:6.2f} %)")
    print(f"total: {sum(conteos.values())} shots")


SHOTS = 1024
conteos = simular_circuito(circuito, shots=SHOTS)

print(f"\n********** simulación ({SHOTS} shots) **********")
imprimir_conteos(conteos, SHOTS)


# ===========================================================================
# Modo batch: 2 URLs Quirk + Braket con return_circuit=True
# ===========================================================================
URL_4X4 = (
    "https://algassert.com/quirk#circuit=%7B%22cols%22%3A%5B%5B%22H%22%2C"
    "%22H%22%5D%2C%5B%22~2utn%22%5D%5D%2C%22gates%22%3A%5B%7B%22id%22%3A"
    "%22~2onn%22%2C%22name%22%3A%22x20%22%2C%22matrix%22%3A%22%7B%7B0."
    "9848078%2C-0.1736482i%7D%2C%7B-0.1736482i%2C0.9848078%7D%7D%22%7D"
    "%2C%7B%22id%22%3A%22~1tvc%22%2C%22name%22%3A%22xy20%22%2C%22matrix"
    "%22%3A%22%7B%7B0.9848078%2C-0.1227878-0.1227878i%7D%2C%7B0.1227878"
    "-0.1227878i%2C0.9848078%7D%7D%22%7D%2C%7B%22id%22%3A%22~egdf%22%2C"
    "%22name%22%3A%22xyz20%22%2C%22matrix%22%3A%22%7B%7B0.9848078-0."
    "1002558i%2C-0.1002558-0.1002558i%7D%2C%7B0.1002558-0.1002558i%2C0."
    "9848078%2B0.1002558i%7D%7D%22%7D%2C%7B%22id%22%3A%22~pt7e%22%2C"
    "%22name%22%3A%22y20%22%2C%22matrix%22%3A%22%7B%7B0.9848078%2C-0."
    "1736482%7D%2C%7B0.1736482%2C0.9848078%7D%7D%22%7D%2C%7B%22id%22%3A"
    "%22~aebp%22%2C%22name%22%3A%22z20%22%2C%22matrix%22%3A%22%7B%7B0."
    "9848078-0.1736482i%2C0%7D%2C%7B0%2C0.9848078%2B0.1736482i%7D%7D%22"
    "%7D%2C%7B%22id%22%3A%22~2sp8%22%2C%22name%22%3A%22xz20%22%2C"
    "%22matrix%22%3A%22%7B%7B0.9848078-0.1227878i%2C-0.1227878i%7D%2C"
    "%7B-0.1227878i%2C0.9848078%2B0.1227878i%7D%7D%22%7D%2C%7B%22id%22"
    "%3A%22~15ma%22%2C%22name%22%3A%22yz20%22%2C%22matrix%22%3A%22%7B"
    "%7B0.9848078-0.1227878i%2C-0.1227878%7D%2C%7B0.1227878%2C0.9848078"
    "%2B0.1227878i%7D%7D%22%7D%2C%7B%22id%22%3A%22~2utn%22%2C%22name%22"
    "%3A%224x4%22%2C%22matrix%22%3A%22%7B%7B%E2%88%9A%C2%BD%2C0%2C0%2C"
    "%E2%88%9A%C2%BD%7D%2C%7B0%2C1%2C0%2C0%7D%2C%7B0%2C0%2C1%2C0%7D%2C"
    "%7B-%E2%88%9A%C2%BD%2C0%2C0%2C%E2%88%9A%C2%BD%7D%7D%22%7D%5D%7D"
)

payload_batch = {
    "input": {
        "circuits": [
            {"name": "circuito_actual", "url": URL_COMPLEX_CUSTOM},
            {"name": "custom_4x4", "url": URL_4X4},
        ],
        "qasm_version": "3.0",
        "provider": "braket",
        "shots": 1000,
        "preserve_custom_gates": True,
        "zx": {"enabled": False, "time": 0.5, "timeout": 120},
        "images": {
            "quirk": False,
            "qasm": False,
            "composer": False,
            "capture_timeout": 15,
        },
        "comparison": False,
        "return_circuit": True,
    }
}

print("\n\n===== MODO BATCH: 2 URLs + Braket =====")
result_batch = translate_circuit(payload_batch)
print(json.dumps(result_batch, indent=2, ensure_ascii=False, default=str))

salida_batch = result_batch["output"]
print(f"\n===== circuitos generados: {len(salida_batch)} =====")
for item in salida_batch:
    print(f"\n--- {item['name']} ---")
    print(item["circuits"]["braket"])

print(f"\n**********simulación batch ({SHOTS} shots) **********")
for item in salida_batch:
    conteos_item = simular_circuito(item["circuits"]["braket"], shots=SHOTS)
    print(f"\n--- {item['name']} ---")
    imprimir_conteos(conteos_item, SHOTS)

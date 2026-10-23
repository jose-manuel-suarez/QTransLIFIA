import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qtrans.core import translate_circuit

# Payload de translate_circuit con la estructura completa y valores por defecto.
payload = {
    "input": {
        "url": (
            "https://algassert.com/quirk#circuit=%7B%22cols%22%3A%5B%5B%22H%22%2C%22H%22%5D%2C%5B%22~edqr%22%5D%2C%5B%22~cu10000%22%2C%22%E2%80%A2%22%5D%2C%5B%22%E2%80%A2%22%2C%22~cu10001%22%5D%2C%5B%22~ipt0%22%2C%22~pi31%22%5D%2C%5B%22Measure%22%2C%22Measure%22%5D%5D%2C%22gates%22%3A%5B%7B%22id%22%3A%22~cu10000%22%2C%22name%22%3A%22cu1%28pi%20%2F%20512%29%22%2C%22matrix%22%3A%22%7B%7B1%2C0%7D%2C%7B0%2C0.9999811753%2B0.006135884649i%7D%7D%22%7D%2C%7B%22id%22%3A%22~cu10001%22%2C%22name%22%3A%22cu1%28pi%20%2F%20256%29%22%2C%22matrix%22%3A%22%7B%7B1%2C0%7D%2C%7B0%2C0.9999247018%2B0.01227153829i%7D%7D%22%7D%2C%7B%22id%22%3A%22~edqr%22%2C%22name%22%3A%22mia%22%2C%22matrix%22%3A%22%7B%7B0.5341571-0.0812871i%2C-0.2911111%2B0.3243367i%2C0.2354813-0.5239272i%2C-0.3141007%2B0.2991959i%7D%2C%7B0.0922618-0.0590391i%2C0.1507841%2B0.3020887i%2C0.5312675%2B0.5239244i%2C0.3141036%2B0.4675529i%7D%2C%7B0.664025%2B0.1403262i%2C0.6640229-0.1403212i%2C-0.1403227%2B0.1403248i%2C-0.1403248-0.1403227i%7D%2C%7B0.3593634%2B0.3260492i%2C-0.3593634-0.3260492i%2C-0.2667888-0.0524325i%2C0.6329801%2B0.2334746i%7D%7D%22%7D%2C%7B%22id%22%3A%22~ipt0%22%2C%22name%22%3A%22jo%22%2C%22matrix%22%3A%22%7B%7B0.9512512%2B0.1677313i%2C0.0449435-0.254887i%7D%2C%7B0.0449435-0.254887i%2C0.9512512%2B0.1677313i%7D%7D%22%7D%2C%7B%22id%22%3A%22~rfnt%22%2C%22name%22%3A%22pi%22%2C%22matrix%22%3A%22%7B%7B0.9238795%2C-0.3826834i%7D%2C%7B-0.3826834i%2C0.9238795%7D%7D%22%7D%2C%7B%22id%22%3A%22~bkbo%22%2C%22name%22%3A%22prueba%22%2C%22matrix%22%3A%22%7B%7B0.9238795%2C-0.2705981-0.2705981i%7D%2C%7B0.2705981-0.2705981i%2C0.9238795%7D%7D%22%7D%2C%7B%22id%22%3A%22~pi31%22%2C%22name%22%3A%223ejes%22%2C%22matrix%22%3A%22%7B%7B0.9238795-0.2209424i%2C-0.2209424-0.2209424i%7D%2C%7B0.2209424-0.2209424i%2C0.9238795%2B0.2209424i%7D%7D%22%7D%2C%7B%22id%22%3A%22~f0b8%22%2C%22name%22%3A%22complex_rotation%22%2C%22matrix%22%3A%22%7B%7B0.6338146-0.3885086i%2C-0.4025149-0.5341553i%7D%2C%7B0.5341553-0.4025149i%2C0.5021742%2B0.5481615i%7D%7D%22%7D%5D%7D"
        ),
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

result = translate_circuit(payload)
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


def simular_circuito(circuito, shots=1024, seed=1234):
    """Ejecuta un circuito en un simulador local y devuelve los conteos.

    Parámetros:
        - circuito: circuito nativo (p. ej. ``QuantumCircuit`` de Qiskit).
        - shots (int): cantidad de ejecuciones simuladas.
        - seed (int): semilla para que la corrida sea reproducible.

    Retorna:
        - dict: conteos ``{bitstring: ocurrencias}``.

    Lanza:
        - RuntimeError: si no se recibió un circuito.
    """
    if circuito is None:
        raise RuntimeError(
            'No hay circuito para simular: activa "return_circuit": True en el payload.'
        )
    from qiskit import transpile

    try:
        from qiskit_aer import AerSimulator
    except ImportError:
        # Respaldo sin qiskit-aer (el circuito ya trae sus mediciones).
        from qiskit.primitives import StatevectorSampler

        sampler = StatevectorSampler(default_shots=shots, seed=seed)
        data = sampler.run([circuito]).result()[0].join_data()
        return data.get_counts()

    simulador = AerSimulator()
    compilado = transpile(circuito, simulador, seed_transpiler=seed)
    resultado = simulador.run(
        compilado, shots=shots, seed_simulator=seed
    ).result()
    return resultado.get_counts()


SHOTS = 1024
conteos = simular_circuito(circuito, shots=SHOTS)

print(f"\n===== simulación ({SHOTS} shots) =====")
for estado, ocurrencias in sorted(conteos.items(), key=lambda kv: (-kv[1], kv[0])):
    print(f"{estado}: {ocurrencias:5d}  ({100 * ocurrencias / SHOTS:6.2f} %)")
print(f"total: {sum(conteos.values())} shots")

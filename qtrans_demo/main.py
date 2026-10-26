# -*- coding: utf-8 -*-
"""Demo aislado de QTransLIFIA: traducción y simulación de 1024 shots.

Lee los circuitos de ``input/custom_gates_algorithms.json``, los traduce con la
librería instalada desde PyPI (``qtranslifia``) y simula cada circuito Qiskit
con 1024 shots usando Qiskit Aer.
"""

import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = (BASE_DIR / "demo_venv").resolve()
load_dotenv(BASE_DIR / ".env")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

if Path(sys.prefix).resolve() != VENV_DIR:
    raise SystemExit(
        "Este demo debe ejecutarse con su propio entorno.\n"
        f"  esperado: {VENV_DIR}\n"
        f"  actual:   {Path(sys.prefix).resolve()}\n"
        "Activá el entorno con: source qtrans_demo/demo_venv/Scripts/activate"
    )

import qtrans  # noqa: E402

QTRANS_PATH = Path(qtrans.__file__).resolve()
if VENV_DIR not in QTRANS_PATH.parents:
    raise SystemExit(
        "qtrans no se importó desde el .venv del demo.\n"
        f"  importado: {QTRANS_PATH}\n"
        f"  esperado dentro de: {VENV_DIR}\n"
        "Quitá el repositorio del PYTHONPATH y reinstalá requirements.txt."
    )


def _env(name, default):
    """Devuelve una variable de entorno no vacía o su valor por defecto."""
    value = (os.getenv(name) or "").strip()
    return value or default


def _env_bool(name, default):
    """Interpreta una variable de entorno booleana."""
    value = _env(name, str(default)).casefold()
    return value in {"1", "true", "yes", "on", "si", "sí"}


def _env_int(name, default):
    """Interpreta una variable de entorno entera."""
    return int(_env(name, str(default)))


INPUT_FILE = BASE_DIR / _env("QTRANS_INPUT_FILE", "input/custom_gates_algorithms.json")
OUTPUT_DIR = BASE_DIR / _env("QTRANS_OUTPUT_DIR", "output")
QASM_VERSION = _env("QTRANS_QASM_VERSION", "3.0")
SHOTS = _env_int("QTRANS_SHOTS", 1024)
SEED = _env_int("QTRANS_SEED", 1234)
PRESERVE_CUSTOM_GATES = _env_bool("QTRANS_PRESERVE_CUSTOM_GATES", True)
ZX_ENABLED = _env_bool("QTRANS_GENERATE_ZX", False)
PROVIDERS = [
    value.strip()
    for value in _env("QTRANS_TARGET_PROVIDERS", "qiskit").split(",")
    if value.strip()
]
PROVIDER = PROVIDERS[0] if PROVIDERS else "qiskit"


def _safe_name(name):
    """Convierte el nombre de un algoritmo en un nombre de archivo seguro."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "circuito"


def build_payload(records):
    """Construye el payload de ``translate_circuit`` a partir del registro JSON.

    Parámetros:
        - records (dict): registro ``{nombre: {desc, url, offset}}``.

    Retorna:
        - dict: payload con el lote de circuitos y la configuración del ``.env``.
    """
    circuits = [
        {
            "name": name,
            "url": data["url"],
            "offset": int(data.get("offset", 0)),
        }
        for name, data in records.items()
    ]
    return {
        "input": {
            "circuits": circuits,
            "qasm_version": QASM_VERSION,
            "provider": PROVIDER,
            "shots": SHOTS,
            "preserve_custom_gates": PRESERVE_CUSTOM_GATES,
            "zx": {"enabled": ZX_ENABLED, "time": 0.5, "timeout": 120},
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


def simulate_qiskit(circuit, shots, seed):
    """Simula un ``QuantumCircuit`` de Qiskit y devuelve los conteos.

    Parámetros:
        - circuit (QuantumCircuit): circuito a simular.
        - shots (int): cantidad de ejecuciones.
        - seed (int): semilla reproducible.

    Retorna:
        - dict: conteos ``{bitstring: ocurrencias}``.
    """
    from qiskit import transpile

    if circuit.count_ops().get("measure", 0) == 0:
        circuit = circuit.copy()
        if circuit.num_clbits >= circuit.num_qubits:
            circuit.measure(
                range(circuit.num_qubits), range(circuit.num_qubits)
            )
        else:
            circuit = circuit.measure_all(inplace=False)

    try:
        from qiskit_aer import AerSimulator
    except ImportError:
        from qiskit.primitives import StatevectorSampler

        sampler = StatevectorSampler(default_shots=shots, seed=seed)
        return sampler.run([circuit]).result()[0].join_data().get_counts()

    simulator = AerSimulator()
    compiled = transpile(circuit, simulator, seed_transpiler=seed)
    return simulator.run(
        compiled, shots=shots, seed_simulator=seed
    ).result().get_counts()


def print_counts(counts, shots):
    """Imprime los conteos ordenados por frecuencia y el total de shots."""
    for state, occurrences in sorted(
        counts.items(), key=lambda item: (-item[1], item[0])
    ):
        print(f"  {state}: {occurrences:5d}  ({100 * occurrences / shots:6.2f} %)")
    print(f"  total: {sum(counts.values())} shots")


def save_outputs(name, output, counts):
    """Guarda QASM, scripts migrados y conteos en el directorio ``output``.

    Parámetros:
        - name (str): nombre del algoritmo.
        - output (dict): salida de ``translate_circuit`` para ese circuito.
        - counts (dict | None): conteos de la simulación.

    Retorna:
        - Path: directorio donde se escribieron los archivos.
    """
    safe = _safe_name(name)
    target = OUTPUT_DIR / safe
    target.mkdir(parents=True, exist_ok=True)

    qasm_path = target / f"{safe}_v{QASM_VERSION}.txt"
    qasm_path.write_text(output["qasm"]["code"], encoding="utf-8")

    for script_name, code in output["migrated_code"].items():
        (target / f"{safe}_{script_name}.py").write_text(code, encoding="utf-8")

    if counts is not None:
        (target / f"{safe}_counts.json").write_text(
            json.dumps(counts, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return target


def main():
    """Traduce el lote de entrada, simula cada circuito y guarda los resultados."""
    if not INPUT_FILE.exists():
        raise SystemExit(f"No existe el archivo de entrada: {INPUT_FILE}")
    if PROVIDER != "qiskit":
        raise SystemExit(
            "Este demo simula con Qiskit; configurá "
            f"QTRANS_TARGET_PROVIDERS=qiskit (valor actual: {PROVIDER})."
        )

    records = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    result = qtrans.translate_circuit(build_payload(records))
    outputs = result["output"]
    if isinstance(outputs, dict):
        outputs = [outputs]

    print(f"Python: {sys.executable}")
    print(f"qtrans: {QTRANS_PATH} ({qtrans.__version__})")
    print(f"Entrada: {INPUT_FILE}")
    print(f"Provider: {PROVIDER} | QASM: {QASM_VERSION} | Shots: {SHOTS}")
    print(f"Circuitos: {len(outputs)}")

    for output in outputs:
        name = output["name"]
        print(f"\n===== {name} =====")
        print(output["qasm"]["code"])

        for stage_error in output.get("errors") or []:
            print(f"[error de etapa] {stage_error['stage']}: {stage_error['message']}")

        circuits = output.get("circuits") or {}
        circuit = circuits.get(PROVIDER)
        if circuit is None:
            print(f"[warn] No se pudo cargar el circuito {PROVIDER}.")
            save_outputs(name, output, None)
            continue

        counts = simulate_qiskit(circuit, SHOTS, SEED)
        target = save_outputs(name, output, counts)
        print(f"\nResultados guardados en: {target}")
        print(f"\n-------- simulación ({SHOTS} shots) --------")
        print_counts(counts, SHOTS)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Demo aislado de QTransLIFIA: traducción y simulación.

Lee los circuitos de ``input/custom_gates_algorithms.json``, los traduce con
``qtrans.translate_circuit`` usando un único proveedor configurable desde
``.env`` (``QTRANS_TARGET_PROVIDERS``) y simula el circuito nativo devuelto
con ``return_circuit=True``. Las salidas se agrupan por corrida en
``output/run_DD_MM_YYYY__HH/<proveedor>/``.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = (BASE_DIR / "demo_venv").resolve()
load_dotenv(BASE_DIR / ".env")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

# Guarda temporalmente desactivada para debuggear el código local.
# if Path(sys.prefix).resolve() != VENV_DIR:
#     raise SystemExit(
#         "Este demo debe ejecutarse con su propio entorno.\n"
#         f"  esperado: {VENV_DIR}\n"
#         f"  actual:   {Path(sys.prefix).resolve()}\n"
#         "Activá el entorno con: source demo/demo_venv/Scripts/activate"
#     )

import qtrans  # noqa: E402
from qtrans.utils import pipeline_utils  # noqa: E402

# Guarda temporalmente desactivada para debuggear el código local.
# QTRANS_PATH = Path(qtrans.__file__).resolve()
# if VENV_DIR not in QTRANS_PATH.parents:
#     raise SystemExit(
#         "qtrans no se importó desde el .venv del demo.\n"
#         f"  importado: {QTRANS_PATH}\n"
#         f"  esperado dentro de: {VENV_DIR}\n"
#         "Quitá el repositorio del PYTHONPATH y reinstalá requirements.txt."
#     )


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
OUTPUT_DIR_ENV = _env("QTRANS_OUTPUT_DIR", "output")
OUTPUT_DIR = Path(OUTPUT_DIR_ENV)
if not OUTPUT_DIR.is_absolute():
    OUTPUT_DIR = (BASE_DIR / OUTPUT_DIR_ENV).resolve()

QASM_VERSION = _env("QTRANS_QASM_VERSION", "3.0")
SHOTS = _env_int("QTRANS_SHOTS", 1024)
SEED = _env_int("QTRANS_SEED", 1234)
PRESERVE_CUSTOM_GATES = _env_bool("QTRANS_PRESERVE_CUSTOM_GATES", True)
ZX_ENABLED = _env_bool("QTRANS_GENERATE_ZX", False)

_RAW_PROVIDERS = _env("QTRANS_TARGET_PROVIDERS", "qiskit")
_RAW_PROVIDERS = _RAW_PROVIDERS.replace(",", " ").replace(";", " ")
PROVIDERS = [value.strip().lower() for value in _RAW_PROVIDERS.split() if value.strip()]
if not PROVIDERS:
    PROVIDERS = ["qiskit"]

PROVIDER = PROVIDERS[0]

_ALIAS_MAP = {
    "ibm": "qiskit",
    "qiskit_ibm": "qiskit",
    "aws": "braket",
    "amazon_braket": "braket",
    "xanadu": "pennylane",
    "pl": "pennylane",
}
PROVIDER = _ALIAS_MAP.get(PROVIDER, PROVIDER)

if PROVIDER not in {"qiskit", "braket", "pennylane"}:
    raise SystemExit(
        "Proveedor no soportado por este demo. "
        f"Valor: {PROVIDER!r}. Soportados: qiskit, braket, pennylane (alias: ibm/aws/xanadu)."
    )

# Salida agrupada por corrida: output/run_DD_MM_YYYY__HH/<proveedor>/
RUN_LABEL = pipeline_utils.format_run_label("DD_MM_YYYY__HH", datetime.now())
RUN_DIR = OUTPUT_DIR / f"run_{RUN_LABEL}"


def _safe_name(name):
    """Convierte el nombre de un algoritmo en un nombre de archivo seguro."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "circuito"


def build_payload(records):
    """Construye el payload de ``translate_circuit`` con un único proveedor.

    Parámetros:
        - records (dict): registro ``{nombre: {desc, url, offset}}``.

    Retorna:
        - dict: payload con el lote de circuitos y la configuración del ``.env``.
    """
    circuits = [
        {"name": name, "url": data["url"], "offset": int(data.get("offset", 0))}
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
        },
    }


def simulate_qiskit(circuit, shots, seed):
    """Simula un ``QuantumCircuit`` de Qiskit y devuelve los conteos."""
    from qiskit import transpile

    if circuit.count_ops().get("measure", 0) == 0:
        circuit = circuit.copy()
        if circuit.num_clbits >= circuit.num_qubits:
            circuit.measure(range(circuit.num_qubits), range(circuit.num_qubits))
        else:
            circuit = circuit.measure_all(inplace=False)

    try:
        from qiskit_aer import AerSimulator

        simulator = AerSimulator()
        compiled = transpile(circuit, simulator, seed_transpiler=seed)
        return simulator.run(
            compiled, shots=shots, seed_simulator=seed
        ).result().get_counts()
    except Exception:
        from qiskit.primitives import StatevectorSampler

        sampler = StatevectorSampler(default_shots=shots, seed=seed)
        return sampler.run([circuit]).result()[0].join_data().get_counts()


def simulate_braket(circuit, shots, seed):
    """Simula un ``Circuit`` de AWS Braket con LocalSimulator.

    Braket ordena las claves de conteo con el qubit 0 a la izquierda
    (*big-endian*), al revés que Qiskit. Se invierten para que los conteos de
    los tres proveedores sean comparables entre sí.
    """
    from collections import Counter

    from braket.devices import LocalSimulator

    device = LocalSimulator()
    try:
        result = device.run(circuit, shots=shots).result()
    except Exception:
        c = circuit.copy()
        if hasattr(c, "measure_all"):
            c = c.measure_all()
        result = device.run(c, shots=shots).result()

    if hasattr(result, "measurement_counts"):
        counts = dict(result.measurement_counts)
    elif hasattr(result, "counts"):
        counts = dict(result.counts)
    else:
        raise RuntimeError("No se pudieron obtener conteos de Braket.")

    normalized = Counter()
    for key, value in counts.items():
        bitstring = str(key).replace(" ", "")
        normalized[bitstring[::-1]] += int(value)
    return dict(normalized)


def simulate_pennylane(circuit, shots, seed):
    """Simula un ``QNode`` de PennyLane y devuelve los conteos.

    El ``QNode`` devuelto por la librería ya lleva los *shots* en su device y,
    según el QASM, retorna una tupla de muestras (una por bit clásico medido)
    o el vector de estado cuando no hay mediciones. En ambos casos se construye
    el conteo con la convención de Qiskit (bit más significativo a la izquierda).
    """
    import numpy as np
    import pennylane as qml
    from collections import Counter

    qnode = circuit

    result = qnode()

    if isinstance(result, tuple):
        arrays = [np.asarray(item) for item in result]
        if arrays and all(arr.ndim == 1 and arr.size == shots for arr in arrays):
            num_bits = len(arrays)
            bitstrings = [
                "".join(str(int(arrays[k][i])) for k in range(num_bits - 1, -1, -1))
                for i in range(shots)
            ]
            return dict(Counter(bitstrings))
        raise RuntimeError(
            "PennyLane devolvió una tupla de resultados con forma inesperada."
        )

    arr = np.asarray(result)

    if arr.ndim == 1 and arr.size == shots and np.issubdtype(arr.dtype, np.integer):
        return dict(Counter(str(int(value)) for value in arr))

    if arr.ndim == 1 and np.iscomplexobj(arr):
        num_qubits = qml.math.log2(arr.size)
        num_qubits = int(round(num_qubits))
        probabilities = np.abs(arr) ** 2
        probabilities = probabilities / probabilities.sum()
        rng = np.random.default_rng(seed)
        indices = rng.choice(arr.size, size=shots, p=probabilities)
        bitstrings = [format(int(idx), f"0{num_qubits}b") for idx in indices]
        return dict(Counter(bitstrings))

    raise RuntimeError(
        f"No se pudo interpretar el resultado de PennyLane (tipo {type(result)})."
    )


def print_counts(counts, shots):
    """Imprime los conteos ordenados por frecuencia y el total de shots."""
    for state, occurrences in sorted(
        counts.items(), key=lambda item: (-item[1], item[0])
    ):
        print(f"  {state}: {occurrences:5d}  ({100 * occurrences / shots:6.2f} %)")
    print(f"  total: {sum(counts.values())} shots")


def _text_diagram_figure(text):
    """Convierte un diagrama de texto en una figura de matplotlib.

    Parámetros:
        - text (str): diagrama en texto plano o Unicode.

    Retorna:
        - matplotlib.figure.Figure: figura con el diagrama renderizado.
    """
    import matplotlib.pyplot as plt

    lines = text.splitlines() or [""]
    width = max(6.0, max(len(line) for line in lines) * 0.09)
    height = max(2.0, len(lines) * 0.25)
    figure = plt.figure(figsize=(width, height))
    axes = figure.add_axes([0, 0, 1, 1])
    axes.axis("off")
    axes.text(0.01, 0.99, text, family="monospace", fontsize=8, va="top", ha="left")
    return figure


def save_circuit_image(circuit, provider, target, safe):
    """Guarda un diagrama PNG del circuito nativo en ``target``.

    Parámetros:
        - circuit: objeto nativo (``QuantumCircuit``, ``Circuit`` o ``QNode``).
        - provider (str): proveedor del circuito (``qiskit``/``braket``/``pennylane``).
        - target (Path): directorio de salida del algoritmo.
        - safe (str): nombre saneado del algoritmo.

    Retorna:
        - Path | None: ruta del PNG escrito o ``None`` si no se pudo dibujar.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    image_path = target / f"{safe}_circuit_{provider}.png"
    try:
        if provider == "qiskit":
            figure = circuit.draw(output="mpl")
        elif provider == "pennylane":
            import pennylane as qml

            figure, _ = qml.draw_mpl(circuit)()
        elif provider == "braket":
            figure = _text_diagram_figure(circuit.diagram())
        else:
            print(f"[warn] Sin dibujador para {provider}.")
            return None
        figure.savefig(image_path, dpi=150, bbox_inches="tight")
        plt.close(figure)
    except Exception as exc:
        print(f"[warn] No se pudo generar la imagen del circuito: {exc}")
        return None
    return image_path


def save_payload(payload, result):
    """Guarda el payload de entrada y la salida de ``translate_circuit``.

    Los objetos nativos de ``output["circuits"]`` no son serializables a JSON,
    así que se representan con ``repr`` para poder escribir el archivo.

    Parámetros:
        - payload (dict): entrada enviada a ``translate_circuit``.
        - result (dict): valor devuelto por ``translate_circuit``.

    Retorna:
        - tuple[Path, Path]: rutas de ``input.json`` y ``output.json``.
    """
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    input_path = RUN_DIR / "input.json"
    output_path = RUN_DIR / "output.json"
    input_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=repr) + "\n",
        encoding="utf-8",
    )
    return input_path, output_path


def save_qasm_image(qasm_code, target, safe):
    """Genera un PNG del circuito OpenQASM usando Qiskit.

    A diferencia de Braket y PennyLane, el parser nativo de Qiskit conserva los
    nombres de las compuertas custom declaradas con ``gate``.

    Parámetros:
        - qasm_code (str): código OpenQASM traducido.
        - target (Path): directorio de salida del algoritmo.
        - safe (str): nombre saneado del algoritmo.

    Retorna:
        - Path | None: ruta del PNG escrito o ``None`` si no se pudo dibujar.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from qtrans.utils.qiskit_utils import load_qasm_circuit

    image_path = target / f"{safe}_circuit_qasm.png"
    try:
        circuit = load_qasm_circuit(qasm_code)
        figure = circuit.draw(output="mpl")
        figure.savefig(image_path, dpi=150, bbox_inches="tight")
        plt.close(figure)
    except Exception as exc:
        print(f"[warn] No se pudo generar la imagen del QASM: {exc}")
        return None
    return image_path


def save_outputs(name, output, counts, circuit=None):
    """Guarda QASM, scripts migrados, conteos y diagrama en ``output/run_*/<proveedor>/``.

    Parámetros:
        - name (str): nombre del algoritmo.
        - output (dict): salida de ``translate_circuit`` para ese circuito.
        - counts (dict | None): conteos de la simulación.
        - circuit: circuito nativo para generar el PNG (opcional).

    Retorna:
        - Path: directorio donde se escribieron los archivos.
    """
    safe = _safe_name(name)
    target = RUN_DIR / PROVIDER / safe
    target.mkdir(parents=True, exist_ok=True)

    qasm_path = target / f"{safe}_v{QASM_VERSION}.txt"
    qasm_path.write_text(output["qasm"]["code"], encoding="utf-8")

    for script_name, code in (output.get("migrated_code") or {}).items():
        (target / f"{safe}_{script_name}.py").write_text(code, encoding="utf-8")

    qasm_image = save_qasm_image(output["qasm"]["code"], target, safe)
    if qasm_image is not None:
        print(f"Diagrama QASM guardado en: {qasm_image}")

    if circuit is not None:
        image_path = save_circuit_image(circuit, PROVIDER, target, safe)
        if image_path is not None:
            print(f"Diagrama del proveedor guardado en: {image_path}")

    if counts is not None:
        (target / f"{safe}_counts_{PROVIDER}.json").write_text(
            json.dumps(counts, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return target


def main():
    """Traduce el lote con un único proveedor y simula los circuitos nativos."""
    if not INPUT_FILE.exists():
        raise SystemExit(f"No existe el archivo de entrada: {INPUT_FILE}")

    records = json.loads(INPUT_FILE.read_text(encoding="utf-8"))

    print(f"Python: {sys.executable}")
    print(f"qtrans: {Path(qtrans.__file__).resolve()} ({qtrans.__version__})")
    print(f"Entrada: {INPUT_FILE}")
    print(f"Proveedor: {PROVIDER} | QASM: {QASM_VERSION} | Shots: {SHOTS}")
    print(f"preserve_custom_gates: {PRESERVE_CUSTOM_GATES}")
    print(f"Run dir: {RUN_DIR}")

    payload = build_payload(records)
    try:
        result = qtrans.translate_circuit(payload)
    except Exception as exc:
        raise SystemExit(f"translate_circuit falló: {exc}") from exc

    input_path, output_path = save_payload(payload, result)
    print(f"Payload de entrada guardado en: {input_path}")
    print(f"Resultado guardado en: {output_path}")

    outputs = result.get("output")
    if isinstance(outputs, dict):
        outputs = [outputs]
    if not outputs:
        raise SystemExit("translate_circuit no devolvió ningún circuito.")

    for output in outputs:
        name = output.get("name") or "circuito"
        print(f"\n===== {name} [{PROVIDER}] =====")
        print(output["qasm"]["code"])

        for stage_error in output.get("errors") or []:
            print(f"[error de etapa] {stage_error['stage']}: {stage_error['message']}")

        zx_calculus = output.get("zx_calculus")
        if isinstance(zx_calculus, dict):
            method = zx_calculus.get("method")
            suffix = f" ({method})" if method else ""
            print(f"[ZX] {zx_calculus.get('result')}{suffix}")
            for zx_error in zx_calculus.get("errors") or []:
                print(f"[error ZX] {zx_error['stage']}: {zx_error['message']}")
        elif "zx_calculus_result" in output:
            print(f"[ZX] {output.get('zx_calculus_result')}")

        circuits = output.get("circuits") or {}
        circuit = circuits.get(PROVIDER)
        if circuit is None:
            print(f"[warn] No se pudo cargar el circuito nativo para {PROVIDER}.")
            save_outputs(name, output, None)
            continue

        try:
            if PROVIDER == "qiskit":
                counts = simulate_qiskit(circuit, SHOTS, SEED)
            elif PROVIDER == "braket":
                counts = simulate_braket(circuit, SHOTS, SEED)
            elif PROVIDER == "pennylane":
                counts = simulate_pennylane(circuit, SHOTS, SEED)
            else:
                print(f"[warn] Sin simulador para {PROVIDER}.")
                save_outputs(name, output, None, circuit)
                continue
        except Exception as exc:
            print(f"[error simulación {PROVIDER}] {exc}")
            save_outputs(name, output, None, circuit)
            continue

        target = save_outputs(name, output, counts, circuit)
        print(f"\nResultados guardados en: {target}")
        print(f"\n-------- simulación {PROVIDER} ({SHOTS} shots) --------")
        print_counts(counts, SHOTS)


if __name__ == "__main__":
    main()

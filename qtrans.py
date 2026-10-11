"""Quirk-to-OpenQASM pipeline de QTransLIFIA (librería + CLI).

Reproduce el flujo del cuaderno ``notebooks/QTrans_LIFIA_algorithms_jose.ipynb``:
lee los JSON de entrada, captura los circuitos Quirk, traduce a OpenQASM,
genera diagramas y comparaciones, construye y compara grafos ZX y migra cada
circuito a los ecosistemas objetivo (Qiskit, AWS Braket, PennyLane), incluidas
las imágenes de los circuitos migrados con el estilo de IBM Quantum Composer.

Todas las salidas se agrupan por corrida en ``<output>/run_DD_MM_YYYY__HH``
(fecha y hora sin minutos).
"""

# Importación de las librerías estándar y configuración del entorno
import argparse
import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from utils.qutils import (
    capture_quirk_circuit,
    provider_python_source,
    qasm_to_zx_graph,
    quirk_to_qasm,
    quirk_to_zx_graph,
)

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


# ---------------------------------------------------------------------------
# Configuración (variables QTRANS_* en .env)
# ---------------------------------------------------------------------------
def _configured_path(variable_name, default):
    configured_value = os.getenv(variable_name)
    if configured_value:
        path = Path(configured_value).expanduser()
        if not path.is_absolute():
            # Un separador inicial ("/output") denota una ruta relativa a la raíz del proyecto.
            path = PROJECT_ROOT / str(path).lstrip("/\\")
        return path.resolve()
    return Path(default).expanduser().resolve()


def _configured_bool(variable_name, default):
    configured_value = os.getenv(variable_name)
    if configured_value is None:
        return default
    normalized_value = configured_value.strip().casefold()
    if normalized_value in {"1", "true", "yes", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{variable_name} debe ser un booleano (true/false): {configured_value!r}")


def _configured_int(variable_name, default, minimum=1):
    configured_value = os.getenv(variable_name)
    value = default if configured_value is None else int(configured_value)
    if value < minimum:
        raise ValueError(f"{variable_name} debe ser >= {minimum}: {value}")
    return value


def _configured_float(variable_name, default, minimum=None, maximum=None):
    configured_value = os.getenv(variable_name)
    value = default if configured_value is None else float(configured_value)
    if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        raise ValueError(f"{variable_name} fuera de rango: {value}")
    return value


def _configured_qasm_version():
    version = os.getenv("QTRANS_QASM_VERSION", "3.0").strip()
    if version not in {"2.0", "3.0"}:
        raise ValueError("QTRANS_QASM_VERSION debe ser 2.0 o 3.0")
    return version


SUPPORTED_PROVIDERS = ("ibm_qiskit", "aws_braket", "pennylane")
# Nombre del subdirectorio por provider (coincide con el cuaderno).
PROVIDER_DIRECTORY = {
    "ibm_qiskit": "qiskit",
    "aws_braket": "aws_braket",
    "pennylane": "pennylane",
}


def _parse_target_providers(value):
    values = value.split(",") if isinstance(value, str) else value
    providers = []
    for provider_value in values:
        for provider in str(provider_value).split(","):
            normalized = provider.strip().casefold()
            if not normalized:
                continue
            if normalized not in SUPPORTED_PROVIDERS:
                raise ValueError(
                    f"Provider no soportado: {normalized!r}; opciones: "
                    f"{', '.join(SUPPORTED_PROVIDERS)}"
                )
            if normalized not in providers:
                providers.append(normalized)
    if not providers:
        raise ValueError("target_providers debe contener al menos un provider")
    return tuple(providers)


DEFAULT_INPUT_MODE = (os.getenv("QTRANS_INPUT_MODE") or "batch").strip().casefold()
if DEFAULT_INPUT_MODE not in {"batch", "algorithm"}:
    raise ValueError("QTRANS_INPUT_MODE debe ser 'batch' o 'algorithm'")
DEFAULT_INPUT_FILE = os.getenv("QTRANS_INPUT_FILE") or None
DEFAULT_INPUT_DIR = _configured_path("QTRANS_INPUT_DIR", PROJECT_ROOT / "input")
DEFAULT_OUTPUT_DIR = _configured_path("QTRANS_OUTPUT_DIR", PROJECT_ROOT / "output")
DEFAULT_RUN_LABEL = (os.getenv("QTRANS_RUN_LABEL") or "").strip() or None

# Subdirectorios (relativos a la corrida) que replican la estructura del cuaderno.
RUN_QASM_SUBDIR = "algorithms_qasm"
RUN_IMGS_SUBDIR = "imgs"
RUN_QUIRK_IMAGES_SUBDIR = "imgs/circuits_quirk"
RUN_QASM_IMAGES_SUBDIR = "imgs/circuits_qasm"
RUN_COMPARE_SUBDIR = "imgs/visual_comparations"
RUN_ZX_SUBDIR = "ZXCalculus"
RUN_MIGRATED_SUBDIR = "migrated_circuits"
RUN_COMPOSER_IMAGES_SUBDIR = "migrated_circuits/qiskit/imgs"

DEFAULT_CAPTURE_IMAGES = _configured_bool("QTRANS_CAPTURE_IMAGES", True)
DEFAULT_GENERATE_QASM_IMAGES = _configured_bool("QTRANS_GENERATE_QASM_IMAGES", True)
DEFAULT_GENERATE_COMPARISON = _configured_bool("QTRANS_GENERATE_COMPARISON", True)
DEFAULT_GENERATE_COMPOSER_IMAGES = _configured_bool("QTRANS_GENERATE_COMPOSER_IMAGES", True)
DEFAULT_GENERATE_ZX = _configured_bool("QTRANS_GENERATE_ZX", True)
DEFAULT_GENERATE_ZX_IMAGES = _configured_bool("QTRANS_GENERATE_ZX_IMAGES", True)
DEFAULT_VERBOSE = _configured_bool("QTRANS_VERBOSE", True)
DEFAULT_QASM_VERSION = _configured_qasm_version()
DEFAULT_ZX_TIME = _configured_float("QTRANS_ZX_TIME", 0.5, minimum=0.0, maximum=1.0)
DEFAULT_SHOTS = _configured_int("QTRANS_SHOTS", 1000)
DEFAULT_CAPTURE_TIMEOUT = _configured_int("QTRANS_CAPTURE_TIMEOUT", 15)
DEFAULT_TARGET_PROVIDERS = _parse_target_providers(
    os.getenv("QTRANS_TARGET_PROVIDERS", "ibm_qiskit")
)


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------
_RUN_LABEL_TOKEN_RE = re.compile(r"YYYY|DD|HH|SS|MM")


def _format_run_label(label, now=None):
    """Resuelve los tokens DD/MM/YYYY/HH/MM/SS de una etiqueta con datos reales.

    ``MM`` se interpreta como mes tras DD/YYYY y como minutos tras HH.
    """
    now = now or datetime.now()
    result = []
    position = 0
    last_token = None
    for match in _RUN_LABEL_TOKEN_RE.finditer(label):
        result.append(label[position:match.start()])
        token = match.group()
        if token == "YYYY":
            value = now.strftime("%Y")
        elif token == "DD":
            value = now.strftime("%d")
        elif token == "HH":
            value = now.strftime("%H")
        elif token == "SS":
            value = now.strftime("%S")
        else:  # MM
            value = now.strftime("%M") if last_token == "HH" else now.strftime("%m")
        result.append(value)
        last_token = token
        position = match.end()
    result.append(label[position:])
    return "".join(result)


def _run_label(run_label=None):
    label = (run_label or "").strip() if isinstance(run_label, str) else run_label
    label = label or DEFAULT_RUN_LABEL
    if not label:
        return datetime.now().strftime("%d_%m_%Y__%H_%M")
    return _format_run_label(label)


def _run_directory(output_dir, run_dir=None, run_label=None):
    if run_dir is not None:
        return Path(run_dir).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    return output_dir / f"run_{_run_label(run_label)}"


def _resolve_run_path(value, run_dir, default_subdir):
    if value is not None:
        return Path(value).expanduser().resolve()
    return (Path(run_dir) / default_subdir).resolve()


def _safe_algorithm_name(name):
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(name).replace(".", "_"))
    return safe_name.strip("_")


def _log(verbose, step, message):
    if verbose:
        print(f"[{step}] {message}")


def _resolve_algorithm_file(input_file, input_dir):
    file_path = Path(input_file).expanduser()
    if not file_path.is_absolute():
        local_path = Path.cwd() / file_path
        input_path = Path(input_dir) / file_path
        file_path = local_path if local_path.is_file() else input_path
    file_path = file_path.resolve()
    if file_path.suffix.lower() != ".json":
        raise ValueError(f"El archivo de entrada debe tener extensión .json: {file_path}")
    if not file_path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo de entrada: {file_path}")
    return file_path


def process_json_file(
    input_file,
    qasm_dir,
    quirk_images_dir,
    capture_images=True,
    capture_function=None,
    generated_names=None,
    qasm_version=DEFAULT_QASM_VERSION,
    verbose=False,
    capture_timeout=DEFAULT_CAPTURE_TIMEOUT,
):
    """Procesa un JSON y genera los archivos OpenQASM (y capturas Quirk)."""
    input_path = Path(input_file).resolve()
    with input_path.open("r", encoding="utf-8") as source_file:
        algorithms = json.load(source_file)
    if not isinstance(algorithms, dict):
        raise ValueError(f"El JSON debe contener un objeto de algoritmos: {input_path}")

    qasm_dir = Path(qasm_dir)
    quirk_images_dir = Path(quirk_images_dir)
    qasm_dir.mkdir(parents=True, exist_ok=True)
    if capture_images:
        quirk_images_dir.mkdir(parents=True, exist_ok=True)

    version_suffix = f"_v{qasm_version}"
    filename_prefix = "popular_" if input_path.stem.casefold() == "popular_algorithms" else ""
    if capture_function is None:
        capture = lambda url, path: capture_quirk_circuit(
            url, path, timeout=capture_timeout
        )
    else:
        capture = capture_function
    qasm_paths = []
    algorithm_records = []
    captures_succeeded = 0
    captures_failed = 0
    generated_names = generated_names if generated_names is not None else set()

    for algorithm_name, algorithm_data in algorithms.items():
        if not isinstance(algorithm_data, dict) or not isinstance(algorithm_data.get("url"), str):
            raise ValueError(f"El algoritmo {algorithm_name!r} debe contener una URL Quirk")

        safe_name = _safe_algorithm_name(algorithm_name)
        if not safe_name:
            raise ValueError(f"Nombre de algoritmo vacío o inválido en {input_path}")
        output_name = f"{filename_prefix}{safe_name}"
        if output_name in generated_names:
            raise ValueError(f"Nombre de salida duplicado entre archivos de entrada: {output_name}")
        generated_names.add(output_name)

        url = algorithm_data["url"]
        qasm_code = quirk_to_qasm(
            url,
            algorithm_data.get("offset", 0),
            qasm_version=qasm_version,
        )
        qasm_path = qasm_dir / f"{output_name}{version_suffix}.txt"
        qasm_path.write_text(qasm_code, encoding="utf-8")
        qasm_paths.append(qasm_path)
        _log(verbose, "Entrada", f"Procesando {algorithm_name} desde {input_path.name}.")
        algorithm_records.append(
            {
                "name": output_name,
                "display_name": algorithm_name,
                "input_file": input_path,
                "url": url,
                "offset": algorithm_data.get("offset", 0),
                "qasm_path": qasm_path,
                "qasm_source": qasm_code,
            }
        )
        _log(verbose, "OpenQASM", f"Generado {qasm_path.name} ({qasm_version}).")

        if capture_images:
            image_path = quirk_images_dir / f"{output_name}.png"
            try:
                captured = capture(url, image_path)
            except Exception as exc:
                _log(verbose, "Quirk PNG", f"Error capturando {output_name}: {exc}")
                captured = False
            if captured:
                captures_succeeded += 1
                _log(verbose, "Quirk PNG", f"Generado {image_path.name}.")
            else:
                captures_failed += 1

    return {
        "input_file": input_path,
        "algorithms_processed": len(algorithms),
        "qasm_paths": qasm_paths,
        "algorithm_records": algorithm_records,
        "captures_succeeded": captures_succeeded,
        "captures_failed": captures_failed,
    }


def _load_qasm_circuit(qasm_source, qasm_version):
    from qiskit import qasm2, qasm3

    if qasm_version == "2.0":
        return qasm2.loads(qasm_source)
    return qasm3.loads(qasm_source)


def _generate_provider_files(records, providers, migrated_dir, qasm_version, shots, verbose):
    generated = []
    errors = []
    for provider in providers:
        provider_dir = Path(migrated_dir) / PROVIDER_DIRECTORY.get(provider, provider)
        provider_dir.mkdir(parents=True, exist_ok=True)
        for record in records:
            output_path = provider_dir / f"{record['name']}.py"
            try:
                source = provider_python_source(
                    record["qasm_source"],
                    provider,
                    qasm_version=qasm_version,
                    shots=shots,
                )
                compile(source, str(output_path), "exec")
                output_path.write_text(source, encoding="utf-8")
                generated.append(output_path)
                _log(verbose, provider, f"Generado {output_path.relative_to(migrated_dir)}.")
            except Exception as exc:
                errors.append((f"{provider}/{record['name']}", exc))
                print(f"Error generando {provider}/{record['name']}: {exc}")
    return generated, errors


def _generate_qasm_images(records, qasm_images_dir, qasm_version, verbose):
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    qasm_images_dir = Path(qasm_images_dir)
    qasm_images_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    errors = []
    for record in records:
        image_path = qasm_images_dir / f"{record['name']}.png"
        figure = None
        try:
            circuit = _load_qasm_circuit(record["qasm_source"], qasm_version)
            figure = circuit.draw(output="mpl", filename=str(image_path), style="bw")
            generated.append(image_path)
            _log(verbose, "QASM PNG", f"Generado {image_path.name}.")
        except Exception as exc:
            errors.append((f"QASM PNG/{record['name']}", exc))
            print(f"Error generando diagrama QASM {record['name']}: {exc}")
        finally:
            if figure is not None:
                plt.close(figure)
    return generated, errors


def _generate_composer_images(records, images_dir, qasm_version, verbose):
    """Genera un PNG por circuito migrado con el estilo de IBM Quantum Composer."""
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    images_dir = Path(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    errors = []
    for record in records:
        image_path = images_dir / f"{record['name']}.png"
        figure = None
        try:
            circuit = _load_qasm_circuit(record["qasm_source"], qasm_version)
            figure = circuit.draw(output="mpl", filename=str(image_path), style="iqp")
            generated.append(image_path)
            _log(verbose, "Composer PNG", f"Generado {image_path.name}.")
        except Exception as exc:
            errors.append((f"Composer PNG/{record['name']}", exc))
            print(f"Error generando imagen Composer {record['name']}: {exc}")
        finally:
            if figure is not None:
                plt.close(figure)
    return generated, errors


def _write_comparison_docs(records, quirk_images_dir, qasm_images_dir, compare_dir, verbose):
    quirk_images_dir = Path(quirk_images_dir)
    qasm_images_dir = Path(qasm_images_dir)
    compare_dir = Path(compare_dir)
    compare_dir.mkdir(parents=True, exist_ok=True)
    index_lines = ["# Comparación de circuitos", ""]
    generated = []

    for record in records:
        name = record["name"]
        quirk_image = quirk_images_dir / f"{name}.png"
        qasm_image = qasm_images_dir / f"{name}.png"
        quirk_link = (
            Path(os.path.relpath(quirk_image, compare_dir)).as_posix()
            if quirk_image.is_file()
            else None
        )
        qasm_link = (
            Path(os.path.relpath(qasm_image, compare_dir)).as_posix()
            if qasm_image.is_file()
            else None
        )
        page_path = compare_dir / f"{name}.md"
        quirk_cell = (
            f'<a href="{quirk_link}"><img src="{quirk_link}" alt="{name} Quirk" width="100%"></a>'
            if quirk_link
            else "Sin captura Quirk"
        )
        qasm_cell = (
            f'<a href="{qasm_link}"><img src="{qasm_link}" alt="{name} OpenQASM" width="100%"></a>'
            if qasm_link
            else "Sin diagrama OpenQASM"
        )
        page_path.write_text(
            "\n".join(
                [
                    f"# Comparación: {name}",
                    "",
                    "<table>",
                    "<tr><th>Circuito Quirk</th><th>Circuito OpenQASM</th></tr>",
                    f"<tr><td>{quirk_cell}</td><td>{qasm_cell}</td></tr>",
                    "</table>",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        index_lines.append(f"- [{name}]({page_path.name})")
        generated.append(page_path)
        _log(verbose, "Comparación visual", f"Generado {page_path.name}.")

    index_path = compare_dir / "README.md"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    return generated + [index_path]


def _run_zx_workflow(records, zx_dir, zx_time, generate_images, verbose):
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    import pyzx as zx

    zx_dir = Path(zx_dir)
    base_dir = zx_dir / "algorithms_base"
    qasm_dir = zx_dir / "algorithms_qasm"
    graphs_dir = zx_dir / "graphs"
    base_dir.mkdir(parents=True, exist_ok=True)
    qasm_dir.mkdir(parents=True, exist_ok=True)
    if generate_images:
        graphs_dir.mkdir(parents=True, exist_ok=True)

    base_graphs = {}
    qasm_graphs = {}
    errors = []
    for record in records:
        name = record["name"]
        try:
            base_graph = quirk_to_zx_graph(
                record["url"], record["offset"], time=zx_time
            )
            qasm_graph = qasm_to_zx_graph(record["qasm_source"])
            base_path = base_dir / f"{name}.json"
            qasm_path = qasm_dir / f"{name}.json"
            base_path.write_text(base_graph.to_json(), encoding="utf-8")
            qasm_path.write_text(qasm_graph.to_json(), encoding="utf-8")
            base_graphs[name] = base_graph
            qasm_graphs[name] = qasm_graph
            _log(verbose, "Grafo ZX", f"Generados grafos base/QASM para {name}.")
        except Exception as exc:
            errors.append((f"Grafo ZX/{name}", exc))
            print(f"Error generando grafos ZX para {name}: {exc}")

    comparisons = []
    for name in base_graphs.keys() & qasm_graphs.keys():
        base_graph = base_graphs[name]
        qasm_graph = qasm_graphs[name]
        base_qubits = base_graph.num_inputs()
        qasm_qubits = qasm_graph.num_inputs()
        method = "sin comparar"
        result = "NO COMPARABLES"

        try:
            if base_qubits != qasm_qubits:
                result = f"NO COMPARABLES ({base_qubits} vs. {qasm_qubits} qubits)"
            elif base_qubits > 10:
                base_circuit = zx.Circuit.from_graph(base_graph)
                qasm_circuit = zx.Circuit.from_graph(qasm_graph)
                method = "verify_equality"
                equivalent = base_circuit.verify_equality(
                    qasm_circuit, up_to_global_phase=True
                )
                result = "EQUIVALENTES" if equivalent else "NO DEMOSTRADO"
            else:
                zx.simplify.full_reduce(base_graph)
                zx.simplify.full_reduce(qasm_graph)
                method = "compare_tensors (rw-greedy-linear)"
                equivalent = zx.compare_tensors(
                    base_graph, qasm_graph, strategy="rw-greedy-linear"
                )
                result = "EQUIVALENTES" if equivalent else "NO EQUIVALENTES"
        except Exception as exc:
            errors.append((f"Comparación ZX/{name}", exc))
            result = f"ERROR: {type(exc).__name__}"
            print(f"Error comparando grafos ZX para {name}: {exc}")

        comparisons.append(
            {
                "Nombre algoritmo": name,
                "Cúbits": base_qubits,
                "Método": method,
                "Resultado": result,
            }
        )
        _log(
            verbose,
            "Comparación ZX",
            f"Quirk vs OpenQASM de {name}: {result} (método: {method}).",
        )

    if verbose and comparisons:
        equivalent = sum(
            1 for c in comparisons if c["Resultado"].startswith("EQUIVALENTES")
        )
        not_demonstrated = sum(
            1 for c in comparisons if c["Resultado"].startswith("NO DEMOSTRADO")
        )
        print(
            f"[Comparación ZX] Grafos reducidos Quirk vs OpenQASM: "
            f"{equivalent}/{len(comparisons)} circuitos EQUIVALENTES"
            + (f", {not_demonstrated} NO DEMOSTRADOS" if not_demonstrated else "")
            + "."
        )

    comparison_path = zx_dir / "comparison_results.csv"
    with comparison_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=["Nombre algoritmo", "Cúbits", "Método", "Resultado"],
        )
        writer.writeheader()
        writer.writerows(comparisons)

    generated_images = []
    if generate_images:
        for name, graph in base_graphs.items():
            figure = None
            image_path = graphs_dir / f"{name}.svg"
            try:
                reduced_graph = graph.copy()
                zx.simplify.full_reduce(reduced_graph)
                figure = zx.draw(reduced_graph, labels=True)
                figure.savefig(image_path, format="svg")
                generated_images.append(image_path)
                _log(verbose, "ZX SVG", f"Generado {image_path.name}.")
            except Exception as exc:
                errors.append((f"ZX SVG/{name}", exc))
                print(f"Error generando SVG ZX para {name}: {exc}")
            finally:
                if figure is not None:
                    plt.close(figure)

    return {
        "base_graphs": len(base_graphs),
        "qasm_graphs": len(qasm_graphs),
        "comparisons": comparisons,
        "comparison_path": comparison_path,
        "images": generated_images,
        "errors": errors,
    }


def run_pipeline(
    input_mode=DEFAULT_INPUT_MODE,
    input_file=DEFAULT_INPUT_FILE,
    input_dir=DEFAULT_INPUT_DIR,
    output_dir=DEFAULT_OUTPUT_DIR,
    run_label=None,
    run_dir=None,
    qasm_dir=None,
    quirk_images_dir=None,
    qasm_images_dir=None,
    compare_dir=None,
    zx_dir=None,
    migrated_dir=None,
    composer_images_dir=None,
    capture_images=None,
    qasm_version=DEFAULT_QASM_VERSION,
    target_providers=None,
    verbose=None,
    capture_timeout=DEFAULT_CAPTURE_TIMEOUT,
    shots=DEFAULT_SHOTS,
    zx_time=DEFAULT_ZX_TIME,
    generate_qasm_images=None,
    generate_comparison=None,
    generate_composer_images=None,
    generate_zx=None,
    generate_zx_images=None,
):
    """Ejecuta el flujo completo Quirk -> OpenQASM -> migración (por corrida)."""
    if input_mode not in {"batch", "algorithm"}:
        raise ValueError("input_mode debe ser 'batch' o 'algorithm'")
    if qasm_version not in {"2.0", "3.0"}:
        raise ValueError("qasm_version debe ser '2.0' o '3.0'")
    if capture_images is None:
        capture_images = DEFAULT_CAPTURE_IMAGES
    if generate_qasm_images is None:
        generate_qasm_images = DEFAULT_GENERATE_QASM_IMAGES
    if generate_comparison is None:
        generate_comparison = DEFAULT_GENERATE_COMPARISON
    if generate_composer_images is None:
        generate_composer_images = DEFAULT_GENERATE_COMPOSER_IMAGES
    if generate_zx is None:
        generate_zx = DEFAULT_GENERATE_ZX
    if generate_zx_images is None:
        generate_zx_images = DEFAULT_GENERATE_ZX_IMAGES
    if verbose is None:
        verbose = DEFAULT_VERBOSE
    if target_providers is None:
        target_providers = DEFAULT_TARGET_PROVIDERS
    target_providers = _parse_target_providers(target_providers)
    if shots < 1:
        raise ValueError("shots debe ser mayor que cero")
    if capture_timeout < 1:
        raise ValueError("capture_timeout debe ser mayor que cero")
    if not 0 <= zx_time <= 1:
        raise ValueError("zx_time debe estar entre 0 y 1")

    input_dir = Path(input_dir).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    run_dir = _run_directory(output_dir, run_dir=run_dir, run_label=run_label)
    qasm_dir = _resolve_run_path(qasm_dir, run_dir, RUN_QASM_SUBDIR)
    quirk_images_dir = _resolve_run_path(quirk_images_dir, run_dir, RUN_QUIRK_IMAGES_SUBDIR)
    qasm_images_dir = _resolve_run_path(qasm_images_dir, run_dir, RUN_QASM_IMAGES_SUBDIR)
    compare_dir = _resolve_run_path(compare_dir, run_dir, RUN_COMPARE_SUBDIR)
    zx_dir = _resolve_run_path(zx_dir, run_dir, RUN_ZX_SUBDIR)
    migrated_dir = _resolve_run_path(migrated_dir, run_dir, RUN_MIGRATED_SUBDIR)
    composer_images_dir = _resolve_run_path(
        composer_images_dir, run_dir, RUN_COMPOSER_IMAGES_SUBDIR
    )

    if input_mode == "batch":
        if input_file is not None:
            raise ValueError("input_file solo se utiliza cuando input_mode='algorithm'")
        if not input_dir.is_dir():
            raise FileNotFoundError(f"No existe el directorio de entrada: {input_dir}")
        input_files = sorted(input_dir.glob("*.json"))
    else:
        if input_file is None:
            raise ValueError("input_file es obligatorio cuando input_mode='algorithm'")
        input_files = [_resolve_algorithm_file(input_file, input_dir)]
    if not input_files:
        raise FileNotFoundError(f"No se encontraron archivos .json en {input_dir}")

    print(f"DIRECTORIO DE LA CORRIDA: {run_dir}")
    _log(
        verbose,
        "Configuración",
        f"modo={input_mode}, QASM={qasm_version}, providers={', '.join(target_providers)}",
    )
    results = []
    errors = []
    algorithm_records = []
    generated_names = set()
    for input_path in input_files:
        try:
            result = process_json_file(
                input_path,
                qasm_dir=qasm_dir,
                quirk_images_dir=quirk_images_dir,
                capture_images=capture_images,
                generated_names=generated_names,
                qasm_version=qasm_version,
                verbose=verbose,
                capture_timeout=capture_timeout,
            )
            results.append(result)
            algorithm_records.extend(result["algorithm_records"])
            _log(
                verbose,
                "Entrada",
                f"Procesado {input_path.name}: {result['algorithms_processed']} algoritmos.",
            )
        except Exception as exc:
            errors.append((str(input_path), exc))
            print(f"Error procesando {input_path.name}: {exc}")
            if input_mode == "algorithm":
                break

    output_dir.mkdir(parents=True, exist_ok=True)
    qasm_images = []
    comparison_docs = []
    composer_images = []
    zx_result = {
        "base_graphs": 0,
        "qasm_graphs": 0,
        "comparisons": [],
        "comparison_path": None,
        "images": [],
        "errors": [],
    }
    provider_scripts = []

    if algorithm_records and generate_qasm_images:
        qasm_images, stage_errors = _generate_qasm_images(
            algorithm_records, qasm_images_dir, qasm_version, verbose
        )
        errors.extend(stage_errors)

    if algorithm_records and generate_comparison:
        try:
            comparison_docs = _write_comparison_docs(
                algorithm_records,
                quirk_images_dir,
                qasm_images_dir,
                compare_dir,
                verbose,
            )
        except Exception as exc:
            errors.append(("Comparación visual", exc))
            print(f"Error generando comparaciones visuales: {exc}")

    if algorithm_records and generate_zx:
        try:
            zx_result = _run_zx_workflow(
                algorithm_records, zx_dir, zx_time, generate_zx_images, verbose
            )
            errors.extend(zx_result["errors"])
        except Exception as exc:
            errors.append(("Workflow ZX", exc))
            print(f"Error en el workflow ZX: {exc}")

    if algorithm_records:
        provider_scripts, provider_errors = _generate_provider_files(
            algorithm_records,
            target_providers,
            migrated_dir,
            qasm_version,
            shots,
            verbose,
        )
        errors.extend(provider_errors)

    if algorithm_records and generate_composer_images and "ibm_qiskit" in target_providers:
        composer_images, composer_errors = _generate_composer_images(
            algorithm_records, composer_images_dir, qasm_version, verbose
        )
        errors.extend(composer_errors)

    summary = {
        "input_mode": input_mode,
        "qasm_version": qasm_version,
        "target_providers": target_providers,
        "run_dir": run_dir,
        "files_processed": len(results),
        "algorithms_processed": sum(result["algorithms_processed"] for result in results),
        "qasm_generated": sum(len(result["qasm_paths"]) for result in results),
        "captures_succeeded": sum(result["captures_succeeded"] for result in results),
        "captures_failed": sum(result["captures_failed"] for result in results),
        "qasm_images_generated": len(qasm_images),
        "comparison_docs_generated": len(comparison_docs),
        "composer_images_generated": len(composer_images),
        "zx_base_graphs_generated": zx_result["base_graphs"],
        "zx_qasm_graphs_generated": zx_result["qasm_graphs"],
        "zx_comparisons": zx_result["comparisons"],
        "zx_images_generated": len(zx_result["images"]),
        "provider_scripts_generated": len(provider_scripts),
        "output_directories": {
            "run": run_dir,
            "qasm": qasm_dir,
            "quirk_images": quirk_images_dir,
            "qasm_images": qasm_images_dir,
            "comparison": compare_dir,
            "zx": zx_dir,
            "migrated": migrated_dir,
            "composer_images": composer_images_dir,
        },
        "errors": errors,
    }
    print(
        f"Resumen: {summary['files_processed']} JSON, {summary['algorithms_processed']} algoritmos, "
        f"{summary['qasm_generated']} QASM, {summary['captures_succeeded']} capturas Quirk, "
        f"{summary['qasm_images_generated']} diagramas QASM, "
        f"{summary['composer_images_generated']} imágenes Composer, "
        f"{summary['provider_scripts_generated']} scripts provider y {len(errors)} errores."
    )
    _log(verbose, "Salida", f"Scripts migrados en {migrated_dir}.")
    return summary


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Traduce algoritmos Quirk a OpenQASM y genera capturas, comparaciones, "
            "grafos ZX y scripts migrados. Agrupa la salida por corrida en "
            "output/run_DD_MM_YYYY__HH."
        )
    )
    parser.add_argument(
        "--input-mode",
        choices=("batch", "algorithm"),
        default=DEFAULT_INPUT_MODE,
        help="batch procesa todos los JSON de input-dir; algorithm procesa input-file.",
    )
    parser.add_argument(
        "--input-file",
        default=DEFAULT_INPUT_FILE,
        help="Nombre o ruta de un archivo JSON; obligatorio en modo algorithm.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directorio de JSON de entrada (default: {DEFAULT_INPUT_DIR}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directorio raíz de las corridas (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--run-label",
        default=DEFAULT_RUN_LABEL,
        help="Etiqueta de la corrida; por defecto DD_MM_YYYY__HH_MM (fecha y hora con minutos).",
    )
    parser.add_argument(
        "--qasm-version",
        choices=("2.0", "3.0"),
        default=DEFAULT_QASM_VERSION,
        help=f"Versión de OpenQASM generada (default: {DEFAULT_QASM_VERSION}).",
    )
    parser.add_argument(
        "--providers",
        default=",".join(DEFAULT_TARGET_PROVIDERS),
        help=(
            "Lista separada por comas de ecosistemas objetivo: "
            f"{', '.join(SUPPORTED_PROVIDERS)} (default: {','.join(DEFAULT_TARGET_PROVIDERS)})."
        ),
    )
    parser.add_argument("--shots", type=int, default=DEFAULT_SHOTS, help="Shots para PennyLane.")
    parser.add_argument(
        "--zx-time",
        type=float,
        default=DEFAULT_ZX_TIME,
        help="Snapshot temporal Quirk para gates como Rxft, en el rango 0..1.",
    )
    parser.add_argument(
        "--capture-timeout",
        type=int,
        default=DEFAULT_CAPTURE_TIMEOUT,
        help="Timeout del navegador Selenium, en segundos.",
    )
    capture_group = parser.add_mutually_exclusive_group()
    capture_group.add_argument(
        "--capture-images",
        dest="capture_images",
        action="store_true",
        help="Genera capturas PNG de Quirk incluso si el .env las desactiva.",
    )
    capture_group.add_argument(
        "--no-capture",
        dest="capture_images",
        action="store_false",
        help="Omite las capturas PNG de Quirk.",
    )
    parser.set_defaults(capture_images=None)
    parser.add_argument(
        "--no-qasm-images",
        dest="generate_qasm_images",
        action="store_false",
        default=None,
        help="Omite los diagramas PNG de los circuitos OpenQASM.",
    )
    parser.add_argument(
        "--no-comparison",
        dest="generate_comparison",
        action="store_false",
        default=None,
        help="Omite los informes Markdown de comparación visual.",
    )
    parser.add_argument(
        "--no-composer-images",
        dest="generate_composer_images",
        action="store_false",
        default=None,
        help="Omite las imágenes de los circuitos migrados (estilo IBM Composer).",
    )
    parser.add_argument(
        "--no-zx",
        dest="generate_zx",
        action="store_false",
        default=None,
        help="Omite la conversión y comparación de grafos ZX.",
    )
    parser.add_argument(
        "--no-zx-images",
        dest="generate_zx_images",
        action="store_false",
        default=None,
        help="Omite los diagramas SVG de los grafos ZX.",
    )
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Muestra el resultado de cada etapa del pipeline (activado por defecto).",
    )
    verbosity_group.add_argument(
        "--quiet",
        dest="verbose",
        action="store_false",
        help="Silencia las trazas por etapa del pipeline.",
    )
    parser.set_defaults(verbose=None)
    return parser


def main(argv=None):
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    try:
        summary = run_pipeline(
            input_mode=args.input_mode,
            input_file=args.input_file,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            run_label=args.run_label,
            qasm_version=args.qasm_version,
            target_providers=args.providers,
            capture_images=args.capture_images,
            shots=args.shots,
            zx_time=args.zx_time,
            capture_timeout=args.capture_timeout,
            generate_qasm_images=args.generate_qasm_images,
            generate_comparison=args.generate_comparison,
            generate_composer_images=args.generate_composer_images,
            generate_zx=args.generate_zx,
            generate_zx_images=args.generate_zx_images,
            verbose=args.verbose,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}")
        return 1
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

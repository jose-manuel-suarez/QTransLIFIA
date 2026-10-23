"""

Quirk-to-OpenQASM pipeline de QTransLIFIA (librería + CLI).

Reproduce el flujo del cuaderno ``notebooks/QTrans.ipynb``:
lee los JSON de entrada, captura los circuitos Quirk, traduce a OpenQASM (versión configurable, 2.0+), genera diagramas y comparaciones, construye y compara grafos ZX, genera los circuitos mediante 'loads' del QASM y migra cada circuito a los ecosistemas objetivo (Qiskit, AWS Braket, PennyLane) en codigo python, incluidas las imágenes de los circuitos migrados con el estilo de IBM Quantum Composer.

Todas las salidas se agrupan por corrida en ``<output>/run_DD_MM_YYYY__HH``, donde ``<output>`` es el directorio de salida configurado y la etiqueta de la corrida se genera a partir de la fecha y hora actual.

Como librería instalable con pip, expone la función core ``translate_circuit(payload)``: recibe un objeto JSON (dict o cadena) con el grupo ``input`` (circuito como ``url``/``json`` o lote ``circuits``, más ``offset``, ``qasm_version``, ``provider`` y las etapas opcionales) y devuelve ``{"input": ..., "output": ...}``; cada circuito de ``output`` incluye ``qasm`` (``code``, ``version``, ``lines`` y ``gates`` con ``custom``/``native``), ``migrated_code`` (por proveedor), ``zx_calculus_result``, ``circuit_info``, ``custom_gates`` (catálogo exhaustivo de las compuertas custom declaradas, con ``used_in_circuit``), ``img`` (PNG en base64), ``comparison_doc`` y ``errors`` (más ``name`` si es un lote).

Este módulo es el **orquestador**: resuelve la configuración (variables ``QTRANS_*`` de
``.env``), la línea de comandos y el flujo por corrida, y delega cada etapa en los
módulos de ``qtrans.utils``:

- ``utils.pipeline_utils``: utilidades genéricas (log, etiqueta de corrida, nombres).
- ``utils.qasm_utils``: tablas de ``stdgates.inc``, ángulos, versiones y resumen de compuertas.
- ``utils.quirk_utils``: traducción Quirk → OpenQASM, captura de Quirk y comparación visual.
- ``utils.provider_utils``: registro de proveedores y generación de los scripts migrados.
- ``utils.qiskit_utils`` / ``utils.braket_utils`` / ``utils.pennylane_utils``: cada ecosistema.
- ``utils.zx_utils``: grafos ZX (PyZX) y su comparación.

"""

# Importación de las librerías estándar y configuración del entorno
import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .utils import (
    pipeline_utils,
    provider_utils,
    qasm_utils,
    qiskit_utils,
    quirk_utils,
    zx_utils,
)
from .utils.provider_utils import (
    PROVIDER_DIRECTORY,
    SUPPORTED_PROVIDERS,
    parse_providers,
    providers_from_env,
)
from .utils.qasm_utils import qasm3_to_qasm2
from .utils.zx_utils import (
    qasm_to_zx_graph,
    quirk_to_zx_graph,
)

# Reexports de compatibilidad: el ``core.py`` original importaba estos nombres
# desde ``utils.qutils`` y los exponía a nivel de módulo. Se mantienen aquí
# para no romper código externo del tipo ``from qtrans.core import quirk_to_qasm``.
from .utils.provider_utils import provider_python_source  # noqa: F401
from .utils.qiskit_utils import load_qasm_circuit, render_qasm_image  # noqa: F401
from .utils.quirk_utils import (  # noqa: F401
    capture_quirk_circuit,
    quirk_circuit_info,
    quirk_to_qasm,
)
from .utils.url_utils import encode_quirk_url  # noqa: F401
from .utils.zx_utils import compare_zx_graphs, reduce_and_draw_zx_svg  # noqa: F401

PROJECT_ROOT = Path(__file__).resolve().parents[1]
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
    if normalized_value in {"1", "true", "yes", "on", "si"}: return True
    if normalized_value in {"0", "false", "no", "off", "no"}: return False
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


def _parse_input_files(value):
    """Convierte una lista separada por comas de JSON en tupla de nombres."""
    if value is None:
        return None
    names = [part.strip() for part in str(value).split(",")]
    names = [name for name in names if name]
    return tuple(names) or None

# Obtención de variables constantes relacionadas a la configuración
DEFAULT_INPUT_MODE = (os.getenv("QTRANS_INPUT_MODE") or "batch").strip().casefold()
if DEFAULT_INPUT_MODE not in {"batch", "algorithm"}:
    raise ValueError("QTRANS_INPUT_MODE debe ser 'batch' o 'algorithm'")
DEFAULT_INPUT_FILE = os.getenv("QTRANS_INPUT_FILE") or None
DEFAULT_INPUT_FILES = _parse_input_files(os.getenv("QTRANS_INPUT_FILES"))
DEFAULT_INPUT_DIR = _configured_path("QTRANS_INPUT_DIR", PROJECT_ROOT / "input")
DEFAULT_OUTPUT_DIR = _configured_path("QTRANS_OUTPUT_DIR", PROJECT_ROOT / "output")
DEFAULT_RUN_LABEL = (os.getenv("QTRANS_RUN_LABEL") or "").strip() or None

# Subdirectorios (relativos a la corrida) que replican la estructura del cuaderno.
RUN_QASM_SUBDIR = "algorithms_qasm"
RUN_IMGS_SUBDIR = "imgs"
RUN_QUIRK_IMAGES_SUBDIR = "imgs/circuits_quirk"
RUN_QASM_IMAGES_SUBDIR = "imgs/circuits_qasm"
RUN_COMPARE_SUBDIR = "imgs/visual_comparisons"
RUN_ZX_SUBDIR = "ZXCalculus"
RUN_MIGRATED_SUBDIR = "migrated_circuits"
RUN_COMPOSER_IMAGES_SUBDIR = "migrated_circuits/ibm_qiskit/imgs"
RUN_MARKER_FILE = ".qtrans_run"

DEFAULT_CAPTURE_IMAGES = _configured_bool("QTRANS_CAPTURE_IMAGES", True)
DEFAULT_GENERATE_QASM_IMAGES = _configured_bool("QTRANS_GENERATE_QASM_IMAGES", True)
DEFAULT_GENERATE_COMPARISON = _configured_bool("QTRANS_GENERATE_COMPARISON", True)
DEFAULT_GENERATE_COMPOSER_IMAGES = _configured_bool("QTRANS_GENERATE_COMPOSER_IMAGES", True)
DEFAULT_GENERATE_ZX = _configured_bool("QTRANS_GENERATE_ZX", True)
DEFAULT_GENERATE_ZX_IMAGES = _configured_bool("QTRANS_GENERATE_ZX_IMAGES", True)
DEFAULT_VERBOSE = _configured_bool("QTRANS_VERBOSE", True)
DEFAULT_QASM_VERSION = _configured_qasm_version()
DEFAULT_ZX_TIME = _configured_float("QTRANS_ZX_TIME", 0.5, minimum=0.0, maximum=1.0)
DEFAULT_ZX_TIMEOUT = _configured_int("QTRANS_ZX_TIMEOUT", 120)
DEFAULT_SHOTS = _configured_int("QTRANS_SHOTS", 1000)
DEFAULT_CAPTURE_TIMEOUT = _configured_int("QTRANS_CAPTURE_TIMEOUT", 15)
DEFAULT_TARGET_PROVIDERS = providers_from_env()
DEFAULT_PRESERVE_CUSTOM_GATES = _configured_bool("QTRANS_PRESERVE_CUSTOM_GATES", True)


# ---------------------------------------------------------------------------
# Utilidades internas (delegadas en utils.pipeline_utils)
# ---------------------------------------------------------------------------
def _format_run_label(label, now=None):
    """Resuelve los tokens DD/MM/YYYY/HH/MM/SS de una etiqueta con datos reales.

    ``MM`` se interpreta como mes tras DD/YYYY y como minutos tras HH.
    """
    return pipeline_utils.format_run_label(label, now)


def _run_label(run_label=None):
    """Resuelve la etiqueta de la corrida (carpeta ``run_<etiqueta>``).

    La etiqueta por defecto tiene resolución de **hora** (``DD_MM_YYYY__HH``):
    dos ejecuciones dentro de la misma hora reutilizan la misma carpeta y
    sobrescriben sus archivos, de modo que ``output/`` no acumula una carpeta
    por corrida.

    Parámetros:
        - run_label (str | None): etiqueta explícita con tokens
          (``DD``, ``MM``, ``YYYY``, ``HH``, ``MM``, ``SS``).

    Retorna:
        - str: etiqueta resuelta.
    """
    label = (run_label or "").strip() if isinstance(run_label, str) else run_label
    label = label or DEFAULT_RUN_LABEL
    if not label:
        return datetime.now().strftime("%d_%m_%Y__%H")
    return _format_run_label(label)


def _run_directory(output_dir, run_dir=None, run_label=None):
    if run_dir is not None:
        return Path(run_dir).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    return output_dir / f"run_{_run_label(run_label)}"


def _resolve_run_path(value, run_dir, default_subdir):
    return pipeline_utils.resolve_run_path(value, run_dir, default_subdir)


def _prepare_run_directory(run_dir, verbose):
    """Deja la carpeta de la corrida lista para reutilizarse o crearse.

    La carpeta lleva la estampa de fecha y **hora**: dos ejecuciones dentro de
    la misma hora comparten carpeta, de modo que los archivos se sobrescriben en
    lugar de acumular una carpeta nueva por corrida. Cuando la carpeta ya
    existía (corrida previa de la misma hora) se borran sus artefactos
    generados para que no se mezclen con los nuevos; si la carpeta no fue
    creada por la herramienta, no se toca nada.

    Parámetros:
        - run_dir (str | Path): carpeta de la corrida.
        - verbose (bool): si es True, informa de la limpieza.

    Retorna:
        - None
    """
    run_dir = Path(run_dir)
    marker = run_dir / RUN_MARKER_FILE
    if not run_dir.exists():
        run_dir.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            "Carpeta de corrida de QTransLIFIA (se reutiliza dentro de la misma hora).\n",
            encoding="utf-8",
        )
        return
    if not marker.is_file():
        return
    removed = []
    for subdir in (RUN_QASM_SUBDIR, RUN_IMGS_SUBDIR, RUN_ZX_SUBDIR, RUN_MIGRATED_SUBDIR):
        target = run_dir / subdir
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            removed.append(subdir)
    if removed:
        _log(
            verbose,
            "Corrida",
            f"Misma hora: se regeneran {', '.join(removed)} en {run_dir.name}.",
        )


def _safe_algorithm_name(name):
    return pipeline_utils.safe_algorithm_name(name)


def _log(verbose, step, message):
    pipeline_utils.log_stage(verbose, step, message)


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
        capture = lambda url, path: quirk_utils.capture_quirk_circuit(
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
        qasm_code = quirk_utils.quirk_to_qasm(
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


def _json_safe(value):
    """Convierte rutas, tuplas y estructuras anidadas en tipos serializables a JSON.

    Parámetros:
        - value: valor de cualquier tipo (dict, list, tuple, Path, str, ...).

    Retorna:
        - object: copia del valor con ``pathlib.Path`` como ``str`` y tuplas
        como listas; los demás tipos se devuelven sin cambios.
    """
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _build_run_report(summary):
    """Construye el reporte JSON-safe de una corrida (incluye los circuitos OpenQASM).

    Parámetros:
        - summary (dict): resumen devuelto por ``run_pipeline`` (claves
          ``algorithms`` con el OpenQASM de cada circuito, ``errors``, etc.).

    Retorna:
        - dict: copia serializable del resumen; ``errors`` queda como lista de
        ``{"stage", "message"}`` y todas las rutas como texto.
    """
    report = _json_safe(summary)
    report.pop("json_report", None)
    report.pop("json_report_path", None)
    report["errors"] = [
        {"stage": str(stage), "message": str(exc)} for stage, exc in summary["errors"]
    ]
    return report


def run_pipeline(
    input_mode=DEFAULT_INPUT_MODE,
    input_file=DEFAULT_INPUT_FILE,
    input_files=DEFAULT_INPUT_FILES,
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
    preserve_custom_gates=None,
    verbose=None,
    capture_timeout=DEFAULT_CAPTURE_TIMEOUT,
    shots=DEFAULT_SHOTS,
    zx_time=DEFAULT_ZX_TIME,
    zx_timeout=DEFAULT_ZX_TIMEOUT,
    generate_qasm_images=None,
    generate_comparison=None,
    generate_composer_images=None,
    generate_zx=None,
    generate_zx_images=None,
    json_out=None,
    print_status=True,
):
    """Ejecuta el flujo completo Quirk -> OpenQASM -> migración (por corrida).

    ``json_out`` ('-' | ruta | None) construye además un reporte JSON-safe
    (claves ``algorithms`` con el OpenQASM de cada circuito y ``errors`` como
    ``{"stage", "message"}``): con una ruta lo escribe en disco y con '-'
    solo lo deja en ``summary['json_report']`` para que la CLI lo imprima.
    ``print_status`` controla los prints de estado (directorio de la corrida,
    resumen); la CLI lo desactiva al imprimir JSON en stdout.
    """
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
    target_providers = parse_providers(target_providers)
    if preserve_custom_gates is None:
        preserve_custom_gates = DEFAULT_PRESERVE_CUSTOM_GATES
    if shots < 1:
        raise ValueError("shots debe ser mayor que cero")
    if capture_timeout < 1:
        raise ValueError("capture_timeout debe ser mayor que cero")
    if not 0 <= zx_time <= 1:
        raise ValueError("zx_time debe estar entre 0 y 1")
    if zx_timeout < 1:
        raise ValueError("zx_timeout debe ser mayor que cero")
    if isinstance(input_files, str):
        input_files = _parse_input_files(input_files)
    elif input_files is None:
        input_files = DEFAULT_INPUT_FILES
    else:
        flattened = []
        for item in input_files:
            if isinstance(item, str) and "," in item:
                flattened.extend(_parse_input_files(item) or ())
            elif item is None or not str(item).strip():
                continue
            else:
                flattened.append(item)
        input_files = tuple(flattened)
    if input_file is not None and not str(input_file).strip():
        input_file = None

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
            raise ValueError(
                "input_file solo se utiliza cuando input_mode='algorithm'; "
                "déjalo vacío para que el modo batch procese todos los .json de input-dir"
            )
        if not input_dir.is_dir():
            raise FileNotFoundError(f"No existe el directorio de entrada: {input_dir}")
        if input_files:
            selected_input_files = []
            for raw_name in input_files:
                candidate = Path(raw_name).expanduser()
                candidate = candidate if candidate.is_absolute() else input_dir / candidate
                candidate = candidate.resolve()
                if candidate.suffix.lower() != ".json":
                    raise ValueError(
                        f"Los archivos de entrada deben tener extensión .json: {candidate}"
                    )
                if not candidate.is_file():
                    raise FileNotFoundError(f"No se encontró el archivo de entrada: {candidate}")
                selected_input_files.append(candidate)
            input_files = sorted(set(selected_input_files))
        else:
            input_files = sorted(input_dir.glob("*.json"))
    else:
        if input_file is None:
            raise ValueError("input_file es obligatorio cuando input_mode='algorithm'")
        if input_files:
            raise ValueError("input_files solo se utiliza cuando input_mode='batch'")
        input_files = [_resolve_algorithm_file(input_file, input_dir)]
    if not input_files:
        raise FileNotFoundError(f"No se encontraron archivos .json en {input_dir}")
    if input_mode == "batch" and input_files:
        _log(
            verbose,
            "Configuración",
            f"Archivos seleccionados: {', '.join(path.name for path in input_files)}",
        )

    if print_status:
        print(f"DIRECTORIO DE LA CORRIDA: {run_dir}")
    _prepare_run_directory(run_dir, verbose)
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
            if print_status:
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
        _log(
            verbose,
            "Visual QASM",
            f"Iniciando diagramas OpenQASM para {len(algorithm_records)} algoritmos.",
        )
        qasm_images, stage_errors = qiskit_utils.generate_qasm_images(
            algorithm_records, qasm_images_dir, qasm_version, verbose
        )
        errors.extend(stage_errors)

    if algorithm_records and generate_comparison:
        _log(
            verbose,
            "Comparación visual",
            f"Iniciando comparaciones visuales de {len(algorithm_records)} algoritmos.",
        )
        try:
            comparison_docs = quirk_utils.write_comparison_docs(
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
        _log(
            verbose,
            "ZX",
            f"Iniciando comprobación ZX de {len(algorithm_records)} algoritmos.",
        )
        try:
            zx_result = zx_utils.run_zx_workflow(
                algorithm_records, zx_dir, zx_time, generate_zx_images, verbose,
                zx_timeout,
            )
            errors.extend(zx_result["errors"])
        except Exception as exc:
            errors.append(("Workflow ZX", exc))
            print(f"Error en el workflow ZX: {exc}")

    if algorithm_records:
        _log(
            verbose,
            "Migración",
            f"Iniciando migración de {len(algorithm_records)} algoritmos "
            f"a {', '.join(target_providers)}.",
        )
        provider_scripts, provider_errors = provider_utils.generate_provider_files(
            algorithm_records,
            target_providers,
            migrated_dir,
            qasm_version,
            shots,
            verbose,
            preserve_custom_gates=preserve_custom_gates,
        )
        errors.extend(provider_errors)

    if algorithm_records and generate_composer_images and "qiskit" in target_providers:
        _log(
            verbose,
            "Composer",
            f"Iniciando imágenes Composer de {len(algorithm_records)} algoritmos.",
        )
        composer_images, composer_errors = qiskit_utils.generate_composer_images(
            algorithm_records, composer_images_dir, qasm_version, verbose
        )
        errors.extend(composer_errors)

    qasm_image_by_name = {path.stem: path for path in qasm_images}
    composer_image_by_name = {path.stem: path for path in composer_images}
    comparison_doc_by_name = {path.stem: path for path in comparison_docs}
    migrated_scripts_by_name = {}
    for script_path in provider_scripts:
        migrated_scripts_by_name.setdefault(script_path.stem, []).append(script_path)
    algorithm_reports = []
    for record in algorithm_records:
        record_name = record["name"]
        quirk_capture = quirk_images_dir / f"{record_name}.png"
        algorithm_reports.append(
            {
                "name": record_name,
                "display_name": record["display_name"],
                "input_file": record["input_file"].name,
                "url": record["url"],
                "offset": record["offset"],
                "qasm": {
                    "version": qasm_version,
                    "path": record["qasm_path"],
                    "code": record["qasm_source"],
                },
                "quirk_capture": quirk_capture if quirk_capture.is_file() else None,
                "qasm_image": qasm_image_by_name.get(record_name),
                "comparison_doc": comparison_doc_by_name.get(record_name),
                "composer_image": composer_image_by_name.get(record_name),
                "migrated_scripts": sorted(migrated_scripts_by_name.get(record_name, ())),
            }
        )

    summary = {
        "input_mode": input_mode,
        "qasm_version": qasm_version,
        "target_providers": target_providers,
        "preserve_custom_gates": preserve_custom_gates,
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
        "algorithms": algorithm_reports,
        "errors": errors,
    }
    if print_status:
        print(
            f"Resumen: {summary['files_processed']} JSON, {summary['algorithms_processed']} algoritmos, "
            f"{summary['qasm_generated']} QASM, {summary['captures_succeeded']} capturas Quirk, "
            f"{summary['qasm_images_generated']} diagramas QASM, "
            f"{summary['composer_images_generated']} imágenes Composer, "
            f"{summary['provider_scripts_generated']} scripts provider y {len(errors)} errores."
        )
    _log(verbose, "Salida", f"Scripts migrados en {migrated_dir}.")
    if json_out is not None:
        report = _build_run_report(summary)
        summary["json_report"] = report
        if json_out != "-":
            json_path = Path(json_out).expanduser()
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            summary["json_report_path"] = json_path
            _log(verbose, "JSON", f"Reporte JSON escrito en {json_path}.")
    return summary


# ---------------------------------------------------------------------------
# API de librería: translate_circuit()
# ---------------------------------------------------------------------------
_TRANSLATE_TOP_KEYS = frozenset({"input"})
_TRANSLATE_INPUT_KEYS = frozenset({
    "url",
    "json",
    "circuits",
    "offset",
    "qasm_version",
    "provider",
    "shots",
    "preserve_custom_gates",
    "zx",
    "images",
    "comparison",
    "return_circuit",
})
_TRANSLATE_CIRCUIT_KEYS = frozenset({"name", "url", "json", "offset"})
_TRANSLATE_ZX_KEYS = frozenset({"enabled", "time", "timeout"})
_TRANSLATE_IMAGES_KEYS = frozenset({"quirk", "qasm", "composer", "capture_timeout"})


def _unknown_keys(payload, allowed, label):
    """Lista de claves no admitidas en un dict (para mensajes de error).

    Parámetros:
        - payload (dict): dict a inspeccionar.
        - allowed (frozenset): claves permitidas.
        - label (str): nombre del grupo para el mensaje.

    Retorna:
        - list[str]: claves desconocidas ordenadas (vacía si no hay).
    """
    return [f"{label}.{key}" for key in sorted(set(payload) - allowed)]


def _resolve_circuit_url(entry):
    """Construye la URL Quirk de trabajo a partir de ``url`` o ``json``.

    Parámetros:
        - entry (dict): dict con exactamente una de las claves ``url`` (URL de
          Quirk) o ``json`` (dict o cadena JSON del circuito con ``cols``).

    Retorna:
        - str: URL de Quirk ``https://algassert.com/quirk#circuit=...``.

    Lanza:
        - ValueError: si faltan/clavan las claves o el circuito JSON es inválido.
    """
    return quirk_utils.resolve_circuit_url(entry)


def _zx_calculus_result(url, qasm_code, offset, zx_time, zx_timeout):
    """Compara los grafos ZX de Quirk y del QASM generado.

    Parámetros:
        - url (str): URL de Quirk de origen.
        - qasm_code (str): código OpenQASM generado (2.0 o 3.0).
        - offset (int): desplazamiento de índices q[i].
        - zx_time (float): tiempo de simulación usado en la construcción ZX.
        - zx_timeout (int): límite en segundos de la comparación.

    Retorna:
        - str: 'equivalente' si los grafos son EQUIVALENTES, 'no-equivalente'
          si son NO EQUIVALENTES o NO COMPARABLES y 'no-comprobado' si no se
          pudo demostrar (timeout, error o resultado indeterminado).
    """
    try:
        base_graph = quirk_to_zx_graph(url, offset, time=zx_time)
        qasm_graph = qasm_to_zx_graph(qasm_code)
        _, result = zx_utils.zx_compare_once(base_graph, qasm_graph, zx_timeout)
    except Exception:  # noqa: BLE001 — la validación ZX nunca debe tumbar la traducción
        return "no-comprobado"
    if result.startswith("EQUIVALENTES"):
        return "equivalente"
    if result.startswith(("NO EQUIVALENTES", "NO COMPARABLES")):
        return "no-equivalente"
    return "no-comprobado"


def _require_keys(payload, allowed, label):
    """Valida que un dict solo contenga claves admitidas.

    Parámetros:
        - payload (dict): dict a validar.
        - allowed (frozenset): claves admitidas.
        - label (str): nombre del grupo (para el mensaje de error).

    Retorna:
        - None

    Lanza:
        - ValueError: si hay claves desconocidas.
    """
    unknown = _unknown_keys(payload, allowed, label)
    if unknown:
        raise ValueError(
            f"Claves desconocidas: {', '.join(unknown)}. "
            f"Claves admitidas en {label}: "
            f"{', '.join(f'{label}.{key}' for key in sorted(allowed))}."
        )


def _validated_bool(value, label):
    """Valida que value sea bool.

    Parámetros:
        - value: valor a validar.
        - label (str): nombre del campo (para el mensaje de error).

    Retorna:
        - bool: el valor validado.

    Lanza:
        - ValueError: si no es booleano.
    """
    if not isinstance(value, bool):
        raise ValueError(f"{label} debe ser booleano: {value!r}")
    return value


def _validated_int(value, label, minimum):
    """Valida que value sea un entero >= minimum.

    Parámetros:
        - value: valor a validar.
        - label (str): nombre del campo (para el mensaje de error).
        - minimum (int): cota inferior incluida.

    Retorna:
        - int: el valor validado.

    Lanza:
        - ValueError: si no es un entero >= minimum.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} debe ser un entero >= {minimum}: {value!r}")
    return value


def _normalize_translate_input(input_payload):
    """Valida y normaliza el grupo ``input`` de un payload de ``translate_circuit``.

    Resuelve los valores por defecto (QASM_VERSION/shots/etc. desde el entorno),
    normaliza los proveedores y construye la URL Quirk efectiva de cada circuito.

    Parámetros:
        - input_payload (dict): objeto ``input`` del payload.

    Retorna:
        - dict: entrada normalizada; sirve como eco en la respuesta y como
          configuración de ejecución. Siempre contiene ``offset``,
          ``qasm_version``, ``provider`` (lista), ``shots``,
          ``preserve_custom_gates``, ``return_circuit``, ``zx``, ``images``,
          ``comparison`` y exactamente uno de ``url`` (circuito único) o
          ``circuits`` (lote).

    Lanza:
        - ValueError: claves desconocidas, falta de circuito, tipos o rangos
          inválidos; o ``return_circuit`` en modo lote.
    """
    if not isinstance(input_payload, dict):
        raise ValueError('El payload debe tener la clave "input" con un objeto.')
    _require_keys(input_payload, _TRANSLATE_INPUT_KEYS, "input")

    has_single = ("url" in input_payload) or ("json" in input_payload)
    has_batch = "circuits" in input_payload
    if has_single == has_batch:
        raise ValueError(
            'Debe enviar exactamente uno: "input.url"/"input.json" (circuito '
            'único) o "input.circuits" (lote).'
        )

    settings = {
        "offset": _validated_int(input_payload.get("offset", 0), "input.offset", 0),
        "qasm_version": str(
            input_payload.get("qasm_version", DEFAULT_QASM_VERSION)
        ).strip(),
        "provider": list(parse_providers(input_payload.get("provider", "qiskit"))),
        "shots": _validated_int(input_payload.get("shots", DEFAULT_SHOTS), "input.shots", 1),
        "preserve_custom_gates": _validated_bool(
            input_payload.get("preserve_custom_gates", DEFAULT_PRESERVE_CUSTOM_GATES),
            "input.preserve_custom_gates",
        ),
        "comparison": _validated_bool(input_payload.get("comparison", False), "input.comparison"),
        "return_circuit": _validated_bool(
            input_payload.get("return_circuit", False), "input.return_circuit"
        ),
    }
    if settings["return_circuit"] and has_batch:
        raise ValueError(
            'input.return_circuit solo se admite con "input.url"/"input.json" '
            "(circuito único); la API de objetos translate_circuits() ya "
            "devuelve los circuitos cargados por proveedor."
        )
    if settings["qasm_version"] not in {"2.0", "3.0"}:
        raise ValueError(
            f"input.qasm_version debe ser '2.0' o '3.0': {settings['qasm_version']!r}"
        )

    zx_payload = input_payload.get("zx")
    if zx_payload is None:
        zx_payload = {}
    if not isinstance(zx_payload, dict):
        raise ValueError("input.zx debe ser un objeto.")
    _require_keys(zx_payload, _TRANSLATE_ZX_KEYS, "input.zx")
    zx_time = zx_payload.get("time", DEFAULT_ZX_TIME)
    if isinstance(zx_time, bool) or not isinstance(zx_time, (int, float)) or not 0 <= zx_time <= 1:
        raise ValueError(f"input.zx.time debe estar entre 0 y 1: {zx_time!r}")
    settings["zx"] = {
        "enabled": _validated_bool(zx_payload.get("enabled", True), "input.zx.enabled"),
        "time": float(zx_time),
        "timeout": _validated_int(
            zx_payload.get("timeout", DEFAULT_ZX_TIMEOUT), "input.zx.timeout", 1
        ),
    }

    images_payload = input_payload.get("images")
    if images_payload is None:
        images_payload = {}
    if not isinstance(images_payload, dict):
        raise ValueError("input.images debe ser un objeto.")
    _require_keys(images_payload, _TRANSLATE_IMAGES_KEYS, "input.images")
    settings["images"] = {
        "quirk": _validated_bool(images_payload.get("quirk", False), "input.images.quirk"),
        "qasm": _validated_bool(images_payload.get("qasm", False), "input.images.qasm"),
        "composer": _validated_bool(
            images_payload.get("composer", False), "input.images.composer"
        ),
        "capture_timeout": _validated_int(
            images_payload.get("capture_timeout", DEFAULT_CAPTURE_TIMEOUT),
            "input.images.capture_timeout",
            1,
        ),
    }

    if has_batch:
        circuits = input_payload["circuits"]
        if not isinstance(circuits, list) or not circuits:
            raise ValueError("input.circuits debe ser una lista no vacía de circuitos.")
        normalized_circuits = []
        for index, entry in enumerate(circuits):
            if not isinstance(entry, dict):
                raise ValueError(f"input.circuits[{index}] debe ser un objeto.")
            _require_keys(entry, _TRANSLATE_CIRCUIT_KEYS, f"input.circuits[{index}]")
            name = entry.get("name")
            if name is None:
                name = f"circuit_{index + 1}"
            elif not isinstance(name, str) or not name.strip():
                raise ValueError(f"input.circuits[{index}].name debe ser una cadena no vacía.")
            normalized_circuits.append({
                "name": name.strip(),
                "url": _resolve_circuit_url(entry),
                "offset": _validated_int(
                    entry.get("offset", settings["offset"]),
                    f"input.circuits[{index}].offset",
                    0,
                ),
            })
        settings["circuits"] = normalized_circuits
    else:
        settings["url"] = _resolve_circuit_url(input_payload)
    return settings


def _translate_circuit_entry(name, url, offset, settings):
    """Traduce un circuito Quirk y arma su objeto de salida completo.

    Ejecuta la traducción a OpenQASM, el conteo de gates, la migración a los
    proveedores pedidos y, si están habilitados, la validación ZX, las
    imágenes en base64, el documento de comparación y, con
    ``return_circuit``, la carga del circuito nativo de cada proveedor. Los
    fallos de las etapas opcionales se acumulan en ``errors`` sin
    interrumpir el resto.

    Parámetros:
        - name (str | None): nombre del circuito (None en modo single).
        - url (str): URL de Quirk del circuito.
        - offset (int): desplazamiento de los índices q[i].
        - settings (dict): entrada normalizada (ver ``_normalize_translate_input``).

    Retorna:
        - dict: objeto de salida del circuito; JSON-serializable salvo los
        objetos vivos de ``circuits`` cuando ``settings['return_circuit']``
        es true.

    Lanza:
        - excepciones de ``quirk_to_qasm``/``provider_python_source`` si la
          traducción o la migración fallan (errores de etapas opcionales NO
          lanzan: van a ``errors``).
    """
    errors = []

    qasm3_source = quirk_utils.quirk_to_qasm(url, offset=offset, qasm_version="3.0")
    gates_summary = qasm_utils.qasm_gate_summary(qasm3_source)
    qasm_version = settings["qasm_version"]
    qasm_code = (
        qasm3_source if qasm_version == "3.0" else qasm3_to_qasm2(qasm3_source)
    )
    qasm_block = {
        "code": qasm_code,
        "version": qasm_version,
        "lines": len(qasm_code.splitlines()),
        "gates": gates_summary,
    }

    info = quirk_utils.quirk_circuit_info(url)
    circuit_info = {
        "n_qubits": info["n_qubits"],
        "n_cols": info["n_cols"],
        "gates": info["gates"],
    }
    custom_gates = quirk_utils.custom_gates_catalog(url)

    migrated_code = {}
    for provider in settings["provider"]:
        migrated_code[f"{PROVIDER_DIRECTORY[provider]}_code"] = provider_utils.provider_python_source(
            qasm_code,
            provider,
            qasm_version=qasm_version,
            shots=settings["shots"],
            preserve_custom_gates=settings["preserve_custom_gates"],
        )

    circuits = None
    if settings["return_circuit"]:
        circuits = {}
        for provider in settings["provider"]:
            try:
                circuits[provider] = provider_utils.load_provider_circuit(
                    qasm_code,
                    provider,
                    qasm_version=qasm_version,
                    shots=settings["shots"],
                    preserve_custom_gates=settings["preserve_custom_gates"],
                )
            except Exception as exc:  # noqa: BLE001 — la carga no interrumpe el resto
                circuits[provider] = None
                errors.append({"stage": f"circuits.{provider}", "message": str(exc)})

    zx_settings = settings["zx"]
    zx_calculus_result = (
        _zx_calculus_result(
            url, qasm_code, offset, zx_settings["time"], zx_settings["timeout"]
        )
        if zx_settings["enabled"]
        else None
    )

    images_settings = settings["images"]
    img = {"quirk": None, "qasm": None, "composer": None}
    if images_settings["quirk"]:
        try:
            img["quirk"] = quirk_utils.image_quirk_base64(
                url, images_settings["capture_timeout"]
            )
            if img["quirk"] is None:
                errors.append({
                    "stage": "img.quirk",
                    "message": "No se pudo capturar el circuito Quirk (Selenium).",
                })
        except Exception as exc:  # noqa: BLE001 — etapa opcional no interrumpe el resultado
            errors.append({"stage": "img.quirk", "message": str(exc)})
    if images_settings["qasm"]:
        try:
            img["qasm"] = qiskit_utils.image_qasm_base64(qasm_code, qasm_version, "bw")
        except Exception as exc:  # noqa: BLE001
            errors.append({"stage": "img.qasm", "message": str(exc)})
    if images_settings["composer"]:
        try:
            img["composer"] = qiskit_utils.image_composer_base64(qasm_code, qasm_version)
        except Exception as exc:  # noqa: BLE001
            errors.append({"stage": "img.composer", "message": str(exc)})

    comparison_doc = None
    if settings["comparison"]:
        try:
            comparison_doc = quirk_utils.comparison_markdown(name, url, qasm_code, qasm_version)
        except Exception as exc:  # noqa: BLE001
            errors.append({"stage": "comparison", "message": str(exc)})

    output = {}
    if name is not None:
        output["name"] = name
    output.update({
        "qasm": qasm_block,
        "migrated_code": migrated_code,
        "circuits": circuits,
        "zx_calculus_result": zx_calculus_result,
        "circuit_info": circuit_info,
        "custom_gates": custom_gates,
        "img": img,
        "comparison_doc": comparison_doc,
        "errors": errors,
    })
    return output


def translate_circuit(payload):
    """Función core de la librería: traduce circuitos Quirk con un payload JSON.

    Ejecuta el flujo Quirk -> OpenQASM -> código de proveedor, con las etapas
    opcionales (validación ZX, imágenes en base64, documento de comparación)
    configurables desde el propio payload. Estructura espejo del proyecto:
    ``input`` agrupa las entradas (como la carpeta ``input/``) y ``output``
    las salidas (como la carpeta ``output/``).

    Payload de entrada (dict o cadena JSON):
        - input (dict, obligatorio) con exactamente uno de:
            - url (str): URL de Quirk con ``circuit=<JSON>``; o
            - json (dict | str): circuito Quirk con ``cols``; o
            - circuits (list): lote de ``{name?, url|json, offset?}``.
        - y opcionalmente:
            - offset (int >= 0, default 0): desplazamiento de q[i] (global;
              cada entrada de ``circuits`` puede sobreescribirlo).
            - qasm_version (str, default QTRANS_QASM_VERSION o '3.0'): '2.0'|'3.0'.
            - provider (str | list, default 'qiskit'): alias canónicos
              ('qiskit'/'ibm', 'braket'/'aws', 'pennylane'/'xanadu').
            - shots (int >= 1, default QTRANS_SHOTS o 1000).
            - preserve_custom_gates (bool, default QTRANS_PRESERVE_CUSTOM_GATES).
            - zx (object, default {enabled: true, time: 0.5, timeout: 120}).
            - images (object, default {quirk: false, qasm: false, composer:
              false, capture_timeout: 15}); las imágenes van en base64 en
              ``output.img`` (no se escribe nada en disco).
            - comparison (bool, default false): documento Markdown inline.
            - return_circuit (bool, default false): **solo con circuito único**
              (prohibido con ``circuits``; para lotes existe
              ``translate_circuits``). Añade ``output.circuits`` con el
              circuito nativo de cada proveedor ya cargado vía su parser
              (objetos Python vivos, NO serializables a JSON).

    Respuesta (dict; serializable a JSON salvo ``output.circuits`` cuando
    ``return_circuit`` es true):
        - input: eco de la entrada normalizada (con defaults resueltos y URLs
          efectivas).
        - output: objeto de salida si es circuito único, o **lista** de
          objetos si se usó ``circuits``. Cada objeto contiene:
            - name (str): nombre del circuito; **solo** en modo lote (los
              objetos de un circuito único no incluyen esta clave).
            - qasm (dict): bloque del código generado:
                - code (str): código OpenQASM completo.
                - version (str): versión efectiva de ``code``.
                - lines (int): cantidad de líneas de ``code``.
                - gates (dict): ``custom``/``native``, cada uno con ``count``
                  (operaciones) y ``names`` (nombres únicos, ordenados). Se
                  cuentan sobre el QASM 3.0 previo a la reducción de basis,
                  de modo que el conteo es estable aunque se pida la versión 2.0.
            - migrated_code (dict): código Python por proveedor, con clave
              ``<subcarpeta_proveedor>_code`` (p. ej. ``ibm_qiskit_code``,
              ``aws_braket_code``, ``xanadu_pennylane_code``).
            - circuits (dict | None): si ``return_circuit=true``, ``{proveedor:
              objeto nativo}`` — qiskit → ``QuantumCircuit``, braket →
              ``Circuit``, pennylane → ``QNode`` — obtenido con
              ``load_provider_circuit`` sobre ``qasm.code`` (parser nativo con
              respaldo por script). ``null`` si no se pidió; si la carga de un
              proveedor falla, su valor es ``null`` y el detalle va a
              ``errors`` con stage ``circuits.<proveedor>``.
            - zx_calculus_result (str | None): 'equivalente' |
              'no-equivalente' | 'no-comprobado'; None si zx.enabled=false.
            - circuit_info (dict): n_qubits, n_cols, gates.
            - custom_gates (list): catálogo exhaustivo de las compuertas custom
              **declaradas** en el circuito Quirk (las que se usan y las que no),
              con id, name, qasm_name, kind ('matrix'|'circuit'|'unknown'),
              n_qubits y used_in_circuit (bool).
            - img (dict): {quirk, qasm, composer} en base64 (PNG) o None si
              no se pidió o falló.
            - comparison_doc (str | None): Markdown inline o None.
            - errors (list): [{stage, message}] de etapas opcionales fallidas.

    Parámetros:
        - payload (dict | str): objeto JSON de entrada (dict o cadena).

    Retorna:
        - dict: ``{"input": ..., "output": ...}`` JSON-serializable.

    Lanza:
        - ValueError: payload inválido (claves desconocidas, faltantes, mal
          tipadas o fuera de rango).
        - Propaga las excepciones de la traducción/migración (etapas
          obligatorias); las etapas opcionales nunca lanzan, van a ``errors``.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(f"El payload debe ser JSON válido: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("El payload debe ser un dict o una cadena JSON.")
    _require_keys(payload, _TRANSLATE_TOP_KEYS, "payload")
    if "input" not in payload:
        raise ValueError('El payload debe tener la clave "input".')

    settings = _normalize_translate_input(payload["input"])

    if "circuits" in settings:
        output = [
            _translate_circuit_entry(
                circuit["name"], circuit["url"], circuit["offset"], settings
            )
            for circuit in settings["circuits"]
        ]
    else:
        output = _translate_circuit_entry(None, settings["url"], settings["offset"], settings)

    return {"input": settings, "output": output}


def translate_circuits(payload):
    """Función de librería: traduce circuitos Quirk y devuelve los circuitos ya cargados.

    Es la contrapartida de ``translate_circuit`` para uso programático: en vez de
    devolver el OpenQASM y el código Python migrado, devuelve el **circuito
    nativo de cada proveedor**, listo para ejecutarse.

    El flujo es: Quirk → OpenQASM (2.0 o 3.0) → ``loads`` del proveedor →
    circuito. Cada proveedor usa su propio parser cuando existe:

    - qiskit → ``qiskit.QuantumCircuit`` (``qasm2.loads``/``qasm3.loads``);
    - braket → ``braket.circuits.Circuit`` (``Circuit.from_ir``; el OpenQASM se
      normaliza antes porque el parser de Braket no define ``p``/``cx``/``u1``);
    - pennylane → ``pennylane.QNode`` (no hay parser nativo viable para el
      OpenQASM que genera el proyecto, así que se materializa con su script
      migrado).

    Payload de entrada: el mismo de ``translate_circuit`` (ver su docstring).

    Respuesta (dict):
        - input: eco de la entrada normalizada (igual que ``translate_circuit``).
        - circuits: diccionario ``{provider: {nombre_circuito: circuito}}``, donde
          el proveedor es el nombre canónico ('qiskit', 'braket', 'pennylane') y
          el nombre del circuito es el del JSON de entrada (en modo lote) o
          ``circuit_1`` (circuito único). Los valores son objetos vivos, no
          serializables a JSON.

    Parámetros:
        - payload (dict | str): objeto JSON de entrada (dict o cadena).

    Retorna:
        - dict: ``{"input": ..., "circuits": {provider: {nombre: objeto}}}``.

    Lanza:
        - ValueError: payload inválido (claves desconocidas, faltantes, mal
          tipadas o fuera de rango).
        - Propaga las excepciones de la traducción y de la carga del circuito.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(f"El payload debe ser JSON válido: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("El payload debe ser un dict o una cadena JSON.")
    _require_keys(payload, _TRANSLATE_TOP_KEYS, "payload")
    if "input" not in payload:
        raise ValueError('El payload debe tener la clave "input".')

    settings = _normalize_translate_input(payload["input"])
    qasm_version = settings["qasm_version"]

    if "circuits" in settings:
        entries = [
            (circuit["name"], circuit["url"], circuit["offset"])
            for circuit in settings["circuits"]
        ]
    else:
        entries = [("circuit_1", settings["url"], settings["offset"])]

    circuits = {provider: {} for provider in settings["provider"]}
    for name, url, offset in entries:
        qasm3_source = quirk_utils.quirk_to_qasm(url, offset=offset, qasm_version="3.0")
        qasm_code = (
            qasm3_source if qasm_version == "3.0" else qasm3_to_qasm2(qasm3_source)
        )
        for provider in settings["provider"]:
            circuits[provider][name] = provider_utils.load_provider_circuit(
                qasm_code,
                provider,
                qasm_version=qasm_version,
                shots=settings["shots"],
                preserve_custom_gates=settings["preserve_custom_gates"],
            )

    return {"input": settings, "circuits": circuits}


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
        help=(
            "batch procesa todos los JSON de input-dir (o solo los listados en "
            "--input-files); algorithm procesa input-file."
        ),
    )
    parser.add_argument(
        "--input-file",
        default=DEFAULT_INPUT_FILE,
        help=(
            "Nombre o ruta de un archivo JSON; obligatorio en modo algorithm y "
            "debe quedar vacío en modo batch."
        ),
    )
    parser.add_argument(
        "--input-files",
        nargs="*",
        default=DEFAULT_INPUT_FILES,
        help=(
            "Uno o más archivos JSON (relativos a input-dir); cada valor puede "
            "separarse por espacios o comas. Restringe el modo batch a esos "
            "archivos; si se omite o viene vacío, el modo batch procesa todos "
            "los .json de input-dir."
        ),
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
        "--json-out",
        default=None,
        help=(
            "Escribe el reporte de la corrida como JSON en la ruta indicada "
            "(incluye el código OpenQASM de cada circuito en algorithms[].qasm.code); "
            "con '-' imprime únicamente el JSON en stdout, silenciando la traza."
        ),
    )
    parser.add_argument(
        "--run-label",
        default=DEFAULT_RUN_LABEL,
        help="Etiqueta de la corrida; por defecto DD_MM_YYYY__HH (fecha y hora sin minutos).",
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
    preserve_group = parser.add_mutually_exclusive_group()
    preserve_group.add_argument(
        "--preserve-custom-gates",
        dest="preserve_custom_gates",
        action="store_true",
        help="Conserva las compuertas custom/nativas como funciones locales.",
    )
    preserve_group.add_argument(
        "--no-preserve-custom-gates",
        dest="preserve_custom_gates",
        action="store_false",
        help="Expande en línea las compuertas custom/nativas en los scripts migrados.",
    )
    parser.set_defaults(preserve_custom_gates=None)
    parser.add_argument(
        "--zx-time",
        type=float,
        default=DEFAULT_ZX_TIME,
        help="Snapshot temporal Quirk para gates como Rxft, en el rango 0..1.",
    )
    parser.add_argument(
        "--zx-timeout",
        type=int,
        default=DEFAULT_ZX_TIMEOUT,
        help=(
            "Límite en segundos por comparación/reducción ZX; al excederse se "
            "marca 'NO DEMOSTRADO (timeout)' en lugar de colgar el pipeline."
        ),
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


def _configure_console_encoding():
    """Fuerza UTF-8 en la salida de consola y sustituye lo no codificable.

    La consola de Windows usa ``cp1252``, que no representa todos los símbolos
    de Quirk (``⟩``, ``⟨``, ``†``…). Con ``errors="replace"`` esos caracteres
    se sustituyen en lugar de abortar la etapa que los imprime.

    Retorna:
        - None
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):  # pragma: no cover — depende de la consola
            pass


def main(argv=None):
    _configure_console_encoding()
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    try:
        summary = run_pipeline(
            input_mode=args.input_mode,
            input_file=args.input_file,
            input_files=args.input_files,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            run_label=args.run_label,
            qasm_version=args.qasm_version,
            target_providers=args.providers,
            preserve_custom_gates=args.preserve_custom_gates,
            capture_images=args.capture_images,
            shots=args.shots,
            zx_time=args.zx_time,
            zx_timeout=args.zx_timeout,
            capture_timeout=args.capture_timeout,
            generate_qasm_images=args.generate_qasm_images,
            generate_comparison=args.generate_comparison,
            generate_composer_images=args.generate_composer_images,
            generate_zx=args.generate_zx,
            generate_zx_images=args.generate_zx_images,
            verbose=False if args.json_out == "-" else args.verbose,
            json_out=args.json_out,
            print_status=args.json_out != "-",
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}")
        return 1
    if args.json_out == "-":
        print(json.dumps(summary["json_report"], indent=2, ensure_ascii=False))
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""

Librería de QTransLIFIA: traducción de circuitos Quirk a OpenQASM y a los
ecosistemas objetivo (Qiskit, AWS Braket, PennyLane).

El punto de entrada es ``translate_circuit(payload)``: recibe un payload JSON
(dict o cadena) con el grupo ``input`` (circuito único como ``url``/``json`` o
lote ``circuits``, más ``offset``, ``qasm_version``, ``provider`` y las etapas
opcionales) y devuelve ``{"input": ..., "output": ...}`` sin escribir nada en
disco. ``translate_circuits(payload)`` es la variante que devuelve los
circuitos nativos ya cargados.

Los valores por defecto del payload se pueden parametrizar con variables
``QTRANS_*`` en un archivo ``.env`` del directorio de trabajo actual. Cada
etapa delega en los módulos de ``qtrans.utils``:

- ``utils.qasm_utils``: tablas de ``stdgates.inc``, ángulos, versiones y resumen de compuertas.
- ``utils.quirk_utils``: traducción Quirk → OpenQASM, captura de Quirk y comparación visual.
- ``utils.provider_utils``: registro de proveedores y código Python migrado.
- ``utils.qiskit_utils`` / ``utils.braket_utils`` / ``utils.pennylane_utils``: cada ecosistema.
- ``utils.zx_utils``: grafos ZX (PyZX) y su comparación.

"""

# Importación de las librerías estándar y configuración del entorno
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from .utils import (
    provider_utils,
    qasm_utils,
    quirk_utils,
    zx_utils,
)
from .utils.provider_utils import (
    PROVIDER_DIRECTORY,
    SUPPORTED_PROVIDERS,
    normalize_provider,
    providers_from_env,
)
from .utils.qasm_utils import qasm3_to_qasm2
from .utils.zx_utils import (
    qasm_to_zx_graph,
    quirk_to_zx_graph_with_method,
)

# La configuración de entrada se lee del ``.env`` del directorio de trabajo
# actual (no del árbol del paquete), para que el usuario pueda parametrizar la
# librería desde su propio proyecto; si el archivo no existe no hace nada.
load_dotenv(Path.cwd() / ".env")


# ---------------------------------------------------------------------------
# Configuración (variables QTRANS_* en .env)
# ---------------------------------------------------------------------------
def _configured_bool(variable_name, default):
    configured_value = os.getenv(variable_name)
    if configured_value is None:
        return default
    normalized_value = configured_value.strip().casefold()
    if normalized_value in {"1", "true", "yes", "on", "si"}: return True
    if normalized_value in {"0", "false", "no", "off"}: return False
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


# Obtención de variables constantes relacionadas a la configuración
DEFAULT_QASM_VERSION = _configured_qasm_version()
DEFAULT_ZX_TIME = _configured_float("QTRANS_ZX_TIME", 0.5, minimum=0.0, maximum=1.0)
DEFAULT_ZX_TIMEOUT = _configured_int("QTRANS_ZX_TIMEOUT", 120)
DEFAULT_ZX_ENABLED = _configured_bool("QTRANS_GENERATE_ZX", True)
DEFAULT_SHOTS = _configured_int("QTRANS_SHOTS", 1000)
DEFAULT_CAPTURE_TIMEOUT = _configured_int("QTRANS_CAPTURE_TIMEOUT", 15)
DEFAULT_TARGET_PROVIDERS = providers_from_env()
DEFAULT_PRESERVE_CUSTOM_GATES = _configured_bool("QTRANS_PRESERVE_CUSTOM_GATES", True)


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
    "comparison",
    "return_circuit",
    "generate_provider_code",
})
_TRANSLATE_CIRCUIT_KEYS = frozenset({"name", "url", "json", "offset"})
_TRANSLATE_ZX_KEYS = frozenset({"enabled", "time", "timeout"})


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


def _zx_calculus(url, qasm_code, offset, zx_time, zx_timeout):
    """Compara los grafos ZX de Quirk y del QASM generado.

    Parámetros:
        - url (str): URL de Quirk de origen.
        - qasm_code (str): código OpenQASM generado (2.0 o 3.0).
        - offset (int): desplazamiento de índices q[i].
        - zx_time (float): tiempo de simulación usado en la construcción ZX.
        - zx_timeout (int): límite en segundos de la comparación.

    Retorna:
        - dict: ``{"result": str | None, "errors": [{"stage", "message"}],
          "method": str | None}``. ``result`` es 'equivalente' si los grafos
          son EQUIVALENTES, 'no-equivalente' si son NO EQUIVALENTES o NO
          COMPARABLES y 'no-comprobado' si no se pudo demostrar (timeout, error
          o resultado indeterminado). ``method`` indica cómo se construyó el
          grafo de Quirk: 'directo' o 'aplanado' (custom gates compuestos o
          matrices de más de un qubit expandidos). Los errores de la etapa
          quedan en ``errors`` sin tumbar la traducción.
    """
    method = None
    comparison_method = None
    try:
        base_graph, method = quirk_to_zx_graph_with_method(
            url, offset, time=zx_time
        )
        qasm_graph = qasm_to_zx_graph(
            qasm_code, zx_utils._zx_matrix_gate_names(url)
        )
        comparison_method, result = zx_utils.zx_compare_once(base_graph, qasm_graph, zx_timeout)
    except Exception as exc:  # noqa: BLE001 — la validación ZX nunca debe tumbar la traducción
        return {
            "result": "no-comprobado",
            "errors": [{"stage": "zx", "message": str(exc)}],
            "method": method,
            "comparison_method": comparison_method,
        }
    if result.startswith("EQUIVALENTES"):
        outcome = "equivalente"
    elif result.startswith(("NO EQUIVALENTES", "NO COMPARABLES")):
        outcome = "no-equivalente"
    else:
        outcome = "no-comprobado"
    return {"result": outcome, "errors": [], "method": method, "comparison_method": comparison_method}


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


def _validated_provider(value):
    """Valida y normaliza el proveedor para ``input.provider``.

    Por defecto usa el primer proveedor configurado en
    ``QTRANS_TARGET_PROVIDERS`` (``.env``) o ``qiskit`` si no hay ninguno.
    Si se pasa ``__env__`` explícitamente, se leen todos los proveedores de
    ``QTRANS_TARGET_PROVIDERS``. La API solo admite un proveedor único.

    Parámetros:
        - value: valor recibido en ``input.provider``.

    Retorna:
        - str | tuple[str]: nombre canónico único, o tupla si se pidió
          ``__env__`` con varios proveedores.

    Lanza:
        - ValueError: si no hay proveedores válidos o si el valor es inválido.
    """
    if value is None:
        return DEFAULT_TARGET_PROVIDERS[0] if DEFAULT_TARGET_PROVIDERS else "qiskit"
    if isinstance(value, str) and value.strip().lower() == "__env__":
        providers = DEFAULT_TARGET_PROVIDERS
        return providers if len(providers) != 1 else providers[0]
    if isinstance(value, (list, tuple, set)):
        raise ValueError("input.provider debe ser una cadena con un único proveedor.")
    if isinstance(value, str):
        if not value.strip():
            raise ValueError(
                "input.provider debe contener al menos un proveedor válido: "
                f"{', '.join(SUPPORTED_PROVIDERS)} (alias: ibm, aws, xanadu)."
            )
        if "," in value:
            raise ValueError(
                "input.provider admite un único proveedor; "
                f"recibido {value!r}."
            )
        return normalize_provider(value)
    raise ValueError(
        "input.provider debe ser una cadena, lista o tupla con proveedores válidos: "
        f"{', '.join(SUPPORTED_PROVIDERS)} (alias: ibm, aws, xanadu)."
    )


def _normalize_translate_input(input_payload):
    """Valida y normaliza el grupo ``input`` de un payload de ``translate_circuit``.

    Resuelve los valores por defecto (QASM_VERSION/shots/etc. desde el entorno),
    normaliza el proveedor y construye la URL Quirk efectiva de cada circuito.

    Parámetros:
        - input_payload (dict): objeto ``input`` del payload.

    Retorna:
        - dict: entrada normalizada; sirve como eco en la respuesta y como
          configuración de ejecución. Siempre contiene ``offset``,
          ``qasm_version``, ``provider`` (str), ``shots``,
          ``preserve_custom_gates``, ``return_circuit``, ``zx``,
          ``comparison`` y ``generate_provider_code`` y exactamente uno de
          ``url`` (circuito único) o ``circuits`` (lote).

    Lanza:
        - ValueError: claves desconocidas, falta de circuito, tipos o rangos
          inválidos, o más de un proveedor.
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
        "provider": _validated_provider(input_payload.get("provider")),
        "shots": _validated_int(input_payload.get("shots", DEFAULT_SHOTS), "input.shots", 1),
        "preserve_custom_gates": _validated_bool(
            input_payload.get("preserve_custom_gates", DEFAULT_PRESERVE_CUSTOM_GATES),
            "input.preserve_custom_gates",
        ),
        "comparison": _validated_bool(input_payload.get("comparison", False), "input.comparison"),
        "return_circuit": _validated_bool(
            input_payload.get("return_circuit", False), "input.return_circuit"
        ),
        "generate_provider_code": _validated_bool(
            input_payload.get("generate_provider_code", True), "input.generate_provider_code"
        ),
    }
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
        "enabled": _validated_bool(zx_payload.get("enabled", DEFAULT_ZX_ENABLED), "input.zx.enabled"),
        "time": float(zx_time),
        "timeout": _validated_int(
            zx_payload.get("timeout", DEFAULT_ZX_TIMEOUT), "input.zx.timeout", 1
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


def _translate_to_qasm(url, offset, settings):
    """Traduce Quirk a código OpenQASM y devuelve el bloque ``qasm`` + info."""
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
    return qasm_block, circuit_info, custom_gates


def _generate_provider_code(qasm_code, settings):
    """Genera el diccionario ``migrated_code``.

    Si ``settings['generate_provider_code']`` es ``True`` (por omisión)
    se llama a ``provider_utils.provider_python_source`` para cada proveedor
    configurado; de lo contrario se devuelve un dict vacío.
    """
    if not settings.get("generate_provider_code", True):
        return {}
    providers = settings.get("provider") or DEFAULT_TARGET_PROVIDERS
    if isinstance(providers, str):
        providers = (providers,)
    migrated_code = {}
    for provider in providers:
        migrated_code[f"{PROVIDER_DIRECTORY[provider]}_code"] = provider_utils.provider_python_source(
            qasm_code,
            provider,
            qasm_version=settings["qasm_version"],
            shots=settings["shots"],
            preserve_custom_gates=settings["preserve_custom_gates"],
        )
    return migrated_code


def _load_provider_circuits(qasm_code, settings, errors=None):
    """Carga los circuitos nativos del proveedor (``return_circuit``).

    Parámetros:
        - qasm_code (str): código OpenQASM traducido.
        - settings (dict): entrada normalizada.
        - errors (list | None): lista mutable a la que se appendarán
          errores de carga por proveedor. Si es ``None``, la función no
          registra errores (la captura la llamada ``_translate_circuit_entry``).

    Retorna:
        - dict | ``None``: diccionario ``{provider: circuito_nativo}`` o
          ``None`` si ``return_circuit`` es ``False``. Si un circuito no se
          pudo cargar, su entrada será ``None`` y se registrará un error en
          ``errors`` (cuando se proporcione).

    Nota:
        Cuando ``errors`` no es ``None`` y un proveedor falla, la entrada
        correspondiente en el diccionario de retorno será ``None`` y se
        registrará un dict ``{"stage": "circuits.<nombre>", "message": <texto>}``
        en la lista ``errors``. Esto permite al llamador diferenciar entre
        un circuito que simplemente no tiene circuito nativo cargado y un
        error real de carga.
    """
    if not settings["return_circuit"]:
        return None
    providers = settings.get("provider") or DEFAULT_TARGET_PROVIDERS
    if isinstance(providers, str):
        providers = (providers,)
    circuits: dict[str, object] = {}
    for prov in providers:
        try:
            circuits[prov] = provider_utils.load_provider_circuit(
                qasm_code,
                prov,
                qasm_version=settings["qasm_version"],
                shots=settings["shots"],
                preserve_custom_gates=settings["preserve_custom_gates"],
                native=True,
            )
        except Exception as exc:  # noqa: BLE001 — la carga no interrumpe el resto
            circuits[prov] = None
            if errors is not None:
                errors.append({
                    "stage": f"circuits.{prov}",
                    "message": str(exc),
                })
    return circuits if circuits else None
    return circuits if circuits else None


def _run_zx(url, qasm_code, offset, zx_settings):
    """Ejecuta la validación ZX si está activada; devuelve el dict correspondiente."""
    if not zx_settings["enabled"]:
        return {"result": None, "errors": [], "method": None, "comparison_method": None}
    return _zx_calculus(url, qasm_code, offset, zx_settings["time"], zx_settings["timeout"])


def _run_comparison(name, url, qasm_code, qasm_version, settings):
    """Genera el documento Markdown de comparación si está activado."""
    comparison_doc = None
    if settings["comparison"]:
        try:
            comparison_doc = quirk_utils.comparison_markdown(name, url, qasm_code, qasm_version)
        except Exception as exc:  # noqa: BLE001
            pass
    return comparison_doc


def _translate_circuit_entry(name, url, offset, settings):
    """Traduce un circuito Quirk y arma su objeto de salida completo.

    Ejecuta las etapas de forma modular (QASM → OpenQASM, código de proveedor,
    validación ZX, comparación, carga de circuito).  Los fallos de las
    etapas opcionales se acumulan en ``output['errors']`` sin interrumpir
    el resto.  Esta firma es idéntica a la versión anterior para mantener
    compatibilidad con los tests existentes.

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
          lanzan: van a ``output['errors']``).
    """
    errors = []

    # 1️⃣ QASM + información del circuito
    qasm_block, circuit_info, custom_gates = _translate_to_qasm(url, offset, settings)
    qasm_code = qasm_block["code"]

    # 2️⃣ Código de proveedor (controlado por flag)
    migrated_code = _generate_provider_code(qasm_code, settings)

    # 3️⃣ Cargar circuitos nativos (solo si return_circuit true)
    circuits = None
    if settings["return_circuit"]:
        circuits = _load_provider_circuits(qasm_code, settings, errors=errors)

    # 4️⃣ Validación ZX
    zx_calculus = _run_zx(url, qasm_code, offset, settings["zx"])

    # 5️⃣ Documento de comparación
    comparison_doc = _run_comparison(name, url, qasm_code, qasm_block["version"], settings)

    output = {}
    if name is not None:
        output["name"] = name
    output.update({
        "qasm": qasm_block,
        "migrated_code": migrated_code,
        "circuits": circuits,
        "zx_calculus": zx_calculus,
        "circuit_info": circuit_info,
        "custom_gates": custom_gates,
        "comparison_doc": comparison_doc,
        "errors": errors,
    })
    return output


def translate_circuit(payload):
    """Función core de la librería: traduce circuitos Quirk con un payload JSON.

    Ejecuta el flujo Quirk -> OpenQASM -> código de proveedor, con las etapas
    opcionales (validación ZX, documento de comparación) configurables desde el
    propio payload. Estructura espejo del proyecto:
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
            - provider (str, default primer QTRANS_TARGET_PROVIDERS o 'qiskit'):
              **un único** proveedor, canónico o alias ('qiskit'/'ibm',
              'braket'/'aws', 'pennylane'/'xanadu'). No admite listas ni varios
              separados por comas.
            - shots (int >= 1, default QTRANS_SHOTS o 1000).
            - preserve_custom_gates (bool, default QTRANS_PRESERVE_CUSTOM_GATES).
            - zx (object, default {enabled: QTRANS_GENERATE_ZX, time: 0.5,
              timeout: 120}).
            - comparison (bool, default false): documento Markdown inline.
            - generate_provider_code (bool, default true): genera ``migrated_code``
              para el proveedor configurado a partir del código OpenQASM.
            - return_circuit (bool, default false): añade ``output.circuits``
              con el circuito nativo del proveedor ya cargado vía su parser
              (objeto Python vivo, NO serializable a JSON). Se admite tanto en
              circuito único como en lote: en lote, cada objeto de ``output``
              trae su propio ``circuits``.

    Respuesta (dict; serializable a JSON salvo los objetos de ``circuits``
    cuando ``return_circuit`` es true):
        - input: eco de la entrada normalizada (con defaults resueltos y URLs
          efectivas).
        - output: objeto de salida si es circuito único, o **lista** de
          objetos (uno por URL) si se usó ``circuits``. Cada objeto contiene:
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
            - migrated_code (dict): código Python del proveedor, con una sola
              clave ``<subcarpeta_proveedor>_code`` (p. ej. ``ibm_qiskit_code``,
              ``aws_braket_code``, ``xanadu_pennylane_code``).
            - circuits (dict | None): si ``return_circuit=true``,
              ``{proveedor: objeto nativo}`` — qiskit → ``QuantumCircuit``,
              braket → ``Circuit``, pennylane → ``QNode`` — obtenido con
              ``load_provider_circuit`` sobre ``qasm.code`` (parser nativo con
              respaldo por script). ``null`` si no se pidió; si la carga falla,
              el valor es ``null`` y el detalle va a ``errors`` con stage
              ``circuits.<proveedor>``.
            - zx_calculus_result (str | None): 'equivalente' |
              'no-equivalente' | 'no-comprobado'; None si zx.enabled=false.
            - zx_calculus (dict): detalle de la etapa ZX con
              ``result`` (mismo valor que ``zx_calculus_result``), ``errors``
              (lista de ``{stage, message}``; vacía si no hubo fallos) y
              ``method`` ('directo' si el grafo se construyó sin aplanar,
              'aplanado' si hubo que expandir custom gates compuestos o
              matrices de más de un qubit; None si la etapa no corrió o falló).
            - circuit_info (dict): n_qubits, n_cols, gates.
            - custom_gates (list): catálogo exhaustivo de las compuertas custom
              **declaradas** en el circuito Quirk (las que se usan y las que no),
              con id, name, qasm_name, kind ('matrix'|'circuit'|'unknown'),
              n_qubits y used_in_circuit (bool).
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



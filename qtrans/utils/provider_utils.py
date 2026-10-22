"""Registro de proveedores y dispatch de la migración a cada ecosistema.

Define los proveedores soportados (Qiskit, AWS Braket y PennyLane), sus alias
canónicos y la subcarpeta de salida de cada uno, y despacha la generación del
código Python migrado y la carga del circuito nativo.

La lógica particular de cada ecosistema vive en su propio módulo
(``qiskit_utils``, ``braket_utils``, ``pennylane_utils``); aquí solo se enruta.
Los imports de esos módulos son *diferidos* (dentro de las funciones) para no
arrastrar los SDK pesados al importar el paquete y para evitar ciclos.
"""

import os
import warnings
from pathlib import Path

from .qasm_utils import detect_qasm_version, qasm_custom_gate_operations
from .pipeline_utils import log_stage


# ---------------------------------------------------------------------------
# Proveedores soportados (Qiskit / AWS Braket / PennyLane)
# ---------------------------------------------------------------------------
SUPPORTED_PROVIDERS = ('qiskit', 'pennylane', 'braket')

# Sinónimos admitidos en .env, CLI y cargar_circuito_qasm().
PROVIDER_ALIASES = {
    'qiskit': 'qiskit', 'ibm': 'qiskit', 'ibm_qiskit': 'qiskit',
    'braket': 'braket', 'aws': 'braket', 'aws_braket': 'braket',
    'pennylane': 'pennylane', 'xanadu': 'pennylane', 'xanadu_pennylane': 'pennylane',
}

# Subcarpeta de migrated_circuits/ por proveedor (coincide con qtrans/core.py y el README).
PROVIDER_DIRECTORY = {
    'qiskit': 'ibm_qiskit',
    'braket': 'aws_braket',
    'pennylane': 'xanadu_pennylane',
}


def normalize_provider(provider):
    """Normaliza un alias de proveedor a su nombre canónico.

    Parámetros:
        - provider (str): 'ibm', 'aws', 'xanadu', 'qiskit', 'braket' o 'pennylane'.

    Retorna:
        - str: 'qiskit', 'braket' o 'pennylane'.
    """
    key = str(provider).strip().casefold()
    normalized = PROVIDER_ALIASES.get(key)
    if normalized is None:
        raise ValueError(
            f'Provider no soportado: {provider!r}; opciones: '
            f'{", ".join(SUPPORTED_PROVIDERS)} (alias: ibm, aws, xanadu)'
        )
    return normalized


def parse_providers(value):
    """Convierte una lista separada por comas de proveedores a nombres canónicos.

    Parámetros:
        - value (str | None): p. ej. 'IBM, AWS, XANADU'.

    Retorna:
        - tuple[str]: nombres canónicos únicos (sin vacíos).
    """
    items = [value] if isinstance(value, str) else value
    providers = []
    for item in items:
        for token in str(item).split(','):
            if not token.strip():
                continue
            normalized = normalize_provider(token)
            if normalized not in providers:
                providers.append(normalized)
    if not providers:
        raise ValueError(
            f'providers debe contener al menos un provider; opciones: '
            f'{", ".join(SUPPORTED_PROVIDERS)}'
        )
    return tuple(providers)


def providers_from_env(getenv=None, default='qiskit'):
    """Lee los proveedores configurados desde las variables de entorno.

    Única variable: ``QTRANS_TARGET_PROVIDERS``, con valores canónicos
    ``qiskit``, ``pennylane`` y ``braket`` (se toleran los alias ``ibm``,
    ``aws`` y ``xanadu``).  Si no está definida se devuelve ``default``.
    La variable ``QTRANS_PROVIDERS`` quedó obsoleta: se ignora su valor y,
    si está definida, se emite un ``UserWarning``.

    Parámetros:
        - getenv (callable | None): función tipo os.getenv (para tests; opcional).
        - default (str): valor si la variable no está definida.

    Retorna:
        - tuple[str]: nombres canónicos de proveedores.

    Lanza:
        - ValueError: si el valor no corresponde a ningún proveedor soportado.
    """
    if getenv is None:
        getenv = os.getenv

    if getenv('QTRANS_PROVIDERS'):
        warnings.warn(
            "QTRANS_PROVIDERS quedó obsoleta; usa QTRANS_TARGET_PROVIDERS. "
            "Se ignora su valor.",
            UserWarning,
            stacklevel=2,
        )
    configured = getenv('QTRANS_TARGET_PROVIDERS') or default
    return parse_providers(configured)


def provider_python_source(qasm_source, provider, qasm_version='3.0', shots=1000,
                           preserve_custom_gates=False):
    """Devuelve el código Python ejecutable para el proveedor destino.

    El código se genera a partir del **IR canónico** (el ``QuantumCircuit`` que
    produce el parser de Qiskit), que es el único que conserva la estructura del
    OpenQASM: declaraciones ``gate`` custom, modificadores ``ctrl @`` con su
    ``ctrl_state`` y nombres exactos de compuerta. Por eso la generación de
    código no usa el parser nativo de cada proveedor (ver
    ``load_provider_circuit``, que sí lo usa para devolver el circuito).

    Parámetros:
        - qasm_source (str): código OpenQASM (2.0 o 3.0).
        - provider (str): nombre o alias del proveedor.
        - qasm_version (str): '2.0' o '3.0'.
        - shots (int): disparos (solo PennyLane).
        - preserve_custom_gates (bool): conserva custom gates como funciones.

    Retorna:
        - str: el código Python del script migrado.
    """
    # Import a nivel de función: los módulos de proveedor importan de este archivo
    # (_angle_to_expr y helpers), así que un import a nivel de módulo sería cíclico.
    from .braket_utils import _braket_python_source
    from .pennylane_utils import _pennylane_python_source
    from .qiskit_utils import _load_qiskit_native, _qiskit_python_source

    provider = normalize_provider(provider)
    if qasm_version not in {'2.0', '3.0'}:
        raise ValueError("qasm_version debe ser '2.0' o '3.0'")

    circuit = _load_qiskit_native(qasm_source, qasm_version, fallback=False)
    custom_gate_definitions = None
    if preserve_custom_gates:
        # El parser solo conserva las compuertas custom que se usan en el
        # circuito; las declaradas y no usadas se recuperan del OpenQASM para
        # que el script migrado sea exhaustivo con la biblioteca del original.
        custom_gate_definitions = qasm_custom_gate_operations(qasm_source)

    if provider == 'qiskit':
        return _qiskit_python_source(
            circuit,
            preserve_custom_gates=preserve_custom_gates,
            custom_gate_definitions=custom_gate_definitions,
        )
    if provider == 'braket':
        return _braket_python_source(
            circuit,
            preserve_custom_gates=preserve_custom_gates,
            custom_gate_definitions=custom_gate_definitions,
        )
    return _pennylane_python_source(
        circuit,
        shots=shots,
        preserve_custom_gates=preserve_custom_gates,
        custom_gate_definitions=custom_gate_definitions,
    )


def _cargar_circuito_desde_codigo(qasm_str, provider, qasm_version, shots, preserve_custom_gates):
    """Materializa el circuito nativo del proveedor ejecutando su script migrado.

    Parámetros:
        - qasm_str (str): código OpenQASM.
        - provider (str): nombre canónico del proveedor.
        - qasm_version (str): '2.0' o '3.0'.
        - shots (int): disparos (solo PennyLane).
        - preserve_custom_gates (bool): conserva custom gates como funciones.

    Retorna:
        - object: el objeto 'circuit' del namespace (QuantumCircuit/Circuit/QNode).
    """
    source = provider_python_source(
        qasm_str,
        provider,
        qasm_version=qasm_version,
        shots=shots,
        preserve_custom_gates=preserve_custom_gates,
    )
    namespace = {}
    exec(compile(source, f'<cargar_circuito_qasm:{provider}>', 'exec'), namespace)
    return namespace['circuit']


def load_provider_circuit(qasm_source, provider, qasm_version='3.0', shots=1000,
                           preserve_custom_gates=False, native=True):
    """Carga el circuito del proveedor con **el parser nativo de ese proveedor**.

    Es el punto único de carga de OpenQASM hacia cada ecosistema:

    - **Qiskit**: ``qasm2.loads``/``qasm3.loads`` → ``QuantumCircuit``.
    - **AWS Braket**: ``Circuit.from_ir`` → ``Circuit`` (el código se normaliza
      antes: ``_normalize_for_braket``). Si el parser nativo rechaza el código,
      se recurre al respaldo por script migrado.
    - **Xanadu PennyLane**: no existe parser nativo utilizable para el OpenQASM
      que genera este proyecto (``qml.from_qasm`` exige el plugin
      ``pennylane-qiskit`` y ``qml.from_qasm3`` rechaza los registros ``qreg``
      indexados), así que el circuito se materializa ejecutando su script
      migrado → ``QNode``.

    Parámetros:
        - qasm_source (str): código OpenQASM (2.0 o 3.0).
        - provider (str): nombre o alias del proveedor.
        - qasm_version (str): '2.0' o '3.0'; si es None se detecta de la cabecera.
        - shots (int): disparos (solo PennyLane).
        - preserve_custom_gates (bool): conserva las puertas custom como funciones locales en el respaldo por script migrado.
        - native (bool): si False, siempre se materializa el circuito ejecutando el script migrado (sin usar el parser nativo del proveedor).

    Retorna:
        - qiskit -> ``qiskit.QuantumCircuit``; braket -> ``braket.circuits.Circuit``;
          pennylane -> ``pennylane.QNode`` (circuito ejecutable).

    Lanza:
        - ValueError: si el proveedor no está soportado, la versión de OpenQASM
          no es válida o el circuito no se puede cargar.
    """
    from .braket_utils import _load_braket_native
    from .qiskit_utils import _load_qiskit_native

    canonical = normalize_provider(provider)
    version = detect_qasm_version(qasm_source, qasm_version)
    if version not in ('2.0', '3.0'):
        raise ValueError(f"Versión de OpenQASM no soportada: {version!r} (use '2.0' o '3.0')")

    if canonical == 'qiskit':
        if native:
            return _load_qiskit_native(qasm_source, version)
        return _cargar_circuito_desde_codigo(
            qasm_source, canonical, version, shots, preserve_custom_gates
        )

    if canonical == 'pennylane':
        # Sin parser nativo viable: el circuito es el propio script migrado.
        return _cargar_circuito_desde_codigo(
            qasm_source, canonical, version, shots, preserve_custom_gates
        )

    native_error = None
    if native:
        try:
            return _load_braket_native(qasm_source)
        except Exception as exc:
            native_error = exc

    try:
        return _cargar_circuito_desde_codigo(
            qasm_source, canonical, version, shots, preserve_custom_gates
        )
    except Exception as source_error:
        attempted = (
            f'parser nativo ({type(native_error).__name__}: {native_error}); '
            if native_error is not None
            else ''
        )
        raise ValueError(
            f'No se pudo cargar el circuito para {canonical!r}: {attempted}'
            f'migración ({type(source_error).__name__}: {source_error})'
        ) from source_error


def cargar_circuito_qasm(qasm_str: str, provider: str, qasm_version: str = None,
                         shots: int = 1000, preserve_custom_gates: bool = False,
                         native: bool = True):
    """Carga un circuito cuántico desde una cadena OpenQASM según el proveedor especificado.

    Parámetros:
        - qasm_str (str): código OpenQASM (2.0 o 3.0; si ``qasm_version`` no se indica,
          la versión se detecta de la cabecera ``OPENQASM x.y;``).
        - provider (str): 'qiskit'/'ibm', 'braket'/'aws' o 'pennylane'/'xanadu'
          (ver ``PROVIDER_ALIASES``).
        - qasm_version (str): '2.0' | '3.0'; fuerza la versión a usar en el parseo.
        - shots (int): disparos para el circuito PennyLane del respaldo por migración.
        - preserve_custom_gates (bool): conserva las puertas custom como funciones locales
          en el respaldo por migración.
        - native (bool): ``True`` usa el parser nativo del proveedor cuando existe
          (Qiskit siempre, Braket si reconoce el código); ``False`` materializa siempre
          el circuito vía ``provider_python_source``+``exec``.

    Funcionalidad:
        Delega en ``load_provider_circuit``, que parsea con la librería del
        proveedor. Qiskit y Braket usan su parser nativo; el de Braket se
        complementa con un respaldo porque no cubre todo el OpenQASM que genera
        este proyecto. PennyLane se materializa siempre con su script migrado,
        porque su parser nativo tampoco sirve aquí: ``qml.from_qasm`` exige el
        plugin ``pennylane-qiskit`` y ``qml.from_qasm3`` no acepta los registros
        ``qreg`` indexados.

    Retorna:
        - qiskit -> ``qiskit.QuantumCircuit``; braket -> ``braket.circuits.Circuit``;
        - pennylane -> ``pennylane.QNode`` (circuito ejecutable).
    """
    if qasm_str is None or not str(qasm_str).strip():
        raise ValueError('qasm_str está vacío')
    return load_provider_circuit(
        qasm_str,
        provider,
        qasm_version=qasm_version,
        shots=shots,
        preserve_custom_gates=preserve_custom_gates,
        native=native,
    )


def generate_provider_files(records, providers, migrated_dir, qasm_version, shots, verbose,
                            preserve_custom_gates=False):
    """Genera los scripts Python migrados de cada circuito para cada proveedor.

    Parámetros:
        - records (list[dict]): registros de los circuitos (claves ``name`` y
          ``qasm_source``).
        - providers (list[str] | tuple[str, ...]): proveedores canónicos.
        - migrated_dir (str | Path): carpeta raíz de ``migrated_circuits``.
        - qasm_version (str): '2.0' o '3.0'.
        - shots (int): disparos (solo PennyLane).
        - verbose (bool): muestra el log de cada etapa.
        - preserve_custom_gates (bool): conserva las compuertas custom como
          funciones locales en el script migrado.

    Retorna:
        - tuple[list[pathlib.Path], list[tuple[str, Exception]]]: archivos
          generados y los errores (``(etiqueta, excepción)``).
    """
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
                    preserve_custom_gates=preserve_custom_gates,
                )
                compile(source, str(output_path), "exec")
                output_path.write_text(source, encoding="utf-8")
                generated.append(output_path)
                log_stage(verbose, provider, f"Generado {output_path.relative_to(migrated_dir)}.")
            except Exception as exc:
                errors.append((f"{provider}/{record['name']}", exc))
                print(f"Error generando {provider}/{record['name']}: {exc}")
    return generated, errors

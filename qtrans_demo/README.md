# qtrans_demo

Subproyecto aislado para probar la librería `qtranslifia` instalada desde PyPI, sin depender del código fuente de QTransLIFIA.

## Puesta en marcha
Desde el directorio del subproyecto creamos el entorno virtual de ejecución, lo activamos, instalamos las dependencias necesarias y ejecutamos el script Python principal.

```bash
cd qtrans_demo
python -m venv demo_venv
source demo_venv/Scripts/activate
python -m pip install -r requirements.txt
python main.py
```

En Linux/macOS, activá con `source demo_venv/bin/activate`.

## Qué hace

- Lee `input/custom_gates_algorithms.json`.
- Traduce los circuitos con `qtrans.translate_circuit`.
- Carga el circuito nativo del proveedor configurado y lo simula con 1024 shots.
- Guarda QASM, scripts migrados y conteos en `output/run_DD_MM_YYYY__HH/<proveedor>/<algoritmo>/`.

La configuración se toma de `.env`. `main.py` verifica que se ejecute con `demo_venv` y que `qtrans` se importe desde ese entorno, nunca desde el repositorio.

## Ejecución por consola de comandos

El demo debe correr **siempre** con el intérprete de `demo_venv`; si se invoca con otro Python, `main.py` aborta con un mensaje accionable. Hay dos formas equivalentes:

**1. Con el entorno activado** (desde `qtrans_demo/`):

```bash
source demo_venv/Scripts/activate      # Git Bash / macOS / Linux
# o bien: .venv\Scripts\Activate.ps1    # PowerShell
python main.py
```

**2. Sin activar el entorno**, usando directamente el intérprete del venv:

```bash
# desde la raíz del repositorio
qtrans_demo/demo_venv/Scripts/python.exe qtrans_demo/main.py

# o desde qtrans_demo/
demo_venv/Scripts/python.exe main.py
```

### Elegir el proveedor desde la consola

`translate_circuit` acepta **un único proveedor por llamada**. El demo lee `QTRANS_TARGET_PROVIDERS` (un solo valor) y elige el simulador correspondiente:

| Valor en `.env` | Alias            | Simulador                     |
| --------------- | ---------------- | ----------------------------- |
| `qiskit`        | `ibm`            | `qiskit-aer` (`AerSimulator`) |
| `braket`        | `aws`            | `LocalSimulator` de `braket`  |
| `pennylane`     | `xanadu`, `pl`   | `default.qubit` del `QNode`   |

Se puede sobrescribir `.env` en la propia invocación, sin editarlo:

```bash
# Git Bash / macOS / Linux
QTRANS_TARGET_PROVIDERS=qiskit    python main.py
QTRANS_TARGET_PROVIDERS=braket    python main.py
QTRANS_TARGET_PROVIDERS=pennylane python main.py
```

```powershell
# PowerShell
$env:QTRANS_TARGET_PROVIDERS="braket"; python main.py
```

Los conteos se normalizan a la convención de Qiskit (bit más significativo a la izquierda); Braket, que usa *big-endian*, se invierte para que los tres proveedores sean comparables.

## Estructura de la corrida (`run_<estampa_fecha_hora>`)

Cada ejecución crea un **directorio de corrida nuevo**, identificado por la fecha y la hora de inicio con el formato `DD_MM_YYYY__HH` (día, mes, año y hora en 24 h; por ejemplo `run_28_10_2026__11`). Así, dos corridas nunca se pisan y es posible comparar ejecuciones sucesivas.

Dentro de la corrida, las salidas se separan **por proveedor** y luego **por algoritmo**:

```
output/
└── run_28_10_2026__11/                 # corrida: DD_MM_YYYY__HH
    ├── qiskit/                         # proveedor
    │   ├── 1._complex_customs/
    │   │   ├── 1._complex_customs_v3.0.txt
    │   │   ├── 1._complex_customs_ibm_qiskit_code.py
    │   │   └── 1._complex_customs_counts_qiskit.json
    │   └── 2._rotational_customs/
    │       └── ...
    ├── braket/                         # proveedor
    │   ├── 1._complex_customs/
    │   │   ├── 1._complex_customs_v3.0.txt
    │   │   ├── 1._complex_customs_aws_braket_code.py
    │   │   └── 1._complex_customs_counts_braket.json
    │   └── 2._rotational_customs/
    │       └── ...
    └── pennylane/                      # proveedor
        └── ...
```

- **Corrida**: `run_<DD_MM_YYYY__HH>` (una por ejecución).
- **Proveedor**: `qiskit`, `braket` o `pennylane`, según `QTRANS_TARGET_PROVIDERS`. Solo aparece la carpeta del proveedor de esa corrida.
- **Algoritmo**: nombre del circuito saneado (espacios y caracteres especiales → `_`).
- La carpeta base `output/` se puede cambiar con `QTRANS_OUTPUT_DIR` (relativa a `qtrans_demo/`).

## Salidas de resultados

Para cada algoritmo se guardan tres archivos:

| Archivo                                | Contenido                                    |
| -------------------------------------- | -------------------------------------------- |
| `<algoritmo>_v<version>.txt`           | El OpenQASM traducido (`2.0` o `3.0`).       |
| `<algoritmo>_<proveedor>_code.py`      | El script migrado al ecosistema destino.     |
| `<algoritmo>_counts_<proveedor>.json`  | Los conteos de la simulación (shots).        |

Además, la corrida imprime por consola el circuito OpenQASM y, por cada algoritmo, la distribución de medición ordenada por frecuencia:

```
Proveedor: qiskit | QASM: 3.0 | Shots: 1024
Run dir: ...\qtrans_demo\output\run_28_10_2026__11

===== 1. complex_customs [qiskit] =====
OPENQASM 3.0;
... (circuito completo) ...

Resultados guardados en: ...\output\run_28_10_2026__11\qiskit\1._complex_customs

-------- simulación qiskit (1024 shots) --------
  01:   474  ( 46.29 %)
  10:   283  ( 27.64 %)
  11:   174  ( 16.99 %)
  00:    93  (  9.08 %)
  total: 1024 shots
```

Si una etapa opcional falla (por ejemplo, el circuito nativo no se pudo cargar o el simulador rechazó el circuito), el error se informa en consola y los archivos QASM/script se guardan igualmente, sin conteos.

## Variables de entorno (`.env`)

| Variable                       | Default                              | Descripción                                  |
| ------------------------------ | ------------------------------------ | -------------------------------------------- |
| `QTRANS_INPUT_FILE`            | `input/custom_gates_algorithms.json` | Registro de circuitos de entrada.            |
| `QTRANS_OUTPUT_DIR`            | `output`                             | Carpeta base de salida (relativa al demo).   |
| `QTRANS_TARGET_PROVIDERS`      | `qiskit`                             | Proveedor único a traducir/simular.          |
| `QTRANS_QASM_VERSION`          | `3.0`                                | Versión de OpenQASM (`2.0` o `3.0`).         |
| `QTRANS_SHOTS`                 | `1024`                               | Disparos de la simulación.                   |
| `QTRANS_SEED`                  | `1234`                               | Semilla del simulador.                       |
| `QTRANS_PRESERVE_CUSTOM_GATES` | `true`                               | Conserva compuertas custom como funciones.   |
| `QTRANS_GENERATE_ZX`           | `false`                              | Activa el cálculo ZX (no usado por el demo). |

# QTransLIFIA

QTransLIFIA traduce circuitos cuánticos de [Quirk](https://algassert.com/quirk) a OpenQASM 3.0 y ofrece dos formas de trabajo: un pipeline Python/CLI y cuadernos Jupyter para exploración, visualización y migración a otros frameworks.

## Estructura

```text
.
├── input/                         # JSON de entrada del CLI
├── output/                        # OpenQASM y capturas generadas por el CLI
│   ├── algorithms_qasm/
│   └── circuits_quirk/
├── notebooks/
│   ├── input/                     # Datos usados por los cuadernos
│   ├── algorithms_qasm/           # Fuentes OpenQASM 3.0
│   ├── circuits_qasm/             # Diagramas OpenQASM
│   ├── circuits_quirk/            # Diagramas Quirk
│   ├── output/migrated_circuits/  # Código Qiskit, Braket y PennyLane
│   ├── ZXCalculus/                # Grafos y análisis ZX
│   └── QTrans_LIFIA_algorithms_jose.ipynb
├── utils/qutils.py                # Traducción Quirk/OpenQASM, grafos y captura
├── qtrans.py                      # API Python y CLI del pipeline
├── translator.py                  # API HTTP heredada
├── requirements.txt
└── requirements_original.txt
```

Los cuadernos mantienen sus datos y resultados dentro de `notebooks/`. El CLI utiliza las carpetas `input/` y `output/` de la raíz del proyecto.

## Instalación

Se recomienda Python 3.12, que es la versión usada en el entorno de desarrollo.

```bash
python -m venv .venv
```

Activa el entorno:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

Instala las dependencias:

```bash
python -m pip install -r requirements.txt
```

Para capturar circuitos Quirk como PNG se necesita Chrome o Chromium disponible en el equipo. Selenium inicia el navegador en modo headless.

## Configuración

El CLI carga `.env` desde la raíz del proyecto. La configuración local actual está en `.env`; la plantilla compartible está en `.env.example`.

```dotenv
QTRANS_INPUT_MODE=batch
QTRANS_INPUT_FILE=
QTRANS_INPUT_DIR=notebooks/input
QTRANS_OUTPUT_DIR=notebooks/output
QTRANS_QASM_DIR=notebooks/algorithms_qasm
QTRANS_QUIRK_IMAGES_DIR=notebooks/circuits_quirk
QTRANS_QASM_IMAGES_DIR=notebooks/circuits_qasm
QTRANS_COMPARE_DIR=notebooks/compare
QTRANS_ZX_DIR=notebooks/ZXCalculus
QTRANS_MIGRATED_DIR=notebooks/output/migrated_circuits
QTRANS_CAPTURE_IMAGES=true
QTRANS_GENERATE_QASM_IMAGES=true
QTRANS_GENERATE_COMPARISON=true
QTRANS_GENERATE_ZX=true
QTRANS_GENERATE_ZX_IMAGES=true
QTRANS_VERBOSE=false
QTRANS_QASM_VERSION=3.0
QTRANS_ZX_TIME=0.5
QTRANS_SHOTS=1000
QTRANS_CAPTURE_TIMEOUT=15
QTRANS_TARGET_PROVIDERS=ibm_qiskit
```

Todas las rutas relativas se resuelven desde la raíz del proyecto. Los valores de arriba son los defaults incorporados en `qtrans.py`; `.env` permite cambiarlos para la ejecución local y `.env.example` sirve como plantilla compartible.

| Variable                      | Uso y valores                                                                                                        |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `QTRANS_INPUT_MODE`           | `batch` procesa todos los JSON del directorio; `algorithm` procesa un solo archivo. Default: `batch`.                |
| `QTRANS_INPUT_FILE`           | Archivo JSON seleccionado en modo `algorithm`. Vacío por defecto; puede pasarse también por CLI.                     |
| `QTRANS_INPUT_DIR`            | Directorio de JSON de entrada. Default: `notebooks/input`.                                                           |
| `QTRANS_OUTPUT_DIR`           | Raíz de los resultados del pipeline. Default: `notebooks/output`.                                                    |
| `QTRANS_QASM_DIR`             | Archivos OpenQASM generados. Default: `notebooks/algorithms_qasm`.                                                   |
| `QTRANS_QUIRK_IMAGES_DIR`     | Capturas PNG de Quirk. Default: `notebooks/circuits_quirk`.                                                          |
| `QTRANS_QASM_IMAGES_DIR`      | Diagramas PNG de los circuitos OpenQASM. Default: `notebooks/circuits_qasm`.                                         |
| `QTRANS_COMPARE_DIR`          | Informes Markdown de comparación visual. Default: `notebooks/compare`.                                               |
| `QTRANS_ZX_DIR`               | Grafos, comparativas e imágenes ZX. Default: `notebooks/ZXCalculus`.                                                 |
| `QTRANS_MIGRATED_DIR`         | Raíz de los scripts por provider; crea un subdirectorio por provider. Default: `notebooks/output/migrated_circuits`. |
| `QTRANS_TARGET_PROVIDERS`     | Lista separada por comas: `ibm_qiskit`, `aws_braket`, `pennylane`. Default: `ibm_qiskit`.                            |
| `QTRANS_QASM_VERSION`         | Formato fuente generado: `2.0` o `3.0`. Default: `3.0`.                                                              |
| `QTRANS_CAPTURE_IMAGES`       | Activa capturas de Quirk. Booleano (`true/false`, `yes/no`, `on/off`, `1/0`). Default: `true`.                       |
| `QTRANS_GENERATE_QASM_IMAGES` | Activa diagramas de los circuitos QASM. Booleano. Default: `true`.                                                   |
| `QTRANS_GENERATE_COMPARISON`  | Activa páginas de comparación Quirk/QASM. Booleano. Default: `true`.                                                 |
| `QTRANS_GENERATE_ZX`          | Activa conversión y comparación de grafos ZX. Booleano. Default: `true`.                                             |
| `QTRANS_GENERATE_ZX_IMAGES`   | Activa diagramas SVG de grafos ZX. Booleano. Default: `true`.                                                        |
| `QTRANS_VERBOSE`              | Muestra el resultado de cada etapa del pipeline. Booleano. Default: `false`.                                         |
| `QTRANS_ZX_TIME`              | Snapshot temporal Quirk para gates como `Rxft`, en el rango `0..1`. Default: `0.5`.                                  |
| `QTRANS_SHOTS`                | Número de shots para los QNodes PennyLane con mediciones. Entero positivo; default: `1000`.                          |
| `QTRANS_CAPTURE_TIMEOUT`      | Timeout de carga/captura del navegador Selenium, en segundos. Entero positivo; default: `15`.                        |

Coloca en `input/` uno o más archivos `.json`. Cada archivo debe ser un objeto cuyas claves son nombres de algoritmos y cuyos valores incluyen una URL de Quirk:

```json
{
	"1. Ejemplo": {
		"url": "https://algassert.com/quirk#circuit=...",
		"offset": 0,
		"desc": "Descripción opcional"
	}
}
```

`url` es obligatorio; `offset` y `desc` son opcionales. El modo batch procesa los JSON del primer nivel de `input/` (no busca recursivamente). Si el nombre del archivo es `popular_algorithms.json`, los nombres de salida llevan el prefijo `popular_`.

## CLI

Ejecuta los comandos desde la raíz del repositorio.

Procesar todos los JSON de `input/`:

```bash
python qtrans.py --input-mode batch
```

Procesar un único JSON:

```bash
python qtrans.py --input-mode algorithm --input-file algorithms.json
```

`--input-file` acepta un nombre relativo a `input/`, una ruta relativa al directorio actual o una ruta absoluta. Las opciones `--input-dir`, `--qasm-dir` y `--quirk-images-dir` permiten reemplazar las rutas configuradas.

Omitir las capturas PNG:

```bash
python qtrans.py --input-mode batch --no-capture
```

Forzar capturas aunque `.env` tenga `QTRANS_CAPTURE_IMAGES=false`:

```bash
python qtrans.py --input-mode batch --capture-images
```

Para consultar todos los argumentos:

```bash
python qtrans.py --help
```

El resultado es OpenQASM 3.0 en `output/algorithms_qasm/` y, cuando las capturas están activas, imágenes PNG en `output/circuits_quirk/`. Los errores de captura se contabilizan y no cancelan la conversión del JSON.

## Uso Como Librería

`qtrans.py` también expone `run_pipeline` para integrar la traducción en código Python:

```python
from qtrans import run_pipeline

batch_result = run_pipeline(input_mode="batch")
single_result = run_pipeline(
		input_mode="algorithm",
		input_file="algorithms.json",
		capture_images=False,
)
```

La función devuelve un resumen con los archivos procesados, algoritmos, archivos QASM, capturas y errores. También se puede pasar `input_dir`, `qasm_dir` y `quirk_images_dir` como argumentos.

## Cuadernos Jupyter

Los cuadernos se conservan como flujo alternativo e independiente del CLI. Abre `notebooks/QTrans_LIFIA_algorithms_jose.ipynb`, selecciona un kernel con las dependencias instaladas y ejecuta las celdas en orden. La primera celda verifica e instala los paquetes necesarios en el kernel.

El cuaderno principal lee `notebooks/input/algorithms.json` y `notebooks/input/popular_algorithms.json`, genera OpenQASM y diagramas bajo `notebooks/`, y crea los scripts migrados en:

- `notebooks/output/migrated_circuits/qiskit/`
- `notebooks/output/migrated_circuits/aws_braket/`
- `notebooks/output/migrated_circuits/pennylane/`

Los scripts Braket requieren `amazon-braket-sdk`; los scripts PennyLane requieren `pennylane`. Las celdas de migración leen los archivos OpenQASM de `notebooks/algorithms_qasm/`.

## API HTTP Heredada

`translator.py` conserva la API Flask usada por las integraciones existentes. Se inicia con:

```bash
python translator.py
```

El servidor escucha en `http://localhost:8081`. Endpoints POST disponibles:

- `/code/ibm` y `/code/ibm/individual`
- `/code/aws` y `/code/aws/individual`
- `/code/qasm` y `/code/qasm/individual`

La colección de Postman está en `postman/Quirk_Translator_IBM_AWS.postman_collection_original.json`.

## Pruebas

Ejecuta la suite del pipeline con:

```bash
python -m unittest discover -s test -p "test_*.py" -v
```

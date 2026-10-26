# QTransLIFIA - Testing y Estrategias de Comprobación del Flujo

## 1. Introducción

El flujo de QTransLIFIA no es una transformación monolítica: es una **tubería de etapas** (parsing de la URL/JSON de Quirk, análisis estructurado, traducción a OpenQASM, generación de imágenes, comparación visual, grafos ZX y migración a ecosistemas) donde cada paso transforma la representación del circuito. Cada transformación es una oportunidad de introducir un defecto y, por lo tanto, un punto donde la comprobación es necesaria.

El paso más crítico de todo el flujo es la **traducción Quirk → OpenQASM**: los errores introducidos allí se propagan a todos los artefactos posteriores. Por ello, QTransLIFIA propone comprobar la traducción mediante **tres familias de estrategias complementarias**:

1. **Verificación estática**: comprobación de características del circuito (cantidad de compuertas, qubits, dimensiones, controles, *custom gates*) sobre la representación analizada, sin ejecutar el circuito.
2. **Equivalencia semántica mediante cálculo ZX**: comparación automática entre el grafo ZX derivado de la fuente Quirk y el derivado del OpenQASM generado, para establecer equivalencia de la transformación unitaria.
3. **Comprobación visual rápida**: herramientas gráficas (capturas, diagramas, comparaciones lado a lado) aptas para inspección humana inmediata, especialmente en circuitos sencillos.

Sobre esas tres familias se apoya el **arsenal de pruebas efectivamente desplegado** en el repositorio, que es lo que este documento precisa: qué baterías existen, cómo se ejecutan, qué garantía aporta cada una y qué límites tienen. La mantener al día es parte del mantenimiento de la librería: una batería que documenta un contrato congelado deja de ser redundante y pasa a ser el mecanismo que detecta su propia rotura.

## 2. El Flujo como Objeto de Prueba

`run_pipeline` (`qtrans/core.py:310`) orquesta el flujo completo. Cada etapa puede activarse/desactivarse de forma independiente mediante flags (CLI) o variables de entorno (`QTRANS_*`), lo que permite **probar cada paso aislado**:

| Etapa | Artefacto principal | Flag / `QTRANS_*` | Riesgo si falla |
| --- | --- | --- | --- |
| Lectura de entradas | JSON del directorio `input/` | `input_mode` / `input_file` | Algoritmos ausentes o mal parseados |
| Traducción | OpenQASM en `algorithms_qasm/*.txt` | (siempre activa) | Semántica del circuito alterada |
| Captura Quirk | PNG en `imgs/circuits_quirk/` | `capture_images` / `QTRANS_CAPTURE_IMAGES` | Referencia visual indisponible |
| Diagrama OpenQASM | PNG en `imgs/circuits_qasm/` | `generate_qasm_images` / `QTRANS_GENERATE_QASM_IMAGES` | Sin inspección visual del QASM |
| Comparación visual | Markdown en `imgs/visual_comparisons/` | `generate_comparison` / `QTRANS_GENERATE_COMPARISON` | Sin contraste lado a lado |
| Grafos ZX | JSON + `comparison_results.md` en `ZXCalculus/` | `generate_zx` / `QTRANS_GENERATE_ZX` | Sin equivalencia semántica automática |
| Migración | Scripts en `migrated_circuits/` | `QTRANS_TARGET_PROVIDERS` | Backend recibe un circuito incorrecto |

El determinismo de `quirk_to_qasm` (`qtrans/utils/quirk_utils.py:1437`) (misma URL → mismo OpenQASM) es el prerequisito que convierte a cada una de estas etapas en **comprobable automáticamente** (*golden tests*, *regression tests*, *differential testing*).

La arquitectura del paquete se reorganizó en módulos de responsabilidad única (`qtrans/core.py` como orquestador y `qtrans/utils/{qasm,quirk,provider,pipeline,qiskit,braket,pennylane,zx,url}_utils.py`), conservando `qtrans/utils/qutils.py` como **fachada de re-export** para no romper cuadernos y código externo. Las referencias de este documento apuntan siempre al módulo propietario de cada símbolo, porque es donde los parches de las pruebas surten efecto.

## 3. Estrategias de Comprobación de la Traducción

### 3.1 Verificación Estática por Características del Circuito

La verificación estática opera sobre el **modelo estructurado** provisto por `quirk_circuit_info` (`qtrans/utils/quirk_utils.py:1504`), antes de cualquier simulación. Consiste en asertar invariantes y contrastarlas contra el OpenQASM emitido:

- **Dimensiones**: el `n_qubits` efectivo (que incluye la altura de *custom gates* y multi-qubit) debe coincidir con el número de qubits declarados en el registro `q` del OpenQASM generado.
- **Número de columnas** (`n_cols`) y mapeo columna → instrucciones: conservador del orden temporal de la semántica columnar de Quirk.
- **Inventario de compuertas**: el conjunto `gates` reportado debe corresponderse con las instrucciones emitidas — toda compuerta presente en Quirk debe generar al menos una instrucción y no deben aparecer compuertas no declaradas.
- **Conteo por tipo de compuerta**: número de ocurrencias de cada gate en el circuito contra las apariciones en el OpenQASM, detectando duplicaciones o pérdidas en la expansión de *custom gates*.
- ***Custom gates***: todas las `custom_gate_ids`/`custom_gate_names` presentes y correctamente mapeadas, con expansión respetando controles, conectividad y el límite de profundidad (≤ 10).
- **Geometría**: correcta asignación de `offset` y alturas (`_gate_height`), garantizando índices `q[i]` dentro del rango y sin colisiones.
- **Parámetros**: ángulos y fases (incluidas fracciones de `π`) preservados sin redondeos.

Esta estrategia es **barata, determinista y totalmente automatizable**, por lo que se aplica siempre y en cada corrida.

### 3.2 Equivalencia Semántica mediante Cálculo ZX

El pipeline incorpora un **verificador semántico automático** basado en el cálculo ZX, que supera la comprobación estructural al comparar la acción unitaria de ambas representaciones:

1. `quirk_to_zx_graph(url, offset, time)` (`qtrans/utils/zx_utils.py:400`) construye el grafo ZX directamente desde la fuente Quirk.
2. `qasm_to_zx_graph(qasm_code)` (`qtrans/utils/zx_utils.py:480`) construye el grafo ZX desde el OpenQASM generado.
3. `compare_zx_graphs` (`qtrans/utils/zx_utils.py:677`) compara ambos grafos por circuito (regla única compartida por las tres formas de ejecución); `run_zx_workflow` (`qtrans/utils/zx_utils.py:817`) lo invoca:
   - **Circuitos grandes** (> 10 qubits): `zx.Circuit.verify_equality(..., up_to_global_phase=True)`.
   - **Circuitos pequeños** (≤ 10 qubits): `zx.simplify.full_reduce` + `zx.compare_tensors(..., strategy='rw-greedy-linear')`.
   - Resultado por circuito en `ZXCalculus/comparison_results.md` (`EQUIVALENTES` / `NO DEMOSTRADO` / `NO COMPARABLES` / `ERROR`), **una fila por circuito analizado** (comparables y no comparables) más una **leyenda** que explica el significado de cada estado y el recuento de cada causa de no comparabilidad.

Esta estrategia convierte la equivalencia semántica en un **artefacto reproducible del pipeline**, sin depender de herramientas externas ni de ejecución en simuladores. Estado real de qubits distintos, controles duplicados o expansiones incorrectas de *custom gates* quedan expuestos aquí.

### 3.3 Comprobación Visual Rápida para Circuitos Sencillos

Para circuitos pequeños el costo de la inspección humana es bajo y alto su valor explicativo, por lo que los **artefactos visuales** son una comprobación directa y de rápida lectura:

- **Capturas del circuito Quirk** (`capture_quirk_circuit`, `qtrans/utils/quirk_utils.py:1597`; PNG en `imgs/circuits_quirk/`): fijan la referencia oficial diseñada por el usuario.
- **Diagrama del OpenQASM generado** (`imgs/circuits_qasm/`): permite contrastar el circuito tal como lo interpretó el traductor.
- **Comparación lado a lado** (`write_comparison_docs`, `qtrans/utils/quirk_utils.py:1751` → `imgs/visual_comparisons/*.md`): una página por circuito con Quirk y OpenQASM en la misma vista, más un `README.md` índice.
- **Imágenes estilo IBM Quantum Composer** (para los scripts migrados): confirman la lectura del circuito en el ecosistema destino.

Para circuitos de pocos qubits (estados Bell, Toffoli, «la demostración por la vista») la comparación visual es la comprobación más rápida y suficiente; para circuitos grandes, en cambio, debe relegarse a un rol de *sanity check* y delegarse la garantía a 3.1 y 3.2.

## 4. Baterías de Testing Desplegadas

### 4.0 Panorama

| Batería | Ubicación | Ejecución | Garantía principal |
| --- | --- | --- | --- |
| A. Análisis estático | `tools/check_static.py` | `python tools/check_static.py qtrans test` | Integridad referencial y ausencia de imports muertos |
| B. Suite unitaria | `test/test_*.py` (131 pruebas) | `python -m unittest discover -s test -p "test_*.py"` | Contrato funcional del traductor, de la API y del pipeline |
| C. Verificación numérica de matrices | `tools/verify_matrix_gates.py` | `python tools/verify_matrix_gates.py` | Fidelidad de las *custom gates* con campo `matrix` |
| D. Equivalencia ZX | `qtrans/utils/zx_utils.py` + `input/*.json` | Etapa ZX del pipeline (`QTRANS_GENERATE_ZX=true`) | Equivalencia unitaria Quirk ↔ OpenQASM |
| E. Equivalencia cruzada entre backends | `tools/verify_backend_equivalence.py` | `python tools/verify_backend_equivalence.py` | La ruta nativa y la ruta migrada describen el mismo circuito |
| E2. Migración aislada de un circuito | `tools/migrate_circuit.py` | `python tools/migrate_circuit.py --file input/popular_algorithms.json --index 39` | El JSON de la API (OpenQASM + un script por proveedor) se materializa y se imprime en consola |
| F. Corrida end-to-end | CLI `python -m qtrans` | `python -m qtrans --input-mode batch --input-file ""` | Integración completa y artefactos de corrida |
| G. Comprobaciones manuales | `test/test_qasm.py`, `test/test_translate_lib.py`, `notebooks/` | Ejecución directa del script | Exploración y documentación de cara al usuario |
| H. Aceptación de la distribución | `qtrans_demo/` (subproyecto aislado) | `qtrans_demo/demo_venv/Scripts/python.exe qtrans_demo/main.py` | El artefacto instalado desde PyPI traduce y simula en un entorno limpio |

Las baterías A–F y H son **ejecutables y repetibles** y constituyen el criterio de aceptación del proyecto; la G es de apoyo y documentación.

### 4.1 Batería A — Análisis estático del código

**Qué detecta.** Dos clases de defecto que las pruebas unitarias no ven, porque solo se manifiestan al ejecutar una ruta no cubierta por ellas:

- **Nombres globales no definidos**: un identificador usado en una función que no existe en el ámbito local, ni en el módulo, ni entre los *builtins*. Es el síntoma típico de una reorganización del paquete (por ejemplo, al extraer `qutils.py` en módulos) que olvidó actualizar una referencia, o de una reexportación eliminada por error de la fachada.
- **Imports sin usar**: un `import` cuyo nombre no aparece en ninguna carga del módulo ni en su `__all__`. Señala dependencias colgando tras una edición. Las marcas `# noqa: F401` se respetan, porque son la convención del proyecto para las reexportaciones intencionales de `qtrans/core.py`.

**Por qué es una batería de *testing* y no una tarea de estilo.** El paquete se reorganizó en nueve módulos con una fachada de compatibilidad; la red de referencias cruzadas (`core` → `utils/*` → `facade`) es precisamente donde un error pasa inadvertido y rompe el consumo por `from qtrans.core import ...`. El analizador es puramente sintáctico (AST), sin dependencias externas, y devuelve código de salida 1 cuando encuentra problemas, de modo que puede engancharse directamente a un CI.

```bash
python tools/check_static.py qtrans test tools
# --- 0 problemas (0 nombres no definidos, 0 imports sin usar)
```

### 4.2 Batería B — Suite unitaria de integración

El repositorio incluye **131 pruebas** distribuidas en once archivos, organizados por el contrato que cada uno congela:

| Archivo | Pruebas | Contrato congelado |
| --- | --- | --- |
| `test/test_qtrans.py` | 28 | Pipeline y CLI: modos `algorithm`/`batch`, artefactos por corrida, imágenes, scripts migrados, errores por etapa y robustez de la salida por consola (`safe_print`) |
| `test/test_providers.py` | 22 | Registro y alias de proveedores, carga nativa de cada ecosistema, normalización del OpenQASM para Braket, `preserve_custom_gates` |
| `test/test_translate.py` | 14 | Contrato JSON de `translate_circuit`: claves obligatorias, tipos, rangos, `ValueError` ante payloads inválidos, modo lote |
| `test/test_translate_circuits.py` | 6 | API de objetos `translate_circuits`: forma `{proveedor: {nombre: circuito}}` y tipos nativos (`QuantumCircuit`, `Circuit`, `QNode`) |
| `test/test_endianness.py` | 14 | Convención *little-endian* de Quirk ↔ OpenQASM ↔ los tres ecosistemas destino |
| `test/test_matrix_customs.py` | 7 | Compuertas personalizadas con campo `matrix`: equivalencia numérica con la matriz de origen y con el código generado |
| `test/test_matrix_equivalence.py` | 6 | Barrida exhaustiva del corpus: la unitaria de cada declaración `gate` con `matrix` coincide con la matriz de la URL, fase global incluida |
| `test/test_xy_probes.py` | 9 | X/Y Probes (controles de eje X/Y) y post-selecciones nativas de Quirk, incluida su traza ZX |
| `test/test_qft_canonical.py` | 9 | Canonicidad de `QFT†n`, sus variantes y la regresión sobre `input/qft_algorithms.json` |
| `test/test_url_utils.py` | 9 | Normalización y canonicalización de URLs de Quirk pegadas a mano y codificación percent-encoded |
| `test/test_custom_gates.py` | 7 | Tratamiento exhaustivo de las compuertas custom: catálogo con `used_in_circuit`, traslado de las declaradas sin uso al script migrado y conservación de los parámetros de las compuertas controladas |

```bash
python -m unittest discover -s test -p "test_*.py"
# Ran 131 tests ... OK
```

**Corpora de entrada.** Las pruebas y las baterías C–F se apoyan en registros de algoritmos que actúan como *fixtures* estables: `input/popular_algorithms.json` (39 algoritmos reales: Shor, Bernstein-Vazirani, Grover, Deutsch-Jozsa, Simon, QFT, QPE, post-selecciones y compuertas personalizadas), `input/xy_probes_gates_algorithms.json` (24 sondas de X/Y Probes y post-selecciones, todas deterministas), `input/qft_algorithms.json` (12 casos de QFT), `input/main_algorithms.json` (15 algoritmos), `input/natives_post_select_algorithms.json` (16 casos) e `input/scalar_gates_algorithms.json` (28 casos).

**Disciplina de los parches.** `qtrans/core.py` invoca a los módulos con **nombre qualificado** (`quirk_utils.quirk_to_qasm`, `provider_utils.generate_provider_files`, `qiskit_utils.generate_composer_images`, `zx_utils.run_zx_workflow`…) para que los parches de las pruebas apunten al módulo real y no a una copia reexportada.

### 4.3 Batería C — Verificación numérica de las compuertas con campo `matrix`

**Por qué existe.** Las *custom gates* declaradas en Quirk con el campo `matrix` son el punto del flujo donde la traducción puede perder información: el traductor no copia la matriz, emite una **descomposición equivalente** (`p` + ZYZ para unitarias 2×2, KAK con `U` + `cx` para 4×4). Una equivalencia «de texto» no basta: hay que comparar matrices.

**Qué compara.** Para cada compuerta con matriz, la batería contrasta cuatro representaciones:

1. la **matriz de origen** extraída de la URL de Quirk (fuente de verdad);
2. la **unitaria reconstruida** desde el cuerpo OpenQASM emitido (`gate ... { ... }`), es decir, lo que realmente ejecutará el backend;
3. la **unitaria de un camino independiente**: la descomposición ZYZ del verificador ZX para 2×2 y la descomposición KAK de Qiskit para 4×4;
4. el **residuo de la proyección a unitaria** (SVD) que el pipeline aplica cuando la matriz publicada no es exactamente unitaria.

**Resultado actual sobre el corpus:** 52 compuertas con `matrix` verificadas, con un residuo máximo `|OpenQASM − URL| = 4.927e-08`, que es exactamente el redondeo a siete decimales con el que Quirk serializa las matrices. La tolerancia por defecto de la batería es `1e-6`, dos órdenes de magnitud por encima de ese redondeo.

```bash
python tools/verify_matrix_gates.py
# compuertas con "matrix" verificadas: 52   residuo máximo |OpenQASM-URL| = 4.927e-08   (tolerancia 1e-06)
```

### 4.4 Batería D — Equivalencia semántica mediante cálculo ZX

Además de ejecutarse como etapa del pipeline (y dejar el reporte auditable `ZXCalculus/comparison_results.md`), la equivalencia ZX está congelada en la suite unitaria: `test/test_xy_probes.py` verifica la traza ZX de las sondas de X/Y Probes y post-selecciones, y `test/test_matrix_customs.py` contrasta la descomposición ZX con la matriz de origen. La ventaja de esta batería es que opera sobre el **IR**, no sobre el código: valida el modelo matemático de la traducción con independencia del dialecto de OpenQASM emitido.

**Cobertura medida.** Sobre el corpus de sondas (`input/xy_probes_gates_algorithms.json`, 24 circuitos) la etapa ZX construye y compara los 12 circuitos de X/Y Probes con veredicto `EQUIVALENTES` en los tres tamaños (2, 4 y 6 qubits). Los 12 circuitos restantes son **post-selecciones**, que no son unitarias: la equivalencia unitaria no está definida para ellas y las dos rutas de ejecución lo reflejan de forma explícita, aunque con expresiones distintas.

- **API de biblioteca** (`translate_circuit` con `zx.enabled=true`): el veredicto es `'no-comprobado'`, congelado por `test/test_xy_probes.py` (`test_postselect_probes_are_not_zx_checkable`), porque la validación ZX nunca debe tumbar la traducción.
- **Pipeline (CLI)**: la construcción del grafo ZX desde la fuente Quirk aborta con «Compuerta Quirk no soportada: |+⟩⟨+|» y el pipeline registra el incidente como error de esa etapa. El circuito **sí aparece en el informe** `comparison_results.md`, con estado `NO COMPARABLES` y el motivo en la columna «Motivo».

Es un comportamiento **esperado y conocido**, no una regresión. Por eso el informe distingue `EQUIVALENTES`, `NO EQUIVALENTES`, `NO DEMOSTRADO` (timeout o coste intratable), `NO COMPARABLES` y `ERROR`, y por eso el criterio de aceptación de una corrida con post-selecciones es «cero errores *salvo* los de las post-selecciones», no «cero errores».

**El informe lista todos los circuitos, no solo los comparables.** `run_zx_workflow` (`qtrans/utils/zx_utils.py:817`) mantiene una entrada por circuito analizado: los que se compararon (con método, veredicto y número de cúbits) y los que no se pudieron comparar (con el motivo: compuerta no soportada, matriz no representable, timeout o excepción). El `comparison_results.md` resultante lleva, además de la tabla, una **leyenda** con el significado y el recuento de cada estado y una tabla de **motivos de no comparabilidad** con el número de circuitos afectado por cada uno. De este modo, la ausencia de un veredicto de equivalencia es siempre visible y explicada, en lugar de desaparecer del informe. Regresión: `test/test_xy_probes.py::ProbeComparisonTableTests` (sobre el corpus de sondas: 24 filas = 12 `EQUIVALENTES` + 12 `NO COMPARABLES` con motivo, leyenda y tabla de motivos).

**Cobertura sobre el corpus completo.** En la corrida E2E de los 134 algoritmos de `input/` la etapa ZX comparó **77 circuitos y los 77 resultaron `EQUIVALENTES`** (`compare_tensors (rw-greedy-linear)`), generando además los 77 diagramas SVG de los grafos. Los 57 restantes no son comparables y el pipeline los registra como error de esa etapa, todos por el mismo motivo (compuerta no representable en el grafo ZX, no fallo de traducción); en el informe figuran como `NO COMPARABLES` con su motivo:

| Causa | Circuitos | Detalle |
| --- | :-: | --- |
| Post-selección nativa | 28 | 16 de `natives_post_select_algorithms.json` + 12 de `xy_probes_gates_algorithms.json`; no son unitarias |
| Compuerta escalar de Quirk | 28 | `0`, `i`, `√i`, `√-i`, `-i`, `NeGate`, `…` (7）× 4 tamaños: multiplican la amplitud global |
| Matriz 4×4 personalizada | 1 | `mia` en `popular_algorithms.json`: el constructor ZX solo admite matrices 2×2 |

Ninguna de las 57 incidencias afecta a la traducción: los 134 OpenQASM, las 134 capturas, los 134 diagramas y los 402 scripts migrados se generaron sin errores.

Para habilitar esta etapa desde la línea de órdenes hay que activar la variable de entorno `QTRANS_GENERATE_ZX=true` (el `.env` local del proyecto la deja desactivada y la CLI solo ofrece el flag `--no-zx` para omitirla):

```bash
QTRANS_GENERATE_ZX=true python -m qtrans --input-mode batch --input-file "" \
    --input-files xy_probes_gates_algorithms.json --zx-timeout 60
# ZXCalculus/comparison_results.md -> 12/12 EQUIVALENTES
```

### 4.5 Batería E — Equivalencia cruzada entre backends

**Qué problema resuelve.** QTransLIFIA materializa cada circuito de dos formas complementarias:

- **ruta nativa**: el parser del propio ecosistema (`qasm2/qasm3.loads` en Qiskit, `Circuit.from_ir` en Braket; PennyLane no tiene parser viable y usa el script);
- **ruta migrada**: la ejecución del script Python que la librería genera (`migrated_circuits/<proveedor>/<nombre>.py`).

Ambas deben describir el mismo circuito, porque el usuario puede consumir cualquiera de las dos. La batería compara, sobre los 39 algoritmos del corpus:

- **Qiskit**: los vectores de estado finales de ambos circuitos (salvo fase global), después de retirar mediciones y barreras. Se comparan vectores y no matrices unitarias porque el corpus incluye circuitos de hasta 16 qubits, donde la matriz unitaria (65536×65536) no es materializable.
- **AWS Braket**: una **firma semántica** de las instrucciones, tras canonicalizar las representaciones equivalentes que Braket ofrece (`PhaseShift` con control ≡ `CPhaseShift` ≡ `U(0,φ,0)`; `CNot` ≡ `X` con control) e ignorar la posición de las mediciones —el generador las difiere al final, lo que no altera el resultado porque ningún qubit medido se vuelve a tocar después.
- **Xanadu PennyLane**: la materialización por script (el `QNode` que produce el script migrado), al no existir parser nativo.

Con `--simulate` se añade una comprobación estadística con el simulador local de Braket: la distribución de conteos de la ruta nativa frente a la migrada.

```bash
python tools/verify_backend_equivalence.py
# qiskit: rutas equivalentes 39/39
# braket: rutas equivalentes 39/39

python tools/verify_backend_equivalence.py --providers braket --only "39. complex_customs" --simulate
#   [simulación] 39. complex_customs: max|Δconteos| = 16/2000 -> EQUIVALENTE
```

Esta batería es la que sostiene la frontera de responsabilidades descrita en `doc/QTransLIFIA_Verificabilidad.md`: la equivalencia Quirk ↔ OpenQASM es garantía de la librería; la equivalencia OpenQASM ↔ *backend* se verifica dentro del entorno del proveedor.

### 4.6 Batería F — Corrida end-to-end del pipeline

Comprobación de integración: se ejecuta el pipeline completo sobre el corpus y se verifican los artefactos que produce.

```bash
python -m qtrans --input-mode batch --input-file "" --input-dir input
```

Resultado de referencia sobre `input/popular_algorithms.json`: **39 archivos OpenQASM** (2.0 y 3.0), 39 capturas de Quirk, 39 diagramas del circuito, 39 comparaciones lado a lado (más el `README.md` índice), 39 scripts migrados por proveedor y **0 errores por etapa**. La corrida sobre el directorio `input/` completo (6 registros JSON, 134 algoritmos) arroja el mismo resultado: 134 OpenQASM, 134 capturas, 134 diagramas, 134 scripts y 0 errores. Las únicas celdas en cero son las imágenes de IBM Quantum Composer, que requieren credenciales de IBM Quantum y por tanto no se generan en un entorno desatendido.

El resumen de la corrida (`Resumen: N JSON, N algoritmos, N QASM, N capturas Quirk, N diagramas QASM, N imágenes Composer, N scripts provider y N errores`) es el indicador de aceptación: un error en una etapa opcional no cancela las demás, pero queda registrado y es visible.

El modo `algorithm` (`--input-mode algorithm --input-file <json>`) aísla un único circuito y es el que se usa para depurar una traducción concreta; el modo `batch` (con `--input-file ""` explícito, porque `.env` puede fijar el modo `algorithm`) es el que valida el flujo completo.

**Carpeta de corrida: resolución por hora.** Todas las salidas de una corrida viven en `output/run_DD_MM_YYYY__HH/` (`QTRANS_OUTPUT_DIR` + etiqueta `QTRANS_RUN_LABEL`, por defecto `DD_MM_YYYY__HH`). Como la estampa se resuelve a nivel de **hora**, dos ejecuciones dentro de la misma hora **comparten carpeta y sobrescriben sus archivos**: la herramienta borra los artefactos de la corrida previa (marcada con el fichero `.qtrans_run`) y regenera los suyos, de modo que `output/` no acumula una carpeta por ejecución. Una carpeta ajena, sin ese marcador, no se toca. Regresión: `test/test_qtrans.py::RunDirectoryTests`.

### 4.7 Batería G — Comprobaciones manuales y de documentación

Comprobaciones que no encajan en una aserción automática pero que son parte del flujo de trabajo:

- `test/test_qasm.py`: imprime el OpenQASM de circuitos canónicos (Bell, Toffoli, *offset*, *placeholders*) para inspección directa.
- `test/test_translate_lib.py`: imprime el JSON completo que devuelve `translate_circuit` sobre el primer registro de `input/main_algorithms.json`; documenta el contrato de cara al usuario.
- `notebooks/QTrans.ipynb` y `notebooks/QTrans_utils.ipynb`: pipeline principal y utilidades auxiliares (URLs de Quirk, generación de enlaces clicables, validación *round-trip*).
- `test/test_curl.sh`, `test/test_curl.bat`, `test/test_endpoints.ps1`, `test/test_qasm_endpoints.ps1`: sondeos de los puntos de acceso de los proveedores (disponibilidad de SDK y conectividad).

### 4.8 Batería H — Aceptación de la distribución publicada (módulo aislado)

**Qué problema resuelve.** Las baterías A–G se ejecutan contra el árbol de fuentes. Un paquete puede pasar todas ellas y, sin embargo, fallar al instalarse desde el wheel publicado: un módulo fuera de `packages.find`, una dependencia no declarada, una versión mal estampada o un import que solo resuelve por el `cwd` del repositorio. `qtrans_demo/` cierra ese hueco: es un **consumidor externo de caja negra** que instala `qtranslifia` desde PyPI en su propio entorno y ejercita el contrato público sin acceso al código fuente.

**Aislamiento.** El subproyecto tiene su propio `qtrans_demo/demo_venv` y fija la versión en `qtrans_demo/requirements.txt` (`qtranslifia==0.2.0`). `main.py` impone dos guardas antes de traducir: `sys.prefix` debe ser exactamente `qtrans_demo/demo_venv` (`qtrans_demo/main.py:26`) y `qtrans.__file__` debe estar dentro de ese entorno (`qtrans_demo/main.py:37`). Si se ejecuta con el `.venv` del repositorio o si el paquete se importa desde las fuentes locales, el script aborta con un mensaje accionable. `demo_venv/` y `output/` están ignorados por Git.

**Flujo.** Lee `qtrans_demo/input/custom_gates_algorithms.json` (2 circuitos con compuertas definidas por matriz), llama a `translate_circuit` en modo lote con `return_circuit=True`, QASM 3.0, proveedor Qiskit, 1024 shots, `preserve_custom_gates=true` y sin ZX ni imágenes. Después simula el `QuantumCircuit` devuelto con Qiskit Aer (con respaldo a `StatevectorSampler`) y guarda el OpenQASM, el script migrado de Qiskit y los conteos en `qtrans_demo/output/<nombre>/`.

```bash
# Desde la raíz del repositorio; el entorno del demo ya debe existir.
qtrans_demo/demo_venv/Scripts/python.exe qtrans_demo/main.py
# qtrans: ...\qtrans_demo\demo_venv\Lib\site-packages\qtrans\__init__.py (0.2.0)
# Circuitos: 2
# total: 1024 shots   (por cada circuito)
```

Para recrear el entorno: `cd qtrans_demo && python -m venv demo_venv && source demo_venv/Scripts/activate && python -m pip install -r requirements.txt && python main.py` (en Linux/macOS, `source demo_venv/bin/activate`).

**Resultado de referencia.** 2/2 circuitos traducidos y simulados, sin errores de etapa; las salidas quedan en `qtrans_demo/output/1._complex_customs/` y `qtrans_demo/output/2._rotational_customs/`, cada una con su `_v3.0.txt`, su `_ibm_qiskit_code.py` y su `_counts.json` de 1024 shots.

**Qué garantiza y qué no.** Garantiza que el artefacto **instalado desde PyPI** se importa en un entorno limpio, resuelve sus dependencias, traduce compuertas personalizadas con matriz a OpenQASM 3.0, las carga con el parser nativo de Qiskit y las ejecuta en un simulador local. No sustituye a las baterías A–G: cubre un solo proveedor, un corpus de dos circuitos y un simulador, no un QPU, y no ejerce la CLI ni la generación de imágenes. Al publicar una versión nueva hay que actualizar el pin de `requirements.txt` y repetir la corrida.

## 5. Qué Garantiza Cada Batería (y Qué No)

| Propiedad verificable | A (estático) | B (unitaria) | C (matrices) | D (ZX) | E (backends) | F (E2E) | H (distribución) |
| --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| Integridad referencial del paquete | ✔ | parcial | | | | | parcial |
| Contrato de la API y del CLI | | ✔ | | | | parcial | parcial |
| Fidelidad numérica de `matrix` | | parcial | ✔ | ✔ | | | parcial |
| Equivalencia unitaria Quirk ↔ OpenQASM | | | parcial | ✔ | | | |
| Consistencia parser nativo ↔ script migrado | | parcial | | | ✔ | | |
| Generación completa de artefactos | | | | | | ✔ | parcial |
| Equivalencia frente al *backend* real (QPU/simulador) | | | | | parcial | | parcial |
| Distribución instalable e importable desde PyPI | | | | | | | ✔ |

**Límites declarados.** Ninguna batería cubre el comportamiento de un *hardware* real (el simulador local de Braket es un simulador, no un dispositivo), ni la corrección del modelo de Quirk como interfaz de usuario, ni la equivalencia de las post-selecciones (no son unitarias y quedan fuera de la comparación ZX por construcción). La batería H verifica la distribución instalada, pero solo con Qiskit y sobre dos circuitos. La ausencia de hallazgos en las baterías A–H significa que **el contrato congelado se respeta**, no que el circuito sea útil para un algoritmo concreto: esa valoración es del usuario.

## 6. Procedimiento de Mantenimiento

Orden recomendado antes de dar por cerrada una modificación (cualquiera que toque `qtrans/`, el contrato de la API o el flujo de traducción):

1. **Análisis estático**: `python tools/check_static.py qtrans test tools` (sin referencias rotas ni imports muertos).
2. **Suite unitaria**: `python -m unittest discover -s test -p "test_*.py"` (131 pruebas; sin fallos).
3. **Fidelidad numérica**: `python tools/verify_matrix_gates.py` (residuo ≤ `1e-6`; se espera `≈5e-8`).
4. **Equivalencia entre backends**: `python tools/verify_backend_equivalence.py` (39/39 en Qiskit y Braket).
5. **Corrida end-to-end**: `python -m qtrans --input-mode batch --input-file ""` y revisión del resumen (0 errores de traducción; los errores de la etapa ZX son los de compuertas no comparables descritos en §4.4).
6. **ZX** (cuando la modificación afecta a la semántica): activar `QTRANS_GENERATE_ZX=true` y revisar `ZXCalculus/comparison_results.md`.

Al añadir una functionality nueva se mantiene la disciplina de **congelar el contrato**: cada batería nueva debe poder fallar —es decir, debe ser capaz de detectar un defecto real— y su documentación (este archivo) debe actualizarse en la misma entrega.

## 7. Regresiones Corregidas

La suite se ejecuta completa sin fallos. Quedan documentados aquí los dos defectos que estuvieron abiertos, porque ambos explican decisiones actuales de las pruebas:

- **Canonicidad de `QFT†n`.** `test.test_qft_canonical.CanonicalQuirkUrlTests.test_canonicalization_is_idempotent` comparaba el texto crudo de la URL con el literal `QFT†3`, pero `canonicalize_quirk_url` serializa con `ensure_ascii=True` y el dagger aparece como `\u2020`. El test ahora valida el **circuito parseado** (`parse_quirk_url(once)["cols"][0]`), que es la representación que importa, en lugar de un detalle de escapado. Las otras ocho pruebas de canonicidad y la regresión sobre `input/qft_algorithms.json` ya pasaban; el flujo de traducción nunca estuvo afectado.

**Defecto corregido por la batería F.** La primera corrida E2E con la etapa ZX activa abortó tras el algoritmo 15: el mensaje de error «Compuerta Quirk no soportada: |+⟩⟨+|» contiene caracteres (`⟨`, `⟩`) que la consola de Windows (`cp1252`) no puede codificar, y el `UnicodeEncodeError` resultante cancelaba la etapa ZX **y con ella el informe de equivalencia completo**. La corrección consiste en imprimir siempre con `pipeline_utils.safe_print` (sustituye lo no codificable en lugar de propagar el error) y en forzar UTF-8 con `errors="replace"` en la salida de la CLI (`core._configure_console_encoding`); la batería B congela el comportamiento con tres pruebas de regresión en `test/test_qtrans.py`. Es el ejemplo canónico de por qué la corrida E2E es una batería y no un trámite: el defecto era invisible en la suite unitaria porque solo se manifiesta en la consola real de Windows y solo con circuitos que contienen post-selecciones.

## 8. Conclusión

La comprobación del flujo de QTransLIFIA se apoya en la **complementariedad** de tres familias de estrategias —verificación **estática** por características del circuito, equivalencia **semántica** mediante cálculo ZX y comprobación **visual** rápida para circuitos sencillos— y sobre ellas en un arsenal de **ocho baterías** que cubren desde la integridad sintáctica del código (A) hasta la integración completa (F) y la aceptación del artefacto publicado (H). La complementariedad es el punto: la estática garantiza que «no se pierden piezas», la numérica (C) que las piezas conservadas son la misma matriz, la ZX (D) que la acción unitaria es la misma, la cruzada (E) que cualquier forma de materializar el circuito coincide, y la visual (3.3) ofrece la lectura inmediata que acelera la detección de defectos en las etapas iniciales. Documentar y mantener estas baterías es, en la práctica, lo que permite detectar los errores en el punto más temprano y económico del flujo: garantizar que el circuito efectivamente ejecutado sea el que el usuario diseñó.

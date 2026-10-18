# QTransLIFIA - Testing y Estrategias de Comprobación del Flujo

## 1. Introducción

El flujo de QTransLIFIA no es una transformación monolítica: es una **tubería de etapas** (parsing de la URL/JSON de Quirk, análisis estructurado, traducción a OpenQASM, generación de imágenes, comparación visual, grafos ZX y migración a ecosistemas) donde cada paso transforma la representación del circuito. Cada transformación es una oportunidad de introducir un defecto y, por lo tanto, un punto donde la comprobación es necesaria.

El paso más crítico de todo el flujo es la **traducción Quirk → OpenQASM**: los errores introducidos allí se propagan a todos los artefactos posteriores. Por ello, QTransLIFIA propone comprobar la traducción mediante **tres familias de estrategias complementarias**:

1. **Verificación estática**: comprobación de características del circuito (cantidad de compuertas, qubits, dimensiones, controles, *custom gates*) sobre la representación analizada, sin ejecutar el circuito.
2. **Equivalencia semántica mediante cálculo ZX**: comparación automática entre el grafo ZX derivado de la fuente Quirk y el derivado del OpenQASM generado, para establecer equivalencia de la transformación unitaria.
3. **Comprobación visual rápida**: herramientas gráficas (capturas, diagramas, comparaciones lado a lado) aptas para inspección humana inmediata, especialmente en circuitos sencillos.

## 2. El Flujo como Objeto de Prueba

`run_pipeline` (`qtrans/core.py:637`) orquesta el flujo completo. Cada etapa puede activarse/desactivarse de forma independiente mediante flags (CLI) o variables de entorno (`QTRANS_*`), lo que permite **probar cada paso aislado**:

| Etapa | Artefacto principal | Flag / `QTRANS_*` | Riesgo si falla |
| --- | --- | --- | --- |
| Lectura de entradas | JSON del directorio `input/` | `input_mode` / `input_file` | Algoritmos ausentes o mal parseados |
| Traducción | OpenQASM en `algorithms_qasm/*.txt` | (siempre activa) | Semántica del circuito alterada |
| Captura Quirk | PNG en `imgs/circuits_quirk/` | `capture_images` / `QTRANS_CAPTURE_IMAGES` | Referencia visual indisponible |
| Diagrama OpenQASM | PNG en `imgs/circuits_qasm/` | `generate_qasm_images` / `QTRANS_GENERATE_QASM_IMAGES` | Sin inspección visual del QASM |
| Comparación visual | Markdown en `imgs/visual_comparations/` | `generate_comparison` / `QTRANS_GENERATE_COMPARISON` | Sin contraste lado a lado |
| Grafos ZX | JSON + `comparison_results.md` en `ZXCalculus/` | `generate_zx` / `QTRANS_GENERATE_ZX` | Sin equivalencia semántica automática |
| Migración | Scripts en `migrated_circuits/` | `(etapas de migración)` | Backend recibe un circuito incorrecto |

El determinismo de `quirk_to_qasm` (misma URL → mismo OpenQASM) es el prerequisito que convierte a cada una de estas etapas en **comprobable automáticamente** (*golden tests*, *regression tests*, *differential testing*).

## 3. Estrategias de Comprobación de la Traducción

### 3.1 Verificación Estática por Características del Circuito

La verificación estática opera sobre el **modelo estructurado** provisto por `quirk_circuit_info` (`qtrans/utils/qutils.py:1255`), antes de cualquier simulación. Consiste en asertar invariantes y contrastarlas contra el OpenQASM emitido:

- **Dimensiones**: el `n_qubits` efectivo (que incluye la altura de *custom gates* y multi-qubit) debe coincidir con el número de qubits declarados en el registro `q` del OpenQASM generado.
- **Número de columnas** (`n_cols`) y mapeo columna → instrucciones: conservador del orden temporal de la semántica columnar de Quirk.
- **Inventario de compuertas**: el conjunto `gates` reportado debe corresponderse con las instrucciones emitidas — toda compuerta presente en Quirk debe generar al menos una instrucción y no deben aparecer compuertas no declaradas.
- **Conteo por tipo de compuerta**: número de ocurrencias de cada gate en el circuito contra las apariciones en el OpenQASM, detectando duplicaciones o pérdidas en la expansión de *custom gates*.
- ***Custom gates***: todas las `custom_gate_ids`/`custom_gate_names` presentes y correctamente mapeadas, con expansión respetando controles, conectividad y el límite de profundidad (≤ 10).
- **Geometría**: correcta asignación de `offset` y alturas (`_gate_height`), garantizando índices `q[i]` dentro del rango y sin colisiones.
- **Parámetros**: ángulos y fases (incluidas fracciones de `π`) preservados sin redondeos.

Esta estrategia es **barata, determinista y totalmente automatizable**, por lo que debería aplicarse siempre y en cada corrida.

### 3.2 Equivalencia Semántica mediante Cálculo ZX

El pipeline incorpora un **verificador semántico automático** basado en el cálculo ZX, que supera la comprobación estructural al comparar la acción unitaria de ambas representaciones:

1. `quirk_to_zx_graph(url, offset, time)` (`qtrans/utils/zx_utils.py:374`) construye el grafo ZX directamente desde la fuente Quirk.
2. `qasm_to_zx_graph(qasm_code)` (`qtrans/utils/zx_utils.py:431`) construye el grafo ZX desde el OpenQASM generado.
3. `compare_zx_graphs` (`qtrans/utils/zx_utils.py`) compara ambos grafos por circuito (regla única compartida por las tres formas de ejecución); `_run_zx_workflow` (`qtrans/core.py`) lo invoca:
   - **Circuitos grandes** (> 10 qubits): `zx.Circuit.verify_equality(..., up_to_global_phase=True)`.
   - **Circuitos pequeños** (≤ 10 qubits): `zx.simplify.full_reduce` + `zx.compare_tensors(..., strategy='rw-greedy-linear')`.
   - Resultado por circuito en `ZXCalculus/comparison_results.md` (`EQUIVALENTES` / `NO DEMOSTRADO` / `NO COMPARABLES` / `ERROR`).

Esta estrategia convierte la equivalencia semántica en un **artefacto reproducible del pipeline**, sin depender de herramientas externas ni de ejecución en simuladores. Estado real de qubits distintos, controles duplicados o expansiones incorrectas de *custom gates* quedan expuestos aquí.

### 3.3 Comprobación Visual Rápida para Circuitos Sencillos

Para circuitos pequeños el costo de la inspección humana es bajo y alto su valor explicativo, por lo que los **artefactos visuales** son una comprobación directa y de rápida lectura:

- **Capturas del circuito Quirk** (`capture_quirk_circuit`, PNG en `imgs/circuits_quirk/`): fijan la referencia oficial diseñada por el usuario.
- **Diagrama del OpenQASM generado** (`imgs/circuits_qasm/`): permite contrastar el circuito tal como lo interpretó el traductor.
- **Comparación lado a lado** (`_write_comparison_docs`, `qtrans/core.py:385` → `imgs/visual_comparations/*.md`): una página por circuito con Quirk y OpenQASM en la misma vista, más un `README.md` índice.
- **Imágenes estilo IBM Quantum Composer** (para los scripts migrados): confirman la lectura del circuito en el ecosistema destino.

Para circuitos de pocos qubits (estados Bell, Toffoli, «la demostración por la vista») la comparación visual es la comprobación más rápida y suficiente; para circuitos grandes, en cambio, debe relegarse a un rol de *sanity check* y delegarse la garantía a 3.1 y 3.2.

## 4. Estrategias por Etapa del Flujo

| Etapa | Estrategia principal | Comprobación complementaria |
| --- | --- | --- |
| Parsing (URL/JSON) | `quirk_circuit_info` como *round-trip* de `parse_quirk_url` | Re-encodeo con `encode_quirk_url` y re-apertura en Quirk |
| Traducción Quirk → OpenQASM | Verificación estática (3.1) | Equivalencia ZX (3.2) + validación sintáctica con parsers externos |
| Diagramas OpenQASM | Comprobación visual (3.3) | Contraste de dimensiones vs. circuito Quirk |
| Grafos ZX | Equivalencia semántica (3.2) | `comparison_results.md` como reporte auditable |
| Migración a ecosistemas | Simulación cruzada entre backends | Comparación de resultados (estados, distribuciones) |
| Pipeline completo | Tests automatizados (sección 5) | *Golden tests* sobre artefactos de corrida |

## 5. Pruebas Automatizadas del Repositorio

El repositorio incluye suites de pruebas que automatizan la comprobación del flujo:

- `test/test_qtrans.py`: pruebas del pipeline/CLI (`run_pipeline`) — modos `algorithm`/`batch`, artefactos por corrida, apertura de imágenes y generación de scripts migrados.
- `test/test_translate.py`: pruebas del contrato de la API de librería `translate_circuit`.
- `test/test_qasm.py`: pruebas de traducción sobre circuitos canónicos (Bell, Toffoli, *offset*, *placeholders*) invocando `quirk_to_qasm`.
- Ejecución:
  ```text
  python -m unittest discover -s test -p "test_*.py" -v
  ```

Además, el determinismo del traductor habilita en el repositorio (o en CI/CD) estrategias adicionales:

- **Golden / snapshot tests**: OpenQASM esperado fijo por circuito canónico, comparación bit-a-bit.
- **Regression tests**: detección automática de cambios no intencionales entre versiones del traductor.
- **Differential testing**: contraste entre `QASM_VERSION='2.0'` y `'3.0'`, o entre instancias del pipeline (librería vs. cuaderno).

## 6. Recomendaciones Prácticas

- **Aplicar siempre la verificación estática (3.1)** en cada corrida: es la de menor costo y cubre las características esenciales.
- **Habilitar los grafos ZX (3.2)** en las corridas de validación formal; el reporte `ZXCalculus/comparison_results.md` es evidencia auditable de equivalencia.
- **Usar la comprobación visual (3.3)** como inspección rápida en circuitos sencillos y como *sanity check* previa al análisis profundo en circuitos grandes.
- **Complementar con validación externa**: parser OpenQASM y simulación cruzada en al menos dos ecosistemas destino para confirmar que el IR es consumible y las discrepancias provienen del backend, no de la traducción.
- **Registrar los errores por etapa**: `run_pipeline` contabiliza errores por etapa sin cancelar las demás, permitiendo detectar *dónde* falla el flujo y aislar la falla.

## 7. Conclusión

La comprobación del flujo de QTransLIFIA se apoya en la **complementariedad** de tres familias de estrategias: verificación **estática** por características del circuito, equivalencia **semántica** mediante cálculo ZX y comprobación **visual** rápida para circuitos sencillos, sostenidas por pruebas automatizadas y por el **determinismo** del traductor. Ninguna estrategia es suficiente por sí sola: la estática garantiza que "no se pierden piezas", la semántica aporta la garantía formal de equivalencia y la visual ofrece la lectura inmediata que acelera la detección de defectos en las etapas iniciales. En conjunto, permiten detectar los errores en el punto más temprano y económico del flujo, garantizando que el circuito efectivamente ejecutado sea el que el usuario diseñó.
# QTransLIFIA - Verificabilidad y Equivalencia entre Circuitos

## 1. Introducción

La verificabilidad en QTransLIFIA se refiere a la capacidad de comprobar que el circuito traducido desde Quirk a OpenQASM es **equivalente** al circuito original, tanto desde el punto de vista estructural como, potencialmente, funcional. Esto resulta fundamental para garantizar una migración fiable entre lenguajes y ecosistemas distintos.

## 2. Fundamentos para la Verificabilidad

El diseño del traductor incorpora elementos explícitos que facilitan la inspección, trazabilidad y comparación entre representaciones:

- **Separación entre análisis y generación**: La existencia de `quirk_circuit_info` permite auditar el circuito antes de emitir OpenQASM, independizando la verificación estructural de la sintaxis generada.
- **Modelo estructurado completo**: Se expone un inventario detallado del circuito original, lo que habilita contrastes sistemáticos entre origen (Quirk) y destino (OpenQASM).
- **Determinismo**: Dada una misma URL Quirk, `quirk_to_qasm` produce un resultado determinista. Esto permite *regression testing* robusto y comparación bit-a-bit entre versiones.

## 3. Aspectos Fundamentales desde la Perspectiva de la Ingeniería de Software Cuántica (QSE)

Desde la disciplina de la **Ingeniería de Software Cuántica** (*Quantum Software Engineering*, QSE), la verificación temprana es la piedra angular de la confiabilidad de un traductor de circuitos. En QTransLIFIA, el punto de comprobación más sensible se ubica en las **etapas iniciales de la tubería**: cuando el circuito todavía existe en su forma de origen, es decir, como URL de Quirk o como el JSON embebido en ella (`circuit=...`). Detectar aquí un defecto de traducción es la barrera de control de calidad más temprana y económica del flujo completo: cualquier error introducido en esta fase se propaga a todos los artefactos posteriores (OpenQASM, diagramas, grafos ZX, scripts migrados). Verificar en origen garantiza dos atributos fundamentales:

1. **Equivalencia del circuito ejecutado vs. el diseñado**: el circuito que efectivamente se va a simular o ejecutar representa la misma transformación cuántica que el usuario diseñó en Quirk.
2. **Uso fiel de las compuertas provistas por Quirk**: toda compuerta disponible en Quirk (nativas, parametrizadas, *custom gates* definidas por el usuario) se traduce con la semántica correcta, sin mapeos impropios ni pérdida de parámetros.

### 3.1 Niveles de Verificación en Etapas Iniciales

La QSE estructura la verificación en niveles complementarios, cada uno con sus propios criterios y herramientas:

- ***Nivel sintáctico***: comprobar que el OpenQASM emitido es conforme al estándar — encabezado `OPENQASM`, declaraciones de registros válidas, instrucciones con aridad correcta, identificadores válidos. Es la primera compuerta del pipeline y se resuelve con parsers OpenQASM existentes.
- ***Nivel estructural***: comprobar que dimensiones, inventario de puertas, controles, *targets*, conectividad y jerarquía de *custom gates* coinciden entre el circuito Quirk analizado (`quirk_circuit_info`) y el OpenQASM emitido. Es 100% automatizable sin simulación.
- ***Nivel semántico (funcional)***: comprobar que ambas representaciones producen la misma acción unitaria sobre el espacio de estados (salvo fase global). Requiere herramientas de equivalencia de circuitos; en QTransLIFIA está soportado de forma nativa mediante el cálculo ZX (sección 3.7).

En etapas iniciales, los niveles sintáctico y estructural deben ser estrictamente obligatorios y totalmente automáticos; el semántico aporta la garantía formal de equivalencia.

### 3.2 Preservación Semántica como Criterio Central de Corrección

El criterio de oro en QSE para comprobar una traducción es que **el circuito diseñado y el traducido representen la misma transformación unitaria**, salvo fases globales irrelevantes. Para eso, en las etapas iniciales el traductor debe preservar:

- La **semántica columnar** de Quirk: cada columna representa una "tajada" temporal de operaciones; la traducción debe preservar el orden y la composición de esas tajadas.
- La **relación control-target** de cada compuerta: un control desplazado o un *target* intercambiado altera la unitaria del circuito.
- El **orden de qubits**: el mapeo columna → registros `q[i]` debe respetar la disposición visual original (verificación del `n_qubits` efectivo y del `offset`).
- La **jerarquía de abstracciones**: la expansión de *custom gates* debe ser semánticamente equivalente a la definición original, no una aproximación aplanada.

La preservación estructural es una condición **necesaria pero no suficiente** de la equivalencia funcional: garantiza que "no se perdieron piezas", pero la comprobación definitiva de igualdad de la unitaria la aporta el nivel semántico.

### 3.3 Comprobación del Uso Correcto de las Compuertas de Quirk

Uno de los objetivos específicos de la verificación temprana es auditar que cada compuerta provista por Quirk se traduzca exactamente a la operación OpenQASM equivalente:

- **Mapeo biyectivo de compuertas**: cada símbolo Quirk tiene una correspondencia definida y correcta (p. ej. `X^½` → `s`/`t`/`rx(...)` según exponente, `•`+`Swap` → `swap`, controles múltiples → expansión `ccx`/multi-controlada).
- **Parámetros y ángulos íntegros**: las fases y ángulos (incluidas fracciones de `π`) se conservan sin redondeos ni pérdida de precisión en el OpenQASM emitido.
- ***Custom gates* definidas por el usuario**: se resuelven por `id`/`name`; sus instancias multi-columna se desambiguan con el sufijo `:k`; el anidamiento (profundidad ≤ 10) se expande respetando controles y conectividad.
- **Compuertas por matriz**: las definiciones `matrix` se traducen a su operación equivalente en OpenQASM (p. ej. `U(-pi/2)` → `p(-pi/2)`), garantizando que una compuerta ingresada por la vía matricial sigue manteniendo equivalencia.
- **Geometría *height-aware***: `_gate_height`, `offset` y `n_qubits` efectivo aseguran que una compuerta multi-qubit o una *custom gate* de altura `h` no desplace incorrectamente los qubits adyacentes.

### 3.4 Trazabilidad de Extremo a Extremo

La trazabilidad es el habilitador de toda verificación: permite responder "¿de dónde provino esta instrucción?" para cada línea del OpenQASM generado. El flujo es:

```text
URL / JSON de Quirk
   → parse_quirk_url
   → quirk_circuit_info      (modelo estructurado: inspección pre-traducción)
   → _resolve_gate_names     (id/name → identificador QASM único)
   → _col_to_qasm_with_gates (expansión por columna con contexto :k)
   → quirk_to_qasm           (OpenQASM emitido)
```

La correspondencia columna ↔ instrucciones, el identificador único por instancia y la resolución recursiva documentada convierten al OpenQASM generado en un artefacto **auditable**: cada instrucción puede rastrearse hasta una columna concreta y hasta la definición de compuerta que le dio origen.

### 3.5 Determinismo, Reproducibilidad y Pruebas de Regresión

En QSE, la reproducibilidad es prerequisito de todo proceso de V&V. `quirk_to_qasm` es **funcionalmente determinista**: la misma URL produce siempre el mismo OpenQASM. Esta propiedad habilita:

- **Golden / snapshot tests**: comparación contra OpenQASM de referencia fijos.
- **Regression tests**: detección automática de cambios no intencionales entre versiones del traductor.
- **Differential testing**: contraste entre implementaciones o entre variantes del traductor (p. ej., entre `QASM_VERSION='2.0'` y `'3.0'`).

### 3.6 Estrategias de Verificación Automatizada Aplicables en Etapas Iniciales

Además del determinismo, la estructura del traductor permite estrategias concretas que la QSE recomienda para software cuántico:

- **Contraste análisis–generación**: cruzar `quirk_circuit_info.gates` con las instrucciones efectivamente emitidas en OpenQASM (cobertura: toda compuerta presente en Quirk debe generar al menos una instrucción y no deben aparecer compuertas no declaradas).
- **Invariantes (*property-based testing*)**: `n_qubits`, número de columnas, cantidad de controles por operación, rango válido de índices `q[i]`.
- **Pruebas metamórficas**: el resultado debe permanecer invariante ante cambios que no alteran el circuito (desplazamiento por `offset`, renombrado equivalente de *custom gates*, reordenamiento de columnas disjuntas).
- **Validación sintáctica**: parsear el OpenQASM emitido con consumidores externos (Qiskit, validador OpenQASM) para detectar no conformidad.
- **Simulación cruzada**: migrar el OpenQASM a al menos dos simuladores/ecosistemas y comparar resultados, atribuyendo las discrepancias solo a los backends y no a la traducción.

### 3.7 Cálculo ZX como Verificador Semántico Integrado en Etapas Iniciales

El pipeline incorpora un verificador semántico automático basado en grafos ZX, sin depender de herramientas externas:

- `quirk_to_zx_graph` construye el grafo ZX directamente desde la fuente Quirk.
- `qasm_to_zx_graph` construye el grafo ZX desde el OpenQASM generado.
- `compare_zx_graphs` (`qtrans/utils/zx_utils.py`) compara ambos grafos: con `zx.Circuit.verify_equality(..., up_to_global_phase=True)` para circuitos grandes y con `zx.simplify.full_reduce` + `zx.compare_tensors` para circuitos pequeños. `_run_zx_workflow` (`qtrans/core.py`) lo invoca y registra el resultado en `ZXCalculus/comparison_results.md`; esta regla de equivalencia es única y compartida por las tres formas de ejecución (librería/CLI y cuaderno).

Este mecanismo integrado convierte la comprobación semántica (el nivel más fuerte de verificación) en **un artefacto reproducible del pipeline**, alineado con la exigencia de la QSE de instrumentar la verificación como parte del proceso de desarrollo y no como una actividad manual posterior.

## 4. Inspección Estructurada mediante `quirk_circuit_info`

`quirk_circuit_info(url)` retorna un objeto con información exhaustiva del circuito:

```text
{
  n_qubits,
  n_cols,
  gates,
  custom_gates,
  custom_gate_ids,
  custom_gate_names,
  n_custom_gates,
  custom_gates_gates,
  custom_gates_info
}
```

Esta información permite:

- **Verificación de dimensiones**: Comprobar que `n_qubits` efectivo (incluyendo altura de puertas utilizadas) coincide con el número de registros `q` requeridos en OpenQASM.
- **Inventario de puertas**: Auditar que todas las puertas presentes en el circuito Quirk han sido consideradas por el traductor.
- **Inventario de *custom gates***: Verificar que todas las abstracciones definidas (`custom_gates`) y referenciadas (`custom_gate_ids/names`) están presentes y correctamente mapeadas.
- **Inspección de definiciones internas**: `custom_gates_info` y `custom_gates_gates` permiten examinar la estructura interna de cada *custom gate* (columnas, puertas, jerarquías), facilitando la validación antes de su expansión.
- **Cobertura estructural**: Asegurar que el conjunto de elementos extraídos cubre íntegramente lo representado en `circuit.cols`.

## 5. Trazabilidad y Preservación de Estructura

### 5.1 Trazabilidad de Puertas

Gracias a la resolución explícita de *custom gates* mediante `_build_gate_map` y `_col_to_qasm_with_gates`, es posible **trazar cada instrucción OpenQASM** hasta su origen en el circuito Quirk:

- **Identificación por definición**: Cada *custom gate* se resuelve a partir de su `id`/`name`, manteniendo correspondencia con la definición original.
- **Contexto por columna**: El sufijo `:k` asegura trazabilidad cuando la misma definición se instancia múltiples veces en columnas distintas.
- **Resolución recursiva documentada**: La expansión paso a paso permite seguir la jerarquía de resolución (definición → subdefiniciones → puertas primitivas), lo cual resulta crítico para depuración y auditoría.

### 5.2 Preservación de Conectividad y Jerarquía

- **Conectividad explícita**: Controles y *targets* se preservan durante la expansión, evitando reordenamientos que podrían alterar la semántica.
- **Jerarquía intacta**: El soporte a anidamiento (profundidad ≤ 10) mantiene la estructura jerárquica definida por el usuario, permitiendo contrastar la jerarquía Quirk contra la secuencia expandida en OpenQASM.
- **Geometría coherente**: `_gate_height`, `offset` y el cálculo del número efectivo de qubits garantizan que la asignación a registros `q[i]` refleje fielmente la disposición del circuito original.

## 6. Equivalencia entre Circuitos Migrados

### 6.1 Equivalencia Estructural

La **equivalencia estructural** se establece cuando:

1. Las dimensiones efectivas coinciden: `n_qubits` (Quirk, efectivo) ≡ número de qubits declarados en OpenQASM.
2. La topología de operaciones se preserva: mismo conjunto de puertas efectivas, mismas relaciones control-target y misma conectividad.
3. La jerarquía de abstracciones se resuelve de forma coherente: la expansión produce una secuencia que corresponde semánticamente a las definiciones originales.
4. El mapeo columna→instrucciones respeta la semántica columnar de Quirk.

Al mantener todos estos elementos, QTransLIFIA permite establecer una **correspondencia estructural verificable** entre la representación Quirk y la representación OpenQASM.

### 6.2 Equivalencia Funcional

La **equivalencia funcional** (misma acción unitaria sobre el espacio de estados, salvo fases globales irrelevantes según contexto) puede verificarse externamente aprovechando la fidelidad estructural lograda:

- **Base para simulación cruzada**: Al migrar a OpenQASM, el mismo circuito puede ejecutarse en distintos simuladores/compiladores que consuman ese IR. La comparación de resultados (estados, distribuciones, valores esperados) permite detectar discrepancias atribuibles al backend, no a errores de traducción.
- **Verificación mediante herramientas externas**: Herramientas de equivalencia de circuitos (comparadores unitarios, verificadores formales o frameworks de *circuit equivalence checking*) pueden operar sobre el OpenQASM generado, tomando como referencia la semántica preservada desde Quirk.
- **Comparación entre variantes**: Resulta viable comparar el circuito original (conceptualmente) con el traducido mediante ejecución en entornos equivalentes para validar corrección funcional.

### 6.3 Equivalencia entre Distintos Lenguajes y Ecosistemas

El proceso completo habilita la **verificabilidad cruzada entre ecosistemas**:

1. **Origen**: Circuito definido en Quirk (modelo visual/URL).
2. **Intermedio**: Representación canónica OpenQASM (texto, ampliamente soportado).
3. **Destinos múltiples**: Simuladores, transpiladores, SDKs o hardware que consumen OpenQASM.

Dado que OpenQASM actúa como *punto de referencia intermedio*, la equivalencia puede validarse en dos niveles:

- **Quirk ↔ OpenQASM**: Verificable estructuralmente mediante `quirk_circuit_info` + inspección del OpenQASM generado (trazabilidad de puertas, conteos, conectividad).
- **OpenQASM ↔ múltiples backends**: Verificable funcionalmente mediante ejecución cruzada con resultados consistentes entre ecosistemas.

## 7. Mecanismos que Facilitan la Verificación Automatizada

### 7.1 Determinismo como Requisito Crítico

La traducción es **funcionalmente determinista**: mismo input (URL Quirk) → misma salida (OpenQASM). Esto permite:

- *Golden tests*: Comparación contra *snapshots* conocidos.
- *Regression tests*: Detección automática de cambios no intencionales entre versiones.
- *Differential testing*: Comparación entre implementaciones o entre versiones del traductor.

### 7.2 Verificación por Contraste Análisis–Generación

La separación entre `quirk_circuit_info` y `quirk_to_qasm` permite diseñar verificadores automatizados:

- **Contraste de dimensiones**: Verificar que `n_qubits` declarado en OpenQASM coincide con `n_qubits` efectivo reportado por `quirk_circuit_info`.
- **Contraste de puertas**: Cruce entre `gates` (listado estructurado) y las instrucciones emitidas en OpenQASM (conteo por tipo, presencia de referencias).
- **Cobertura de *custom gates***: Asegurar que todas las `custom_gate_ids` referenciadas han sido resueltas y que ninguna definición queda sin utilizar cuando corresponde.
- **Validación de resolución**: Comprobar que la expansión recursiva cubre todos los niveles definidos en `custom_gates_info`, respetando el límite de profundidad.

### 7.3 Trazabilidad Sistemática

- **Resolución explícita**: El proceso `_col_to_qasm_with_gates` hace explícita la expansión, lo que facilita *logging* estructurado para auditoría paso a paso.
- **Mapeo unívoco**: `id`/`name` + sufijo `:k` proporcionan claves únicas para rastrear cada instancia expandida, esencial para identificar el origen de cualquier instrucción generada.

## 8. Recomendaciones para Verificación Práctica

Aunque la verificación funcional completa puede requerir herramientas externas, el proyecto provee los elementos necesarios para un riguroso proceso de validación:

- **Verificación estructural**: Usar `quirk_circuit_info` para validar inventario, dimensiones, *custom gates* y jerarquías antes de revisar OpenQASM.
- **Verificación sintáctica**: Validar el OpenQASM generado con parsers OpenQASM existentes (simuladores, validadores) para asegurar conformidad con el estándar.
- **Verificación cruzada**: Ejecutar el mismo circuito traducido en al menos dos simuladores distintos que soporten OpenQASM y comparar resultados para detectar posibles errores de traducción.
- **Verificación por casos canónicos**: Mantener un conjunto de circuitos Quirk representativos (puertas nativas, multi-qubit, *custom gates* simples/anidados) con sus correspondientes OpenQASM esperados para *regression testing*.

## 9. Conclusión

QTransLIFIA está diseñado con la **verificabilidad como atributo de calidad**. La combinación de:

1. **Metadatos estructurados** (`quirk_circuit_info`) para inspección sistemática.
2. **Trazabilidad explícita** mediante resolución por `id`/`name` y sufijo `:k`.
3. **Preservación estructural** de conectividad, jerarquía, geometría y controles.
4. **Determinismo** del proceso de traducción.
5. **Representación intermedia estable** (OpenQASM) que permite verificación cruzada entre ecosistemas.

...permite establecer tanto **equivalencia estructural** (Quirk ↔ OpenQASM) como habilitar **equivalencia funcional** mediante validación externa. Esto garantiza que la migración entre lenguajes y ecosistemas se realice con alta confianza, priorizando la **fidelidad semántica** del circuito original por encima de una mera conversión superficial.
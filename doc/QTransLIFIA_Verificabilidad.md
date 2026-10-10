# QTransLIFIA - Verificabilidad y Equivalencia entre Circuitos

## 1. Introducción

La verificabilidad en QTransLIFIA se refiere a la capacidad de comprobar que el circuito traducido desde Quirk a OpenQASM 2.0 es **equivalente** al circuito original, tanto desde el punto de vista estructural como, potencialmente, funcional. Esto resulta fundamental para garantizar una migración fiable entre lenguajes y ecosistemas distintos.

## 2. Fundamentos para la Verificabilidad

El diseño del traductor incorpora elementos explícitos que facilitan la inspección, trazabilidad y comparación entre representaciones:

- **Separación entre análisis y generación**: La existencia de `quirk_circuit_info` permite auditar el circuito antes de emitir OpenQASM, independizando la verificación estructural de la sintaxis generada.
- **Modelo estructurado completo**: Se expone un inventario detallado del circuito original, lo que habilita contrastes sistemáticos entre origen (Quirk) y destino (OpenQASM).
- **Determinismo**: Dada una misma URL Quirk, `quirk_to_qasm` produce un resultado determinista. Esto permite *regression testing* robusto y comparación bit-a-bit entre versiones.

## 3. Inspección Estructurada mediante `quirk_circuit_info`

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

## 4. Trazabilidad y Preservación de Estructura

### 4.1 Trazabilidad de Puertas

Gracias a la resolución explícita de *custom gates* mediante `_build_gate_map` y `_col_to_qasm_with_gates`, es posible **trazar cada instrucción OpenQASM** hasta su origen en el circuito Quirk:

- **Identificación por definición**: Cada *custom gate* se resuelve a partir de su `id`/`name`, manteniendo correspondencia con la definición original.
- **Contexto por columna**: El sufijo `:k` asegura trazabilidad cuando la misma definición se instancia múltiples veces en columnas distintas.
- **Resolución recursiva documentada**: La expansión paso a paso permite seguir la jerarquía de resolución (definición → subdefiniciones → puertas primitivas), lo cual resulta crítico para depuración y auditoría.

### 4.2 Preservación de Conectividad y Jerarquía

- **Conectividad explícita**: Controles y *targets* se preservan durante la expansión, evitando reordenamientos que podrían alterar la semántica.
- **Jerarquía intacta**: El soporte a anidamiento (profundidad ≤ 10) mantiene la estructura jerárquica definida por el usuario, permitiendo contrastar la jerarquía Quirk contra la secuencia expandida en OpenQASM.
- **Geometría coherente**: `_gate_height`, `offset` y el cálculo del número efectivo de qubits garantizan que la asignación a registros `q[i]` refleje fielmente la disposición del circuito original.

## 5. Equivalencia entre Circuitos Migrados

### 5.1 Equivalencia Estructural

La **equivalencia estructural** se establece cuando:

1. Las dimensiones efectivas coinciden: `n_qubits` (Quirk, efectivo) ≡ número de qubits declarados en OpenQASM 2.0.
2. La topología de operaciones se preserva: mismo conjunto de puertas efectivas, mismas relaciones control-target y misma conectividad.
3. La jerarquía de abstracciones se resuelve de forma coherente: la expansión produce una secuencia que corresponde semánticamente a las definiciones originales.
4. El mapeo columna→instrucciones respeta la semántica columnar de Quirk.

Al mantener todos estos elementos, QTransLIFIA permite establecer una **correspondencia estructural verificable** entre la representación Quirk y la representación OpenQASM 2.0.

### 5.2 Equivalencia Funcional

La **equivalencia funcional** (misma acción unitaria sobre el espacio de estados, salvo fases globales irrelevantes según contexto) puede verificarse externamente aprovechando la fidelidad estructural lograda:

- **Base para simulación cruzada**: Al migrar a OpenQASM 2.0, el mismo circuito puede ejecutarse en distintos simuladores/compiladores que consuman ese IR. La comparación de resultados (estados, distribuciones, valores esperados) permite detectar discrepancias atribuibles al backend, no a errores de traducción.
- **Verificación mediante herramientas externas**: Herramientas de equivalencia de circuitos (comparadores unitarios, verificadores formales o frameworks de *circuit equivalence checking*) pueden operar sobre el OpenQASM generado, tomando como referencia la semántica preservada desde Quirk.
- **Comparación entre variantes**: Resulta viable comparar el circuito original (conceptualmente) con el traducido mediante ejecución en entornos equivalentes para validar corrección funcional.

### 5.3 Equivalencia entre Distintos Lenguajes y Ecosistemas

El proceso completo habilita la **verificabilidad cruzada entre ecosistemas**:

1. **Origen**: Circuito definido en Quirk (modelo visual/URL).
2. **Intermedio**: Representación canónica OpenQASM 2.0 (texto, ampliamente soportado).
3. **Destinos múltiples**: Simuladores, transpiladores, SDKs o hardware que consumen OpenQASM.

Dado que OpenQASM 2.0 actúa como *punto de referencia intermedio*, la equivalencia puede validarse en dos niveles:

- **Quirk ↔ OpenQASM**: Verificable estructuralmente mediante `quirk_circuit_info` + inspección del OpenQASM generado (trazabilidad de puertas, conteos, conectividad).
- **OpenQASM ↔ múltiples backends**: Verificable funcionalmente mediante ejecución cruzada con resultados consistentes entre ecosistemas.

## 6. Mecanismos que Facilitan la Verificación Automatizada

### 6.1 Determinismo como Requisito Crítico

La traducción es **funcionalmente determinista**: mismo input (URL Quirk) → misma salida (OpenQASM 2.0). Esto permite:

- *Golden tests*: Comparación contra *snapshots* conocidos.
- *Regression tests*: Detección automática de cambios no intencionales entre versiones.
- *Differential testing*: Comparación entre implementaciones o entre versiones del traductor.

### 6.2 Verificación por Contraste Análisis–Generación

La separación entre `quirk_circuit_info` y `quirk_to_qasm` permite diseñar verificadores automatizados:

- **Contraste de dimensiones**: Verificar que `n_qubits` declarado en OpenQASM coincide con `n_qubits` efectivo reportado por `quirk_circuit_info`.
- **Contraste de puertas**: Cruce entre `gates` (listado estructurado) y las instrucciones emitidas en OpenQASM (conteo por tipo, presencia de referencias).
- **Cobertura de *custom gates***: Asegurar que todas las `custom_gate_ids` referenciadas han sido resueltas y que ninguna definición queda sin utilizar cuando corresponde.
- **Validación de resolución**: Comprobar que la expansión recursiva cubre todos los niveles definidos en `custom_gates_info`, respetando el límite de profundidad.

### 6.3 Trazabilidad Sistemática

- **Resolución explícita**: El proceso `_col_to_qasm_with_gates` hace explícita la expansión, lo que facilita *logging* estructurado para auditoría paso a paso.
- **Mapeo unívoco**: `id`/`name` + sufijo `:k` proporcionan claves únicas para rastrear cada instancia expandida, esencial para identificar el origen de cualquier instrucción generada.

## 7. Recomendaciones para Verificación Práctica

Aunque la verificación funcional completa puede requerir herramientas externas, el proyecto provee los elementos necesarios para un riguroso proceso de validación:

- **Verificación estructural**: Usar `quirk_circuit_info` para validar inventario, dimensiones, *custom gates* y jerarquías antes de revisar OpenQASM.
- **Verificación sintáctica**: Validar el OpenQASM 2.0 generado con parsers OpenQASM 2.0 existentes (simuladores, validadores) para asegurar conformidad con el estándar.
- **Verificación cruzada**: Ejecutar el mismo circuito traducido en al menos dos simuladores distintos que soporten OpenQASM 2.0 y comparar resultados para detectar posibles errores de traducción.
- **Verificación por casos canónicos**: Mantener un conjunto de circuitos Quirk representativos (puertas nativas, multi-qubit, *custom gates* simples/anidados) con sus correspondientes OpenQASM esperados para *regression testing*.

## 8. Conclusión

QTransLIFIA está diseñado con la **verificabilidad como atributo de calidad**. La combinación de:

1. **Metadatos estructurados** (`quirk_circuit_info`) para inspección sistemática.
2. **Trazabilidad explícita** mediante resolución por `id`/`name` y sufijo `:k`.
3. **Preservación estructural** de conectividad, jerarquía, geometría y controles.
4. **Determinismo** del proceso de traducción.
5. **Representación intermedia estable** (OpenQASM 2.0) que permite verificación cruzada entre ecosistemas.

...permite establecer tanto **equivalencia estructural** (Quirk ↔ OpenQASM) como habilitar **equivalencia funcional** mediante validación externa. Esto garantiza que la migración entre lenguajes y ecosistemas se realice con alta confianza, priorizando la **fidelidad semántica** del circuito original por encima de una mera conversión superficial.
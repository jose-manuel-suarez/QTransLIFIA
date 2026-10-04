# QTransLIFIA - Abstracción y Características Determinantes

## 1. Propósito del Proyecto

QTransLIFIA es un traductor de circuitos cuánticos definidos en **Quirk** (mediante su URL con JSON embebido) utilizando el lenguaje **OpenQASM** como lenguaje "pivote" en la traducción. Su objetivo principal es realizar una migración con alta fidelidad semántica, preservando tanto la estructura del circuito como la expresividad algorítmica definida por el usuario.

## 2. Características Determinantes

Las características que definen el proyecto son las siguientes:

### 2.1 Preservación Semántica

- **Conservación de *custom gates***: El traductor no se limita al mapeo de puertas nativas, sino que mantiene las puertas personalizadas (`custom gates`) definidas por el usuario en Quirk. Estas se identifican por su `id` y `name`, garantizando que la semántica original se conserva íntegramente.
- **Expansión controlada con anidamiento**: Las *custom gates* se expanden recursivamente con soporte de anidamiento (profundidad ≤ 10). Esto permite trasladar jerarquías completas de abstracciones sin pérdida de información.
- **Resolución diferenciada por contexto**: El sufijo `:k` (ej. `~abc:1`) permite distinguir expansiones de una misma *custom gate* cuando aparece en columnas distintas, preservando su contexto de uso dentro del circuito.
- **Fidelidad estructural**: Se preservan conectividad, controles, *targets* y la disposición columnar original, asegurando que el circuito traducido mantenga la intención algorítmica del diseño en Quirk.

### 2.2 Tratamiento de la Geometría del Circuito

- **Altura consciente (*height-aware*)**: Mediante `_gate_height`, el traductor calcula correctamente la altura ocupada por puertas multi-qubit y *custom gates*, evitando desplazamientos erróneos entre qubits.
- **Cálculo de *offset***: El parámetro `offset` desplaza todos los índices `q[i+offset]`, ajustando `n = max(len(col)) + offset` en función de la altura de las compuertas utilizadas. Esto garantiza una asignación coherente entre la representación de Quirk y los registros de OpenQASM 2.0.
- **Determinación del número efectivo de qubits**: `n_qubits` se calcula considerando la altura efectiva de las puertas empleadas, no únicamente la anchura visible, lo que permite representar correctamente circuitos con abstracciones jerárquicas.

### 2.3 Separación entre Análisis y Generación

- **Extracción estructurada de metadatos**: `quirk_circuit_info` proporciona un modelo de datos completo: `{n_qubits, n_cols, gates, custom_gates, custom_gate_ids, custom_gate_names, n_custom_gates, custom_gates_gates, custom_gates_info}`.
- **Desacoplamiento de responsabilidades**: La fase de *parsing* y reconocimiento del circuito (`parse_quirk_url`, extracción de *custom gates*) está separada de la fase de emisión (`quirk_to_qasm`, mapeo por columna). Esto permite analizar el circuito sin generar necesariamente código OpenQASM.

### 2.4 Normalización del Formato

- **Interoperabilidad con Quirk**: `parse_quirk_url` y `encode_quirk_url` trabajan con JSON estrictamente con comillas dobles, asegurando compatibilidad con el formato exacto empleado por Quirk para sus URLs.
- **Representación intermedia estable**: La elección de **OpenQASM 2.0** como lenguaje intermedio convierte a QTransLIFIA en un puente entre el ecosistema de diseño/visualización (Quirk) y los ecosistemas de simulación, compilación y ejecución cuántica.

## 3. Abstracción desde la Perspectiva de Ingeniería de Software

### 3.1 Frontera Clara entre Dominios

El proyecto establece una frontera bien definida entre dos modelos semánticos distintos:

1. **Dominio Quirk**: Modelo visual, basado en columnas (`cols`), URL-encoded y centrado en la exploración algorítmica interactiva.
2. **Dominio OpenQASM**: Modelo textual, imperativo y basado en registros cuánticos (`q[...]`), orientado a simuladores, compiladores y toolchains.

Esta separación evita que los detalles de representación de un dominio contaminen al otro, aplicando el principio de **separación de preocupaciones**.

### 3.2 Preservación de la Expresividad Algorítmica

Uno de los aspectos más relevantes es la **preservación de las abstracciones definidas por el usuario**. En Quirk, las *custom gates* constituyen primitivas algorítmicas creadas durante el diseño del circuito. Tradicionalmente, un traductor sintáctico tendería a "aplanar" (*flatten*) dichas abstracciones, perdiendo su intención conceptual.

QTransLIFIA, en cambio, **transfiere esa abstracción**: mantiene la estructura jerárquica definida en Quirk y la traslada al proceso de traducción. Esto permite que dicha expresividad algorítmica se conserve en OpenQASM y, consecuentemente, en el ecosistema destino.

### 3.3 Ocultación de Complejidad

- **Abstracción del *parsing***: La complejidad del JSON anidado dentro de la URL queda encapsulada en `parse_quirk_url`, exponiendo al resto del sistema estructuras de datos normalizadas.
- **Modelo estructurado para análisis**: `quirk_circuit_info` abstrae la representación críptica de la URL y ofrece una vista de alto nivel del circuito (puertas, *custom gates*, dimensiones), facilitando el razonamiento, la inspección y la validación sin operar directamente sobre el formato de Quirk.

### 3.4 Reutilización Conceptual de las Abstracciones

Al preservar las *custom gates*, estas dejan de ser un artefacto puramente visual para convertirse en **entidades trasladables, reutilizables y analizables** fuera de Quirk. Esto eleva el nivel de abstracción del proceso de migración: no se traduce únicamente una secuencia de puertas, sino también la **jerarquía de diseño** con la que fue concebido el algoritmo cuántico.

## 4. Conclusión

QTransLIFIA adopta un enfoque de **traducción semántica con preservación de abstracciones**, en lugar de una mera transliteración sintáctica. La conservación sistemática de las *custom gates* definidas por el usuario, junto con un modelo de análisis estructurado y una clara separación entre dominios, constituyen sus características determinantes. Esto garantiza que la **expresividad algorítmica** del circuito original se mantenga íntegra al migrar hacia OpenQASM 2.0+ y, posteriormente, hacia cualquier ecosistema destino. Además debemos considerar la modularidad de funcionalidad y reutilización inherente cuando se conservan las funcionalidades locales asociadas a la definición de las compuertas definidas por el usuario.
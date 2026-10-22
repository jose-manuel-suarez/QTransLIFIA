# QTransLIFIA - Abstracción y Características Determinantes

## 1. Propósito del Proyecto

QTransLIFIA es un traductor de circuitos cuánticos definidos utilizando la herramienta interactiva: **Quirk** (mediante su URL con JSON embebido) y a partir de la utilización del lenguaje **OpenQASM** como lenguaje "pivote" en la traducción. Su objetivo principal es realizar una migración con alta fidelidad semántica, preservando tanto la estructura del circuito como la expresividad algorítmica definida por el usuario.

## 2. Características Determinantes

Las características que definen el proyecto son las siguientes:

### 2.1 Preservación Semántica

- **Conservación de *custom gates***: El traductor no se limita al mapeo de puertas nativas, sino que mantiene las puertas personalizadas (`custom gates`) definidas por el usuario en Quirk. Estas se identifican por su `id` y `name`, garantizando que la semántica original se conserva íntegramente.
- **Expansión controlada con anidamiento**: Las *custom gates* se expanden recursivamente con soporte de anidamiento (profundidad ≤ 10). Esto permite trasladar jerarquías completas de abstracciones sin pérdida de información.
- **Resolución diferenciada por contexto**: El sufijo `:k` (ej. `~abc:1`) permite distinguir expansiones de una misma *custom gate* cuando aparece en columnas distintas, preservando su contexto de uso dentro del circuito.
- **Fidelidad estructural**: Se preservan conectividad, controles, *targets* y la disposición columnar original, asegurando que el circuito traducido mantenga la intención algorítmica del diseño en Quirk.

### 2.2 Tratamiento de la Geometría del Circuito

- **Altura consciente (*height-aware*)**: Mediante `_gate_height`, el traductor calcula correctamente la altura ocupada por puertas multi-qubit y *custom gates*, evitando desplazamientos erróneos entre qubits.
- **Cálculo de *offset***: El parámetro `offset` desplaza todos los índices `q[i+offset]`, ajustando `n = max(len(col)) + offset` en función de la altura de las compuertas utilizadas. Esto garantiza una asignación coherente entre la representación de Quirk y los registros de OpenQASM.
- **Determinación del número efectivo de qubits**: `n_qubits` se calcula considerando la altura efectiva de las puertas empleadas, no únicamente la anchura visible, lo que permite representar correctamente circuitos con abstracciones jerárquicas.

### 2.3 Separación entre Análisis y Generación

- **Extracción estructurada de metadatos**: `quirk_circuit_info` proporciona un modelo de datos completo: `{n_qubits, n_cols, gates, custom_gates, custom_gate_ids, custom_gate_names, n_custom_gates, custom_gates_gates, custom_gates_info}`.
- **Desacoplamiento de responsabilidades**: La fase de *parsing* y reconocimiento del circuito (`parse_quirk_url`, extracción de *custom gates*) está separada de la fase de emisión (`quirk_to_qasm`, mapeo por columna). Esto permite analizar el circuito sin generar necesariamente código OpenQASM.

### 2.4 Normalización del Formato

- **Interoperabilidad con Quirk**: `parse_quirk_url` y `encode_quirk_url` trabajan con JSON estrictamente con comillas dobles, asegurando compatibilidad con el formato exacto empleado por Quirk para sus URLs.
- **Representación intermedia estable**: La elección de **OpenQASM** (versiones 2.0 y 3.0, por defecto 3.0) como lenguaje intermedio convierte a QTransLIFIA en un puente entre el ecosistema de diseño/visualización (Quirk) y los ecosistemas de simulación, compilación y ejecución cuántica.

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

Al preservar las *custom gates*, estas dejan de ser un artefacto puramente visual para convertirse en **entidades trasladables, reutilizables y analizables** fuera de Quirk. Es decir, módulos funcionales e identificables perfectamente reutilizables, afectando positivamente el mantenimiento del software cuántico y su expresividad. Esto eleva el nivel de abstracción del proceso de migración: no se traduce únicamente una secuencia de puertas, sino también la **jerarquía de diseño** con la que fue concebido el algoritmo cuántico por parte del ingeniero.

## 4. Estructura de la URL de Quirk y Estrategias de Traducción a OpenQASM

### 4.1 Anatomía de la URL: `cols` y `gates`

La representación canónica de un circuito en Quirk es la URL:

```
https://algassert.com/quirk#circuit={"cols":[...],"gates":[...]}
```

- **`cols` (columnas)**: lista de columnas sincrónicas; cada celda de una columna es:
  - un **string con una compuerta estándar** de Quirk — `H`, `X`, `Z`, `Measure`, `•` (control), `⊖`/`⊕`/`(/)`/`⊗` (sondas de eje X/Y), `X^½`/`Z^t` (rotaciones con ángulo como exponente), `QFT3`/`QFT†3` (QFT nativa), etc.;
  - un **string `~id`**, que *referencia* una custom gate definida en el campo `gates`;
  - un entero (`1` o la altura del bloque), que indica un canal inactivo (*idle*) ocupando qubits.
- **`gates` (banco de definiciones)**: cada entrada tiene un `id` (referenciado como `~id`) y/o un `name`, y se define por **una de tres formas**:

| Forma de definición | Estructura JSON | Ejemplo |
|---|---|---|
| **Circuito acotado** | `{"id": "~rvcr", "name": "MultiX", "circuit": {"cols": [["•","•","X","•"]]}}` | compuerta multi-control anidada |
| **Matriz** | `{"id": "~edqr", "name": "mia", "matrix": [...]}` | unitaria 2×2 o 4×4 con entradas `{"re":..,"im":..}` o strings `"1/sqrt(2)"` |
| **Ángulos / operación estándar** | `{"id": "~cu10000", "name": "cu1(pi/512)"}` | operación `op(args)` de `stdgates.inc` parametrizada por ángulo |

Un circuito acotado puede, a su vez, referenciar otras custom gates (anidamiento soportado, profundidad ≤ 10) y usar el sufijo `:k` (p. ej. `~abc:1`) para distinguir expansiones de la misma `id` en contextos de columnas distintas.

### 4.2 Estrategias de traducción a OpenQASM

Para cada custom gate, `_build_gate_map` / `_resolve_gate_names` construyen el mapa de definiciones y `append_custom_gates` emite, una sola vez, la declaración `gate nombre(a, b, ...) { ... }` de OpenQASM con todas las definiciones del banco (incluso las no usadas en `cols`). El cuerpo se resuelve en **cadena de estrategias**, en orden de menor a mayor complejidad:

**A. Definición por circuito acotado (`circuit.cols`)**
Se expande recursivamente columna a columna con la misma maquinaria que el circuito principal (mapeo por columna, controles, altura consciente), anidamiento ≤ 10. La compuerta queda como una declaración `gate` reutilizable y, con `preserve_custom_gates=true`, se conserva como función local en los scripts migrados; si no, se expande en línea.

**B. Definición por matriz: operación única primero (`_resolve_matrix_operation`)**
Antes de descomponer, se intenta resolver la matriz a **una sola operación** de `stdgates.inc`:
1. **`name` con forma `op(args)`**: se contrasta contra la tabla de operaciones estándar (`cu1(pi/512)` → `cp`, `op(0.3)` → rotación por ángulo, etc.).
2. **Fases conocidas**: fases fijas reconocibles (`U(-pi/2, …)` → `p(-pi/2)`, `cu1(θ)` de un qubit → `p(θ)`).
3. **Matriz diagonal de fase 2×2** (`{{1,0},{0,z}}`) → `p(phase(z))`.

**C. Definición por matriz: descomposición numérica (fallback unitario)**
Si B no aplica y la matriz es unitaria de dimensión adecuada (`_unitary_matrix_body`; tolerancia 1e-6 sobre Frobenius, con proyección SVD a la unitaria más cercana porque Quirk publica matrices redondeadas ~7 dígitos):
- **2×2 (1 qubit) → `p` + ZYZ** (`_euler_matrix_body`): toda unitaria 2×2 es `e^{i·g}·rz(β)·ry(γ)·rz(δ)` con `g = phase(det)/2` — el mismo algoritmo ZYZ del pipeline ZX. Como `p` **no** es una fase global (es `diag(1, e^{i·α})`, fase *relativa*), la fase se materializa con la identidad `e^{i·g}·I = p(2g)·rz(−2g)`, que sí es escalar por identidad y conmuta con el resto. Se emite: `p(α); rz(−α); rz(δ); ry(γ); rz(β);` (líneas nulas omitidas, `id` si es casi identidad).
- **4×4 (2 qubits) → KAK + `U`/`cx`** (`_two_qubit_kak_body`): síntesis de dos qubits de Qiskit (`transpile` a base `['u','cx']`); cada `u` se serializa como la **`U` intrínseca** de OpenQASM 3 (la `u` minúscula de Qiskit no está en `stdgates.inc` y su parser la rechaza) y la fase global del resultado del KAK se emite con la misma identidad `p(2φ); rz(−2φ);`.
- Si la matriz **no** es unitaria de dimensión 2 o 4, ni `name`/diagonal la resuelven, la traducción falla con un error accionable (no emite QASM inválido).

**D. Casos nativos**: las QFT de Quirk (`QFTn`, `QFTn†` → `QFT†n` canónico) tienen tratamiento propio con declaración `gate QFTn a,b,c {…}` y sus controles (`ctrl @ QFTn …`).

**Convención de bits**: en Quirk el wire superior de un bloque es el **bit menos significativo**, la misma convención de OpenQASM/Qiskit, por lo que las matrices se descomponen sin invertir qubits (el qubit 0 de Qiskit corresponde a la letra `a` de la declaración `gate`). Los nombres se sanitizan para no chocar con palabras reservadas de QASM (`pi` → `pi_gate`, dígitos iniciales → `gate_N`), y el resultado carga con `qasm3.loads`/`qasm2.loads` y produce scripts migrados válidos en los tres ecosistemas.

## 5. Conclusión

QTransLIFIA adopta un enfoque de **traducción semántica con preservación de abstracciones**, en lugar de una mera transliteración sintáctica. La conservación sistemática de las *custom gates* definidas por el usuario, junto con un modelo de análisis estructurado y una clara separación entre dominios, constituyen sus características determinantes. Esto garantiza que la **expresividad algorítmica** del circuito original se mantenga íntegra al migrar hacia OpenQASM y, posteriormente, hacia cualquier ecosistema destino. Además debemos considerar la modularidad de funcionalidad y reutilización inherente cuando se conservan las funcionalidades locales asociadas a la definición de las compuertas definidas por el usuario.

A nivel de conservación de expresividad y nivel de abstracción, ahora los ingenieros cuánticos pueden definir o importar sobre Quirk sus compuertas personalizadas y probadas, no siendo una limitante la traducción al ecosistema destino sino más bien significando una transferencia de dichos módulos funcionales.
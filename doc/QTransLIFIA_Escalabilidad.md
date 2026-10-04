# QTransLIFIA - Escalabilidad

## 1. Introducción

La escalabilidad en QTransLIFIA se entiende como la capacidad del traductor para crecer en complejidad (más qubits, más columnas, jerarquías de *custom gates* más profundas) y, fundamentalmente, para integrarse con distintos ecosistemas cuánticos sin necesidad de modificar la lógica central de traducción Quirk → OpenQASM 2.0.

## 2. Escalabilidad Arquitectónica

### 2.1 Pipeline Modular y Desacoplado

El proceso de traducción sigue una tubería claramente definida, compuesta por etapas con responsabilidades independientes:

1. **Parsing** (`parse_quirk_url`): Normaliza la URL de Quirk y extrae el JSON embebido.
2. **Extracción de metadatos** (`quirk_circuit_info`): Identifica dimensiones, puertas y *custom gates* presentes.
3. **Construcción de mapa de puertas** (`_build_gate_map`): Resuelve identificadores (`id`, `name`) para puertas nativas y personalizadas.
4. **Cálculo geométrico** (`_gate_height`): Determina la altura ocupada por cada puerta para garantizar asignación correcta de qubits.
5. **Expansión de *custom gates*** (`_col_to_qasm_with_gates`): Resuelve recursivamente las definiciones internas preservando conectividad y controles.
6. **Generación OpenQASM** (`quirk_col_to_qasm`, `quirk_to_qasm`): Emite el código OpenQASM 2.0 resultante.

Esta modularización permite escalar el sistema por evolución de cada etapa, sin introducir acoplamiento entre dominio Quirk, resolución interna y formato destino.

### 2.2 Separación entre Lógica Quirk y Lógica OpenQASM

Al centralizar la emisión exclusivamente en las funciones `quirk_to_qasm` y `quirk_col_to_qasm`, la lógica específica de Quirk queda contenida en el *parser* y en el resolutor de *custom gates*. La capa de generación es responsable únicamente de producir sintaxis OpenQASM 2.0 válida. Este desacoplamiento es la base para escalar hacia múltiples formatos o versiones en el futuro.

## 3. Escalabilidad Funcional con Respecto al Circuito

### 3.1 Escalado en Número de Qubits y Columnas

- **Altura consciente del circuito**: `_gate_height` permite manejar correctamente puertas de distinta altura (multi-qubit, *custom gates* con múltiples *targets*), evitando asignaciones incorrectas cuando el circuito crece en complejidad.
- **Cálculo dinámico de registros**: El uso de `offset` junto al ajuste de `n = max(len(col)) + offset` garantiza que la asignación `q[i]` se mantenga coherente incluso ante expansiones de *custom gates* que añaden qubits virtuales o modifican la altura efectiva.
- **Número efectivo de qubits**: `n_qubits` se determina en función de la altura real de las puertas utilizadas, lo que permite representar circuitos de mayor tamaño sin asumir una geometría fija.

### 3.2 Escalado en Jerarquías de *Custom Gates*

- **Expansión recursiva controlada**: La resolución de *custom gates* mediante `_col_to_qasm_with_gates` soporta anidamiento (profundidad ≤ 10). Esto permite componer abstracciones complejas (una *custom gate* que contiene otras *custom gates*) sin aplanado prematuro.
- **Identificación unívoca por contexto**: El sufijo `:k` evita ambigüedad al expandir la misma definición en distintas columnas, lo cual resulta esencial cuando un mismo bloque abstracto se reutiliza múltiples veces a lo largo del circuito.
- **Mapa global de definiciones**: `_build_gate_map` integra tanto puertas nativas como *custom gates*, proporcionando un mecanismo extensible para resolver nuevas abstracciones conforme el circuito escala en complejidad.

## 4. Escalabilidad hacia Múltiples Ecosistemas Destino

### 4.1 OpenQASM 2.0 como Interfaz Estable

La adopción de **OpenQASM 2.0** como representación intermedia es el eje central de la escalabilidad entre ecosistemas. OpenQASM 2.0 constituye una *lingua franca* ampliamente soportada por simuladores, transpiladores, compiladores cuánticos, SDKs y plataformas de hardware/cuántico-emulación.

Al emitir este formato intermedio, QTransLIFIA queda **agnóstico al backend destino**. Cualquier herramienta capaz de consumir OpenQASM 2.0 puede recibir directamente el circuito traducido.

### 4.2 Pipeline Reutilizable para Nuevos Destinos

El diseño actual permite escalar horizontalmente a nuevos ecosistemas sin modificar el núcleo Quirk→OpenQASM:

- **Sin reescritura del parser**: La extracción, normalización y resolución de *custom gates* permanecen invariantes ante cambios en el ecosistema destino.
- **Consumidores independientes**: Nuevos backends (simuladores, frameworks, toolchains de validación, entornos de ejecución) pueden integrarse como consumidores puros del OpenQASM generado.
- **Post-procesadores opcionales**: Resulta factible añadir etapas posteriores al generador (optimización, mapeo a topología física, reescritura para dispositivos específicos, análisis estático) que operen sobre OpenQASM, sin acoplarse a la lógica de parsing Quirk.
- **Migración a nuevos lenguajes destino**: En caso de requerir OpenQASM 3.0 u otro lenguaje, basta con implementar un nuevo generador que reutilice íntegramente `quirk_circuit_info`, el mapa de puertas y el mecanismo de expansión. La tubería Quirk→análisis permanece válida.

### 4.3 Escalabilidad por Composición

Gracias a la separación análisis/generación, el traductor puede integrarse en flujos de trabajo automatizados:

- **Integración en pipelines CI/CD**: Al ser determinista y modular, puede emplearse para validar migraciones de circuitos entre entornos de forma automatizada.
- **Procesamiento por lotes**: La interfaz `quirk_to_qasm(url, offset=0)` es minimalista y predecible, lo que facilita su invocación masiva para colecciones de circuitos Quirk.
- **Orquestación multi-destino**: Un mismo circuito Quirk puede traducirse una única vez a OpenQASM 2.0 y distribuirse simultáneamente a múltiples ecosistemas destino, maximizando la reutilización.

## 5. Escalabilidad en Mantenimiento y Evolución

- **Bajo acoplamiento**: Las responsabilidades bien definidas reducen el impacto de cambios. Extender soporte a nuevas puertas nativas afecta mayoritariamente al mapeo, no al mecanismo de expansión.
- **Trazabilidad estructurada**: Al disponer de `quirk_circuit_info`, es posible inspeccionar el circuito antes de generar OpenQASM, lo que facilita escalar las capacidades de validación sin modificar el generador.
- **Robustez ante crecimiento**: El enfoque *height-aware* y la resolución explícita de *custom gates* minimizan errores al escalar a circuitos con mayor número de qubits, más reutilización de abstracciones y mayor profundidad jerárquica.

## 6. Conclusión

QTransLIFIA presenta una arquitectura escalable tanto **verticalmente** (complejidad creciente del circuito: qubits, columnas, jerarquías anidadas) como **horizontalmente** (múltiples ecosistemas destino). El uso de OpenQASM 2.0 como interfaz estable, unido a un pipeline modular, desacoplado y reutilizable, permite que el traductor crezca sin reescribir su núcleo. En consecuencia, el sistema es escalable para incorporar nuevos destinos, nuevos consumidores y futuras variantes del propio lenguaje cuántico intermedio, manteniendo intacta la lógica que resuelve el origen Quirk.
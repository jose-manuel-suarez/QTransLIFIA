# QTransLIFIA - Extensibilidad

## 1. Introducción

La extensibilidad de QTransLIFIA hace referencia a su capacidad para adaptarse y evolucionar sin rediseñar su arquitectura central. Esto incluye la incorporación de nuevas funcionalidades, la evolución de Quirk, la adición de nuevas compuertas, la evolución de las versiones de OpenQASM y la ampliación a nuevos ecosistemas destino.

## 2. Principios de Extensibilidad

El diseño se fundamenta en:

- **Separación de responsabilidades**: Parsing, análisis, expansión de *custom gates* y emisión están claramente desacoplados.
- **Abstracción mediante mapeos**: El uso de tablas/mapas (`_build_gate_map`) y modelos estructurados (`quirk_circuit_info`) facilita añadir elementos sin alterar mecanismos existentes.
- **Centralización de la emisión**: Toda la sintaxis OpenQASM 2.0 se genera en `quirk_to_qasm` y `quirk_col_to_qasm`, lo que permite sustituir o extender la capa de salida de forma aislada.

## 3. Extensibilidad ante Evolución de Quirk

- **Mapeo basado en `id` y `name`**: `_build_gate_map` construye el mapa de puertas utilizando tanto el identificador (`id`) como el nombre (`name`) de cada puerta. Esto permite absorber cambios en nomenclatura o nuevos identificadores introducidos por futuras versiones de Quirk, siempre que la estructura `circuit.cols` se mantenga.
- **Extracción explícita de *custom gates***: El parser identifica y aísla las definiciones de *custom gates* (`custom_gates`, `custom_gate_ids`, `custom_gate_names`). Esto permite que nuevas puertas personalizadas definidas en versiones futuras de Quirk sean reconocidas y resueltas sin modificar la lógica de expansión.
- **Robustez frente a la estructura URL-JSON**: `parse_quirk_url`/`encode_quirk_url` operan sobre JSON estricto (comillas dobles), lo cual proporciona un contrato estable ante la representación empleada por Quirk. Cualquier extensión que preserve dicha estructura puede integrarse de forma natural.

## 4. Extensibilidad para Nuevas Compuertas y Funcionalidades

### 4.1 Incorporación de Nuevas Compuertas Nativas

Para añadir soporte a nuevas compuertas, basta con extender el mapeo de traducción en:

- `_build_gate_map`: Para asegurar su correcta resolución dentro del conjunto de puertas del circuito.
- `quirk_col_to_qasm` (y lógica asociada): Para definir su equivalencia de sintaxis en OpenQASM 2.0 (operadores de 1, 2 o más qubits, rotaciones, etc.).

Este enfoque localiza el cambio en la capa de mapeo/emisión, sin afectar al cálculo de alturas (`_gate_height`), al mecanismo de expansión o al parsing.

### 4.2 Incorporación y Evolución de *Custom Gates*

- **Reconocimiento automático**: Al extraerse todas las *custom gates* definidas en la URL (con sus definiciones `circuit.cols` internas), el soporte a nuevas *custom gates* es **implícito**: el sistema las resuelve siempre que sean referenciadas.
- **Expansión recursiva genérica**: `_col_to_qasm_with_gates` no asume un conjunto fijo de puertas personalizadas, sino que las resuelve dinámicamente a partir del mapa construido. Esto facilita la aparición de nuevas abstracciones definidas por el usuario.
- **Profundidad controlada y ampliable**: El límite de anidamiento (≤ 10) constituye una salvaguarda práctica de robustez (prevención de ciclos o expansiones excesivas). El mecanismo recursivo es extensible: dicho umbral podría ajustarse o formalizarse con criterios de validación, sin rediseñar el algoritmo de expansión.

### 4.3 Extensión a Nuevas Funcionalidades

La información estructurada ofrecida por `quirk_circuit_info` habilita funcionalidades futuras sin acoplarlas a la lógica de generación:

- **Validación de circuitos**: Comprobaciones estructurales (puertas no soportadas, referencias a *custom gates* inexistentes, inconsistencias de columnas).
- **Métricas y análisis**: Conteo de puertas, profundidad, ancho efectivo, reutilización de *custom gates*, complejidad jerárquica.
- **Visualización inversa, comparación o normalización**: Flujos que requieran inspección previa del circuito antes de emitir OpenQASM.
- **Reportes estructurados**: Generación de informes sobre el proceso de migración basados en metadatos, no en el texto OpenQASM.

## 5. Extensibilidad a Versiones de OpenQASM

- **Generador aislado**: La emisión OpenQASM se concentra en `quirk_to_qasm` y `quirk_col_to_qasm`. Esto permite introducir un **nuevo generador** para otras versiones (p.ej. **OpenQASM 3.0**) sin modificar el parser, la extracción de *custom gates*, la expansión recursiva ni el cálculo geométrico.
- **Reutilización completa del análisis**: `quirk_circuit_info`, el mapa de puertas resuelto y la representación expandida pueden reutilizarse íntegramente para generar sintaxis OpenQASM 3.0, QIR, o cualquier otro IR cuántico textual.
- **Evolución incremental**: Podría adoptarse un enfoque multi-generador (seleccionable por parámetro) manteniendo OpenQASM 2.0 como opción estable, lo cual resulta compatible con la arquitectura actual.

## 6. Extensibilidad a Nuevos Ecosistemas Destino

- **Arquitectura basada en representación intermedia**: Al adoptar OpenQASM 2.0 como formato canónico intermedio, nuevos ecosistemas destino no requieren modificar el núcleo Quirk→OpenQASM. Basta con integrar consumidores del OpenQASM generado.
- **Post-procesadores desacoplados**: Es posible añadir etapas posteriores al traductor (optimización, mapeo a topología de dispositivo, compilación dirigida, *routing*, *gate decomposition* específica de backend) que operen **sobre OpenQASM**. Estos post-procesadores no dependen del formato Quirk, lo cual refuerza la extensibilidad.
- **Adaptadores por ecosistema**: Nuevos destinos pueden implementarse como adaptadores externos al proyecto, reutilizando QTransLIFIA como traductor Quirk→IR estable. Esto evita proliferación de lógicas específicas de Quirk por backend.
- **Soporte a flujos multi-destino**: Un único circuito Quirk puede migrarse a OpenQASM 2.0 una vez y distribuirse a múltiples toolchains, lo cual facilita la incorporación progresiva de nuevos ecosistemas.

## 7. Consideraciones de Extensibilidad y Robustez

- **Crecimiento controlado**: El límite de anidamiento (≤ 10) es una decisión de diseño orientada a robustez ante posibles estructuras recursivas complejas, compatible con ampliar ese umbral si se justifica con criterios de validación.
- **Extensibilidad sin ruptura**: Añadir puertas, funcionalidades o generadores puede realizarse manteniendo compatibilidad hacia atrás, gracias al bajo acoplamiento y a la centralización de mapeos.
- **Favorece pruebas futuras**: La separación entre análisis (`quirk_circuit_info`) y generación facilita añadir casos de prueba por extensión (nuevas puertas, nuevos patrones de *custom gates*) sin depender exclusivamente de la salida OpenQASM completa.

## 8. Conclusión

QTransLIFIA está concebido para ser **altamente extensible**. Su arquitectura modular permite absorber:

1. **Futuras versiones de Quirk**, mediante mapeos dinámicos por `id`/`name` y extracción explícita de *custom gates*.
2. **Nuevas compuertas y funcionalidades**, localizando las extensiones en capas de mapeo, análisis o post-procesado sin rediseñar el núcleo.
3. **Evolución de versiones de OpenQASM** (incluido OpenQASM 3.0), reutilizando íntegramente el análisis y la expansión de abstracciones a través de un nuevo generador aislado.
4. **Nuevos ecosistemas destino**, aprovechando OpenQASM 2.0 como representación intermedia estable y desacoplando los consumidores del formato Quirk.

Este enfoque posiciona al proyecto como una solución preparada para evolucionar conforme avanza el ecosistema de computación cuántica, preservando al mismo tiempo estabilidad, mantenibilidad y fidelidad semántica.
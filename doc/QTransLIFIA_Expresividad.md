# QTransLIFIA - Expresividad

## 1. Introducción

La expresividad de QTransLIFIA hace referencia a su capacidad para **conservar el poder expresivo con el que el usuario diseñó el circuito** en la herramienta de partida (Quirk) y trasladarlo sin pérdida a la representación intermedia OpenQASM y, desde allí, al ecosistema destino seleccionado (Qiskit, AWS Braket, PennyLane).

El aspecto central de esta expresividad es la **conservación funcional de las compuertas definibles en Quirk**. Quirk no solo ofrece compuertas nativas: permite al usuario **definir sus propias compuertas** (a partir de un circuito interno o de una matriz), componiendo nuevas abstracciones sobre el lenguaje visual de la herramienta. QTransLIFIA respeta ese punto de partida de diseño: no trata esas compuertas como un detalle visual efímero, sino como **entidades funcionales que deben sobrevivir a la traducción**. Solo así el circuito diseñado sigue siendo *admisible* por OpenQASM y por el ecosistema destino, con la misma intención algorítmica con la que fue concebido.

## 2. Expresividad como Atributo de Calidad

- **Expresividad del origen**: la capacidad de Quirk de expresar algoritmos mediante compuertas nativas, compuertas parametrizadas y compuertas definidas por el usuario (vía `circuit.cols` o vía `matrix`).
- **Expresividad conservada**: la capacidad del traductor de preservar íntegramente esa expresividad al migrar el circuito, sin aplanar ni descartar las abstracciones definidas.
- **Expresividad trasladada**: la capacidad del OpenQASM generado —y consecuentemente del ecosistema destino— de *recibir y admitir* esas compuertas, ya sea manteniendo su estructura declarativa o garantizando su equivalencia funcional.

## 3. El Punto de Partida de Diseño en Quirk

En Quirk el diseño comienza en una matriz visual de columnas (`circuit.cols`). Sobre esa base, la herramienta habilita **dos vías para definir compuertas propias**, ambas presentes en el JSON embebido en la URL:

1. **Compuertas por circuito** (`={"id":"~rvcr","name":"MultiX","circuit":{"cols":[["•","•","X","•"]]}}`): una compuerta compuesta por columnas internas que reutilizan otras compuertas (nativas o previamente definidas).
2. **Compuertas por matriz** (`matrix`): una compuerta definida directamente por su matriz unitaria.

Estas definiciones constituyen el **lenguaje expresivo del diseñador**: la forma en que el usuario estructura un algoritmo en bloques reutilizables. QTransLIFIA reconoce esta intención y la eleva a ciudadano de primera clase del proceso de traducción.

## 4. Conservación Funcional de las Compuertas Definibles en Quirk

### 4.1 Resolución por `id` y `name`

`_build_gate_map` (`utils/qutils.py:21`) construye un mapa de puertas que resuelve cada definición tanto por su identificador (`id`) como por su nombre (`name`). Esto garantiza que toda compuerta definible en Quirk sea **reconocida y resuelta** sin importar la forma en que sea referenciada en las columnas del circuito.

### 4.2 Conservación de compuertas definidas por circuito

Las compuertas definidas mediante `circuit.cols` se traducen como **declaraciones `gate` de OpenQASM** (`append_custom_gates`, `utils/qutils.py:573`): el cuerpo interno de la compuerta se deriva de sus columnas y se mantiene su estructura, en lugar de expandirse y desaparecer. Esto significa que:

- La **abstracción del usuario se conserva** en el OpenQASM generado (módulo reutilizable, no una secuencia aplanada).
- Cada **instancia** de la compuerta en el circuito queda referenciada por el identificador resuelto (`_resolve_gate_names`, `utils/qutils.py:108`), y la declaración y sus llamadas **coinciden siempre**.
- El elemento se mantiene **trasladable y reutilizable** fuera de Quirk, en todos los ecosistemas que admiten declaraciones `gate`.

### 4.3 Conservación de compuertas definidas por matriz

Las compuertas definidas por `matrix` se convierten en su **operación OpenQASM equivalente** (`_matrix_gate_operation`/`_resolve_matrix_operation`, p. ej. `U(-pi/2)` → `p(-pi/2)`), asegurando que la compuerta ingresada por la vía matricial mantiene su comportamiento funcional. De este modo, ninguna vía de definición de Quirk queda fuera del alcance del traductor.

### 4.4 Composición y anidamiento

- Las compuertas pueden **componerse jerárquicamente**: una compuerta definida puede contener otras compuertas definidas, con un límite de profundidad de anidamiento (≤ 10) como salvaguarda de robustez.
- Las instancias multi-columna de una misma definición se desambiguan mediante el sufijo `:k` (p. ej. `~abc:1`), preservando su **contexto de uso** dentro del circuito.
- El **orden de las declaraciones** se resuelve topológicamente para respetar la regla de OpenQASM *"declarar antes de usar"*, incluso ante referencias anidadas entre compuertas (`append_custom_gates`, `utils/qutils.py:625-654`).

## 5. Traslación a OpenQASM

- Los `n_qubits` efectivos de cada compuerta definida se calculan con `_gate_height` (altura por circuito o por dimensión de la matriz), garantizando que la declaración `gate <nombre> (#qubits) { ... }` tenga la aridad correcta.
- Los **nombres se sanitizan** (`_sanitize_gate_name`, `utils/qutils.py:93`) para ser identificadores OpenQASM válidos, evitando colisiones con palabras reservadas y con los gates estándar.
- El circuito queda expresado tanto por sus **compuertas definidas** (declaradas) como por sus **compuertas usadas** (llamadas), de modo que el OpenQASM generado es una representación **fiel y admisible** del diseño original.

En la versión OpenQASM 2.0, el transpilado intermedio (`qasm3_to_qasm2`, `utils/qutils.py:703`) reduce el circuito a `u1/u2/u3/cx` conservando la **equivalencia funcional** de cada compuerta definida mediante transpilación Qiskit a nivel de optimización 0; en OpenQASM 3.0 (versión por defecto), además, se preserva la **estructura declarativa** de las propias compuertas.

## 6. Admisibilidad en el Ecosistema Destino

La conservación funcional tiene un objetivo concreto: que la compuerta definible en Quirk sea **admisible por el ecosistema destino**, no solo por OpenQASM.

- **OpenQASM como IR admisible**: el OpenQASM generado (2.0 o 3.0 según `QASM_VERSION`) es consumible por parsers, simuladores y transpiladores estándar.
- **Qiskit / AWS Braket / PennyLane**: `provider_python_source` (`utils/qutils.py:716`) importa el circuito (`qasm2.loads`/`qasm3.loads`) y genera scripts Python para cada provider. Las compuertas definidas por el usuario son re-creadas en el SDK destino (p. ej. `CustomGate`/`UGate` controlado) o descompuestas a puertas nativas por el propio SDK, manteniendo la semántica.
- **Herramientas de verificación**: el grafo ZX derivado del OpenQASM (`qasm_to_zx_graph`, `utils/qutils.py:1506`) también admite declaraciones `gate`, por lo que la conservación puede comprobarse en término de equivalencia semántica.
- **Multi-destino**: un único circuito puede migrarse una vez a OpenQASM y distribuirse a varios ecosistemas, lo cual hace que la expresividad conservada rinda en todos los destinos simultáneamente.

## 7. Verificación de la Conservación Expresiva

La conservación no se asume: se comprueba. La preservación funcional de las compuertas definidas se valida mediante:

- **Inspección estructurada**: `quirk_circuit_info` expone `custom_gates`, `custom_gate_ids`, `custom_gate_names`, `custom_gates_gates` y `custom_gates_info`, permitiendo auditar que toda compuerta definida fue considerada y mapeada (ver `doc/QTransLIFIA_Verificabilidad.md`).
- **Estrategias de comprobación**: verificación estática por características, equivalencia por cálculo ZX y comprobación visual rápida (ver `doc/QTransLIFIA_Testing.md`).
- **Round-trip**: re-encodeo de la URL con `encode_quirk_url` y re-apertura en Quirk, confirmando que el punto de partida de diseño permanece íntegro.

## 8. Conclusión

QTransLIFIA coloca la **expresividad** definida en Quirk en el centro de su filosofía de traducción. Al conservar funcionalmente las compuertas definibles por el usuario —tanto las definidas por circuito como por matriz—, el traductor:

1. **Respeta el punto de partida de diseño** de la herramienta: las abstracciones que el usuario creó en Quirk son tratadas como entidades funcionales, no como ruido visual.
2. **Traslada esa expresividad a OpenQASM**: las compuertas se declaran y referencian de forma válida y ordenada en el IR.
3. **La hace admisible por el ecosistema destino**: cada compuerta definida llega a Qiskit, AWS Braket o PennyLane con su semántica intacta o reducida a primitivas equivalentes.

El resultado es una migración que preserva la **intención algorítmica del diseño**, cumpliendo con la premisa del proyecto: lo que el usuario diseñó en Quirk es lo que efectivamente se traduce, se ejecuta y se comprueba en cualquiera de los ecosistemas destino.
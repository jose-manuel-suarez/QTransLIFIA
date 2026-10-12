# QTransLIFIA - Calidad y Atributos desde la Perspectiva QSE

Este documento reúne los seis informes que describen las **características y cualidades** de QTransLIFIA desde la perspectiva de la **Ingeniería de Software Cuántica** (*Quantum Software Engineering*, QSE). Cada informe aborda un atributo de calidad del proyecto y cómo se materializa en la arquitectura, la lógica de traducción y los mecanismos de comprobación.

| # | Atributo | Documento | Resumen |
| --- | --- | --- | --- |
| 1 | Abstracción | [`QTransLIFIA_Abstraccion.md`](QTransLIFIA_Abstraccion.md) | Traducción semántica con preservación de *custom gates*, separación de dominios y separación entre análisis y generación. |
| 2 | Expresividad | [`QTransLIFIA_Expresividad.md`](QTransLIFIA_Expresividad.md) | Conservación funcional de las compuertas definibles en Quirk, respetando el punto de partida de diseño y haciéndolo admisible por OpenQASM y el ecosistema destino. |
| 3 | Verificabilidad | [`QTransLIFIA_Verificabilidad.md`](QTransLIFIA_Verificabilidad.md) | Equivalencia estructural y funcional entre el circuito de Quirk y el OpenQASM generado, con fundamentos V&V desde la perspectiva QSE en etapas iniciales. |
| 4 | Testing | [`QTransLIFIA_Testing.md`](QTransLIFIA_Testing.md) | Estrategias de comprobación de cada paso del flujo: verificación estática por características, equivalencia mediante cálculo ZX y comprobación visual rápida. |
| 5 | Escalabilidad | [`QTransLIFIA_Escalabilidad.md`](QTransLIFIA_Escalabilidad.md) | Crecimiento vertical (complejidad del circuito) y horizontal (múltiples ecosistemas destino) sobre OpenQASM como interfaz estable. |
| 6 | Extensibilidad | [`QTransLIFIA_Extensibilidad.md`](QTransLIFIA_Extensibilidad.md) | Adaptación a nuevas compuertas, nuevas versiones de OpenQASM y nuevos consumidores sin rediseñar el núcleo de traducción. |

## Cómo se integran

- **Expresividad** y **Abstracción** definen *qué* se conserva: la intención algorítmica y las compuertas definidas por el usuario en Quirk.
- **Verificabilidad** y **Testing** garantizan *cómo se comprueba*: equivalencia estructural/estática, semántica por ZX y comprobación visual, con pruebas automatizadas.
- **Escalabilidad** y **Extensibilidad** aseguran *hasta dónde puede crecer*: más qubits, jerarquías más profundas y nuevos ecosistemas destino sin reescribir el núcleo.

Conjuntamente, estos documentos sustentan la premisa central del proyecto: **el circuito que el usuario diseñó en Quirk es el circuito que se traduce, se verifica y se ejecuta** en cualquier ecosistema destino.
# Resultados de equivalencia Quirk vs OpenQASM (ZX-Calculus)

Total de circuitos analizados: 2 (0 comparados, 2 no comparables).

| Nombre algoritmo | Cúbits | Método | Resultado | Motivo |
| --- | :-: | --- | --- | --- |
| 1__complex_customs | 2 | sin grafo | NO COMPARABLES | Matriz no soportada en el grafo ZX (se esperaba 2x2): mia |
| 2__rotational_customs | 2 | sin grafo | NO COMPARABLES | Matriz no soportada en el grafo ZX (se esperaba 2x2): 4x4 |

## Leyenda

| Estado | Circuitos | Significado |
| --- | :-: | --- |
| EQUIVALENTES | 0 | Los grafos ZX del circuito de Quirk y del OpenQASM generado son equivalentes (salvo fase global). |
| NO EQUIVALENTES | 0 | Los grafos ZX son distintos: la traducción no conserva la acción unitaria del circuito original. |
| NO COMPARABLES | 2 | No se pudo establecer la equivalencia (el grafo ZX no es construible o la comparación no está definida); el motivo figura en la columna «Motivo». |
| NO DEMOSTRADO | 0 | La comparación excedió el límite de tiempo configurado y no pudo completarse. |
| ERROR | 0 | Excepción durante la comparación; el motivo figura en la columna «Motivo». |

### Motivos de no comparabilidad

| Motivo | Circuitos |
| --- | :-: |
| Matriz no soportada en el grafo ZX (se esperaba 2x2): 4x4 | 1 |
| Matriz no soportada en el grafo ZX (se esperaba 2x2): mia | 1 |

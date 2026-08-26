# QTransLIFIA — Contexto persistente

> Este archivo se carga automáticamente en cada sesión del agente. Equivale a `MUSE.md` (Claude), `.cursor/rules` (Cursor) o `AGENTS.md` (Codex/opencode). Si tu herramienta usa otro nombre, duplica este archivo como `MUSE.md`.

## Qué es
Traductor de circuitos cuánticos de formato **Quirk** (`https://algassert.com/quirk#circuit=...`) a **OpenQASM 2.0 

## Estructura
- `utils/qutils.py` — lógica central: `parse_quirk_url:5`, `encode_quirk_url:9`, `_build_gate_map:18`, `_gate_height:35`, `quirk_col_to_qasm:50`, `_col_to_qasm_with_gates:142`, `quirk_to_qasm:201`, `quirk_circuit_info:237`

## Reglas de traducción
- `offset` desplaza todos los índices `q[i+offset]`; `n = max(len(col))+offset` ajustado por altura de custom gates (`utils/qutils.py:201-230`).
- `•`+`X`/`Z`/`Y` → `cx`/`cz`/`cy` (1 control), `ccx` (2), `Swap` → `swap`. `X^½` etc → `rx`/`ry`/`s`/`t`.
- Campo `gates` en la URL:
  - `{"id":"~rvcr","name":"MultiX","circuit":{"cols":[["•","•","X","•"]]}}` → expandible. Mapa por `id` y `name`, sufijo `:k` para gates multi-columna (`~abc:1`). Soporta anidamiento (profundidad ≤10).
- URLs Quirk requieren JSON estricto con `"` dobles; para `href` usar `encode_quirk_url`.

## `quirk_circuit_info(url)`
Retorna `{n_qubits, n_cols, gates, custom_gates, custom_gate_ids, custom_gate_names, n_custom_gates, custom_gates_gates, custom_gates_info}`. `n_qubits` es efectivo (incluye altura de gates usados).

## Entorno
- Windows + PowerShell 5.1; usar `curl.exe` no `curl`; evitar `python -c` con JSON complejo → scripts `.py` temporales.
- Venv: `.venv/Scripts/python.exe` (Python 3.12). Consola `cp1252` → `•`/`½` mostrarán `�` pero el logic funciona (UTF-8 en disco).

## Tests

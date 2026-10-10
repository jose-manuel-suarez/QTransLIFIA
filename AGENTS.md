# QTransLIFIA — Contexto persistente

> Este archivo se carga automáticamente en cada sesión del agente. Equivale a `MUSE.md` (Claude), `.cursor/rules` (Cursor) o `AGENTS.md` (Codex/opencode). Si tu herramienta usa otro nombre, duplica este archivo como `MUSE.md`.

## Qué es
Traductor de circuitos cuánticos de formato **Quirk** (`https://algassert.com/quirk#circuit=...`) a **OpenQASM 2.0 

## Estructura
- `utils/qutils.py` — lógica central: `parse_quirk_url:10`, `encode_quirk_url:13`, `_build_gate_map:21`, `_gate_height:35`, `quirk_col_to_qasm:401`, `_col_to_qasm_with_gates:494`, `quirk_to_qasm:663`, `qasm3_to_qasm2:703`, `provider_python_source:716`, `quirk_circuit_info:1080`, `qasm_to_zx_graph:1467`, `_zx_gate_matrix:1271`.

## Reglas de traducción
- `offset` desplaza todos los índices `q[i+offset]`; `n = max(len(col))+offset` ajustado por altura de custom gates (`utils/qutils.py:201-230`).
- `•`+`X`/`Z`/`Y` → `cx`/`cz`/`cy` (1 control), `ccx` (2), `Swap` → `swap`. `X^½` etc → `rx`/`ry`/`s`/`t`.
- Campo `gates` en la URL:
  - `{"id":"~rvcr","name":"MultiX","circuit":{"cols":[["•","•","X","•"]]}}` → expandible. Mapa por `id` y `name`, sufijo `:k` para gates multi-columna (`~abc:1`). Soporta anidamiento (profundidad ≤10).
- URLs Quirk requieren JSON estricto con `"` dobles; para `href` usar `encode_quirk_url`.
- Versión: `quirk_to_qasm(url, offset, qasm_version='3.0')` acepta `'2.0'`/`'3.0'`; `'2.0'` transpila vía Qiskit a `u1/u2/u3/cx`. La celda de generación y las celdas de migración leen `QASM_VERSION` desde `.env` (`QTRANS_QASM_VERSION`, default `'3.0'`) con `load_dotenv()`; la celda de generación escribe `_v2.0.txt`/`_v3.0.txt` y las celdas posteriores quitan el sufijo con `strip_qasm_version`.
- Celdas de migración (Qiskit, AWS Braket «`aws_braket`», PennyLane): parametrizadas por `QASM_VERSION` (`os.getenv("QTRANS_QASM_VERSION") or globals().get('QASM_VERSION') or '3.0'`; `ValueError` si no es `'2.0'|'3.0'`), `QASM_VERSION_SUFFIX = f'_v{QASM_VERSION}'`, filtran estrictamente `path.name.endswith(suffix + ".txt")` y definen una `load_qasm_circuit(text)` local (dispatch por cabecera `OPENQASM 2.0` → `QuantumCircuit.from_qasm_str`, `3.0` → `qasm3.loads`, fallback). No usar `qasm3.loads` directo sobre `_v2.0.txt` (falla con `QASM3ImporterError: '2,0: non-stdgates imports not currently supported'`). El generador Qiskit además mapea `u1/u2/u3` a puertas nativas (`native_gate_for_u`: h/x/y/z/s/sdg/t/tdg/sx/id) para no emitir `circuit.u(...)` en gates estándar.
- Puertas en los generadores de migración: `u1/u2/u3` (u2 lleva 2 params φ,λ: `lam = parameters[2] if name=="u3" else (parameters[1] if name=="u2" else parameters[0])`); ángulos fijos `rx_*/ry_*/rz_*` y fases fijas `cp_*/cu1_*` (incl. fracciones `_pi_`, p.ej. `cU_pi_2`, `cp_7_pi_8`) vía helpers `parse_fixed_angle`/`fixed_rotation_re`/`fixed_phase_re`; Qiskit usa `PhaseGate`/`UGate` (imports dinámicos `gate_imports` from `qiskit.circuit.library`) para `.control(k)`.
- Última celda del notebook: utilidad `mostrar_url_quirk(url)`/`formatear_url_quirk(url)`/`limpiar_url_quirk(url)` — recibe **directamente la URL cruda** de Quirk (con `circuit=<JSON>`, p.ej. `url_quirk_cruda`) aunque venga **mal formateada** (con `\` y `\"` sobrantes al pegar el JSON): `limpiar_url_quirk` quita comillas externas, desescapa `\"`/`\'`, elimina backslashes sobrantes y recorta desde `https://`; luego `encode_quirk_url` percent-encodea para que renderice en algassert.com/quirk. Devuelve/muestra un enlace `<a ...>Abrir en Quirk</a>` y valida round-trip (`parse_quirk_url` + `quirk_circuit_info`). En el JSON el `•` es U+2022 real.
- `qasm_to_zx_graph` admite gates con parámetros `rx/ry/rz/p/u1/u2/u3/u` y declaraciones `qreg` (QASM 2.0) o `qubit` (QASM 3.0).

## `quirk_circuit_info(url)`
Retorna `{n_qubits, n_cols, gates, custom_gates, custom_gate_ids, custom_gate_names, n_custom_gates, custom_gates_gates, custom_gates_info}`. `n_qubits` es efectivo (incluye altura de gates usados).

## Entorno
- Windows + PowerShell 5.1; usar `curl.exe` no `curl`; evitar `python -c` con JSON complejo → scripts `.py` temporales.
- Venv: `.venv/Scripts/python.exe` (Python 3.12). Consola `cp1252` → `•`/`½` mostrarán `�` pero el logic funciona (UTF-8 en disco).

## Tests

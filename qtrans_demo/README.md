# qtrans_demo

Subproyecto aislado para probar la librería `qtranslifia` instalada desde PyPI, sin depender del código fuente de QTransLIFIA.

## Puesta en marcha

```bash
cd qtrans_demo
python -m venv demo_venv
source demo_venv/Scripts/activate
python -m pip install -r requirements.txt
python main.py
```

En Linux/macOS, activá con `source demo_venv/bin/activate`.

## Qué hace

- Lee `input/custom_gates_algorithms.json`.
- Traduce los circuitos con `qtrans.translate_circuit`.
- Simula cada circuito Qiskit con 1024 shots.
- Guarda QASM, scripts migrados y conteos en `output/`.

La configuración se toma de `.env`. `main.py` verifica que se ejecute con `demo_venv` y que `qtrans` se importe desde ese entorno, nunca desde el repositorio.

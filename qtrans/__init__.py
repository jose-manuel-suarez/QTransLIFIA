"""QTransLIFIA: traducción de circuitos Quirk a OpenQASM y migración a Qiskit, AWS Braket y PennyLane.

API pública:
    - ``translate_circuit``: traduce circuitos desde un payload JSON (single o lote).
    - ``run_pipeline``: ejecuta el pipeline completo sobre un directorio de entrada.
    - ``main``: punto de entrada de la CLI (``qtrans``).
"""

from .core import main, run_pipeline, translate_circuit

__all__ = ["translate_circuit", "run_pipeline", "main"]
__version__ = "0.1.0"

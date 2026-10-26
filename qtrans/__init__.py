"""QTransLIFIA: traducción de circuitos Quirk a OpenQASM y migración a Qiskit, AWS Braket y PennyLane.

API pública:
    - ``translate_circuit``: traduce circuitos desde un payload JSON (single o lote).
    - ``translate_circuits``: igual que ``translate_circuit``, pero devuelve los circuitos
      nativos de cada proveedor ya cargados (objetos vivos, no serializables a JSON).
    - ``run_pipeline``: ejecuta el pipeline completo sobre un directorio de entrada.
    - ``main``: punto de entrada de la CLI (``qtrans``).
"""

from .core import main, run_pipeline, translate_circuit, translate_circuits

__all__ = ["translate_circuit", "translate_circuits", "run_pipeline", "main"]
__version__ = "0.2.0"

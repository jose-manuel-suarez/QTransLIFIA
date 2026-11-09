"""QTransLIFIA: traducción de circuitos Quirk a OpenQASM y migración a Qiskit, AWS Braket y PennyLane.

API pública:
    - ``translate_circuit``: traduce circuitos desde un payload JSON (single o lote).
"""

from .core import translate_circuit

__all__ = [
    "translate_circuit",
]
__version__ = "0.3.0"

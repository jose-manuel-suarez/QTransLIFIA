"""Prueba manual de la API ``translate_circuit``: imprime el JSON de salida en consola.

Ejecución (desde cualquier directorio):

    python test/test_translate_lib.py

El circuito de ``INPUT_PAYLOAD`` es el primer registro de ``input/main_algorithms.json``
(algoritmo de Shor, 4 qubits). Editar la variable para probar otros circuitos, o
``python -m unittest discover`` no lo ejecuta (no define TestCase; solo imprime
cuando se corre como script).

Nota: en consolas Windows con codificación cp1252 el carácter ``•`` puede verse
como ``?``; el JSON impreso es correcto (UTF-8).
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qtrans import translate_circuit


TEST_ALGORITHM_URL = (
    "https://algassert.com/quirk#circuit="
    '{"cols":[["H","H","H","H"],["X"],["X","X","X","X"],'
    '[1,"•","X"],[1,"X","•"],[1,"•","X"],[1,1,"•","X"],'
    '[1,1,"X","•"],[1,1,"•","X"],["•",1,1,"X"],'
    '["X",1,1,"•"],["•",1,1,"X"],'
    '["Measure","Measure","Measure","Measure"]]}'
)

INPUT_PAYLOAD = {
    "input": {
        "url": TEST_ALGORITHM_URL,
        "offset": 0,
    }
}


def main():
    """Traduce ``INPUT_PAYLOAD`` y muestra el JSON de salida completo por consola.

    Retorna:
        - dict: la respuesta de ``translate_circuit`` (``{"input": ..., "output": ...}``).
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    result = translate_circuit(INPUT_PAYLOAD)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()

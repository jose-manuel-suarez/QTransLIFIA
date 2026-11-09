"""Utilidades genéricas de la librería (sin dependencias entre módulos).

Ayudas compartidas por el orquestador (``qtrans.core``) y por los módulos de
proveedor y de ZX: impresión segura, log por etapas y claves de orden natural
para los nombres de algoritmo.
"""

import re
import sys

_RUN_LABEL_TOKEN_RE = re.compile(r"YYYY|DD|HH|SS|MM")


def safe_print(message):
    """Imprime un texto sin abortar la etapa por caracteres no codificables.

    La consola de Windows usa ``cp1252``, que no puede representar todos los
    símbolos de Quirk (``⟩``, ``⟨``, ``†``…). En lugar de propagar un
    ``UnicodeEncodeError`` que cancela la etapa que informa del error, el
    carácter problemático se sustituye por ``?``.

    Parámetros:
        - message (str): texto a imprimir.

    Retorna:
        - None
    """
    text = str(message)
    try:
        print(text)
        return
    except UnicodeEncodeError:
        pass
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))


def log_stage(verbose, step, message):
    """Imprime un mensaje de etapa del pipeline si ``verbose`` está activo.

    Parámetros:
        - verbose (bool): si es False no imprime nada.
        - step (str): nombre de la etapa (p. ej. 'ZX', 'Migración').
        - message (str): mensaje a mostrar.

    Retorna:
        - None
    """
    if verbose:
        safe_print(f"[{step}] {message}")


def algorithm_sort_key(name):
    """Clave de orden natural ascendente para nombres tipo '10__QAOA'.

    Parámetros:
        - name (str): nombre del algoritmo.

    Retorna:
        - list: lista de pieces comparables (enteros y textos en minúsculas).
    """
    parts = re.split(r"(\d+)", str(name))
    return [int(part) if part.isdigit() else part.casefold() for part in parts]

"""Utilidades genéricas del pipeline (sin dependencias entre módulos).

Ayudas compartidas por el orquestador (``qtrans.core``) y por los módulos de
proveedor y de ZX: log por etapas, formato de la etiqueta de corrida, claves de
orden natural para los nombres de algoritmo y saneado de nombres de archivo.
"""

import re
import sys
from datetime import datetime
from pathlib import Path

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


def format_run_label(label, now=None):
    """Resuelve los tokens DD/MM/YYYY/HH/MM/SS de una etiqueta con datos reales.

    ``MM`` se interpreta como mes tras DD/YYYY y como minutos tras HH.

    Parámetros:
        - label (str): etiqueta con los tokens.
        - now (datetime | None): fecha de referencia (opcional).

    Retorna:
        - str: la etiqueta con los tokens ya resueltos.
    """
    now = now or datetime.now()
    result = []
    position = 0
    last_token = None
    for match in _RUN_LABEL_TOKEN_RE.finditer(label):
        result.append(label[position:match.start()])
        token = match.group()
        if token == "YYYY":
            value = now.strftime("%Y")
        elif token == "DD":
            value = now.strftime("%d")
        elif token == "HH":
            value = now.strftime("%H")
        elif token == "SS":
            value = now.strftime("%S")
        else:  # MM
            value = now.strftime("%M") if last_token == "HH" else now.strftime("%m")
        result.append(value)
        last_token = token
        position = match.end()
    result.append(label[position:])
    return "".join(result)


def algorithm_sort_key(name):
    """Clave de orden natural ascendente para nombres tipo '10__QAOA'.

    Parámetros:
        - name (str): nombre del algoritmo.

    Retorna:
        - list: lista de pieces comparables (enteros y textos en minúsculas).
    """
    parts = re.split(r"(\d+)", str(name))
    return [int(part) if part.isdigit() else part.casefold() for part in parts]


def safe_algorithm_name(name):
    """Convierte un nombre de algoritmo en un nombre de archivo seguro.

    Parámetros:
        - name (str): nombre original del algoritmo.

    Retorna:
        - str: nombre sin caracteres problemáticos (puede quedar vacío).
    """
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(name).replace(".", "_"))
    return safe_name.strip("_")


def resolve_run_path(value, run_dir, default_subdir):
    """Resuelve la ruta de una subcarpeta de la corrida.

    Parámetros:
        - value (str | Path | None): ruta explícita (si se da, gana).
        - run_dir (str | Path): carpeta raíz de la corrida.
        - default_subdir (str): subcarpeta relativa por defecto.

    Retorna:
        - pathlib.Path: ruta absoluta resuelta.
    """
    if value is not None:
        return Path(value).expanduser().resolve()
    return (Path(run_dir) / default_subdir).resolve()

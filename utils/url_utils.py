# -*- coding: utf-8 -*-
"""Utilidades de URLs de Quirk y extracción desde la colección Postman.

- `parse_quirk_url(url)` extrae y evalúa el JSON embebido en una URL de Quirk.
- `encode_quirk_url(url)` percent-encodea el `circuit=` para usarla como `href`.
- `main()` recorre la colección Postman del proyecto y escribe `quirks_urls.txt`.

Se importa como ``from utils.url_utils import parse_quirk_url, encode_quirk_url``.
"""

import ast
import json
import os
from urllib.parse import unquote, quote

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_quirk_url(url):
    """Extrae y evalúa el JSON embebido en la URL de Quirk.

    Parámetros:
        - url (str): URL de Quirk con ``circuit=<JSON>`` (acepta percent-encoding).

    Retorna:
        - dict: el circuito parseado (p. ej. ``{'cols': [...], 'gates': [...]}``).
    """
    return ast.literal_eval(unquote(url).split('circuit=')[1])


def encode_quirk_url(url):
    """Percent-encodea el ``circuit=`` de una URL de Quirk para usarla como ``href``.

    Parámetros:
        - url (str): URL de Quirk con ``circuit=<JSON>`` (puede venir sin codificar).

    Retorna:
        - str: URL con el JSON percent-encodeado; la URL original si el parseo falla.
    """
    try:
        circuit_json = unquote(url).split('circuit=')[1]
        encoded = quote(circuit_json, safe='')
        return url.split('circuit=')[0] + 'circuit=' + encoded
    except Exception:
        return url


def main():
    """Extrae las URLs Quirk de la colección Postman del proyecto a quirks_urls.txt.

    Recorre todos los requests de la colección, reconstruye la URL de cada
    circuito (``algassert.com/quirk#circuit=...``) y escribe el listado
    formateado (nombre, endpoint y URL) en quirks_urls.txt en la raíz.

    Retorna:
        - None: imprime el total de entradas escribidas.
    """
    with open(os.path.join(BASE, 'postman', 'Quirk_Translator_IBM_AWS.postman_collection_original.json'), encoding='utf-8') as f:
        data = json.load(f)

    results = []

    for group in data['item']:
        for sub in group['item']:
            raw = sub['request']['body']['raw']
            body = json.loads(raw)
            endpoint = sub['request']['url']['raw']
            prefix = f"{group['name']} / {sub['name']}"
            n = 0
            for k, v in body.items():
                if isinstance(v, str) and 'algassert.com' in v:
                    circuit = v.split('circuit=')[1]
                    url = f"https://algassert.com/quirk#circuit={circuit}"
                    name = f"{prefix} [{k}]" if len([x for x in body.values() if isinstance(x, str) and 'algassert.com' in x]) > 1 else prefix
                    results.append((name, endpoint, url))
                    n += 1

    with open(os.path.join(BASE, 'quirks_urls.txt'), 'w', encoding='utf-8') as f:
        for i, (name, endpoint, url) in enumerate(results, 1):
            f.write(f"{i:2d}. {name}\n")
            f.write(f"    POST {endpoint}\n")
            f.write(f"    {url}\n\n")

    print(f"Total: {len(results)} entradas")


if __name__ == '__main__':
    main()

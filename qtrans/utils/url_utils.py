# -*- coding: utf-8 -*-
r"""Utilidades de URLs de Quirk y extracción desde la colección Postman.

- `parse_quirk_url(url)` extrae y evalúa el JSON embebido en una URL de Quirk.
- `canonicalize_quirk_url(url)` reescribe la QFT inversa a la forma canónica
  `QFT†n` que Quirk reconoce (las variantes `QFTn†`/`QFT^†n` pintan una
  compuerta "parse error" en Quirk).
- `normalize_quirk_url(url)` normaliza una URL pegada a mano (comillas y
  backslashes de más) a un JSON estricto canónico, sin perder los escapes
  `\uXXXX` de las compuertas Unicode.
- `encode_quirk_url(url)` percent-encodea el `circuit=` para usarla como `href`.
- `main()` recorre la colección Postman del proyecto y escribe `quirks_urls.txt`.

Se importa como ``from qtrans.utils.url_utils import parse_quirk_url, encode_quirk_url``.
"""

import ast
import json
import os
import re
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


# Ids de QFT aceptados por Quirk: 'QFT<n>' y, para la inversa, 'QFT†<n>'
# (FourierTransformGates.js: setSerializedId("QFT†" + span)). Las variantes
# 'QFT<n>†' y 'QFT^†<n>' no existen en Quirk y producen una compuerta "parse error".
_QFT_CELL_RE = re.compile(r'^QFT(?:\^?†)?(\d+)(?:\^?†)?$')


def _canonical_qft_cell(value):
    """Devuelve la forma canónica de una celda QFT si debe corregirse.

    Parámetros:
        - value: celda de columna (str u otro tipo).

    Retorna:
        - str | None: el id canónico de Quirk ('QFT†n' / 'QFTn') si value es una
          variante no soportada por Quirk; None si no es una celda QFT o si ya
          es canónica.
    """
    if not isinstance(value, str):
        return None
    match = _QFT_CELL_RE.match(value)
    if match is None:
        return None
    span = int(match.group(1))
    if span < 1:
        return None
    canonical = f'QFT†{span}' if '†' in value else f'QFT{span}'
    return canonical if canonical != value else None


def _canonicalize_qft_in_place(node):
    """Reescribe in situ las celdas QFT no canónicas de un circuito Quirk.

    Recorre ``cols`` (incluidas las de los circuitos anidados en ``gates``)
    y normaliza las variantes de la QFT inversa a ``QFT†n``.

    Parámetros:
        - node (dict | list | str | int): estructura JSON-like del circuito.

    Retorna:
        - bool: True si se reescribió alguna celda.
    """
    changed = False
    if isinstance(node, dict):
        cols = node.get('cols')
        if isinstance(cols, list):
            for col in cols:
                if isinstance(col, list):
                    for index, cell in enumerate(col):
                        canonical = _canonical_qft_cell(cell)
                        if canonical is not None:
                            col[index] = canonical
                            changed = True
        for value in node.values():
            if isinstance(value, (dict, list)) and _canonicalize_qft_in_place(value):
                changed = True
    elif isinstance(node, list):
        for value in node:
            if isinstance(value, (dict, list)) and _canonicalize_qft_in_place(value):
                changed = True
    return changed


def _canonicalize_circuit_json(circuit_text):
    """Canoniza la QFT inversa del JSON ``circuit=`` de una URL de Quirk.

    Parámetros:
        - circuit_text (str): JSON del circuito ya decodificado.

    Retorna:
        - str | None: el JSON canónico (JSON estricto con comillas dobles y
          ASCII, apto para Quirk) si hubo cambios; None si no se pudo parsear
          o no había nada que corregir.
    """
    try:
        circuit = json.loads(circuit_text)
    except Exception:
        try:
            circuit = ast.literal_eval(circuit_text)
        except Exception:
            return None
    if not isinstance(circuit, dict) or not _canonicalize_qft_in_place(circuit):
        return None
    return json.dumps(circuit, ensure_ascii=True, separators=(',', ':'))


def canonicalize_quirk_url(url):
    """Reescribe una URL de Quirk a la forma canónica de la QFT inversa.

    Quirk solo reconoce la QFT inversa con el id ``QFT†<n>``; una URL con
    ``QFT<n>†`` o ``QFT^†<n>`` hace que Quirk pinte una compuerta "parse error"
    en lugar de la QFT inversa. Si no hay nada que corregir (o el JSON del
    circuito no se puede parsear) se devuelve la URL original intacta.

    Parámetros:
        - url (str): URL de Quirk con ``circuit=<JSON>`` (cruda o percent-encodeada).

    Retorna:
        - str: URL con el id de QFT inversa canónico; la original si no hubo cambios.
    """
    try:
        head, fragment = url.split('circuit=', 1)
    except (AttributeError, ValueError):
        return url
    was_encoded = unquote(fragment) != fragment
    canonical_text = _canonicalize_circuit_json(unquote(fragment))
    if canonical_text is None:
        return url
    if was_encoded:
        return head + 'circuit=' + quote(canonical_text, safe='')
    return head + 'circuit=' + canonical_text


def _loads_circuit(text):
    """Parsea el JSON del circuito de una URL de Quirk.

    Acepta JSON estricto (comillas dobles) y, como respaldo, literales de
    Python (comillas simples), que es lo que se obtiene al copiar una URL
    desde un archivo JSON del proyecto.

    Parámetros:
        - text (str): texto del JSON del circuito.

    Retorna:
        - dict | None: el circuito parseado; None si no se pudo parsear.
    """
    for loader in (json.loads, ast.literal_eval):
        try:
            value = loader(text)
        except Exception:
            continue
        if isinstance(value, dict):
            return value
    return None


def _circuit_text_variants(fragment):
    """Variantes del fragmento ``circuit=`` que se intentan parsear.

    Cubre el pegado manual de una URL: JSON con comillas escapadas (``\\"``),
    con comillas simples y con backslashes de más.

    Parámetros:
        - fragment (str): fragmento ``circuit=`` ya des-percent-encoded.

    Yields:
        - str: variante del fragmento a parsear.
    """
    yield fragment
    unescaped = fragment.replace('\\"', '"').replace("\\'", "'")
    if unescaped != fragment:
        yield unescaped
    plain = unescaped.replace('\\', '')
    if plain != unescaped:
        yield plain


def normalize_quirk_url(url):
    r"""Normaliza una URL de Quirk a un JSON estricto canónico.

    Extrae el JSON del circuito, lo interpreta (respetando los escapes
    ``\\uXXXX``) y lo vuelve a serializar en JSON estricto y ASCII, de modo que
    la URL sirva tal cual para abrirse en Quirk.  Es tolerante con el pegado
    manual: comillas externas, comillas escapadas (``\\"``), comillas simples,
    percent-encoding y backslashes de más.

    La QFT inversa se canonicaliza a ``QFT†<n>`` (la única forma que Quirk
    reconoce) igual que en :func:`canonicalize_quirk_url`.

    Parámetros:
        - url (str): URL de Quirk (cruda, escapada o percent-encoded).

    Retorna:
        - str: URL normalizada; la original si no se pudo interpretar el
          circuito.
    """
    if not isinstance(url, str):
        raise ValueError('La URL debe ser una cadena.')
    text = url.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        text = text[1:-1]
    text = text.strip()
    index = text.find('https://')
    if index > 0:
        text = text[index:]
    if 'circuit=' not in text:
        return text
    head, fragment = text.split('circuit=', 1)
    for candidate in _circuit_text_variants(unquote(fragment)):
        circuit = _loads_circuit(candidate)
        if circuit is None:
            continue
        _canonicalize_qft_in_place(circuit)
        return head + 'circuit=' + json.dumps(
            circuit, ensure_ascii=True, separators=(',', ':')
        )
    return text


def encode_quirk_url(url, legible=False):
    """Percent-encodea el ``circuit=`` de una URL de Quirk para usarla como ``href``.

    Antes de codificar se canoniza la QFT inversa (``QFT<n>†`` → ``QFT†<n>``),
    de modo que el enlace generado se grafique en Quirk sin la compuerta
    "parse error".  Si el JSON del circuito no es interpretable (por ejemplo,
    una URL pegada con comillas o backslashes de más) se normaliza primero.

    Con ``legible=True`` se imita a Quirk (``src/ui/url.js``): el JSON se deja
    crudo y sólo se escapa si contiene ``%`` o ``&``, los dos casos que rompen
    el fragmento (se parte por ``&`` y se decodifica con ``decodeURIComponent``).
    Sirve para mostrar o pegar la URL en el navegador, donde ``{``/``"`` se leen
    mucho mejor que ``%7B``/``%22``.  El default escapa todo porque el JSON trae
    comillas dobles que cerrarían un atributo ``href`` HTML.

    Parámetros:
        - url (str): URL de Quirk con ``circuit=<JSON>`` (puede venir sin codificar).
        - legible (bool): deja el JSON sin escapar cuando es seguro hacerlo.

    Retorna:
        - str: URL con el JSON percent-encodeado (o crudo si ``legible``);
          la URL original si el parseo falla.
    """
    try:
        circuit_json = unquote(url).split('circuit=')[1]
        if _loads_circuit(circuit_json) is None:
            # URL pegada a mano: se normaliza y se vuelve a codificar.
            normalized = normalize_quirk_url(url)
            if 'circuit=' in normalized:
                circuit_json = unquote(normalized).split('circuit=')[1]
        canonical_json = _canonicalize_circuit_json(circuit_json)
        if canonical_json is not None:
            circuit_json = canonical_json
        if legible and '%' not in circuit_json and '&' not in circuit_json:
            return url.split('circuit=')[0] + 'circuit=' + circuit_json
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

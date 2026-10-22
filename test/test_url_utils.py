# -*- coding: utf-8 -*-
"""Normalización de URLs de Quirk pegadas a mano (``normalize_quirk_url``).

Al copiar una URL de Quirk desde un archivo JSON del proyecto (o al pegarla en
una celda) el JSON suele traer comillas escapadas (``\\"``) y escapes Unicode
(``\\u00bd``). Si se eliminan los backslashes "de más" a ciegas, los escapes
Unicode se pierden y las compuertas quedan como ``Z^-u00bd`` o
``|/u27e9u27e8/|``, que Quirk no reconoce y pinta como "parse error".

Este módulo cubre la normalización a JSON estricto (canónico) y el uso de la
URL resultante en la web de Quirk.
"""

import json
import unittest
from urllib.parse import unquote

from qtrans.utils.qutils import quirk_circuit_info, quirk_to_qasm
from qtrans.utils.url_utils import (
    encode_quirk_url,
    normalize_quirk_url,
    parse_quirk_url,
)

BASE = 'https://algassert.com/quirk#circuit='
# URL tal como figura en /input/xy_probes_gates_algorithms.json (con escapes).
POSTSELECT_Y_URL = (
    BASE
    + '{"cols": [["H", "H", "H", "H", "H", "H"], '
    + '["Z^-\\u00bd", "Z^-\\u00bd", "Z^-\\u00bd", "Z^-\\u00bd", "Z^-\\u00bd", "Z^-\\u00bd"], '
    + '["|/\\u27e9\\u27e8/|", "|/\\u27e9\\u27e8/|", "|/\\u27e9\\u27e8/|", '
    + '"|/\\u27e9\\u27e8/|", "|/\\u27e9\\u27e8/|", "|/\\u27e9\\u27e8/|"], '
    + '["Measure", "Measure", "Measure", "Measure", "Measure", "Measure"]]}'
)


class NormalizeQuirkUrlTests(unittest.TestCase):
    def test_keeps_unicode_escapes(self):
        normalized = normalize_quirk_url(POSTSELECT_Y_URL)
        self.assertIn('Z^-\\u00bd', normalized)
        self.assertIn('|/\\u27e9\\u27e8/|', normalized)
        self.assertNotIn('u00bd', normalized.replace('\\u00bd', ''))

    def test_circuit_matches_the_original(self):
        circuit = parse_quirk_url(normalize_quirk_url(POSTSELECT_Y_URL))
        self.assertEqual('Z^-\u00bd', circuit['cols'][1][0])
        self.assertEqual('|/⟩⟨/|', circuit['cols'][2][0])
        self.assertEqual(6, len(circuit['cols'][0]))

    def test_output_is_strict_ascii_json(self):
        normalized = normalize_quirk_url(POSTSELECT_Y_URL)
        fragment = normalized.split('circuit=', 1)[1]
        self.assertTrue(fragment.isascii())
        self.assertEqual(
            json.loads(fragment),
            json.loads(fragment.replace('\\"', '"')),
        )

    def test_is_idempotent(self):
        once = normalize_quirk_url(POSTSELECT_Y_URL)
        self.assertEqual(once, normalize_quirk_url(once))

    def test_accepts_quotes_and_escaped_quotes(self):
        variants = (
            '"' + POSTSELECT_Y_URL + '"',
            "'" + POSTSELECT_Y_URL + "'",
            POSTSELECT_Y_URL.replace('"', '\\"'),
        )
        expected = normalize_quirk_url(POSTSELECT_Y_URL)
        for variant in variants:
            with self.subTest(variant=variant[:40]):
                self.assertEqual(expected, normalize_quirk_url(variant))

    def test_accepts_percent_encoded_urls(self):
        encoded = encode_quirk_url(POSTSELECT_Y_URL)
        self.assertEqual(
            normalize_quirk_url(POSTSELECT_Y_URL),
            normalize_quirk_url(encoded),
        )

    def test_keeps_the_url_prefix(self):
        normalized = normalize_quirk_url(POSTSELECT_Y_URL)
        self.assertTrue(normalized.startswith('https://algassert.com/quirk#circuit='))

    def test_circuit_is_translatable(self):
        url = normalize_quirk_url(POSTSELECT_Y_URL)
        info = quirk_circuit_info(url)
        self.assertEqual(6, info['n_qubits'])
        self.assertEqual(4, info['n_cols'])
        self.assertIn('Measure', info['gates'])
        self.assertIn('Z^-\u00bd', info['gates'])
        qasm = quirk_to_qasm(url)
        self.assertIn('OPENQASM', qasm)

    def test_encode_quirk_url_recovers_broken_escapes(self):
        broken = POSTSELECT_Y_URL.replace('\\u00bd', 'u00bd')
        encoded = encode_quirk_url(broken)
        self.assertIn('Z^-u00bd', unquote(encoded))
        self.assertNotIn('u00bd', unquote(encoded).replace('u00bd', ''))


class EncodeQuirkUrlLegibleTests(unittest.TestCase):
    """Modo ``legible=True``: imita a Quirk y deja el JSON crudo."""

    SIMPLE_URL = BASE + '{"cols":[["Z^0.25"],["Y^0.055556"],["Z^-0.25"]]}'

    def test_default_escapes_json_for_html_href(self):
        encoded = encode_quirk_url(self.SIMPLE_URL)
        self.assertNotIn('"', encoded)
        self.assertNotIn('{', encoded)
        self.assertIn('%7B%22cols%22', encoded)

    def test_legible_keeps_json_readable(self):
        legible = encode_quirk_url(self.SIMPLE_URL, legible=True)
        self.assertEqual(legible, self.SIMPLE_URL)
        self.assertIn('{"cols":[["Z^0.25"]', legible)

    def test_legible_escapes_when_json_has_percent_or_ampersand(self):
        # Quirk parte el fragmento por '&' y decodifica con decodeURIComponent:
        # un '%' o un '&' crudo rompería el enlace, así que se escapa igual.
        for extra in ('{"cols":[["X%25"]]}', '{"cols":[["X"]],"&x":1}'):
            url = BASE + extra
            self.assertEqual(encode_quirk_url(url, legible=True),
                             encode_quirk_url(url))

    def test_legible_keeps_the_circuit_translatable(self):
        legible = encode_quirk_url(BASE + '{"cols": [["H"]]}', legible=True)
        # El JSON se deja tal cual (sólo se canoniza la QFT inversa).
        self.assertEqual(unquote(legible), BASE + '{"cols": [["H"]]}')
        self.assertEqual(quirk_circuit_info(legible)['n_qubits'], 1)


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-
"""Canonicidad de la QFT inversa en URLs de Quirk.

Quirk registra la QFT inversa con el id serializado ``QFT†<n>``
(``setSerializedId("QFT†" + span)`` en ``src/gates/FourierTransformGates.js``).
Las variantes ``QFT<n>†`` y ``QFT^†<n>`` no existen en Quirk: ``Serializer.fromJson_Gate``
lanza y la compuerta se pinta como "Parse Error" (motivo ``parse\\nerror``).

El traductor sí acepta todas las variantes (``_QFT_TOKEN_RE``), por lo que este
módulo cubre:
- la canonización de URLs antes de capturar/enlazar (``canonicalize_quirk_url`` y
  ``encode_quirk_url``), y
- que la traducción siga emitiendo ``QFTn_dg`` con cualquier variante.
"""

import json
import unittest
from pathlib import Path
from urllib.parse import quote

from qtrans.utils.qutils import quirk_to_qasm
from qtrans.utils.url_utils import (
    canonicalize_quirk_url,
    encode_quirk_url,
    parse_quirk_url,
)

BASE = 'https://algassert.com/quirk#circuit='
DAGGER = '\u2020'
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def raw_url(circuit):
    return BASE + json.dumps(circuit)


class CanonicalQuirkUrlTests(unittest.TestCase):
    def test_moves_dagger_before_span(self):
        for span in (2, 3, 4, 6, 10, 14):
            with self.subTest(span=span):
                url = raw_url({'cols': [[f'QFT{span}{DAGGER}']]})
                canonical = canonicalize_quirk_url(url)
                self.assertEqual(
                    f'QFT{DAGGER}{span}', parse_quirk_url(canonical)['cols'][0][0]
                )

    def test_canonicalizes_caret_variant(self):
        url = raw_url({'cols': [[f'QFT^{DAGGER}3']]})
        canonical = canonicalize_quirk_url(url)
        self.assertEqual(f'QFT{DAGGER}3', parse_quirk_url(canonical)['cols'][0][0])

    def test_already_canonical_urls_are_returned_unchanged(self):
        urls = (
            raw_url({'cols': [[f'QFT{DAGGER}3']]}),
            raw_url({'cols': [['QFT3'], ['Measure']]}),
            BASE + 'no-es-json',
            'https://algassert.com/quirk',
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(url, canonicalize_quirk_url(url))

    def test_canonicalization_is_idempotent(self):
        url = raw_url({'cols': [[f'QFT3{DAGGER}', 'QFT4']]})
        once = canonicalize_quirk_url(url)
        self.assertEqual(once, canonicalize_quirk_url(once))
        self.assertIn(f'QFT{DAGGER}3', parse_quirk_url(once)['cols'][0])

    def test_canonicalizes_percent_encoded_urls(self):
        encoded = quote(json.dumps({'cols': [[f'QFT2{DAGGER}']]}), safe='')
        canonical = canonicalize_quirk_url(BASE + encoded)
        self.assertEqual(f'QFT{DAGGER}2', parse_quirk_url(canonical)['cols'][0][0])
        # Conserva el estilo percent-encoded del enlace original.
        self.assertIn('%', canonical)
        self.assertNotIn(DAGGER, canonical)

    def test_canonicalizes_nested_custom_gate_circuits(self):
        circuit = {
            'cols': [['~g'], [1]],
            'gates': [{
                'id': '~g',
                'name': 'G',
                'circuit': {'cols': [[f'QFT3{DAGGER}']]},
            }],
        }
        canonical = canonicalize_quirk_url(raw_url(circuit))
        parsed = parse_quirk_url(canonical)
        self.assertEqual(f'QFT{DAGGER}3', parsed['gates'][0]['circuit']['cols'][0][0])

    def test_encode_quirk_url_canonicalizes_for_href(self):
        url = raw_url({'cols': [[f'QFT5{DAGGER}']]})
        encoded = encode_quirk_url(url)
        self.assertEqual(f'QFT{DAGGER}5', parse_quirk_url(encoded)['cols'][0][0])
        # El href queda sin caracteres crudos que rompan HTML/foros.
        self.assertNotIn(DAGGER, encoded)
        self.assertNotIn('"', encoded)


class QftTranslationVariantTests(unittest.TestCase):
    def test_translation_accepts_every_qft_variant(self):
        for token in (f'QFT3{DAGGER}', f'QFT{DAGGER}3', f'QFT^{DAGGER}3'):
            with self.subTest(token=token):
                qasm = quirk_to_qasm(raw_url({'cols': [[token, 1, 1]]}))
                self.assertIn('gate QFT3_dg a,b,c {', qasm)
                self.assertIn('QFT3_dg q[0], q[1], q[2];', qasm)


class InputAlgorithmsRegressionTests(unittest.TestCase):
    def test_qft_algorithm_urls_are_canonical_for_quirk(self):
        path = PROJECT_ROOT / 'input' / 'qft_algorithms.json'
        algorithms = json.loads(path.read_text(encoding='utf-8'))
        self.assertTrue(algorithms)
        for name, data in algorithms.items():
            with self.subTest(algorithm=name):
                url = data['url']
                # Las URLs de entrada ya deben ser válidas en Quirk (sin "parse error").
                self.assertEqual(url, canonicalize_quirk_url(url))
        for name, data in algorithms.items():
            if 'qft-1' not in name:
                continue
            with self.subTest(inverse=name):
                cells = [
                    cell
                    for col in parse_quirk_url(data['url'])['cols']
                    for cell in col
                    if isinstance(cell, str) and cell.startswith('QFT')
                ]
                canonical_cells = [
                    cell for cell in cells
                    if cell.startswith('QFT' + DAGGER)
                    and cell[len('QFT') + 1:].isdigit()
                ]
                self.assertTrue(canonical_cells)


if __name__ == '__main__':
    unittest.main()

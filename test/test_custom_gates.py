# -*- coding: utf-8 -*-
"""Verificación del tratamiento exhaustivo de las compuertas custom.

El circuito ``1. complex_customs`` de ``input/custom_gates_algorithms.json`` (antes
``39. complex_customs`` de ``popular_algorithms.json``) declara
ocho compuertas custom en la URL de Quirk (todas con campo ``matrix``) pero solo
utiliza cinco en el circuito: ``~rfnt`` (``pi``), ``~bkbo`` (``prueba``) y
``~f0b8`` (``complex_rotation``) quedan declaradas y sin usar.

Este módulo comprueba que:

- el catálogo ``custom_gates`` de la API es **exhaustivo** (las ocho
  compuertas declaradas) e indica con ``used_in_circuit`` cuáles se usan;
- con ``preserve_custom_gates`` las ocho compuertas se traslada al script
  migrado (una función local cada una) y sin él solo se expanden en línea las
  que se usan;
- el modo ``preserve`` no pierde los parámetros de las compuertas custom
  controladas: dos compuertas controladas distintas (``cu1_pi_512`` y
  ``cu1_pi_256``) comparten la operación interna ``mcphase`` y cada una debe
  conservar su propio ángulo.
"""

import json
import unittest
from pathlib import Path

import numpy as np
from qiskit.quantum_info import Operator

from qtrans import translate_circuit
from qtrans.utils.quirk_utils import custom_gates_catalog

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALGORITHMS_FILE = PROJECT_ROOT / 'input' / 'custom_gates_algorithms.json'
ALGORITHM_NAME = '1. complex_customs'

# Las ocho compuertas declaradas en la URL y las cinco usadas en el circuito.
DECLARED_IDS = [
    '~cu10000', '~cu10001', '~edqr', '~ipt0',
    '~rfnt', '~bkbo', '~pi31', '~f0b8',
]
USED_IDS = ['~cu10000', '~cu10001', '~edqr', '~ipt0', '~pi31']
UNUSED_IDS = ['~rfnt', '~bkbo', '~f0b8']
UNUSED_QASM_NAMES = ['pi_gate', 'prueba', 'complex_rotation']


def _algorithm_url():
    """Devuelve la URL de Quirk del algoritmo 39.

    Retorna:
        - str: URL con ``circuit=<JSON>``.
    """
    with open(ALGORITHMS_FILE, encoding='utf-8') as handle:
        registry = json.load(handle)
    return registry[ALGORITHM_NAME]['url']


def _translate(preserve):
    """Traduce el algoritmo 39 con y sin conservación de compuertas custom.

    Parámetros:
        - preserve (bool): valor de ``preserve_custom_gates``.

    Retorna:
        - dict: bloque ``output`` de la respuesta de la API.
    """
    response = translate_circuit({
        'input': {
            'url': _algorithm_url(),
            'provider': 'qiskit',
            'preserve_custom_gates': preserve,
            'zx': {'enabled': False},
            'images': {'quirk': False, 'qasm': False, 'composer': False},
        }
    })
    return response['output']


def _run(source):
    """Ejecuta un script migrado y devuelve el circuito que construye.

    Parámetros:
        - source (str): código Python del script migrado.

    Retorna:
        - object: variable ``circuit`` del namespace del script.
    """
    namespace = {}
    exec(compile(source, '<migrated>', 'exec'), namespace)
    return namespace['circuit']


class CustomGatesCatalogTests(unittest.TestCase):
    """El catálogo de compuertas custom describe todas las declaradas."""

    def test_catalog_lists_every_declared_gate(self):
        catalog = custom_gates_catalog(_algorithm_url())

        self.assertEqual(DECLARED_IDS, [entry['id'] for entry in catalog])
        for entry in catalog:
            self.assertEqual(
                {'id', 'name', 'qasm_name', 'kind', 'n_qubits', 'used_in_circuit'},
                set(entry),
            )
            self.assertEqual('matrix', entry['kind'])

    def test_catalog_marks_used_and_unused_gates(self):
        catalog = custom_gates_catalog(_algorithm_url())
        used = [entry['id'] for entry in catalog if entry['used_in_circuit']]
        unused = [entry['id'] for entry in catalog if not entry['used_in_circuit']]

        self.assertEqual(USED_IDS, used)
        self.assertEqual(UNUSED_IDS, unused)

    def test_translate_output_exposes_the_catalog(self):
        output = _translate(False)
        catalog = output['custom_gates']

        self.assertEqual(DECLARED_IDS, [entry['id'] for entry in catalog])
        self.assertEqual(
            5, sum(1 for entry in catalog if entry['used_in_circuit'])
        )
        self.assertEqual(
            UNUSED_QASM_NAMES,
            [
                entry['qasm_name']
                for entry in catalog
                if not entry['used_in_circuit']
            ],
        )


class PreserveCustomGatesTests(unittest.TestCase):
    """El script migrado traslada las compuertas custom según el modo."""

    def test_preserve_mode_defines_every_declared_gate(self):
        output = _translate(True)

        for key, source in output['migrated_code'].items():
            functions = [
                line.split('(')[0].replace('def ', '').strip()
                for line in source.splitlines()
                if line.startswith('def ')
            ]
            for name in UNUSED_QASM_NAMES:
                self.assertIn(name, functions, msg=f"{key} no define {name}")

    def test_flat_mode_expands_only_the_used_gates(self):
        output = _translate(False)

        for key, source in output['migrated_code'].items():
            for name in UNUSED_QASM_NAMES:
                self.assertNotIn(name, source, msg=f"{key} menciona {name}")

    def test_preserve_mode_keeps_controlled_gate_parameters(self):
        """Dos compuertas controladas distintas no pueden compartir cuerpo.

        ``ccu1_pi_512`` y ``ccu1_pi_256`` se descomponen en la misma operación
        interna (``mcphase``): si el helper se definiera una sola vez, la
        segunda perdería su ángulo.
        """
        output = _translate(True)
        source = output['migrated_code']['ibm_qiskit_code']

        self.assertIn('math.pi/512', source)
        self.assertIn('math.pi/256', source)

    def test_flat_and_preserve_circuits_are_equivalent(self):
        flat = _run(_translate(False)['migrated_code']['ibm_qiskit_code'])
        preserve = _run(_translate(True)['migrated_code']['ibm_qiskit_code'])
        flat = flat.remove_final_measurements(inplace=False)
        preserve = preserve.remove_final_measurements(inplace=False)

        delta = np.max(
            np.abs(Operator(flat).data - Operator(preserve).data)
        )
        self.assertLess(float(delta), 1e-9)


if __name__ == '__main__':
    unittest.main()

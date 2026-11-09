# -*- coding: utf-8 -*-
"""Cycle shifts, estados iniciales y alias de anti-control de Quirk.

Los circuitos ``3. 3q_17cols_8_ciclics_shifts_customs`` y
``5. god_custom`` de ``input/custom_gates_algorithms.json`` usan tres
características que el traductor no cubría:

- compuertas ``<<n``/``>>n`` (rotación cíclica de ``n`` wires);
- el campo ``init`` (estado inicial distinto de ``|0>``);
- el id ASCII ``o`` como alias del anti-control ``◦`` (``god_custom``).

Este módulo fija la semántica y comprueba que la etapa ZX coincide con la
traducción OpenQASM.
"""

import json
import unittest
from pathlib import Path

from qiskit import qasm3

from qtrans.utils.quirk_utils import (
    _cycle_token,
    _initial_state_gates,
    quirk_to_qasm,
)
from qtrans.utils.url_utils import encode_quirk_url
from qtrans.utils.zx_utils import (
    _zx_matrix_gate_names,
    compare_zx_graphs,
    qasm_to_zx_graph,
    quirk_to_zx_graph_with_method,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALGORITHMS_FILE = PROJECT_ROOT / 'input' / 'custom_gates_algorithms.json'


def _url(circuit):
    """Construye una URL de Quirk a partir de un circuito JSON.

    Parámetros:
        - circuit (dict): circuito de Quirk (``cols``/``init``/``gates``).

    Retorna:
        - str: URL percent-encoded válida para Quirk.
    """
    raw = 'https://algassert.com/quirk#circuit=' + json.dumps(
        circuit, ensure_ascii=False
    )
    return encode_quirk_url(raw)


def _algorithm_url(name):
    """Devuelve la URL de un algoritmo del registro de compuertas custom.

    Parámetros:
        - name (str): nombre del algoritmo en el registro.

    Retorna:
        - str: URL con ``circuit=<JSON>``.
    """
    with open(ALGORITHMS_FILE, encoding='utf-8') as handle:
        registry = json.load(handle)
    return registry[name]['url']


class CycleTokenTests(unittest.TestCase):
    """Detección de los tokens de rotación cíclica."""

    def test_detects_both_directions(self):
        self.assertEqual(('<<', 3), _cycle_token('<<3'))
        self.assertEqual(('>>', 2), _cycle_token('>>2'))

    def test_rejects_invalid_spans_and_other_cells(self):
        self.assertIsNone(_cycle_token('<<1'))
        self.assertIsNone(_cycle_token('<<x'))
        self.assertIsNone(_cycle_token('Swap'))
        self.assertIsNone(_cycle_token(1))


class CycleShiftTranslationTests(unittest.TestCase):
    """Los shifts se emiten como swaps adyacentes en el orden correcto."""

    def test_left_shift_moves_content_down(self):
        source = quirk_to_qasm(_url({'cols': [['<<3']]}), qasm_version='3.0')
        first = source.index('swap q[1], q[2];')
        second = source.index('swap q[0], q[1];')
        self.assertLess(first, second)
        self.assertEqual(1, source.count('swap q[1], q[2];'))
        self.assertEqual(1, source.count('swap q[0], q[1];'))

    def test_right_shift_moves_content_up(self):
        source = quirk_to_qasm(_url({'cols': [['>>3']]}), qasm_version='3.0')
        first = source.index('swap q[0], q[1];')
        second = source.index('swap q[1], q[2];')
        self.assertLess(first, second)

    def test_controls_are_applied_to_each_swap(self):
        source = quirk_to_qasm(
            _url({'cols': [['•', '<<2']]}), qasm_version='3.0'
        )
        self.assertIn('ctrl @ swap q[0], q[1], q[2];', source)


class InitialStateTests(unittest.TestCase):
    """El campo ``init`` se prepara tras declarar el registro cuántico."""

    def test_initial_state_gate_table(self):
        self.assertEqual(('x',), _initial_state_gates('1'))
        self.assertEqual(('h',), _initial_state_gates('+'))
        self.assertEqual(('h', 'z'), _initial_state_gates('-'))
        self.assertEqual(('h', 'p(pi/2)'), _initial_state_gates('i'))
        self.assertEqual(('h', 'p(-pi/2)'), _initial_state_gates('-i'))
        self.assertEqual((), _initial_state_gates(0))

    def test_initial_state_lines_are_emitted(self):
        source = quirk_to_qasm(
            _url({'init': ['+', '-i', '1'], 'cols': []}),
            qasm_version='3.0',
        )
        self.assertIn('qreg q[3];', source)
        self.assertIn('h q[0];', source)
        self.assertIn('h q[1];', source)
        self.assertIn('p(-pi/2) q[1];', source)
        self.assertIn('x q[2];', source)


class AsciiAntiControlTests(unittest.TestCase):
    """``o`` es el anti-control ASCII de ``◦`` (lo usa ``god_custom``)."""

    def test_o_negates_the_control(self):
        source = quirk_to_qasm(
            _url({'cols': [['o', 'X']]}), qasm_version='3.0'
        )
        self.assertEqual(2, source.count('x q[0];'))
        self.assertIn('ctrl @ x q[0], q[1];', source)


class GodCustomTests(unittest.TestCase):
    """El circuito ``god_custom`` traduce y su grafo ZX es equivalente."""

    def test_god_custom_translates_and_loads(self):
        url = _algorithm_url('5. god_custom')
        source = quirk_to_qasm(url, qasm_version='3.0')
        circuit = qasm3.loads(source)
        self.assertEqual(3, circuit.num_qubits)

    def test_god_custom_zx_matches_qasm(self):
        url = _algorithm_url('5. god_custom')
        base, _ = quirk_to_zx_graph_with_method(url)
        qasm = qasm_to_zx_graph(
            quirk_to_qasm(url, qasm_version='3.0'),
            matrix_gate_names=_zx_matrix_gate_names(url),
        )
        _, verdict = compare_zx_graphs(base, qasm)
        self.assertEqual('EQUIVALENTES', verdict)


if __name__ == '__main__':
    unittest.main()

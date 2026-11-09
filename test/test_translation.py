# -*- coding: utf-8 -*-
"""Tests de traducción de circuitos Quirk vía la API de librería.

Agrupa los tests de traducción a OpenQASM que antes vivían en el pipeline CLI
(de QFT nativa, control de QFT, compuertas custom con ``preserve_custom_gates``
y descomposición de matrices) y los tests de impresión segura de consola.
"""

import io
import json
import sys
import unittest
from unittest.mock import patch

from qiskit import qasm3
from qiskit.quantum_info import Operator

from qtrans import translate_circuit
from qtrans.utils.pipeline_utils import safe_print
from qtrans.utils.provider_utils import provider_python_source
from qtrans.utils.quirk_utils import quirk_to_qasm
from qtrans.utils.url_utils import encode_quirk_url
from qtrans.utils.zx_utils import qasm_to_zx_graph, quirk_to_zx_graph


QUIRK_URL = 'https://algassert.com/quirk#circuit={"cols":[["H"],["Measure"]]}'


def quirk_url(circuit):
    return encode_quirk_url('https://algassert.com/quirk#circuit=' + json.dumps(circuit))


class TranslationQasmTests(unittest.TestCase):
    """La traducción a OpenQASM (3.0 y 2.0) y los tests de QFT comparten aquí."""

    def test_qasm_v2_output_has_blank_line_after_header(self):
        payload = {
            'input': {
                'json': {'cols': [['H'], ['Measure']]},
                'qasm_version': '2.0',
            },
        }
        result = translate_circuit(payload)
        qasm_text = result['output']['qasm']['code']
        lines = qasm_text.splitlines()
        self.assertEqual('OPENQASM 2.0;', lines[0])
        self.assertTrue(lines[1].startswith('include'))
        self.assertEqual('', lines[2])

    def test_qft_native_gate_is_emitted_in_qasm(self):
        url = quirk_url({'cols': [['QFT3', 1, 1], ['Measure', 'Measure', 'Measure']]})
        qasm = quirk_to_qasm(url)

        self.assertIn('gate QFT3 a,b,c {', qasm)
        self.assertIn('QFT3 q[0], q[1], q[2];', qasm)
        self.assertIn('qreg q[3];', qasm)

        inverse = quirk_to_qasm(quirk_url({'cols': [['QFT3\u2020', 1, 1]]}))
        self.assertIn('gate QFT3_dg a,b,c {', inverse)
        self.assertIn('QFT3_dg q[0], q[1], q[2];', inverse)

    def test_qft_zx_graphs_are_equivalent(self):
        import pyzx as zx

        url = quirk_url({'cols': [['QFT3', 1, 1]]})
        base = quirk_to_zx_graph(url)
        qasm_graph = qasm_to_zx_graph(quirk_to_qasm(url))
        zx.simplify.full_reduce(base)
        zx.simplify.full_reduce(qasm_graph)
        self.assertTrue(zx.compare_tensors(base, qasm_graph))

    def test_qft_can_be_controlled(self):
        circuit = {'cols': [['•', 'QFT2', 1], ['Measure', 'Measure', 'Measure']]}
        qasm = quirk_to_qasm(quirk_url(circuit))
        self.assertIn('ctrl @ QFT2 q[0], q[1], q[2];', qasm)

    def test_preserve_custom_gates_generates_local_functions(self):
        url = quirk_url({'cols': [['QFT3', 1, 1], ['Measure', 'Measure', 'Measure']]})
        qasm = quirk_to_qasm(url)

        for provider in ('qiskit', 'braket', 'pennylane'):
            preserved = provider_python_source(qasm, provider, preserve_custom_gates=True)
            inlined = provider_python_source(qasm, provider, preserve_custom_gates=False)
            self.assertIn('def QFT3', preserved)
            self.assertNotIn('def QFT3', inlined)
            compile(preserved, f'<{provider}-preserved>', 'exec')
            compile(inlined, f'<{provider}-inlined>', 'exec')

    def test_matrix_custom_gates_decompose_to_exact_unitaries(self):
        import numpy as np

        half = 0.7071067811865476
        circuit = {
            'cols': [['~g2', '~g4'], [1, 1]],
            'gates': [
                {'id': '~g2', 'name': 'g2', 'matrix': [[half, half], [half, -half]]},
                {
                    'id': '~g4',
                    'name': 'g4',
                    'matrix': [
                        [1, 0, 0, 0],
                        [0, 1, 0, 0],
                        [0, 0, 0, 1],
                        [0, 0, 1, 0],
                    ],
                },
            ],
        }
        qasm = quirk_to_qasm(quirk_url(circuit))
        parsed = qasm3.loads(qasm)
        wanted = {
            'g2': np.array([[half, half], [half, -half]], dtype=complex),
            'g4': np.array(circuit['gates'][1]['matrix'], dtype=complex),
        }
        seen = {}
        for instruction in parsed.data:
            if instruction.operation.name in wanted:
                seen[instruction.operation.name] = Operator(
                    instruction.operation.definition
                ).data
        self.assertEqual(set(seen), set(wanted))
        for name, matrix in wanted.items():
            np.testing.assert_allclose(seen[name], matrix, atol=1e-7)


class ConsoleEncodingTests(unittest.TestCase):
    """La salida de consola no debe abortar una etapa por símbolos no codificables."""

    def _captured_stdout(self, encoding):
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding=encoding, errors="strict")
        return buffer, stream

    def test_safe_print_survives_non_encodable_characters(self):
        buffer, stream = self._captured_stdout("cp1252")
        with patch.object(sys, "stdout", stream):
            safe_print("Compuerta Quirk no soportada: |+⟩⟨+|")
            stream.flush()
        self.assertIn("?", buffer.getvalue().decode("cp1252"))

    def test_safe_print_keeps_text_on_utf8_console(self):
        buffer, stream = self._captured_stdout("utf-8")
        with patch.object(sys, "stdout", stream):
            safe_print("dagger †")
            stream.flush()
        self.assertIn("dagger †", buffer.getvalue().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()

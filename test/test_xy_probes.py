# -*- coding: utf-8 -*-
"""Sondas de los grupos "X/Y Probes" del toolbox de Quirk.

Quirk dibuja estos grupos con los identificadores:
- controles de eje X: ``⊖`` (X-Axis Control) y ``⊕`` (X-Axis Anti-Control);
- controles de eje Y: ``(/)`` (Y-Axis Control) y ``⊗`` (Y-Axis Anti-Control);
- post-selecciones: ``|+⟩⟨+|`` (X-Off), ``|-⟩⟨-|`` (X-On), ``|X⟩⟨X|`` (Y-Off)
  y ``|/⟩⟨/|`` (Y-On).

El archivo ``input/xy_probes_gates_algorithms.json`` contiene 24 sondas: los
8 casos anteriores en 2, 4 y 6 qubits.  Cada sonda es determinista: el qubit
de control se prepara en el estado propio que hace disparar (o no) el mask y
el objetivo es un ``X`` que debe (o no) voltearse.

Este módulo comprueba:
- que la traducción no emite avisos de compuertas no traducibles;
- que el OpenQASM generado es válido y reproduce los bits esperados;
- que la verificación ZX da ``equivalente`` en los controles (unitarios) y
  ``no-comprobado`` en las post-selecciones (no unitarias).
"""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from qiskit import qasm3
from qiskit.primitives import StatevectorSampler

from qtrans.core import translate_circuit
from qtrans.utils import qutils
from qtrans.utils.qutils import quirk_to_qasm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALGORITHMS_FILE = PROJECT_ROOT / 'input' / 'xy_probes_gates_algorithms.json'

# Bits esperados (por índice de qubit) de las sondas de control.  Los pares
# (control, objetivo) alternan entre un control que dispara y otro que no, así
# que el objetivo solo se voltea en los pares "activos".
CONTROL_EXPECTATIONS = {
    'xaxis_control': {
        2: (1, 1),
        4: (1, 1, 0, 0),
        6: (1, 1, 0, 0, 1, 1),
    },
    'xaxis_anticontrol': {
        2: (0, 1),
        4: (0, 1, 1, 0),
        6: (0, 1, 1, 0, 0, 1),
    },
    'yaxis_control': {
        2: (1, 1),
        4: (1, 1, 0, 0),
        6: (1, 1, 0, 0, 1, 1),
    },
    'yaxis_anticontrol': {
        2: (0, 1),
        4: (0, 1, 1, 0),
        6: (0, 1, 1, 0, 0, 1),
    },
}

# Bit esperado (0 = estado OFF, 1 = estado ON) de las sondas de post-selección.
POSTSELECT_EXPECTATIONS = {
    'postselect_x_off': 0,
    'postselect_x_on': 1,
    'postselect_y_off': 0,
    'postselect_y_on': 1,
}

SIZES = (2, 4, 6)


def _algorithms():
    return json.loads(ALGORITHMS_FILE.read_text(encoding='utf-8'))


def _probe_name(kind, size):
    return f'xy_{kind}_{size}q'


def _bits(bitstrings):
    """Convierte los bitstrings de Qiskit en tuplas de bits por índice de qubit."""
    return {
        tuple(int(char) for char in text[::-1])
        for text in bitstrings
    }


def _simulate(qasm, shots=256):
    """Simula el QASM y devuelve (bits de c, bits de ps o None)."""
    circuit = qasm3.loads(qasm)
    result = StatevectorSampler(seed=42).run([circuit], shots=shots).result()[0]
    data = result.data
    c_values = _bits(data['c'].get_bitstrings())
    if len(c_values) != 1:
        raise AssertionError(f'Circuito no determinista: {c_values}')
    ps = None
    if 'ps' in data:
        ps_values = _bits(data['ps'].get_bitstrings())
        if len(ps_values) != 1:
            raise AssertionError(f'Post-selección no determinista: {ps_values}')
        ps = ps_values.pop()
    return c_values.pop(), ps


class ProbeFileTests(unittest.TestCase):
    """El archivo de entrada contiene las 24 sondas esperadas."""

    def test_file_contains_every_probe(self):
        algorithms = _algorithms()
        expected = {
            _probe_name(kind, size)
            for kind in list(CONTROL_EXPECTATIONS) + list(POSTSELECT_EXPECTATIONS)
            for size in SIZES
        }
        self.assertEqual(expected, set(algorithms))
        self.assertEqual(24, len(algorithms))

    def test_every_probe_has_description_and_quirk_url(self):
        for name, data in _algorithms().items():
            with self.subTest(probe=name):
                self.assertIn('desc', data)
                self.assertTrue(data['desc'].strip())
                self.assertTrue(
                    data['url'].startswith('https://algassert.com/quirk#circuit=')
                )


class ProbeTranslationTests(unittest.TestCase):
    """La traducción a OpenQASM de las sondas es completa y correcta."""

    def test_translation_emits_no_unsupported_gate_warning(self):
        for name, data in _algorithms().items():
            with self.subTest(probe=name):
                before = set(qutils._REPORTED_UNSUPPORTED_GATES)
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    quirk_to_qasm(data['url'])
                self.assertEqual(
                    before,
                    set(qutils._REPORTED_UNSUPPORTED_GATES),
                    'La traducción reportó compuertas no traducibles',
                )
                self.assertEqual('', stderr.getvalue())

    def test_generated_qasm_is_valid(self):
        for name, data in _algorithms().items():
            with self.subTest(probe=name):
                qasm = quirk_to_qasm(data['url'])
                circuit = qasm3.loads(qasm)
                self.assertGreater(circuit.num_qubits, 0)

    def test_control_probes_are_deterministic(self):
        algorithms = _algorithms()
        for kind, expectations in CONTROL_EXPECTATIONS.items():
            for size, expected in expectations.items():
                name = _probe_name(kind, size)
                with self.subTest(probe=name):
                    qasm = quirk_to_qasm(algorithms[name]['url'])
                    bits, ps = _simulate(qasm)
                    self.assertEqual(expected, bits)
                    self.assertIsNone(ps)

    def test_postselect_probes_are_deterministic(self):
        algorithms = _algorithms()
        for kind, expected_bit in POSTSELECT_EXPECTATIONS.items():
            for size in SIZES:
                name = _probe_name(kind, size)
                with self.subTest(probe=name):
                    qasm = quirk_to_qasm(algorithms[name]['url'])
                    bits, ps = _simulate(qasm)
                    self.assertEqual((expected_bit,) * size, bits)
                    self.assertEqual((expected_bit,) * size, ps)


class ProbeZxTests(unittest.TestCase):
    """La verificación ZX distingue controles (unitarios) y post-selecciones."""

    def _zx_result(self, url):
        output = translate_circuit({'input': {'url': url, 'zx': {'enabled': True}}})
        self.assertEqual([], output['output']['errors'])
        return output['output']['zx_calculus_result']

    def test_control_probes_are_zx_equivalent(self):
        algorithms = _algorithms()
        for kind in CONTROL_EXPECTATIONS:
            for size in SIZES:
                name = _probe_name(kind, size)
                with self.subTest(probe=name):
                    self.assertEqual(
                        'equivalente', self._zx_result(algorithms[name]['url'])
                    )

    def test_postselect_probes_are_not_zx_checkable(self):
        algorithms = _algorithms()
        for kind in POSTSELECT_EXPECTATIONS:
            for size in SIZES:
                name = _probe_name(kind, size)
                with self.subTest(probe=name):
                    self.assertEqual(
                        'no-comprobado', self._zx_result(algorithms[name]['url'])
                    )


class ProbeComparisonTableTests(unittest.TestCase):
    """El informe ZX debe listar todos los circuitos, comparable o no."""

    def _records(self):
        algorithms = _algorithms()
        records = []
        for kind in list(CONTROL_EXPECTATIONS) + list(POSTSELECT_EXPECTATIONS):
            for size in SIZES:
                name = _probe_name(kind, size)
                url = algorithms[name]['url']
                records.append(
                    {
                        'name': name,
                        'url': url,
                        'offset': 0,
                        'qasm_source': quirk_to_qasm(url, 0),
                    }
                )
        return records

    def test_report_lists_every_circuit_with_legend(self):
        from qtrans.utils import zx_utils

        records = self._records()
        with tempfile.TemporaryDirectory() as temp:
            result = zx_utils.run_zx_workflow(
                records, Path(temp), 0.5, False, False, 60
            )
            comparisons = result['comparisons']
            report = Path(result['comparison_path']).read_text(encoding='utf-8')

        self.assertEqual(len(records), len(comparisons))
        statuses = [c['Resultado'] for c in comparisons]
        self.assertEqual(12, sum(1 for s in statuses if s.startswith('EQUIVALENTES')))
        self.assertEqual(12, sum(1 for s in statuses if s.startswith('NO COMPARABLES')))

        for comparison in comparisons:
            if comparison['Resultado'].startswith('NO COMPARABLES'):
                self.assertIn('no soportada', comparison['Motivo'])
            else:
                self.assertEqual('', comparison['Motivo'])

        self.assertIn('## Leyenda', report)
        self.assertIn('| EQUIVALENTES | 12 |', report)
        self.assertIn('| NO COMPARABLES | 12 |', report)
        self.assertIn('Motivos de no comparabilidad', report)
        for comparison in comparisons:
            self.assertIn(comparison['Nombre algoritmo'], report)


if __name__ == '__main__':
    unittest.main()

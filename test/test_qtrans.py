import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qtrans import run_pipeline
from qtrans.utils.qutils import (
    provider_python_source,
    quirk_to_qasm,
)
from qtrans.utils.url_utils import (
    encode_quirk_url,
)
from qtrans.utils.zx_utils import (
    qasm_to_zx_graph,
    quirk_to_zx_graph,
)


QUIRK_URL = 'https://algassert.com/quirk#circuit={"cols":[["H"],["Measure"]]}'


def quirk_url(circuit):
    return encode_quirk_url('https://algassert.com/quirk#circuit=' + json.dumps(circuit))

DISABLED_STAGES = dict(
    capture_images=False,
    generate_qasm_images=False,
    generate_comparison=False,
    generate_composer_images=False,
    generate_zx=False,
    generate_zx_images=False,
)


class QTransPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.input_dir = self.root / 'input'
        self.output_dir = self.root / 'output'
        self.run_dir = self.output_dir / 'run_TEST'
        self.qasm_dir = self.run_dir / 'algorithms_qasm'
        self.quirk_images_dir = self.run_dir / 'imgs' / 'circuits_quirk'
        self.input_dir.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_algorithms(self, filename, name):
        path = self.input_dir / filename
        path.write_text(
            json.dumps({name: {'url': QUIRK_URL, 'offset': 0, 'desc': 'test'}}),
            encoding='utf-8',
        )
        return path

    def run_case(self, **kwargs):
        options = dict(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            run_label='TEST',
            input_file=None,
            input_files=(),
            qasm_version='3.0',
            target_providers=('qiskit',),
        )
        options.update(kwargs)
        return run_pipeline(**options)

    def test_algorithm_mode_processes_only_selected_json(self):
        self.write_algorithms('algorithms.json', '1. Bell')
        self.write_algorithms('other.json', '2. Ignored')

        summary = self.run_case(
            input_mode='algorithm',
            input_file='algorithms.json',
            **DISABLED_STAGES,
        )

        self.assertEqual(summary['files_processed'], 1)
        self.assertEqual(summary['algorithms_processed'], 1)
        self.assertEqual(summary['run_dir'], self.run_dir)
        qasm_path = self.qasm_dir / '1__Bell_v3.0.txt'
        self.assertTrue(qasm_path.is_file())
        self.assertIn('OPENQASM 3.0;', qasm_path.read_text(encoding='utf-8'))
        self.assertFalse((self.qasm_dir / '2__Ignored_v3.0.txt').exists())

    def test_batch_mode_processes_top_level_json_files(self):
        self.write_algorithms('algorithms.json', '1. Bell')
        self.write_algorithms('popular_algorithms.json', '1. Popular Bell')
        nested_dir = self.input_dir / 'nested'
        nested_dir.mkdir()
        (nested_dir / 'ignored.json').write_text('{}', encoding='utf-8')

        summary = self.run_case(input_mode='batch', **DISABLED_STAGES)

        self.assertEqual(summary['files_processed'], 2)
        self.assertEqual(summary['algorithms_processed'], 2)
        self.assertTrue((self.qasm_dir / '1__Bell_v3.0.txt').is_file())
        self.assertTrue((self.qasm_dir / 'popular_1__Popular_Bell_v3.0.txt').is_file())
        self.assertFalse((self.qasm_dir / 'ignored_v3.0.txt').exists())

    def test_batch_mode_processes_selected_input_files_only(self):
        self.write_algorithms('algorithms.json', '1. Bell')
        self.write_algorithms('other.json', '2. Ignored')

        summary = self.run_case(
            input_mode='batch',
            input_files=['algorithms.json'],
            **DISABLED_STAGES,
        )

        self.assertEqual(summary['files_processed'], 1)
        self.assertEqual(summary['algorithms_processed'], 1)
        self.assertTrue((self.qasm_dir / '1__Bell_v3.0.txt').is_file())
        self.assertFalse((self.qasm_dir / '2__Ignored_v3.0.txt').exists())

    def test_batch_mode_processes_multiple_selected_input_files(self):
        self.write_algorithms('algorithms.json', '1. Bell')
        self.write_algorithms('popular_algorithms.json', '1. Popular Bell')
        self.write_algorithms('other.json', '2. Ignored')

        summary = self.run_case(
            input_mode='batch',
            input_files=['algorithms.json', 'popular_algorithms.json'],
            **DISABLED_STAGES,
        )

        self.assertEqual(summary['files_processed'], 2)
        self.assertEqual(summary['algorithms_processed'], 2)
        self.assertTrue((self.qasm_dir / '1__Bell_v3.0.txt').is_file())
        self.assertTrue((self.qasm_dir / 'popular_1__Popular_Bell_v3.0.txt').is_file())
        self.assertFalse((self.qasm_dir / '2__Ignored_v3.0.txt').exists())

    def test_batch_mode_processes_comma_separated_input_files(self):
        self.write_algorithms('algorithms.json', '1. Bell')
        self.write_algorithms('popular_algorithms.json', '1. Popular Bell')

        summary = self.run_case(
            input_mode='batch',
            input_files=['algorithms.json,popular_algorithms.json'],
            **DISABLED_STAGES,
        )

        self.assertEqual(summary['files_processed'], 2)
        self.assertTrue((self.qasm_dir / '1__Bell_v3.0.txt').is_file())
        self.assertTrue((self.qasm_dir / 'popular_1__Popular_Bell_v3.0.txt').is_file())

    def test_capture_function_is_called_for_each_algorithm(self):
        self.write_algorithms('algorithms.json', '1. Bell')

        with patch('qtrans.core.capture_quirk_circuit', return_value=True) as capture:
            summary = self.run_case(
                input_mode='algorithm',
                input_file='algorithms.json',
                capture_images=True,
                capture_timeout=22,
                generate_qasm_images=False,
                generate_comparison=False,
                generate_composer_images=False,
                generate_zx=False,
            )

        self.assertEqual(summary['captures_succeeded'], 1)
        capture.assert_called_once_with(
            QUIRK_URL,
            self.quirk_images_dir / '1__Bell.png',
            timeout=22,
        )

    def test_full_pipeline_generates_run_artifacts_and_composer_images(self):
        self.write_algorithms('algorithms.json', '1. Bell')

        summary = self.run_case(
            input_mode='algorithm',
            input_file='algorithms.json',
            capture_images=False,
            generate_qasm_images=True,
            generate_comparison=True,
            generate_composer_images=True,
            generate_zx=False,
        )

        self.assertTrue((self.qasm_dir / '1__Bell_v3.0.txt').is_file())
        self.assertTrue((self.run_dir / 'imgs' / 'circuits_qasm' / '1__Bell.png').is_file())
        self.assertTrue((self.run_dir / 'migrated_circuits' / 'ibm_qiskit' / '1__Bell.py').is_file())
        composer_image = self.run_dir / 'migrated_circuits' / 'ibm_qiskit' / 'imgs' / '1__Bell.png'
        self.assertTrue(composer_image.is_file())
        self.assertEqual(summary['composer_images_generated'], 1)

    def test_qasm_v2_output_has_blank_line_after_header(self):
        self.write_algorithms('algorithms.json', '1. Bell')

        self.run_case(
            input_mode='algorithm',
            input_file='algorithms.json',
            qasm_version='2.0',
            **DISABLED_STAGES,
        )

        qasm_text = (self.qasm_dir / '1__Bell_v2.0.txt').read_text(encoding='utf-8')
        lines = qasm_text.splitlines()
        self.assertEqual(lines[0], 'OPENQASM 2.0;')
        self.assertTrue(lines[1].startswith('include'))
        self.assertEqual(lines[2], '')

    def test_invalid_input_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            run_pipeline(input_mode='single')

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

    def test_preserve_custom_gates_flag_flows_to_summary(self):
        self.write_algorithms('algorithms.json', '1. Bell')

        summary = self.run_case(
            input_mode='algorithm',
            input_file='algorithms.json',
            preserve_custom_gates=False,
            **DISABLED_STAGES,
        )

        self.assertFalse(summary['preserve_custom_gates'])


if __name__ == '__main__':
    unittest.main()

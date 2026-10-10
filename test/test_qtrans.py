import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qtrans import run_pipeline


QUIRK_URL = 'https://algassert.com/quirk#circuit={"cols":[["H"],["Measure"]]}'

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

    def test_capture_function_is_called_for_each_algorithm(self):
        self.write_algorithms('algorithms.json', '1. Bell')

        with patch('qtrans.capture_quirk_circuit', return_value=True) as capture:
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
        self.assertTrue((self.run_dir / 'migrated_circuits' / 'qiskit' / '1__Bell.py').is_file())
        composer_image = self.run_dir / 'migrated_circuits' / 'qiskit' / 'imgs' / '1__Bell.png'
        self.assertTrue(composer_image.is_file())
        self.assertEqual(summary['composer_images_generated'], 1)

    def test_invalid_input_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            run_pipeline(input_mode='single')


if __name__ == '__main__':
    unittest.main()

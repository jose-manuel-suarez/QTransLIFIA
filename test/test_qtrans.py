import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qtrans import run_pipeline


QUIRK_URL = 'https://algassert.com/quirk#circuit={"cols":[["H"],["Measure"]]}'


class QTransPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.input_dir = self.root / 'input'
        self.qasm_dir = self.root / 'algorithms_qasm'
        self.images_dir = self.root / 'circuits_quirk'
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

    def test_algorithm_mode_processes_only_selected_json(self):
        self.write_algorithms('algorithms.json', '1. Bell')
        self.write_algorithms('other.json', '2. Ignored')

        summary = run_pipeline(
            input_mode='algorithm',
            input_file='algorithms.json',
            input_dir=self.input_dir,
            qasm_dir=self.qasm_dir,
            quirk_images_dir=self.images_dir,
            capture_images=False,
        )

        self.assertEqual(summary['files_processed'], 1)
        self.assertEqual(summary['algorithms_processed'], 1)
        qasm_path = self.qasm_dir / '1__Bell.txt'
        self.assertTrue(qasm_path.is_file())
        self.assertIn('OPENQASM 3.0;', qasm_path.read_text(encoding='utf-8'))
        self.assertFalse((self.qasm_dir / '2__Ignored.txt').exists())

    def test_batch_mode_processes_top_level_json_files(self):
        self.write_algorithms('algorithms.json', '1. Bell')
        self.write_algorithms('popular_algorithms.json', '1. Popular Bell')
        nested_dir = self.input_dir / 'nested'
        nested_dir.mkdir()
        (nested_dir / 'ignored.json').write_text('{}', encoding='utf-8')

        summary = run_pipeline(
            input_mode='batch',
            input_dir=self.input_dir,
            qasm_dir=self.qasm_dir,
            quirk_images_dir=self.images_dir,
            capture_images=False,
        )

        self.assertEqual(summary['files_processed'], 2)
        self.assertEqual(summary['algorithms_processed'], 2)
        self.assertTrue((self.qasm_dir / '1__Bell.txt').is_file())
        self.assertTrue((self.qasm_dir / 'popular_1__Popular_Bell.txt').is_file())
        self.assertFalse((self.qasm_dir / 'ignored.txt').exists())

    def test_capture_function_is_called_for_each_algorithm(self):
        self.write_algorithms('algorithms.json', '1. Bell')

        with patch('qtrans.capture_quirk_circuit', return_value=True) as capture:
            summary = run_pipeline(
                input_mode='algorithm',
                input_file='algorithms.json',
                input_dir=self.input_dir,
                qasm_dir=self.qasm_dir,
                quirk_images_dir=self.images_dir,
                capture_images=True,
                capture_timeout=22,
            )

        self.assertEqual(summary['captures_succeeded'], 1)
        capture.assert_called_once_with(
            QUIRK_URL,
            self.images_dir / '1__Bell.png',
            timeout=22,
        )

    def test_invalid_input_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            run_pipeline(input_mode='single')


if __name__ == '__main__':
    unittest.main()

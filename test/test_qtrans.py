import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qtrans import main, run_pipeline
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

    def test_batch_mode_with_empty_inputs_processes_all_json(self):
        self.write_algorithms('algorithms.json', '1. Bell')
        self.write_algorithms('other.json', '2. Other')

        summary = self.run_case(
            input_mode='batch',
            input_file='',
            input_files=['', '   '],
            **DISABLED_STAGES,
        )

        self.assertEqual(summary['files_processed'], 2)
        self.assertEqual(summary['algorithms_processed'], 2)
        self.assertTrue((self.qasm_dir / '1__Bell_v3.0.txt').is_file())
        self.assertTrue((self.qasm_dir / '2__Other_v3.0.txt').is_file())

    def test_batch_mode_ignores_blank_entries_and_keeps_selection(self):
        self.write_algorithms('algorithms.json', '1. Bell')
        self.write_algorithms('other.json', '2. Ignored')

        summary = self.run_case(
            input_mode='batch',
            input_files=['', 'algorithms.json'],
            **DISABLED_STAGES,
        )

        self.assertEqual(summary['files_processed'], 1)
        self.assertTrue((self.qasm_dir / '1__Bell_v3.0.txt').is_file())
        self.assertFalse((self.qasm_dir / '2__Ignored_v3.0.txt').exists())

    def test_batch_mode_rejects_non_empty_input_file(self):
        self.write_algorithms('algorithms.json', '1. Bell')

        with self.assertRaises(ValueError):
            self.run_case(input_mode='batch', input_file='algorithms.json')

    def test_cli_allows_empty_input_files_flag(self):
        from qtrans.core import build_argument_parser

        parser = build_argument_parser()
        args = parser.parse_args(['--input-mode', 'batch', '--input-files'])
        self.assertEqual(args.input_files, [])
        args = parser.parse_args(['--input-mode', 'batch', '--input-file', ''])
        self.assertEqual(args.input_file, '')

    def test_capture_function_is_called_for_each_algorithm(self):
        self.write_algorithms('algorithms.json', '1. Bell')

        with patch(
            'qtrans.utils.quirk_utils.capture_quirk_circuit', return_value=True
        ) as capture:
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

    def test_matrix_custom_gates_decompose_to_exact_unitaries(self):
        import numpy as np
        from qiskit import qasm3
        from qiskit.quantum_info import Operator

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


class JsonReportTests(unittest.TestCase):
    """--json-out vuelca un reporte con el circuito OpenQASM de cada algoritmo."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.input_dir = self.root / 'input'
        self.output_dir = self.root / 'output'
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

    def test_json_out_writes_report_with_circuit(self):
        self.write_algorithms('algorithms.json', '1. Bell')
        json_path = self.root / 'report.json'

        summary = run_pipeline(
            input_mode='algorithm',
            input_file='algorithms.json',
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            run_label='TEST',
            input_files=(),
            qasm_version='3.0',
            target_providers=('qiskit',),
            json_out=str(json_path),
            **DISABLED_STAGES,
        )

        self.assertEqual(summary['json_report_path'], json_path)
        report = json.loads(json_path.read_text(encoding='utf-8'))
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['algorithms_processed'], 1)
        self.assertEqual(len(report['algorithms']), 1)
        algorithm = report['algorithms'][0]
        self.assertEqual(algorithm['name'], '1__Bell')
        self.assertEqual(algorithm['qasm']['version'], '3.0')
        self.assertIn('OPENQASM 3.0;', algorithm['qasm']['code'])
        self.assertIn('h q[0];', algorithm['qasm']['code'])
        self.assertEqual(
            Path(algorithm['qasm']['path']),
            self.output_dir.resolve()
            / 'run_TEST'
            / 'algorithms_qasm'
            / '1__Bell_v3.0.txt',
        )
        # El reporte debe serializarse a JSON sin objetos no serializables.
        json.dumps(report)

    def test_main_json_out_dash_prints_only_json(self):
        self.write_algorithms('algorithms.json', '1. Bell')

        buffer = io.StringIO()
        with patch('sys.stdout', buffer):
            exit_code = main([
                '--input-mode', 'algorithm',
                '--input-file', 'algorithms.json',
                '--input-dir', str(self.input_dir),
                '--output-dir', str(self.output_dir),
                '--run-label', 'TEST',
                '--json-out', '-',
                '--no-capture',
                '--no-qasm-images',
                '--no-comparison',
                '--no-composer-images',
                '--no-zx',
                '--no-zx-images',
                # Neutraliza QTRANS_INPUT_FILES del .env (nargs="*" → lista vacía).
                '--input-files',
            ])

        self.assertEqual(exit_code, 0)
        report = json.loads(buffer.getvalue())
        self.assertEqual(report['algorithms_processed'], 1)
        self.assertIn('OPENQASM 3.0;', report['algorithms'][0]['qasm']['code'])


class RunDirectoryTests(unittest.TestCase):
    """La carpeta de corrida se resuelve por hora y se reutiliza."""

    def test_default_label_has_hour_resolution(self):
        from datetime import datetime

        from qtrans import core

        with patch.object(core, 'DEFAULT_RUN_LABEL', None):
            label = core._run_label()
        self.assertRegex(label, r'^\d{2}_\d{2}_\d{4}__\d{2}$')
        self.assertEqual(datetime.now().strftime('%d_%m_%Y__%H'), label)

    def test_two_runs_in_the_same_hour_share_the_directory(self):
        from qtrans.core import _run_directory

        first = _run_directory(Path("C:/tmp/out"), run_label="DD_MM_YYYY__HH")
        second = _run_directory(Path("C:/tmp/out"), run_label="DD_MM_YYYY__HH")
        self.assertEqual(first, second)
        self.assertTrue(first.name.startswith("run_"))

    def test_reused_directory_clears_previous_artifacts(self):
        from qtrans.core import (
            RUN_MIGRATED_SUBDIR,
            RUN_QASM_SUBDIR,
            _prepare_run_directory,
        )

        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "run_21_10_2026__13"
            stale_qasm = run_dir / RUN_QASM_SUBDIR / "viejo.txt"
            stale_script = run_dir / RUN_MIGRATED_SUBDIR / "ibm_qiskit" / "viejo.py"
            for stale in (stale_qasm, stale_script):
                stale.parent.mkdir(parents=True, exist_ok=True)
                stale.write_text("obsoleto", encoding="utf-8")
            (run_dir / ".qtrans_run").write_text("corrida previa", encoding="utf-8")

            _prepare_run_directory(run_dir, verbose=False)
            self.assertTrue((run_dir / ".qtrans_run").is_file())
            self.assertFalse(stale_qasm.exists())
            self.assertFalse(stale_script.exists())

    def test_foreign_directory_is_not_touched(self):
        from qtrans.core import _prepare_run_directory

        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "ajena"
            keep = run_dir / "dato.txt"
            keep.parent.mkdir(parents=True)
            keep.write_text("no borrar", encoding="utf-8")

            _prepare_run_directory(run_dir, verbose=False)
            self.assertTrue(keep.is_file())


class ConsoleEncodingTests(unittest.TestCase):
    """La salida de consola no debe abortar una etapa por símbolos no codificables.

    La consola de Windows usa ``cp1252``, que no representa ``⟩``, ``⟨`` ni ``†``;
    antes de la corrección, el mensaje de error de la etapa ZX abortaba la corrida
    entera con un ``UnicodeEncodeError``.
    """

    def _captured_stdout(self, encoding):
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding=encoding, errors="strict")
        return buffer, stream

    def test_safe_print_survives_non_encodable_characters(self):
        from qtrans.utils.pipeline_utils import safe_print

        buffer, stream = self._captured_stdout("cp1252")
        with patch.object(sys, "stdout", stream):
            safe_print("Compuerta Quirk no soportada: |+⟩⟨+|")
            stream.flush()
        self.assertIn("?", buffer.getvalue().decode("cp1252"))

    def test_safe_print_keeps_text_on_utf8_console(self):
        from qtrans.utils.pipeline_utils import safe_print

        buffer, stream = self._captured_stdout("utf-8")
        with patch.object(sys, "stdout", stream):
            safe_print("dagger †")
            stream.flush()
        self.assertIn("dagger †", buffer.getvalue().decode("utf-8"))

    def test_configure_console_encoding_is_idempotent(self):
        from qtrans.core import _configure_console_encoding

        original = sys.stdout
        try:
            _configure_console_encoding()
            _configure_console_encoding()
        finally:
            sys.stdout = original


if __name__ == '__main__':
    unittest.main()

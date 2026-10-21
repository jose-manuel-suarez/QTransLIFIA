import os
import unittest

from qtrans.utils.qutils import (
    PROVIDER_DIRECTORY,
    SUPPORTED_PROVIDERS,
    cargar_circuito_qasm,
    detect_qasm_version,
    normalize_provider,
    parse_providers,
    provider_python_source,
    providers_from_env,
)

QASM3 = """OPENQASM 3.0;
include "stdgates.inc";

qreg q[2];
creg c[1];
h q[0];
cx q[0], q[1];
c[0] = measure q[0];
"""

QASM3_PHASE = """OPENQASM 3.0;
include "stdgates.inc";

qreg q[1];
p(pi/4) q[0];
"""

QASM2 = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[1];
h q[0];
cx q[0],q[1];
measure q[0] -> c[0];
"""

QASM3_POSTSELECT = """OPENQASM 3.0;
include "stdgates.inc";

qreg q[2];
creg c[2];
creg ps[2];
h q[0];
h q[1];
ps[0] = measure q[0];
ps[1] = measure q[1];
c[0] = measure q[0];
c[1] = measure q[1];
"""


class ProviderConfigTests(unittest.TestCase):
    def test_supported_providers_and_directories(self):
        self.assertEqual(SUPPORTED_PROVIDERS, ('qiskit', 'braket', 'pennylane'))
        self.assertEqual(
            PROVIDER_DIRECTORY,
            {'qiskit': 'ibm_qiskit', 'braket': 'aws_braket', 'pennylane': 'xanadu_pennylane'},
        )

    def test_normalize_provider_accepts_aliases(self):
        self.assertEqual(normalize_provider('IBM'), 'qiskit')
        self.assertEqual(normalize_provider('aws'), 'braket')
        self.assertEqual(normalize_provider('xanadu'), 'pennylane')
        self.assertEqual(normalize_provider('ibm_qiskit'), 'qiskit')

    def test_normalize_provider_rejects_unknown(self):
        with self.assertRaises(ValueError):
            normalize_provider('cirq')

    def test_parse_providers_splits_and_deduplicates(self):
        self.assertEqual(parse_providers('qiskit,braket'), ('qiskit', 'braket'))
        self.assertEqual(parse_providers(['ibm', 'aws ', 'qiskit']), ('qiskit', 'braket'))
        with self.assertRaises(ValueError):
            parse_providers('qiskit,cirq')
        with self.assertRaises(ValueError):
            parse_providers('  , ')

    def test_providers_from_env_priority(self):
        def getenv(mapping):
            return mapping.get

        self.assertEqual(
            providers_from_env(getenv({'QTRANS_PROVIDERS': 'braket,ibm'})),
            ('braket', 'qiskit'),
        )
        self.assertEqual(
            providers_from_env(getenv({'QTRANS_TARGET_PROVIDERS': 'pennylane'})),
            ('pennylane',),
        )
        # QTRANS_PROVIDERS tiene prioridad sobre la clave legada.
        self.assertEqual(
            providers_from_env(getenv({
                'QTRANS_PROVIDERS': 'qiskit',
                'QTRANS_TARGET_PROVIDERS': 'braket',
            })),
            ('qiskit',),
        )
        self.assertEqual(providers_from_env(getenv({})), ('qiskit',))

    def test_detect_qasm_version(self):
        self.assertEqual(detect_qasm_version(QASM3), '3.0')
        self.assertEqual(detect_qasm_version(QASM2), '2.0')
        self.assertEqual(detect_qasm_version('qreg q[1];', '2.0'), '2.0')
        self.assertEqual(detect_qasm_version(''), '3.0')
        self.assertEqual(detect_qasm_version(QASM2, '3.0'), '3.0')


class CargarCircuitoQasmTests(unittest.TestCase):
    def test_qiskit_loads_qasm3_and_qasm2(self):
        from qiskit import QuantumCircuit

        for source in (QASM3, QASM2):
            circuit = cargar_circuito_qasm(source, 'qiskit')
            self.assertIsInstance(circuit, QuantumCircuit)
            self.assertEqual(circuit.num_qubits, 2)

    def test_qiskit_alias_ibm(self):
        from qiskit import QuantumCircuit

        self.assertIsInstance(cargar_circuito_qasm(QASM3, 'ibm'), QuantumCircuit)

    def test_qiskit_empty_and_unknown_provider(self):
        with self.assertRaises(ValueError):
            cargar_circuito_qasm('   ', 'qiskit')
        with self.assertRaises(ValueError):
            cargar_circuito_qasm(QASM3, 'ibm_qiskitx')

    def test_braket_native_parser(self):
        from braket.circuits import Circuit

        self.assertIsInstance(cargar_circuito_qasm(QASM3, 'aws'), Circuit)

    def test_braket_falls_back_when_native_parser_fails(self):
        # La puerta 'p' no está definida en el parser nativo de Braket.
        from braket.circuits import Circuit

        circuit = cargar_circuito_qasm(QASM3_PHASE, 'braket')
        self.assertIsInstance(circuit, Circuit)
        self.assertEqual(len(circuit.instructions), 1)

    def test_pennylane_falls_back_to_migrated_source(self):
        import pennylane as qml

        circuit = cargar_circuito_qasm(QASM3, 'xanadu')
        self.assertIsInstance(circuit, qml.QNode)

    def test_native_flag_false_uses_migrated_source(self):
        from qiskit import QuantumCircuit

        circuit = cargar_circuito_qasm(QASM3, 'qiskit', native=False)
        self.assertIsInstance(circuit, QuantumCircuit)

    def test_provider_python_source_accepts_aliases(self):
        source = provider_python_source(QASM3, 'ibm')
        compile(source, '<ibm>', 'exec')

    def test_braket_script_keeps_one_measure_per_qubit(self):
        # Las post-selecciones miden el mismo qubit dos veces (ps y c); Braket
        # sólo admite una medición por qubit y el generador las difiere al final.
        source = provider_python_source(QASM3_POSTSELECT, 'braket')
        compile(source, '<braket-postselect>', 'exec')
        self.assertEqual(source.count('circuit.measure([0])'), 1)
        self.assertEqual(source.count('circuit.measure([1])'), 1)
        self.assertIn('una sola medición por qubit', source)

    def test_braket_loads_qasm_with_repeated_measures(self):
        from braket.circuits import Circuit

        circuit = cargar_circuito_qasm(QASM3_POSTSELECT, 'braket')
        self.assertIsInstance(circuit, Circuit)
        self.assertEqual(circuit.qubit_count, 2)


if __name__ == '__main__':
    unittest.main()

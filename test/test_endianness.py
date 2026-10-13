# -*- coding: utf-8 -*-
"""Regresión de endianness: Quirk -> OpenQASM -> {Qiskit, PennyLane, AWS Braket}.

Convención confirmada (contrastada contra el código fuente de Quirk y contra las
librerías objetivo):

* **Quirk** numera los wires con el wire 0 como bit MENOS significativo
  (little-endian): ``src/circuit/KetShaderUtil.js`` usa ``_ketgen_step = 1 << ctx.row``.
  El wire 0 se dibuja arriba y su bit queda a la DERECHA en los strings de medición
  (``src/gates/SampleDisplay.js`` + ``Util.bin``).
* **OpenQASM** y **Qiskit** comparten esa convención (qubit 0 = LSB; ``counts`` con
  qubit 0 a la derecha).
* **PennyLane** y **AWS Braket** usan la representación plana opuesta: wire/qubit 0 =
  bit MÁS significativo. Braket además muestra el bitstring de medición con el
  qubit 0 a la IZQUIERDA.

Los generadores de migración siempre emiten el índice de wire explícito
(``q[k]``, ``QuantumRegister``, ``qml.<Gate>(wires=k)``, ``circuit.<gate>(k)``), por lo
que la circuitería *etiquetada* es idéntica en los tres ecosistemas. Comparar sus
matrices/estados requiere conjugar por la permutación de inversión de bits ``R``;
la semántica por wire (qué compuerta actúa sobre qué wire) no se invierte nunca.
"""

import json
import unittest
import warnings

import numpy as np
from qiskit import QuantumCircuit, qasm2, qasm3
from qiskit.circuit.library import QFTGate
from qiskit.quantum_info import Operator

from utils.qutils import provider_python_source, quirk_to_qasm

try:  # dependencia opcional (extra "providers")
    import pennylane as qml

    HAS_PENNYLANE = True
except Exception:  # pragma: no cover - entorno sin PennyLane
    HAS_PENNYLANE = False

try:  # dependencia opcional (extra "providers")
    from braket.circuits import Circuit
    from braket.devices import LocalSimulator

    HAS_BRAKET = True
except Exception:  # pragma: no cover - entorno sin Braket
    HAS_BRAKET = False


QUIRK_BASE = 'https://algassert.com/quirk#circuit='

# Circuito de 3 qubits fuertemente asimétrico bajo inversión de bits: si en algún
# eslabón se invierte el orden de los wires, la unitaria deja de coincidir.
ASYMMETRIC = [
    ['H', 'X', 'Y'],
    ['\u2022', 'X', 1],
    [1, '\u2022', 'X'],
    ['Z^\u00bd', 1, 1],
]

# Circuito con mediciones: (H;CX) prepara (|00> + |11>)/sqrt(2) sobre q0,q1.
MEASURED = [
    ['H', 1, 1],
    ['\u2022', 'X', 1],
    ['Measure', 'Measure', 'Measure'],
]


def quirk_url(cols):
    return QUIRK_BASE + json.dumps({'cols': cols})


def qasm_of(cols, qasm_version='3.0'):
    return quirk_to_qasm(quirk_url(cols), qasm_version=qasm_version)


def qiskit_circuit(cols, qasm_version='3.0'):
    """Circuito Qiskit obtenido del pipeline Quirk -> OpenQASM."""
    source = qasm_of(cols, qasm_version)
    return qasm2.loads(source) if qasm_version == '2.0' else qasm3.loads(source)


def unitary(circuit):
    return np.asarray(Operator(circuit).data, dtype=complex)


def bit_reversal_matrix(n_qubits):
    """Permutación ``R`` que invierte el orden de bits de un índice de n bits."""
    size = 1 << n_qubits
    reversal = np.zeros((size, size), dtype=complex)
    for index in range(size):
        reversed_index = int(format(index, f'0{n_qubits}b')[::-1], 2)
        reversal[index, reversed_index] = 1.0
    return reversal


def exec_source(source):
    """Ejecuta el script migrado y devuelve su espacio de nombres."""
    namespace = {}
    with warnings.catch_warnings():
        # El código generado crea el device PennyLane con ``shots=...`` (estilo
        # vigente en el proyecto); se silencian los avisos de deprecación de las
        # librerías para no ensuciar la salida de la suite.
        warnings.simplefilter('ignore')
        exec(compile(source, '<migrated>', 'exec'), namespace)
    return namespace


class QuirkToOpenQasmEndiannessTests(unittest.TestCase):
    """El wire i de Quirk es el qubit i de OpenQASM/Qiskit (little-endian)."""

    def test_qft_decomposition_matches_qiskit_qft_gate(self):
        for span in (2, 3, 4):
            with self.subTest(span=span):
                cols = [[f'QFT{span}'] + [1] * (span - 1)]
                reference = QuantumCircuit(span)
                reference.append(QFTGate(span), list(range(span)))
                np.testing.assert_allclose(
                    unitary(qiskit_circuit(cols)), unitary(reference), atol=1e-9
                )

    def test_quirk_qft_is_undone_by_its_inverse(self):
        cols = [['QFT3', 1, 1], ['QFT3\u2020', 1, 1]]
        np.testing.assert_allclose(
            unitary(qiskit_circuit(cols)), np.eye(8), atol=1e-9
        )

    def test_control_and_target_keep_wire_order(self):
        cases = {
            'cx_wire_0_1': ([['\u2022', 'X']], lambda c: c.cx(0, 1)),
            'cx_wire_1_2': ([[1, '\u2022', 'X']], lambda c: c.cx(1, 2)),
            'cx_wire_0_2': ([['\u2022', 1, 'X']], lambda c: c.cx(0, 2)),
            'ccx_wire_0_1_2': ([['\u2022', '\u2022', 'X']], lambda c: c.ccx(0, 1, 2)),
            'crx_wire_0_1': ([['\u2022', 'X^\u00bd']], lambda c: c.crx(np.pi / 2, 0, 1)),
        }
        for name, (cols, build_reference) in cases.items():
            with self.subTest(case=name):
                height = max(len(col) for col in cols)
                reference = QuantumCircuit(height)
                build_reference(reference)
                np.testing.assert_allclose(
                    unitary(qiskit_circuit(cols)), unitary(reference), atol=1e-9
                )

    def test_measurement_bit_index_equals_qubit_index(self):
        from qiskit_aer import AerSimulator

        def measure_key(cols):
            circuit = qiskit_circuit(cols + [['Measure'] * 3])
            counts = AerSimulator().run(circuit, shots=64).result().get_counts()
            return set(counts)

        # X en el wire 0 -> q0=1 y el resto 0 -> clave little-endian '001'.
        self.assertEqual(measure_key([['X', 1, 1]]), {'001'})
        # X en el wire 2 -> q2=1 -> clave '100'.
        self.assertEqual(measure_key([[1, 1, 'X']]), {'100'})

    def test_openqasm_2_and_3_agree(self):
        np.testing.assert_allclose(
            unitary(qiskit_circuit(ASYMMETRIC, '2.0')),
            unitary(qiskit_circuit(ASYMMETRIC, '3.0')),
            atol=1e-9,
        )

    def test_offset_shifts_wire_indices(self):
        source = quirk_to_qasm(quirk_url([['X']]), offset=1)
        self.assertIn('qreg q[2];', source)
        self.assertIn('x q[1];', source)
        reference = QuantumCircuit(2)
        reference.x(1)
        np.testing.assert_allclose(
            unitary(qasm3.loads(source)), unitary(reference), atol=1e-9
        )


class QiskitMigrationEndiannessTests(unittest.TestCase):
    """El script Qiskit generado reproduce el circuito sin invertir wires."""

    def test_generated_script_matches_reference_unitary(self):
        namespace = exec_source(provider_python_source(qasm_of(ASYMMETRIC), 'qiskit'))
        np.testing.assert_allclose(
            unitary(namespace['circuit']), unitary(qiskit_circuit(ASYMMETRIC)), atol=1e-9
        )

    def test_generated_script_preserves_measurement_bit_order(self):
        from qiskit_aer import AerSimulator

        namespace = exec_source(provider_python_source(qasm_of(MEASURED), 'qiskit'))
        counts = (
            AerSimulator()
            .run(namespace['circuit'], shots=256)
            .result()
            .get_counts()
        )
        # q0=q1 y q2=0; con qubit 0 a la derecha -> claves '000' y '011'.
        self.assertEqual(set(counts), {'000', '011'})


@unittest.skipUnless(HAS_PENNYLANE, 'pennylane no instalado (extra "providers")')
class PennyLaneMigrationEndiannessTests(unittest.TestCase):
    """PennyLane usa orden big-endian: la circuitería etiquetada coincide, la
    representación plana es la inversión de bits de la de Qiskit."""

    def test_generated_unitary_matches_modulo_bit_reversal(self):
        namespace = exec_source(provider_python_source(qasm_of(ASYMMETRIC), 'pennylane'))
        generated = np.asarray(
            qml.matrix(namespace['circuit'], wire_order=[0, 1, 2])(), dtype=complex
        )
        reference = unitary(qiskit_circuit(ASYMMETRIC))
        reversal = bit_reversal_matrix(3)
        np.testing.assert_allclose(generated, reversal @ reference @ reversal, atol=1e-9)
        # El circuito es asimétrico: sin conjugar NO coincide, lo que confirma que
        # la diferencia es de representación (endianness) y no un cableado erróneo.
        self.assertFalse(np.allclose(generated, reference, atol=1e-6))

    def test_measurement_samples_follow_wire_index(self):
        cols = [['X', 1, 1], ['Measure', 'Measure', 'Measure']]
        namespace = exec_source(
            provider_python_source(qasm_of(cols), 'pennylane', shots=64)
        )
        samples = namespace['circuit']()
        self.assertEqual(len(samples), 3)
        for wire, values in enumerate(samples):
            expected = 1 if wire == 0 else 0
            self.assertTrue(np.all(np.asarray(values) == expected))

    def test_pennylane_flat_state_is_big_endian(self):
        device = qml.device('default.qubit', wires=2)

        @qml.qnode(device)
        def probe():
            qml.PauliX(wires=0)
            return qml.state()

        # wire 0 = bit más significativo -> índice 2 (binario '10').
        self.assertEqual(int(np.argmax(np.abs(np.asarray(probe())))), 2)


@unittest.skipUnless(HAS_BRAKET, 'amazon-braket-sdk no instalado (extra "providers")')
class BraketMigrationEndiannessTests(unittest.TestCase):
    """AWS Braket también usa orden big-endian y muestra el qubit 0 a la izquierda."""

    def test_generated_unitary_matches_modulo_bit_reversal(self):
        namespace = exec_source(provider_python_source(qasm_of(ASYMMETRIC), 'braket'))
        generated = np.asarray(namespace['circuit'].to_unitary(), dtype=complex)
        reference = unitary(qiskit_circuit(ASYMMETRIC))
        reversal = bit_reversal_matrix(3)
        np.testing.assert_allclose(generated, reversal @ reference @ reversal, atol=1e-9)
        self.assertFalse(np.allclose(generated, reference, atol=1e-6))

    def test_generated_measurement_bitstring_is_reversed_vs_qiskit(self):
        cols = [['X', 1, 1], ['Measure', 'Measure', 'Measure']]
        namespace = exec_source(provider_python_source(qasm_of(cols), 'braket'))
        counts = (
            LocalSimulator()
            .run(namespace['circuit'], shots=64)
            .result()
            .measurement_counts
        )
        # Braket muestra el qubit 0 a la izquierda: '100' (Qiskit daría '001').
        self.assertEqual(set(counts), {'100'})

    def test_braket_flat_state_is_big_endian(self):
        circuit = Circuit().x(0).i(1)
        circuit.state_vector()
        state = np.asarray(
            LocalSimulator().run(circuit, shots=0).result().values[0]
        )
        # qubit 0 = bit más significativo -> índice 2.
        self.assertEqual(int(np.argmax(np.abs(state))), 2)


if __name__ == '__main__':
    unittest.main()

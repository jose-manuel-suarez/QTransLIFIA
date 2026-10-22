"""Pruebas de la API de objetos ``translate_circuits`` (circuitos nativos por proveedor)."""

import json
import unittest

from qtrans import translate_circuits


CUSTOM_CIRCUIT = {
    "cols": [["H", "~mvx"], ["•", "X"]],
    "gates": [
        {
            "id": "~mvx",
            "name": "MultiX",
            "circuit": {"cols": [["X", "X"]]},
        }
    ],
}
QUIRK_URL = "https://algassert.com/quirk#circuit=" + json.dumps(
    CUSTOM_CIRCUIT, ensure_ascii=False
)


class TranslateCircuitsTests(unittest.TestCase):
    def test_returns_dict_keyed_by_provider_and_circuit_name(self):
        response = translate_circuits(
            {"input": {"url": QUIRK_URL, "provider": ["qiskit", "braket"]}}
        )

        self.assertEqual({"input", "circuits"}, set(response))
        self.assertEqual({"qiskit", "braket"}, set(response["circuits"]))
        for provider in ("qiskit", "braket"):
            self.assertEqual(["circuit_1"], list(response["circuits"][provider]))

    def test_circuits_are_provider_native_objects(self):
        from braket.circuits import Circuit
        from qiskit import QuantumCircuit

        response = translate_circuits(
            {"input": {"url": QUIRK_URL, "provider": ["qiskit", "braket"]}}
        )

        qiskit_circuit = response["circuits"]["qiskit"]["circuit_1"]
        braket_circuit = response["circuits"]["braket"]["circuit_1"]
        self.assertIsInstance(qiskit_circuit, QuantumCircuit)
        self.assertIsInstance(braket_circuit, Circuit)
        self.assertEqual(qiskit_circuit.num_qubits, braket_circuit.qubit_count)

    def test_batch_uses_names_from_input(self):
        response = translate_circuits(
            {
                "input": {
                    "circuits": [
                        {"name": "alpha", "url": QUIRK_URL},
                        {"name": "beta", "url": QUIRK_URL},
                    ],
                    "provider": "qiskit",
                }
            }
        )

        self.assertEqual(["alpha", "beta"], list(response["circuits"]["qiskit"]))

    def test_pennylane_circuit_is_a_qnode(self):
        import pennylane as qml

        response = translate_circuits(
            {"input": {"url": QUIRK_URL, "provider": "pennylane", "shots": 32}}
        )

        self.assertIsInstance(response["circuits"]["pennylane"]["circuit_1"], qml.QNode)

    def test_qasm_version_2_is_supported(self):
        from qiskit import QuantumCircuit

        response = translate_circuits(
            {
                "input": {
                    "url": QUIRK_URL,
                    "qasm_version": "2.0",
                    "provider": ["qiskit", "braket"],
                }
            }
        )

        self.assertIsInstance(response["circuits"]["qiskit"]["circuit_1"], QuantumCircuit)
        self.assertIn("braket", response["circuits"])

    def test_invalid_payload_raises_value_error(self):
        with self.assertRaises(ValueError):
            translate_circuits({"input": {"url": QUIRK_URL, "desconocida": 1}})
        with self.assertRaises(ValueError):
            translate_circuits({"input": {}})


if __name__ == "__main__":
    unittest.main()

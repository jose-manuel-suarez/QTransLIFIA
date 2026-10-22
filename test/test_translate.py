import base64
import json
import unittest

from qiskit import QuantumCircuit

from qtrans import translate_circuit


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

OUTPUT_KEYS = {
    "qasm",
    "migrated_code",
    "circuits",
    "zx_calculus_result",
    "circuit_info",
    "custom_gates",
    "img",
    "comparison_doc",
    "errors",
}
INPUT_KEYS = {
    "url",
    "offset",
    "qasm_version",
    "provider",
    "shots",
    "preserve_custom_gates",
    "zx",
    "images",
    "comparison",
    "return_circuit",
}
QASM_KEYS = {"code", "version", "lines", "gates"}


class TranslateSingleTests(unittest.TestCase):
    def test_single_url_response_structure(self):
        response = translate_circuit({"input": {"url": QUIRK_URL}})

        self.assertEqual({"input", "output"}, set(response))
        self.assertEqual(INPUT_KEYS, set(response["input"]))
        output = response["output"]
        self.assertEqual(OUTPUT_KEYS, set(output))
        self.assertNotIn("name", output)

        self.assertEqual(QASM_KEYS, set(output["qasm"]))
        self.assertTrue(output["qasm"]["code"].startswith("OPENQASM 3.0;"))
        self.assertEqual("3.0", output["qasm"]["version"])
        self.assertEqual(len(output["qasm"]["code"].splitlines()), output["qasm"]["lines"])
        self.assertIn("qreg q[3];", output["qasm"]["code"])
        self.assertEqual(
            {"custom": {"count": 1, "names": ["MultiX"]},
             "native": {"count": 2, "names": ["h", "x"]}},
            output["qasm"]["gates"],
        )
        self.assertEqual(["qiskit"], response["input"]["provider"])
        self.assertEqual({"ibm_qiskit_code"}, set(output["migrated_code"]))
        self.assertIn("qiskit", output["migrated_code"]["ibm_qiskit_code"])
        self.assertIn(
            output["zx_calculus_result"],
            {"equivalente", "no-equivalente", "no-comprobado"},
        )
        self.assertEqual(3, output["circuit_info"]["n_qubits"])
        self.assertEqual({"n_qubits", "n_cols", "gates"}, set(output["circuit_info"]))
        self.assertEqual({"quirk": None, "qasm": None, "composer": None}, output["img"])
        self.assertIsNone(output["circuits"])
        self.assertIsNone(output["comparison_doc"])
        self.assertEqual([], output["errors"])

    def test_response_is_json_serializable(self):
        response = translate_circuit({"input": {"json": CUSTOM_CIRCUIT}})

        self.assertEqual(response, json.loads(json.dumps(response)))

    def test_json_input_resolves_effective_url(self):
        response = translate_circuit({"input": {"json": CUSTOM_CIRCUIT}})

        self.assertTrue(response["input"]["url"].startswith(
            "https://algassert.com/quirk#circuit="
        ))
        self.assertNotIn("json", response["input"])

    def test_json_string_payload(self):
        payload = json.dumps({"input": {"json": json.dumps(CUSTOM_CIRCUIT)}})

        response = translate_circuit(payload)

        self.assertEqual(1, response["output"]["qasm"]["gates"]["custom"]["count"])

    def test_measurement_reported_by_name(self):
        response = translate_circuit({"input": {"json": {"cols": [["H"], ["Measure"]]}}})

        self.assertEqual(
            {"custom": {"count": 0, "names": []},
             "native": {"count": 2, "names": ["h", "measure"]}},
            response["output"]["qasm"]["gates"],
        )

    def test_qasm_2_multi_provider(self):
        response = translate_circuit(
            {
                "input": {
                    "url": QUIRK_URL,
                    "qasm_version": "2.0",
                    "provider": ["qiskit", "aws"],
                }
            }
        )
        qasm = response["output"]["qasm"]

        self.assertTrue(qasm["code"].startswith("OPENQASM 2.0;"))
        self.assertEqual("2.0", qasm["version"])
        self.assertEqual(
            {"ibm_qiskit_code", "aws_braket_code"},
            set(response["output"]["migrated_code"]),
        )
        for code in response["output"]["migrated_code"].values():
            compile(code, "<test>", "exec")
        self.assertEqual(1, qasm["gates"]["custom"]["count"])
        self.assertEqual(2, qasm["gates"]["native"]["count"])

    def test_offset_shifts_qubit_indices(self):
        response = translate_circuit({"input": {"url": QUIRK_URL, "offset": 1}})
        code = response["output"]["qasm"]["code"]

        self.assertIn("qreg q[4];", code)
        self.assertIn("h q[1];", code)
        self.assertEqual(1, response["input"]["offset"])

    def test_zx_disabled_returns_none(self):
        response = translate_circuit(
            {"input": {"url": QUIRK_URL, "zx": {"enabled": False}}}
        )

        self.assertIsNone(response["output"]["zx_calculus_result"])

    def test_qasm_image_base64_and_comparison_doc(self):
        response = translate_circuit(
            {
                "input": {
                    "url": QUIRK_URL,
                    "images": {"qasm": True},
                    "comparison": True,
                }
            }
        )
        output = response["output"]

        png = base64.b64decode(output["img"]["qasm"])
        self.assertTrue(png.startswith(b"\x89PNG"))
        self.assertIn("OPENQASM", output["comparison_doc"])
        self.assertIn("[Abrir en Quirk](", output["comparison_doc"])
        self.assertIsNone(output["img"]["composer"])

    def test_return_circuit_returns_native_objects(self):
        response = translate_circuit(
            {"input": {"url": QUIRK_URL, "return_circuit": True}}
        )
        circuits = response["output"]["circuits"]

        self.assertEqual({"qiskit"}, set(circuits))
        self.assertIsInstance(circuits["qiskit"], QuantumCircuit)
        self.assertEqual(3, circuits["qiskit"].num_qubits)
        # El resto de la respuesta sigue siendo utilizable.
        self.assertTrue(response["output"]["qasm"]["code"].startswith("OPENQASM 3.0;"))

    def test_return_circuit_rejected_in_batch_mode(self):
        with self.assertRaises(ValueError):
            translate_circuit(
                {"input": {"circuits": [{"url": QUIRK_URL}], "return_circuit": True}}
            )

    def test_invalid_payloads_raise_value_error(self):
        invalid_payloads = (
            {},
            {"input": None},
            {"input": {}, "extra": 1},
            {"input": {"url": QUIRK_URL, "json": CUSTOM_CIRCUIT}},
            {"input": {"url": QUIRK_URL, "circuits": []}},
            {"input": {"circuits": []}},
            {"input": {"circuits": "no-lista"}},
            {"input": {"circuits": [{"url": QUIRK_URL, "extra": 1}]}},
            {"input": {"url": QUIRK_URL, "desconocido": 1}},
            {"input": {"url": QUIRK_URL, "zx": {"no_existe": 1}}},
            {"input": {"url": QUIRK_URL, "images": {"no_existe": 1}}},
            {"input": {"url": "https://algassert.com/quirk"}},
            {"input": {"json": {"cols": "no-lista"}}},
            {"input": {"json": "no-es-json"}},
            {"input": {"url": QUIRK_URL, "qasm_version": "4.0"}},
            {"input": {"url": QUIRK_URL, "provider": "quantinuum"}},
            {"input": {"url": QUIRK_URL, "offset": -1}},
            {"input": {"url": QUIRK_URL, "shots": 0}},
            {"input": {"url": QUIRK_URL, "zx": {"time": 2}}},
            {"input": {"url": QUIRK_URL, "images": "no-objeto"}},
            {"input": {"url": QUIRK_URL, "return_circuit": "true"}},
            "payload-no-json",
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    translate_circuit(payload)


class TranslateBatchTests(unittest.TestCase):
    def test_batch_returns_list_with_names(self):
        response = translate_circuit(
            {
                "input": {
                    "circuits": [
                        {"name": "Bell", "url": QUIRK_URL},
                        {"json": CUSTOM_CIRCUIT, "offset": 2},
                    ]
                }
            }
        )

        self.assertIsInstance(response["output"], list)
        self.assertEqual(2, len(response["output"]))
        self.assertEqual("Bell", response["output"][0]["name"])
        self.assertEqual("circuit_2", response["output"][1]["name"])
        for item in response["output"]:
            self.assertEqual(OUTPUT_KEYS | {"name"}, set(item))
        self.assertIn("h q[2];", response["output"][1]["qasm"]["code"])

    def test_batch_global_settings_apply_to_all(self):
        response = translate_circuit(
            {
                "input": {
                    "circuits": [
                        {"name": "A", "json": CUSTOM_CIRCUIT},
                        {"name": "B", "json": CUSTOM_CIRCUIT},
                    ],
                    "qasm_version": "2.0",
                    "provider": ["qiskit", "pennylane"],
                    "zx": {"enabled": False},
                }
            }
        )

        for item in response["output"]:
            self.assertTrue(item["qasm"]["code"].startswith("OPENQASM 2.0;"))
            self.assertEqual(
                {"ibm_qiskit_code", "xanadu_pennylane_code"},
                set(item["migrated_code"]),
            )
            self.assertIsNone(item["zx_calculus_result"])


if __name__ == "__main__":
    unittest.main()

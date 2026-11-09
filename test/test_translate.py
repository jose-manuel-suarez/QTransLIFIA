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
MATRIX_4X4_CIRCUIT = {
    "cols": [["~4x4"]],
    "gates": [
        {
            "id": "~4x4",
            "name": "4x4",
            "matrix": "{{1,0,0,0},{0,1,0,0},{0,0,1,0},{0,0,0,1}}",
        }
    ],
}
CONTROLLED_MATRIX_CIRCUIT = {
    "cols": [["•", "~m4"]],
    "gates": [
        {
            "id": "~m4",
            "name": "M4",
            "matrix": (
                "{{0.7071067811865476+0.7071067811865475i,0,0,0},"
                "{0,0,0.7071067811865476+0.7071067811865475i,0},"
                "{0,0.7071067811865476+0.7071067811865475i,0,0},"
                "{0,0,0,0.7071067811865476+0.7071067811865475i}}"
            ),
        }
    ],
}
POSTSELECT_CIRCUIT = {
    "cols": [["|+⟩⟨+|"]],
}
NATIVE_CIRCUIT = {
    "cols": [["H"], ["•", "X"]],
}
CONTROLLED_COMPOSITE_CIRCUIT = {
    "cols": [["•", "~cg"]],
    "gates": [
        {
            "id": "~cg",
            "name": "CG",
            "circuit": {
                "cols": [["H", "X"], ["•", "X"], ["Z^½", "Y^¼"]],
            },
        }
    ],
}
WIDE_COMPOSITE_CIRCUIT = {
    "cols": [["~wg"]],
    "gates": [
        {
            "id": "~wg",
            "name": "WideX",
            "circuit": {"cols": [[1, 1, "X"]]},
        }
    ],
}
WIDE_CONTROLLED_COMPOSITE_CIRCUIT = {
    "cols": [["•", "~wg"]],
    "gates": [
        {
            "id": "~wg",
            "name": "WideX",
            "circuit": {"cols": [[1, 1, "X"]]},
        }
    ],
}

OUTPUT_KEYS = {
    "qasm",
    "migrated_code",
    "circuits",
    "zx_calculus",
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
        self.assertEqual("qiskit", response["input"]["provider"])
        self.assertEqual({"ibm_qiskit_code"}, set(output["migrated_code"]))
        self.assertIn("qiskit", output["migrated_code"]["ibm_qiskit_code"])
        self.assertIn(
            output["zx_calculus"]["result"],
            {"equivalente", "no-equivalente", "no-comprobado"},
        )
        self.assertEqual(
            output["zx_calculus"]["result"], output["zx_calculus"]["result"]
        )
        self.assertIsInstance(output["zx_calculus"]["errors"], list)
        self.assertIn(
            output["zx_calculus"]["method"], {"directo", "aplanado", None}
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

    def test_qasm_2_single_provider(self):
        response = translate_circuit(
            {
                "input": {
                    "url": QUIRK_URL,
                    "qasm_version": "2.0",
                    "provider": "aws",
                }
            }
        )
        qasm = response["output"]["qasm"]

        self.assertTrue(qasm["code"].startswith("OPENQASM 2.0;"))
        self.assertEqual("2.0", qasm["version"])
        self.assertEqual("braket", response["input"]["provider"])
        self.assertEqual(
            {"aws_braket_code"},
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

        self.assertIsNone(response["output"]["zx_calculus"]["result"])
        self.assertEqual(
            response["output"]["zx_calculus"],
            {"result": None, "errors": [], "method": None, "comparison_method": None},
        )

    def test_zx_calculus_flattens_4x4_matrix(self):
        response = translate_circuit(
            {"input": {"json": MATRIX_4X4_CIRCUIT, "zx": {"enabled": True}}}
        )

        zx_calculus = response["output"]["zx_calculus"]
        self.assertEqual("equivalente", zx_calculus["result"])
        self.assertEqual("equivalente", response["output"]["zx_calculus"]["result"])
        self.assertEqual([], zx_calculus["errors"])
        self.assertEqual("aplanado", zx_calculus["method"])

    def test_zx_calculus_flattens_controlled_matrix_gate(self):
        response = translate_circuit(
            {
                "input": {
                    "json": CONTROLLED_MATRIX_CIRCUIT,
                    "zx": {"enabled": True},
                }
            }
        )

        zx_calculus = response["output"]["zx_calculus"]
        self.assertEqual("equivalente", zx_calculus["result"])
        self.assertEqual([], zx_calculus["errors"])
        self.assertEqual("aplanado", zx_calculus["method"])

    def test_zx_calculus_flattens_controlled_composite_gate(self):
        response = translate_circuit(
            {
                "input": {
                    "json": CONTROLLED_COMPOSITE_CIRCUIT,
                    "zx": {"enabled": True},
                }
            }
        )

        zx_calculus = response["output"]["zx_calculus"]
        self.assertEqual("equivalente", zx_calculus["result"])
        self.assertEqual([], zx_calculus["errors"])
        self.assertEqual("aplanado", zx_calculus["method"])

    def test_zx_calculus_flattens_wide_composite_gate(self):
        response = translate_circuit(
            {"input": {"json": WIDE_COMPOSITE_CIRCUIT, "zx": {"enabled": True}}}
        )

        zx_calculus = response["output"]["zx_calculus"]
        self.assertEqual("equivalente", zx_calculus["result"])
        self.assertEqual([], zx_calculus["errors"])
        self.assertEqual("aplanado", zx_calculus["method"])
        self.assertIn("x c;", response["output"]["qasm"]["code"])

    def test_zx_calculus_flattens_wide_controlled_composite_gate(self):
        response = translate_circuit(
            {
                "input": {
                    "json": WIDE_CONTROLLED_COMPOSITE_CIRCUIT,
                    "zx": {"enabled": True},
                }
            }
        )

        zx_calculus = response["output"]["zx_calculus"]
        self.assertEqual("equivalente", zx_calculus["result"])
        self.assertEqual([], zx_calculus["errors"])
        self.assertEqual("aplanado", zx_calculus["method"])

    def test_zx_calculus_native_circuit_is_direct(self):
        response = translate_circuit(
            {"input": {"json": NATIVE_CIRCUIT, "zx": {"enabled": True}}}
        )

        zx_calculus = response["output"]["zx_calculus"]
        self.assertEqual("equivalente", zx_calculus["result"])
        self.assertEqual([], zx_calculus["errors"])
        self.assertEqual("directo", zx_calculus["method"])

    def test_zx_calculus_captures_stage_errors(self):
        response = translate_circuit(
            {"input": {"json": POSTSELECT_CIRCUIT, "zx": {"enabled": True}}}
        )

        zx_calculus = response["output"]["zx_calculus"]
        self.assertEqual("no-comprobado", zx_calculus["result"])
        self.assertEqual("no-comprobado", response["output"]["zx_calculus"]["result"])
        self.assertEqual(1, len(zx_calculus["errors"]))
        self.assertEqual("zx", zx_calculus["errors"][0]["stage"])
        self.assertIsNone(zx_calculus["method"])

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

    def test_batch_return_circuit_returns_object_per_url(self):
        response = translate_circuit(
            {
                "input": {
                    "circuits": [
                        {"name": "A", "url": QUIRK_URL},
                        {"name": "B", "url": QUIRK_URL},
                    ],
                    "provider": "qiskit",
                    "return_circuit": True,
                    "zx": {"enabled": False},
                }
            }
        )
        output = response["output"]

        self.assertEqual(2, len(output))
        self.assertEqual(["A", "B"], [item["name"] for item in output])
        for item in output:
            self.assertEqual({"qiskit"}, set(item["circuits"]))
            self.assertIsInstance(item["circuits"]["qiskit"], QuantumCircuit)

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
            {"input": {"url": QUIRK_URL, "provider": ["qiskit"]}},
            {"input": {"url": QUIRK_URL, "provider": "qiskit,braket"}},
            {"input": {"url": QUIRK_URL, "provider": ""}},
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
                    "provider": "pennylane",
                    "zx": {"enabled": False},
                }
            }
        )

        for item in response["output"]:
            self.assertTrue(item["qasm"]["code"].startswith("OPENQASM 2.0;"))
            self.assertEqual(
                {"xanadu_pennylane_code"},
                set(item["migrated_code"]),
            )
            self.assertIsNone(item["zx_calculus"]["result"])
            self.assertEqual(
                item["zx_calculus"],
                {"result": None, "errors": [], "method": None, "comparison_method": None},
            )


if __name__ == "__main__":
    unittest.main()

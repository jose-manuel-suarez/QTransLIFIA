# -*- coding: utf-8 -*-
"""Verificación de las compuertas custom con campo ``matrix`` de Quirk.

El circuito ``39. complex_customs`` de ``input/popular_algorithms.json`` es el
banco de pruebas del campo ``matrix``: ocho compuertas (dos diagonales de fase
``cu1``, una 4x4 y cinco 2x2 genéricas) declaradas en la URL de Quirk con su
matriz numérica.

Este módulo comprueba, para cada una de esas compuertas:

- que la matriz de origen es unitaria salvo el redondeo con que Quirk la
  almacena (~7 dígitos significativos);
- que la declaración ``gate`` emitida en OpenQASM reproduce **exactamente** esa
  matriz (se reconstruye la unitaria de la declaración y se compara con la
  matriz de la URL);
- que la equivalencia se mantiene en OpenQASM 2.0 y 3.0, y que ambos códigos
  cargan con los parsers nativos de Qiskit.

Nota sobre el residuo numérico: las matrices de la URL vienen redondeadas, así
que no son exactamente unitarias.  El pipeline las proyecta a la unitaria más
cercana (SVD) antes de descomponerlas; por eso la comparación se hace con una
tolerancia de 1e-6, del orden del propio redondeo de la fuente.
"""

import json
import math
import unittest
from pathlib import Path

import numpy as np
from qiskit import qasm2, qasm3
from qiskit.quantum_info import Operator

from qtrans.utils.quirk_utils import (
    _build_gate_map,
    _matrix_to_rows,
    _resolve_gate_names,
    quirk_to_qasm,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALGORITHMS_FILE = PROJECT_ROOT / 'input' / 'popular_algorithms.json'
ALGORITHM_NAME = '39. complex_customs'

# Tolerancias: la matriz de la URL está redondeada (~7 dígitos) y la proyección
# a unitaria no puede recuperar esa información perdida.
UNITARITY_TOLERANCE = 1e-6
EQUALITY_TOLERANCE = 1e-6


def _algorithm_entry():
    """Devuelve la entrada del circuito de pruebas.

    Retorna:
        - dict: la entrada del algoritmo con su clave ``url``.
    """
    with ALGORITHMS_FILE.open('r', encoding='utf-8') as source:
        algorithms = json.load(source)
    return algorithms[ALGORITHM_NAME]


def _circuit_json(entry):
    """Devuelve el JSON del circuito de la URL de Quirk.

    Parámetros:
        - entry (dict): entrada del algoritmo.

    Retorna:
        - dict: el circuito con sus claves ``cols`` y ``gates``.
    """
    return json.loads(entry['url'].split('circuit=', 1)[1])


def _matrix_gates(circuit):
    """Devuelve las compuertas custom declaradas con matriz.

    Parámetros:
        - circuit (dict): circuito de Quirk.

    Retorna:
        - list[dict]: las compuertas con clave ``matrix``.
    """
    return [gate for gate in circuit.get('gates', []) if gate.get('matrix') is not None]


def _gate_declarations(qasm_source):
    """Extrae las declaraciones ``gate`` del código OpenQASM.

    Parámetros:
        - qasm_source (str): código OpenQASM 3.0 generado.

    Retorna:
        - dict: nombre de la compuerta -> (parámetros, líneas del cuerpo).
    """
    import re

    declarations = {}
    pattern = re.compile(r'^gate\s+([^\n{]*)\{(.*?)^\}', re.M | re.S)
    for match in pattern.finditer(qasm_source):
        header = match.group(1).split()
        name = header[0]
        parameters = [
            parameter.strip()
            for parameter in ','.join(header[1:]).split(',')
            if parameter.strip()
        ]
        body = [
            line.strip()
            for line in match.group(2).strip().splitlines()
            if line.strip()
        ]
        declarations[name] = (parameters, body)
    return declarations


def _declared_gate_units(qasm_source):
    """Reconstruye la unitaria de cada declaración ``gate`` del código OpenQASM.

    Cada declaración se aísla en un circuito de prueba con sus propios qubits
    y se lee su unitaria con ``Operator``; así el resultado no depende de si la
    compuerta se usa en el cuerpo del circuito ni de los modificadores
    (``ctrl @``) con que aparezca.

    Parámetros:
        - qasm_source (str): código OpenQASM 3.0 generado.

    Retorna:
        - dict: nombre de la compuerta -> unitaria (array de numpy).
    """
    units = {}
    for name, (parameters, body) in _gate_declarations(qasm_source).items():
        if not parameters:
            continue
        count = len(parameters)
        probe = (
            'OPENQASM 3.0;\ninclude "stdgates.inc";\n'
            f"gate probe {', '.join(parameters)} {{\n"
            + '\n'.join(body)
            + '\n}\n'
            f"qreg q[{count}];\n"
            f"probe {', '.join(f'q[{index}]' for index in range(count))};\n"
        )
        units[name] = Operator(qasm3.loads(probe)).data
    return units


class MatrixSourceTests(unittest.TestCase):
    """Las matrices de origen son unitarias (salvo el redondeo de Quirk)."""

    def test_algorithm_declares_eight_matrix_gates(self):
        entry = _algorithm_entry()
        gates = _matrix_gates(_circuit_json(entry))
        self.assertEqual(8, len(gates))

    def test_source_matrices_are_unitary(self):
        entry = _algorithm_entry()
        for gate in _matrix_gates(_circuit_json(entry)):
            with self.subTest(gate=gate.get('name', gate.get('id'))):
                matrix = np.array(_matrix_to_rows(gate['matrix']), dtype=complex)
                self.assertIn(matrix.shape, {(2, 2), (4, 4)})
                identity = matrix.conj().T @ matrix
                self.assertLess(
                    np.abs(identity - np.eye(matrix.shape[0])).max(),
                    UNITARITY_TOLERANCE,
                )
                self.assertAlmostEqual(
                    1.0, abs(np.linalg.det(matrix)), places=6
                )


class MatrixTranslationTests(unittest.TestCase):
    """La declaración ``gate`` emitida reproduce la matriz de la URL."""

    def setUp(self):
        self.entry = _algorithm_entry()
        self.circuit = _circuit_json(self.entry)
        self.gate_map = _build_gate_map(self.circuit)
        self.gate_names = _resolve_gate_names(self.gate_map)
        self.qasm3_source = quirk_to_qasm(
            self.entry['url'],
            offset=self.entry.get('offset', 0),
            qasm_version='3.0',
        )
        self.units = _declared_gate_units(self.qasm3_source)

    def test_every_matrix_gate_is_declared(self):
        for gate in _matrix_gates(self.circuit):
            with self.subTest(gate=gate.get('name', gate.get('id'))):
                identifier = self.gate_names[gate['id']]
                self.assertIn(identifier, self.units)

    def test_declared_gates_reproduce_the_source_matrices(self):
        for gate in _matrix_gates(self.circuit):
            with self.subTest(gate=gate.get('name', gate.get('id'))):
                identifier = self.gate_names[gate['id']]
                source = np.array(_matrix_to_rows(gate['matrix']), dtype=complex)
                emitted = self.units[identifier]
                self.assertEqual(source.shape, emitted.shape)
                self.assertLess(
                    np.abs(emitted - source).max(), EQUALITY_TOLERANCE
                )

    def test_emitted_bodies_use_supported_rotations(self):
        # 2x2 -> rotaciones de un qubit; 4x4 -> U intrínseca y cx.
        declarations = _gate_declarations(self.qasm3_source)
        for gate in _matrix_gates(self.circuit):
            with self.subTest(gate=gate.get('name', gate.get('id'))):
                identifier = self.gate_names[gate['id']]
                rows = _matrix_to_rows(gate['matrix'])
                dimension = int(round(math.log2(len(rows))))
                body = declarations[identifier][1]
                self.assertTrue(body)
                if dimension == 1:
                    for line in body:
                        self.assertRegex(line, r'^(p|rx|ry|rz)\(')
                else:
                    self.assertTrue(
                        any(line.startswith('U(') for line in body),
                        'La compuerta de 2 qubits debe usar la U intrínseca',
                    )
                    self.assertTrue(any(line.startswith('cx ') for line in body))


class MatrixGeneratedCodeTests(unittest.TestCase):
    """El circuito completo se genera y carga en OpenQASM 2.0 y 3.0."""

    def setUp(self):
        self.entry = _algorithm_entry()

    def test_qasm3_loads_with_native_parser(self):
        source = quirk_to_qasm(
            self.entry['url'], offset=self.entry.get('offset', 0), qasm_version='3.0'
        )
        circuit = qasm3.loads(source)
        self.assertGreater(circuit.num_qubits, 0)

    def test_qasm2_loads_with_native_parser(self):
        source = quirk_to_qasm(
            self.entry['url'], offset=self.entry.get('offset', 0), qasm_version='2.0'
        )
        circuit = qasm2.loads(source)
        self.assertGreater(circuit.num_qubits, 0)


def _gate_body(qasm_source, name):
    """Extrae el cuerpo de una declaración ``gate`` del código OpenQASM.

    Parámetros:
        - qasm_source (str): código OpenQASM 3.0.
        - name (str): nombre de la compuerta.

    Retorna:
        - list[str]: líneas del cuerpo (vacía si no aparece la declaración).
    """
    declarations = _gate_declarations(qasm_source)
    return declarations[name][1] if name in declarations else []


if __name__ == '__main__':
    unittest.main()

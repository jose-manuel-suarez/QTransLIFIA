# -*- coding: utf-8 -*-
"""Validación numérica: matriz de la URL de Quirk vs. unitaria del OpenQASM.

``test_matrix_customs.py`` valida en detalle las ocho matrices del circuito
``39. complex_customs``; este módulo hace la **barrida exhaustiva**: recorre
TODAS las baterías de ``input/*.json``, localiza cada compuerta custom
declarada con campo ``matrix`` y comprueba que la unitaria de la declaración
``gate`` emitida en OpenQASM 3.0 reproduce la matriz de la URL.

La comparación es **exacta, incluida la fase global** (no módulo fase): el
pipeline materializa la fase global con la identidad ``e^{i·g}·I =
p(2g)·rz(-2g)``, de modo que un error de fase se detecta igual que un error
de rotación. El corpus cubre los cuatro caminos de descomposición:

- operación única por ``name`` con forma ``op(args)`` (``ry(0.36...)``,
  ``cu1(pi/8)``, ``cp(-7*pi/8)``, ``rz(pi/2)``);
- fase diagonal conocida (``U(-pi/4)`` -> ``p(-pi/4)``);
- unitaria 2x2 genérica -> ``p`` + ZYZ (``rz``/``ry``/``rz``);
- unitaria 4x4 genérica -> KAK (``U`` intrínseca + ``cx``).

Tolerancia 1e-6: las matrices de la URL vienen redondeadas (~7-10 dígitos
significativos), por lo que no son exactamente unitarias y el pipeline las
proyecta a la unitaria más cercana (SVD) antes de descomponerlas; el peor
residuo del corpus actual es 4.927e-08 (``mia``, circuito 39).

Además se comprueba que cada entrada se carga con los parsers nativos de
OpenQASM 2.0 y 3.0, y que las matrices de origen son unitarias.
"""

import json
import re
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
INPUT_DIR = PROJECT_ROOT / 'input'

# Tolerancias: el redondeo de la fuente (~7-10 dígitos) y la proyección a
# unitaria no pueden recuperar la información perdida.
UNITARITY_TOLERANCE = 1e-6
EQUALITY_TOLERANCE = 1e-6

# Cobertura esperada del corpus (fijada para que un fallo de descubrimiento
# rompa el test en lugar de reducir silenciosamente la validación).
EXPECTED_FILES_SCANNED = 6
EXPECTED_MATRIX_GATES_PER_FILE = {
    'main_algorithms.json': 2,
    'popular_algorithms.json': 52,
}

_DECLARATION_RE = re.compile(r'^gate\s+([^\n{]*)\{(.*?)^\}', re.M | re.S)


def _circuit_json(entry):
    """Devuelve el JSON del circuito de la URL de Quirk.

    Parámetros:
        - entry (dict): entrada del algoritmo con su clave ``url``.

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
    return [
        gate for gate in circuit.get('gates', [])
        if gate.get('matrix') is not None
    ]


def _gate_declarations(qasm_source):
    """Extrae las declaraciones ``gate`` del código OpenQASM.

    Parámetros:
        - qasm_source (str): código OpenQASM 3.0 generado.

    Retorna:
        - dict: nombre de la compuerta -> (parámetros, líneas del cuerpo).
    """
    declarations = {}
    for match in _DECLARATION_RE.finditer(qasm_source):
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


def _render_declaration(name, parameters, body):
    """Renderiza una declaración ``gate`` completa.

    Parámetros:
        - name (str): nombre de la compuerta.
        - parameters (list[str]): argumentos (qubits) de la compuerta.
        - body (list[str]): líneas del cuerpo.

    Retorna:
        - str: la declaración OpenQASM formateada.
    """
    head = f"gate {name} {', '.join(parameters)}" if parameters else f"gate {name}"
    return head + " {\n" + "\n".join(body) + "\n}"


def _declared_gate_units(qasm_source):
    """Reconstruye la unitaria de cada declaración ``gate`` del código.

    Cada compuerta se invoca en un circuito de prueba con TODAS las
    declaraciones presentes (en su orden original, que es el topológico):
    así una declaración que referencie a otra resuelve igual que en el
    circuito real y el resultado no depende de los modificadores
    (``ctrl @``) con que aparezca en el cuerpo.

    Parámetros:
        - qasm_source (str): código OpenQASM 3.0 generado.

    Retorna:
        - dict: nombre de la compuerta -> unitaria (array de numpy).
    """
    declarations = _gate_declarations(qasm_source)
    units = {}
    for name, (parameters, body) in declarations.items():
        if not parameters:
            continue
        probe = ['OPENQASM 3.0;', 'include "stdgates.inc";']
        probe.extend(
            _render_declaration(other, other_params, other_body)
            for other, (other_params, other_body) in declarations.items()
        )
        probe.append(f"qreg q[{len(parameters)}];")
        probe.append(
            name + ' ' + ', '.join(f'q[{index}]' for index in range(len(parameters))) + ';'
        )
        units[name] = Operator(qasm3.loads('\n'.join(probe))).data
    return units


def _discover():
    """Recorre las baterías de ``input/`` buscando customs con ``matrix``.

    Retorna:
        - tuple: (número de archivos escaneados, conteo por archivo,
          lista de entradas con su circuito y sus compuertas matrix).
    """
    scanned = 0
    per_file = {}
    entries = []
    for path in sorted(INPUT_DIR.glob('*.json')):
        scanned += 1
        registry = json.loads(path.read_text(encoding='utf-8'))
        for name, entry in registry.items():
            circuit = _circuit_json(entry)
            gates = _matrix_gates(circuit)
            if not gates:
                continue
            per_file[path.name] = per_file.get(path.name, 0) + len(gates)
            entries.append({
                'file': path.name,
                'name': name,
                'entry': entry,
                'circuit': circuit,
                'matrix_gates': gates,
            })
    return scanned, per_file, entries


class MatrixDiscoveryTests(unittest.TestCase):
    """La descubrimiento cubre todo el corpus de baterías de ``input/``."""

    def test_every_battery_file_is_scanned(self):
        scanned, _, _ = _discover()
        self.assertEqual(EXPECTED_FILES_SCANNED, scanned)

    def test_matrix_gate_counts_per_file(self):
        _, per_file, _ = _discover()
        self.assertEqual(EXPECTED_MATRIX_GATES_PER_FILE, per_file)

    def test_every_matrix_gate_translates_to_a_declaration(self):
        _, _, entries = _discover()
        total = 0
        for case in entries:
            with self.subTest(file=case['file'], algorithm=case['name']):
                source = quirk_to_qasm(
                    case['entry']['url'],
                    offset=case['entry'].get('offset', 0),
                    qasm_version='3.0',
                )
                declarations = _gate_declarations(source)
                gate_names = _resolve_gate_names(_build_gate_map(case['circuit']))
                for gate in case['matrix_gates']:
                    identifier = gate_names[gate['id']]
                    self.assertIn(identifier, declarations)
                    total += 1
        self.assertEqual(
            sum(EXPECTED_MATRIX_GATES_PER_FILE.values()), total
        )


class UrlMatrixVsQasmTests(unittest.TestCase):
    """La unitaria de la declaración emitida reproduce la matriz de la URL."""

    @classmethod
    def setUpClass(cls):
        _, _, entries = _discover()
        cls.cases = []
        for case in entries:
            source = quirk_to_qasm(
                case['entry']['url'],
                offset=case['entry'].get('offset', 0),
                qasm_version='3.0',
            )
            case['qasm3_source'] = source
            case['units'] = _declared_gate_units(source)
            case['gate_names'] = _resolve_gate_names(_build_gate_map(case['circuit']))
            cls.cases.append(case)

    def test_source_matrices_are_unitary(self):
        for case in self.cases:
            for gate in case['matrix_gates']:
                label = f"{case['file']}:{case['name']}:{gate.get('name', gate['id'])}"
                with self.subTest(gate=label):
                    matrix = np.array(
                        _matrix_to_rows(gate['matrix']), dtype=complex
                    )
                    self.assertIn(matrix.shape, {(2, 2), (4, 4)})
                    identity = matrix.conj().T @ matrix
                    self.assertLess(
                        np.abs(identity - np.eye(matrix.shape[0])).max(),
                        UNITARITY_TOLERANCE,
                    )

    def test_declared_unitaries_match_the_url_matrices(self):
        for case in self.cases:
            for gate in case['matrix_gates']:
                identifier = case['gate_names'][gate['id']]
                label = f"{case['file']}:{case['name']}:{identifier}"
                with self.subTest(gate=label):
                    source = np.array(
                        _matrix_to_rows(gate['matrix']), dtype=complex
                    )
                    emitted = case['units'][identifier]
                    self.assertEqual(source.shape, emitted.shape)
                    # Exacta incluida fase global: el pipeline la materializa.
                    self.assertLess(
                        np.abs(emitted - source).max(), EQUALITY_TOLERANCE
                    )

    def test_full_circuits_load_in_both_qasm_versions(self):
        for case in self.cases:
            with self.subTest(file=case['file'], algorithm=case['name']):
                entry = case['entry']
                parsed3 = qasm3.loads(case['qasm3_source'])
                source2 = quirk_to_qasm(
                    entry['url'], offset=entry.get('offset', 0), qasm_version='2.0'
                )
                parsed2 = qasm2.loads(source2)
                self.assertGreater(parsed3.num_qubits, 0)
                self.assertEqual(parsed3.num_qubits, parsed2.num_qubits)


if __name__ == '__main__':
    unittest.main()

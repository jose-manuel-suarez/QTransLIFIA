import ast
import json
import math
import operator
import re
from pathlib import Path


SOURCE_DIR = Path(__file__).parent / "notebooks" / "popular_algorithms"
OUTPUT_FILE = SOURCE_DIR.parent / "popular_algorithms.json"
QUIRK_BASE = "https://algassert.com/quirk#circuit="
OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}


def eval_parameter(expression):
    tree = ast.parse(expression.replace("pi", "PI"), mode="eval")

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id == "PI":
            return math.pi
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            return OPS[type(node.op)](visit(node.left), visit(node.right))
        raise ValueError(f"Unsupported QASM parameter: {expression}")

    return visit(tree)


def one_qubit_matrix(name, parameters):
    values = [eval_parameter(value) for value in parameters]
    if name == "u1":
        angle = values[0]
        return ((1, 0), (0, complex(math.cos(angle), math.sin(angle))))
    if name == "rz":
        angle = values[0] / 2
        return (
            (complex(math.cos(angle), -math.sin(angle)), 0),
            (0, complex(math.cos(angle), math.sin(angle))),
        )
    if name == "ry":
        angle = values[0] / 2
        return ((math.cos(angle), -math.sin(angle)), (math.sin(angle), math.cos(angle)))
    if name == "rx":
        angle = values[0] / 2
        return (
            (complex(math.cos(angle), 0), complex(0, -math.sin(angle))),
            (complex(0, -math.sin(angle)), complex(math.cos(angle), 0)),
        )
    if name == "u2":
        phi, lam = values
        scale = 1 / math.sqrt(2)
        return (
            (scale, -scale * complex(math.cos(lam), math.sin(lam))),
            (
                scale * complex(math.cos(phi), math.sin(phi)),
                scale * complex(math.cos(phi + lam), math.sin(phi + lam)),
            ),
        )
    if name == "u3":
        theta, phi, lam = values
        cosine, sine = math.cos(theta / 2), math.sin(theta / 2)
        return (
            (cosine, -sine * complex(math.cos(lam), math.sin(lam))),
            (
                sine * complex(math.cos(phi), math.sin(phi)),
                cosine * complex(math.cos(phi + lam), math.sin(phi + lam)),
            ),
        )
    raise ValueError(f"Unsupported single-qubit gate: {name}")


def format_complex(value):
    value = complex(value)
    real = 0 if abs(value.real) < 5e-12 else value.real
    imag = 0 if abs(value.imag) < 5e-12 else value.imag

    def number(part):
        return format(part, ".10g")

    if not imag:
        return number(real)
    if abs(imag - 1) < 5e-12:
        imaginary = "i"
    elif abs(imag + 1) < 5e-12:
        imaginary = "-i"
    else:
        imaginary = number(abs(imag)) + "i"
    if not real:
        return imaginary
    return number(real) + ("+" if imag > 0 else "-") + imaginary.lstrip("-")


def matrix_text(matrix):
    return (
        "{{" + format_complex(matrix[0][0]) + "," + format_complex(matrix[0][1])
        + "},{" + format_complex(matrix[1][0]) + "," + format_complex(matrix[1][1]) + "}}"
    )


def convert_file(path, index):
    source = re.sub(r"//.*", "", path.read_text(encoding="utf-8"))
    statements = [part.strip() for part in source.split(";") if part.strip()]
    registers = {}
    qubit_count = 0
    columns = []
    last_column = {}
    custom_gates = []
    custom_ids = {}

    def custom_ref(name, parameters, matrix):
        key = tuple(tuple((round(complex(item).real, 12), round(complex(item).imag, 12)) for item in row) for row in matrix)
        if key not in custom_ids:
            gate_id = f"~pa{len(custom_ids):04x}"
            custom_ids[key] = gate_id
            custom_gates.append({
                "id": gate_id,
                "name": f"{name}({','.join(parameters)})",
                "matrix": matrix_text(matrix),
            })
        return custom_ids[key]

    def wire_index(register, local_index):
        return registers[register][0] + local_index

    for statement in statements:
        if re.match(r"^(OPENQASM|include|creg)\b", statement, re.I):
            continue
        register_match = re.fullmatch(r"qreg\s+(\w+)\[(\d+)\]", statement, re.I)
        if register_match:
            register_name, size = register_match.group(1), int(register_match.group(2))
            registers[register_name] = (qubit_count, size)
            qubit_count += size
            continue
        if re.match(r"^(barrier|gate)\b", statement, re.I):
            continue
        measurement = re.fullmatch(r"measure\s+(\w+)\[(\d+)\]\s*->\s*\w+\[\d+\]", statement, re.I)
        if measurement:
            wires = [wire_index(measurement.group(1), int(measurement.group(2)))]
            operation = [(wires[0], "Measure")]
        else:
            operation_match = re.fullmatch(r"([a-zA-Z][a-zA-Z0-9_]*)(?:\s*\((.*?)\))?\s+(.+)", statement, re.S)
            if not operation_match:
                raise ValueError(f"Cannot parse statement in {path.name}: {statement}")
            name = operation_match.group(1).lower()
            parameters = [part.strip() for part in operation_match.group(2).split(",")] if operation_match.group(2) else []
            operands = re.findall(r"(\w+)\[(\d+)\]", operation_match.group(3))
            if not operands:
                raise ValueError(f"Missing QASM operands in {path.name}: {statement}")
            wires = [wire_index(register, int(local_index)) for register, local_index in operands]
            if name == "measure":
                operation = [(wires[0], "Measure")]
            elif name == "id":
                continue
            elif name in {"h", "x", "y", "z", "s", "sdg", "t", "tdg"}:
                quirk_name = {"h": "H", "x": "X", "y": "Y", "z": "Z", "s": "Z^½", "sdg": "Z^-½", "t": "Z^¼", "tdg": "Z^-¼"}[name]
                operation = [(wires[0], quirk_name)]
            elif name in {"cx", "cy", "cz", "ccx"}:
                target_gate = {"cx": "X", "cy": "Y", "cz": "Z", "ccx": "X"}[name]
                operation = [(wire, "•") for wire in wires[:-1]] + [(wires[-1], target_gate)]
            elif name in {"cp", "cu1"}:
                angle = eval_parameter(parameters[0])
                matrix = ((1, 0), (0, complex(math.cos(angle), math.sin(angle))))
                gate_id = custom_ref(name, parameters, matrix)
                operation = [(wires[0], "•"), (wires[1], gate_id)]
            elif name == "swap":
                operation = [(wire, "Swap") for wire in wires]
            elif name in {"rx", "ry", "rz", "u1", "u2", "u3"}:
                gate_id = custom_ref(name, parameters, one_qubit_matrix(name, parameters))
                operation = [(wires[0], gate_id)]
            else:
                raise ValueError(f"Unsupported QASM gate in {path.name}: {name}")

        active_wires = [wire for wire, _ in operation]
        column_index = max((last_column.get(wire, -1) for wire in active_wires), default=-1) + 1
        while len(columns) <= column_index:
            columns.append([1] * qubit_count)
        for wire, gate in operation:
            columns[column_index][wire] = gate
            last_column[wire] = column_index

    if not columns:
        raise ValueError(f"No circuit operations found in {path.name}")
    circuit = {"cols": columns}
    if custom_gates:
        circuit["gates"] = custom_gates
    url = QUIRK_BASE + json.dumps(circuit, ensure_ascii=False, separators=(",", ":"))
    entry = {
        "desc": f"Circuito {path.stem} ({qubit_count} qubits)",
        "url": url,
        "offset": 0,
    }
    return f"{index}. {path.stem}", entry, qubit_count, len(columns)


def natural_key(path):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.stem)]


def main():
    algorithms = {}
    reports = []
    for index, path in enumerate(sorted(SOURCE_DIR.glob("*.qasm"), key=natural_key), start=1):
        key, entry, qubits, columns = convert_file(path, index)
        algorithms[key] = entry
        reports.append(f"{key}: {qubits} qubits, {columns} columns")
    OUTPUT_FILE.write_text(json.dumps(algorithms, ensure_ascii=False, indent="\t") + "\n", encoding="utf-8")
    print("\n".join(reports))
    print(f"Generated {OUTPUT_FILE} with {len(algorithms)} circuits")


if __name__ == "__main__":
    main()
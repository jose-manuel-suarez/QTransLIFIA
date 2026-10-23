# -*- coding: utf-8 -*-
"""Migra un circuito concreto de un registro de ``input/`` y muestra el JSON.

Es el comando de terminal para la **migración aislada** de un circuito: toma
uno de los registros de entrada (por índice o por nombre), pide a la API
``translate_circuit`` el OpenQASM y los scripts de cada proveedor, e imprime
en la consola el JSON devuelto.

Por omisión **no** se activa el cálculo ZX ni se generan imágenes (ambas cosas
son etapas del pipeline completo, no de la migración); sí se puede pedirlas
explícitamente con ``--zx`` e ``--images``.

Ejemplos (Windows, desde la raíz del proyecto)::

    .venv/Scripts/python.exe tools/migrate_circuit.py --file input/popular_algorithms.json --index 39
    .venv/Scripts/python.exe tools/migrate_circuit.py --file input/custom_gates_algorithms.json --name "1. complex_customs" --providers qiskit,braket,pennylane --out output/migrated
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qtrans.core import translate_circuit  # noqa: E402


def _load_registry(path):
    """Lee el registro de algoritmos de entrada.

    Parámetros:
        - path (str | Path): ruta del JSON de entrada.

    Retorna:
        - dict: pares ``nombre -> registro``.
    """
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not data:
        raise ValueError(f"El registro {path} no contiene algoritmos.")
    return data


def _select_entry(registry, index, name):
    """Elige el registro del circuito solicitado.

    Parámetros:
        - registry (dict): pares ``nombre -> registro``.
        - index (int | None): posición (1-based) dentro del registro.
        - name (str | None): nombre exacto de la entrada.

    Retorna:
        - tuple[str, dict]: nombre y registro elegidos.

    Lanza:
        - ValueError: si no se indica índice ni nombre, o no existen.
    """
    names = list(registry)
    if name:
        if name not in registry:
            raise ValueError(
                f"No existe la entrada {name!r}. Disponibles: {', '.join(names)}"
            )
        return name, registry[name]
    if index is None:
        raise ValueError("Indica --index (posición) o --name (entrada exacta).")
    if not 1 <= index <= len(names):
        raise ValueError(
            f"--index fuera de rango: el registro tiene {len(names)} entradas."
        )
    selected = names[index - 1]
    return selected, registry[selected]


def _build_parser():
    """Construye el analizador de argumentos.

    Retorna:
        - argparse.ArgumentParser: analizador configurado.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Migra un circuito de input/ a los proveedores indicados e imprime "
            "el JSON devuelto por la API translate_circuit."
        ),
    )
    parser.add_argument(
        "--file",
        default="input/popular_algorithms.json",
        help="Registro JSON de entrada (por omisión, input/popular_algorithms.json).",
    )
    parser.add_argument(
        "--index", type=int, default=None,
        help="Posición del circuito en el registro (1-based).",
    )
    parser.add_argument(
        "--name", default=None,
        help="Nombre exacto de la entrada del registro (p. ej. '1. complex_customs').",
    )
    parser.add_argument(
        "--providers", default="qiskit,braket,pennylane",
        help="Proveedores destino separados por comas (por omisión, los tres).",
    )
    parser.add_argument(
        "--qasm-version", default="3.0", choices=("2.0", "3.0"),
        help="Versión de OpenQASM generada (por omisión, 3.0).",
    )
    parser.add_argument(
        "--offset", type=int, default=0,
        help="Desplazamiento de índices de qubit.",
    )
    parser.add_argument(
        "--shots", type=int, default=1000,
        help="Disparos por ejecución (solo PennyLane).",
    )
    parser.add_argument(
        "--zx", action="store_true",
        help="Activa el cálculo ZX (desactivado por omisión).",
    )
    parser.add_argument(
        "--images", action="store_true",
        help="Genera las imágenes (desactivado por omisión).",
    )
    parser.add_argument(
        "--preserve-custom-gates", action="store_true",
        help="Conserva las compuertas custom como funciones locales en el script.",
    )
    parser.add_argument(
        "--out", default=None,
        help="Carpeta donde escribir los scripts migrados (por omisión, no se escribe nada).",
    )
    parser.add_argument(
        "--json-out", default=None,
        help="Fichero donde guardar además el JSON devuelto.",
    )
    return parser


def main(argv=None):
    """Ejecuta la migración aislada de un circuito.

    Parámetros:
        - argv (list[str] | None): argumentos de la línea de órdenes.

    Retorna:
        - int: 0 si la migración terminó sin errores; 1 en caso contrario.
    """
    args = _build_parser().parse_args(argv)
    registry = _load_registry(args.file)
    name, entry = _select_entry(registry, args.index, args.name)
    url = entry.get("url")
    if not url:
        raise ValueError(f"La entrada {name!r} no tiene campo 'url'.")

    payload = {
        "input": {
            "url": url,
            "offset": args.offset,
            "qasm_version": args.qasm_version,
            "provider": [p.strip() for p in args.providers.split(",") if p.strip()],
            "shots": args.shots,
            "preserve_custom_gates": args.preserve_custom_gates,
            "zx": {"enabled": bool(args.zx)},
            "images": {
                "quirk": bool(args.images),
                "qasm": bool(args.images),
                "composer": bool(args.images),
            },
        }
    }
    result = translate_circuit(payload)
    output = result["output"]

    print(f"Circuito: {name}")
    print(f"Proveedores: {', '.join(payload['input']['provider'])}")
    print(f"ZX: {'sí' if args.zx else 'no'} | Imágenes: {'sí' if args.images else 'no'}")
    print("=" * 72)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("=" * 72)

    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        for key, source in output.get("migrated_code", {}).items():
            provider = key.replace("_code", "")
            target = out_dir / provider / f"{name}.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding="utf-8")
            print(f"[{provider}] {target}")
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"[json] {args.json_out}")

    errors = output.get("errors") or []
    if errors:
        print(f"Errores: {len(errors)}")
        for error in errors:
            print(f"  - {error.get('stage')}: {error.get('message')}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

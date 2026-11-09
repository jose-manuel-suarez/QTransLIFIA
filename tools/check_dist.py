"""Verifica el contenido de los artefactos de una release (wheel y sdist).

Evita publicar en PyPI un paquete que haya incluido por error directorios ajenos
al código distribuible (``demo/``, ``demo_venv/``, ``.venv/``, ``node_modules/``,
``build/``, etc.). El caso real que motivó esta batería fue el patrón
``include = ["qtrans*"]`` de setuptools, que también empaquetaba
``qtrans_demo/demo_venv`` y generaba un wheel inválido de decenas de MB.

Uso:

    python tools/check_dist.py dist/*
    python tools/check_dist.py dist            # equivalente: expande dist/*.whl y dist/*.tar.gz

Parámetros:
    paths: archivos ``.whl``/``.tar.gz`` o directorios que los contengan. Si se
        omite, se usa ``dist``.

Retorna:
    Código de salida 0 si todos los artefactos son válidos; 1 si falta el wheel
    o el sdist, o si alguno contiene rutas prohibidas.
"""

import argparse
import re
import sys
import tarfile
import zipfile
from pathlib import Path

PACKAGE = "qtrans"
DIST_NAME = "qtranslifia"

WHEEL_ALLOWED_TOP = {PACKAGE}
SDIST_ALLOWED_TOP = {
    "PKG-INFO",
    "LICENSE",
    "README.md",
    "pyproject.toml",
    "setup.cfg",
    PACKAGE,
    DIST_NAME + ".egg-info",
    "test",
}

FORBIDDEN_PARTS = {
    "demo",
    "demo_venv",
    "qtrans_demo",
    ".venv",
    "node_modules",
    "__pycache__",
    "build",
    "dist",
    ".git",
}

FORBIDDEN_SUFFIXES = {".pyc", ".pyo"}

WHEEL_WARN_BYTES = 5 * 1024 * 1024


def _human_size(size):
    """Devuelve un tamaño legible en KB o MB."""
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / 1024:.1f} KB"


def _collect_artifacts(paths):
    """Recolecta wheels y sdists a partir de archivos o directorios."""
    wheels, sdists, missing = [], [], []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            missing.append(path)
        elif path.is_dir():
            wheels.extend(sorted(path.glob("*.whl")))
            sdists.extend(sorted(path.glob("*.tar.gz")))
        elif path.suffix == ".whl":
            wheels.append(path)
        elif path.name.endswith(".tar.gz"):
            sdists.append(path)
        else:
            missing.append(path)
    return wheels, sdists, missing


def _check_wheel(path):
    """Valida el contenido del wheel y devuelve la lista de problemas."""
    issues, warnings = [], []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()

    tops = {name.split("/", 1)[0] for name in names if name}
    dist_infos = {top for top in tops if re.fullmatch(rf"{DIST_NAME}-.+\.dist-info", top)}

    for top in sorted(tops):
        if top in WHEEL_ALLOWED_TOP or top in dist_infos:
            continue
        issues.append(f"directorio de nivel superior no permitido: {top}/")

    if len(dist_infos) != 1:
        issues.append(
            f"se esperaba exactamente un {DIST_NAME}-<versión>.dist-info; "
            f"encontrados: {sorted(dist_infos) or 'ninguno'}"
        )

    if f"{PACKAGE}/__init__.py" not in names:
        issues.append(f"falta {PACKAGE}/__init__.py")
    if f"{PACKAGE}/core.py" not in names:
        issues.append(f"falta {PACKAGE}/core.py")

    issues.extend(_forbidden_paths(names))
    size = path.stat().st_size
    if size > WHEEL_WARN_BYTES:
        warnings.append(
            f"el wheel pesa {_human_size(size)}; un paquete sano ronda los 100-150 KB"
        )
    return issues, warnings, len(names)


def _check_sdist(path):
    """Valida el contenido del sdist y devuelve la lista de problemas."""
    issues, warnings = [], []
    with tarfile.open(path) as archive:
        names = archive.getnames()

    roots = {name.split("/", 1)[0] for name in names if name}
    if len(roots) != 1:
        issues.append(
            f"se esperaba un único directorio raíz {DIST_NAME}-<versión>/; "
            f"encontrados: {sorted(roots)}"
        )

    unknown = set()
    for name in names:
        if "/" not in name:
            continue
        relative = name.split("/", 1)[1]
        if not relative:
            continue
        top = relative.split("/", 1)[0]
        if top not in SDIST_ALLOWED_TOP:
            unknown.add(top)
    for top in sorted(unknown):
        issues.append(f"entrada de nivel superior no permitida en el sdist: {top}/")

    if not any(name.endswith(f"/{PACKAGE}/__init__.py") for name in names):
        issues.append(f"falta {PACKAGE}/__init__.py en el sdist")

    issues.extend(_forbidden_paths(names))
    size = path.stat().st_size
    if size > WHEEL_WARN_BYTES:
        warnings.append(
            f"el sdist pesa {_human_size(size)}; revisá que no incluya entornos virtuales"
        )
    return issues, warnings, len(names)


def _forbidden_paths(names):
    """Detecta componentes de ruta prohibidos y bytecode compilado."""
    issues = []
    for name in names:
        parts = name.replace("\\", "/").split("/")
        for part in parts:
            if part.casefold() in FORBIDDEN_PARTS:
                issues.append(f"ruta prohibida: {name}")
                break
        else:
            if any(name.casefold().endswith(suffix) for suffix in FORBIDDEN_SUFFIXES):
                issues.append(f"bytecode compilado en el artefacto: {name}")
    return issues


def main(argv=None):
    """Ejecuta la validación y devuelve el código de salida."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    parser = argparse.ArgumentParser(
        description="Valida que el wheel y el sdist solo incluyan el paquete qtrans."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["dist"],
        help="Archivos .whl/.tar.gz o directorios que los contengan (default: dist).",
    )
    args = parser.parse_args(argv)

    wheels, sdists, missing = _collect_artifacts(args.paths)
    if missing:
        for path in missing:
            print(f"[ERROR] No existe o no es un artefacto válido: {path}")
        print("Pasá un directorio `dist` o los archivos .whl/.tar.gz generados por `python -m build`.")
        return 1
    if not wheels:
        print("[ERROR] No se encontró ningún wheel (.whl). Ejecutá `python -m build`.")
        return 1
    if not sdists:
        print("[ERROR] No se encontró ningún sdist (.tar.gz). Ejecutá `python -m build`.")
        return 1

    failures = 0
    for path in wheels + sdists:
        checker = _check_wheel if path.suffix == ".whl" else _check_sdist
        issues, warnings, entries = checker(path)
        issues = list(dict.fromkeys(issues))
        if issues:
            failures += 1
            print(f"[ERROR] {path} ({entries} entradas)")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print(f"[OK] {path} ({entries} entradas, {_human_size(path.stat().st_size)})")
        for warning in warnings:
            print(f"  [AVISO] {warning}")

    if failures:
        print(f"\n{failures} artefacto(s) con problemas; no publiques esta build.")
        return 1
    print("\nTodos los artefactos contienen únicamente el paquete distribuible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Batería de análisis estático del código de QTransLIFIA (sin dependencias).

Comprueba, sobre el AST de los módulos, dos clases de defectos que no detectan
las pruebas unitarias porque solo aparecen cuando el código afectado se ejecuta
por una ruta no cubierta:

1. **Nombres globales no definidos**: un identificador usado dentro de una
   función que no está definido ni en el ámbito local, ni en el ámbito del
   módulo, ni entre los *builtins*. Es el síntoma típico de un *refactor* que
   movió una función de módulo y olvidó actualizar una referencia, o de una
   reexportación eliminada de la fachada ``qtrans/utils/qutils.py``.
2. **Imports sin usar**: un ``import`` cuyo nombre no aparece en ninguna carga
   del módulo ni en su ``__all__``. Detecta rastro de dependencias que la
   reorganización del paquete dejó colgando.

Uso:

    python tools/check_static.py qtrans test

Devuelve código de salida 1 si encuentra problemas (útil para engancharlo a un
CI) y 0 en caso contrario.
"""

import argparse
import ast
import builtins
import sys
from pathlib import Path

BUILTINS = set(dir(builtins)) | {'__file__', '__name__', '__doc__', '__package__'}


class Scope:
    """Conjunto de nombres definidos en un ámbito (módulo o función)."""

    def __init__(self):
        self.defined = set()

    def add(self, name):
        self.defined.add(name)

    def update(self, names):
        self.defined.update(names)


def collect_targets(node, scope):
    """Recolecta los nombres que el nodo define (asignaciones, defs, args...)."""
    for child in ast.walk(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scope.add(child.name)
        elif isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
            scope.add(child.id)
        elif isinstance(child, ast.arg):
            scope.add(child.arg)
        elif isinstance(child, ast.alias):
            scope.add(child.asname or child.name.split('.')[0])
        elif isinstance(child, ast.ExceptHandler) and child.name:
            scope.add(child.name)
        elif isinstance(child, (ast.Global, ast.Nonlocal)):
            scope.update(child.names)


def check_undefined(path, tree):
    """Detecta nombres globales no definidos dentro de funciones."""
    module_scope = Scope()
    collect_targets(tree, module_scope)
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        local = Scope()
        collect_targets(node, local)
        args = node.args
        for arg in list(args.args) + list(args.posonlyargs) + list(args.kwonlyargs):
            local.add(arg.arg)
        if args.vararg:
            local.add(args.vararg.arg)
        if args.kwarg:
            local.add(args.kwarg.arg)
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                if sub.id in local.defined or sub.id in module_scope.defined:
                    continue
                if sub.id in BUILTINS:
                    continue
                problems.append((path, node.name, sub.id, sub.lineno))
    return problems


def check_unused_imports(path, tree, source_lines):
    """Detecta imports cuyo nombre no se usa ni se exporta en ``__all__``.

    Se respetan las marcas ``# noqa`` (típicamente ``# noqa: F401``): son la
    convención del proyecto para señalar reexportaciones intencionales, que no
    son código muerto.
    """
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported[alias.asname or alias.name.split('.')[0]] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported[alias.asname or alias.name] = node.lineno

    used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    exported = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == '__all__':
                    for elt in getattr(node.value, 'elts', []):
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            exported.add(elt.value)

    return [
        (path, name, line)
        for name, line in imported.items()
        if name not in used and name not in exported
        and 'noqa' not in _source_line(source_lines, line)
    ]


def _source_line(source_lines, lineno):
    """Devuelve la línea de código ``lineno`` (1-indexado) o cadena vacía."""
    if 1 <= lineno <= len(source_lines):
        return source_lines[lineno - 1]
    return ''


def iter_files(targets):
    """Expande los destinos (archivos o directorios) a una lista de *.py."""
    files = []
    for target in targets:
        path = Path(target)
        if path.is_dir():
            files.extend(sorted(path.rglob('*.py')))
        elif path.suffix == '.py':
            files.append(path)
        else:
            print(f'[aviso] se ignora {path} (no es un archivo .py)')
    return files


def main(argv=None):
    """Punto de entrada: analiza los destinos y resume los hallazgos."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'targets', nargs='*', default=['qtrans', 'test'],
        help='archivos o directorios a analizar (por defecto: qtrans test)',
    )
    args = parser.parse_args(argv)

    undefined = []
    unused = []
    for path in iter_files(args.targets):
        source = path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(path))
        undefined.extend(check_undefined(path, tree))
        unused.extend(check_unused_imports(path, tree, source.splitlines()))

    for path, func, name, line in undefined:
        print(f'{path}:{line} en {func}() -> nombre no definido: {name!r}')
    for path, name, line in sorted(unused, key=lambda item: item[2]):
        print(f'{path}:{line} import sin usar: {name}')

    total = len(undefined) + len(unused)
    print(f'--- {total} problemas ({len(undefined)} nombres no definidos, '
          f'{len(unused)} imports sin usar)')
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main())

"""Limpieza de los directorios de salida de QTransLIFIA.

Elimina los directorios de corrida (``run_*``) que genera el pipeline en
``output/`` y ``notebooks/output/``. Uso desde consola:

    python utils/cleanup_outputs.py              # pide confirmación y borra run_*
    python utils/cleanup_outputs.py --dry-run    # solo muestra qué eliminaría
    python utils/cleanup_outputs.py -y           # sin confirmación
    python utils/cleanup_outputs.py --keep 1     # conserva la corrida más reciente
    python utils/cleanup_outputs.py --all        # borra además archivos sueltos
    python utils/cleanup_outputs.py --remove-roots

También puede importarse: ``from utils.cleanup_outputs import clean_outputs``.
"""

import argparse
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOTS = (
    PROJECT_ROOT / "output",
    PROJECT_ROOT / "notebooks" / "output",
)
RUN_DIR_PREFIX = "run_"


def human_size(num_bytes):
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


def _path_size(path):
    path = Path(path)
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                pass
    return total


def discover_targets(roots=None, include_files=False, keep=0):
    """Devuelve las rutas a eliminar (dirs ``run_*`` y, opcionalmente, archivos)."""
    roots = [Path(r) for r in (roots or DEFAULT_ROOTS)]
    targets = []
    for root in roots:
        if not root.is_dir():
            continue
        run_dirs = sorted(
            (d for d in root.iterdir() if d.is_dir() and d.name.startswith(RUN_DIR_PREFIX)),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        targets.extend(run_dirs[keep:] if keep else run_dirs)
        if include_files:
            targets.extend(f for f in root.iterdir() if f.is_file())
    return targets


def clean_outputs(
    roots=None,
    dry_run=False,
    include_files=False,
    keep=0,
    remove_roots=False,
    assume_yes=False,
    verbose=True,
):
    """Elimina las salidas de corrida y devuelve un resumen de la operación."""
    roots = [Path(r) for r in (roots or DEFAULT_ROOTS)]
    targets = discover_targets(roots, include_files=include_files, keep=keep)

    removed = []
    failed = []
    total_bytes = 0

    for target in targets:
        total_bytes += _path_size(target)
        if dry_run:
            removed.append(target)
            continue
        try:
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=False)
            else:
                target.unlink()
            removed.append(target)
        except OSError as exc:
            failed.append((target, exc))

    removed_roots = []
    if remove_roots and not dry_run:
        for root in roots:
            if root.is_dir() and not any(root.iterdir()):
                try:
                    root.rmdir()
                    removed_roots.append(root)
                except OSError as exc:
                    failed.append((root, exc))
            elif root.is_dir():
                failed.append((root, "no está vacío; se conserva"))

    summary = {
        "roots": roots,
        "targets": targets,
        "removed": removed,
        "failed": failed,
        "removed_roots": removed_roots,
        "total_bytes": total_bytes,
        "dry_run": dry_run,
    }

    if verbose:
        if not targets and not (remove_roots and not dry_run):
            print("Nada que limpiar: no se encontraron salidas de corrida.")
        else:
            action = "Se eliminarían" if dry_run else "Eliminados"
            print(f"{action} {len(removed)} elemento(s) ({human_size(total_bytes)}):")
            for target in removed:
                try:
                    shown = target.relative_to(PROJECT_ROOT)
                except ValueError:
                    shown = target
                print(f"  - {shown}")
            for target, exc in failed:
                print(f"  ! Error con {target}: {exc}")
        if removed_roots:
            print(f"Directorios raíz eliminados: {', '.join(str(r) for r in removed_roots)}")
    return summary


def _confirm(count):
    try:
        answer = input(f"¿Eliminar {count} elemento(s) de salida? [y/N]: ").strip().casefold()
    except EOFError:
        return False
    return answer in {"y", "yes", "s", "si", "sí"}


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description="Elimina los directorios de corrida (run_*) de output/ y notebooks/output/."
    )
    parser.add_argument(
        "--root",
        dest="roots",
        action="append",
        type=Path,
        default=None,
        help="Directorio de salida adicional (repetible). Por defecto: output/ y notebooks/output/.",
    )
    parser.add_argument(
        "--all",
        dest="include_files",
        action="store_true",
        help="Elimina también los archivos sueltos presentes en los directorios de salida.",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=0,
        help="Conserva las N corridas más recientes de cada directorio (default: 0).",
    )
    parser.add_argument(
        "--remove-roots",
        action="store_true",
        help="Elimina también los directorios raíz cuando quedan vacíos.",
    )
    parser.add_argument("-n", "--dry-run", action="store_true", help="Muestra qué se eliminaría sin borrar nada.")
    parser.add_argument("-y", "--yes", action="store_true", help="No pide confirmación.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Salida reducida.")
    return parser


def main(argv=None):
    args = build_argument_parser().parse_args(argv)
    roots = [Path(r) for r in (args.roots or DEFAULT_ROOTS)]

    preview = discover_targets(roots, include_files=args.include_files, keep=args.keep)
    if not preview:
        print("Nada que limpiar: no se encontraron salidas de corrida.")
        return 0
    if not args.dry_run and not args.yes:
        if not _confirm(len(preview)):
            print("Operación cancelada.")
            return 1

    summary = clean_outputs(
        roots=roots,
        dry_run=args.dry_run,
        include_files=args.include_files,
        keep=args.keep,
        remove_roots=args.remove_roots,
        assume_yes=args.yes,
        verbose=not args.quiet,
    )
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

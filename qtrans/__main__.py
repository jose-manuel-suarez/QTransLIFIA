"""Punto de entrada para ``python -m qtrans`` (equivale al script ``qtrans``)."""

from .core import main

if __name__ == "__main__":
    raise SystemExit(main())
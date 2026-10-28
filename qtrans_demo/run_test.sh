#!/bin/bash
cd "$(dirname "$0")"
source demo_venv/Scripts/activate
export PYTHONDONTWRITEBYTECODE=1
python -u main.py

#!/bin/bash

# Get directory of this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

PYTHON_SCRIPT="$ROOT_DIR/optical/optical.py"

python3 "$PYTHON_SCRIPT" "$@"
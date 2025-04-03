#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

source $PROJECT_ROOT/venv/bin/activate

python3 $PROJECT_ROOT/Hardware/src/flask_batch_transcription.py
#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "transcribe.sh started at $(date)" >> $PROJECT_ROOT/Hardware/logs/transcribe.log

source $PROJECT_ROOT/venv/bin/activate

TODAY=$(date +"%b%d")
HIGHEST_COUNTER=$(ls -d $PROJECT_ROOT/Hardware/dataset/${TODAY}_* 2>/dev/null | awk -F"${TODAY}_" '{print $2}' | sort -n | tail -1)
DIRPATH="$PROJECT_ROOT/Hardware/dataset/${TODAY}_${HIGHEST_COUNTER}"

if [ -z "$HIGHEST_COUNTER" ]; then
    # If no directories found, start with 0
    DIRPATH="$PROJECT_ROOT/Hardware/dataset/${TODAY}_0"
fi

python3 $PROJECT_ROOT/Hardware/src/transcribe_chunk_pi.py -d $DIRPATH



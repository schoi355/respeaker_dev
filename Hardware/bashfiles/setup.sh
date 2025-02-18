#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

source $PROJECT_ROOT/venv/bin/activate

TODAY=$(date +"%b%d")
counter=0

DATAPATH="$PROJECT_ROOT/Hardware/dataset/${TODAY}_${counter}"

while [ -d "$DATAPATH" ]; do
    counter=$((counter + 1))
    DATAPATH="$PROJECT_ROOT/Hardware/dataset/${TODAY}_${counter}"
done

echo "Creating directory '$DATAPATH'"
mkdir -p "$DATAPATH/assign_speaker"
mkdir -p "$DATAPATH/recorded_data"


# python3 $PROJECT_ROOT/Hardware/src/record_DOA_ID_chunks_pi.py -d $DATAPATH -s 1800 >> $PROJECT_ROOT/Hardware/logs/record.log 2>&1 &
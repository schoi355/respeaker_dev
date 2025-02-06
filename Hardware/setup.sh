#!/bin/bash
source ../venv/bin/activate

TODAY=$(date +"%b%d")
counter=0
DIRPATH="dataset/${TODAY}_${counter}"

while [ -d "$DIRPATH" ]; do
    counter=$((counter + 1))
    DIRPATH="dataset/${TODAY}_${counter}"
done

echo "Creating directory '$DIRPATH'"
mkdir -p "$DIRPATH/assign_speaker"
mkdir -p "$DIRPATH/recorded_data"

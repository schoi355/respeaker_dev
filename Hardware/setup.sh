#!/bin/bash
source /home/respeaker2/respeaker_dev/venv/bin/activate

TODAY=$(date +"%b%d")
counter=0
DIRPATH="/home/respeaker2/respeaker_dev/Hardware/dataset/${TODAY}_${counter}"

while [ -d "$DIRPATH" ]; do
    counter=$((counter + 1))
    DIRPATH="/home/respeaker2/respeaker_dev/Hardware/dataset/${TODAY}_${counter}"
done

echo "Creating directory '$DIRPATH'"
mkdir -p "$DIRPATH/assign_speaker"
mkdir -p "$DIRPATH/recorded_data"


python3 /home/respeaker2/respeaker_dev/Hardware/record_DOA_ID_chunks_pi.py -d $DIRPATH -s 1800 >> /home/respeaker2/logs/record.log 2>&1 &
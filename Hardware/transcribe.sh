#!/bin/bash
source /home/respeaker2/respeaker_dev/venv/bin/activate

TODAY=$(date +"%b%d")
HIGHEST_COUNTER=$(ls -d /home/respeaker2/respeaker_dev/Hardware/dataset/${TODAY}_* 2>/dev/null | awk -F"${TODAY}_" '{print $2}' | sort -n | tail -1)
DIRPATH="/home/respeaker2/respeaker_dev/Hardware/dataset/${TODAY}_${HIGHEST_COUNTER}"

if [ -z "$HIGHEST_COUNTER" ]; then
    # If no directories found, start with 0
    DIRPATH="/home/respeaker2/respeaker_dev/Hardware/dataset/${TODAY}_0"
fi

python3 /home/respeaker2/respeaker_dev/Hardware/transcribe_chunk_pi.py -d $DIRPATH


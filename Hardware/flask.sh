#!/bin/bash

source /home/respeaker2/respeaker_dev/venv/bin/activate

TODAY=$(date +"%b%d")
HIGHEST_COUNTER=$(ls -d dataset/${TODAY}_* 2>/dev/null | awk -F"${TODAY}_" '{print $2}' | sort -n | tail -1)
DIRPATH="dataset/${TODAY}_${HIGHEST_COUNTER}"

if [ -z "$HIGHEST_COUNTER" ]; then
    # If no directories found, start with 0
    DIRPATH="dataset/${TODAY}_0"
fi


python3 flask_prep_pi_dynamoDB.py -d $DIRPATH
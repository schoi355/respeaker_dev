#!/bin/bash
source venv/bin/activate

DIRPATH='dataset/Apr5'

if [ -d "$DIRPATH" ]; then
    echo "Dataset directory '$DIRPATH' already exists"
else
    echo "create directory '$DIRPATH'"
    mkdir $DIRPATH
    mkdir "$DIRPATH/assign_speaker"
    mkdir "$DIRPATH/recorded_data"
fi


#!/bin/bash

set -e  

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

log() {
    echo "$1" >> $PROJECT_ROOT/Hardware/logs/wrapper.log 2>&1
}

log "Starting setup.sh"
sleep 5
$SCRIPT_DIR/setup.sh >> $PROJECT_ROOT/Hardware/logs/setup.log 2>&1 &

log "Starting record.sh"
sleep 5
$SCRIPT_DIR/record.sh >> $PROJECT_ROOT/Hardware/logs/record.log 2>&1 &

log "Starting flask.sh"
sleep 5
$SCRIPT_DIR/flask.sh >> $PROJECT_ROOT/Hardware/logs/flask.log 2>&1 &

log "Starting transcribe.sh"
sleep 5
$SCRIPT_DIR/transcribe.sh >> $PROJECT_ROOT/Hardware/logs/transcribe.log 2>&1 &

wait
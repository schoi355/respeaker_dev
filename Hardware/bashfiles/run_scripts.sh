#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "Starting setup.sh" >> $PROJECT_ROOT/Hardware/logs/wrapper.log 2>&1
sleep 5
$SCRIPT_DIR/setup.sh >> $PROJECT_ROOT/Hardware/logs/setup.log 2>&1 &

echo "Starting record.sh" >> $PROJECT_ROOT/Hardware/logs/wrapper.log 2>&1
sleep 5
$SCRIPT_DIR/record.sh >> $PROJECT_ROOT/Hardware/logs/record.log 2>&1 &

echo "Starting flask.sh" >> $PROJECT_ROOT/Hardware/logs/wrapper.log 2>&1
sleep 5
$SCRIPT_DIR/flask.sh >> $PROJECT_ROOT/Hardware/logs/flask.log 2>&1 &

echo "Starting transcribe.sh" >> $PROJECT_ROOT/Hardware/logs/wrapper.log 2>&1
sleep 5
$SCRIPT_DIR/transcribe.sh >> $PROJECT_ROOT/Hardware/logs/transcribe.log 2>&1 &

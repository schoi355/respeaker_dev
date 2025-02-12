#!/bin/bash

echo "Starting setup.sh" >> /home/respeaker2/logs/wrapper.log 2>&1
sleep 5
/home/respeaker2/respeaker_dev/Hardware/setup.sh >> /home/respeaker2/logs/setup.log 2>&1 &

echo "Starting flask.sh" >> /home/respeaker2/logs/wrapper.log 2>&1
sleep 5
/home/respeaker2/respeaker_dev/Hardware/flask.sh >> /home/respeaker2/logs/flask.log 2>&1 &

echo "Starting transcribe.sh" >> /home/respeaker2/logs/wrapper.log 2>&1
sleep 5
/home/respeaker2/respeaker_dev/Hardware/transcribe.sh >> /home/respeaker2/logs/transcribe.log 2>&1 &

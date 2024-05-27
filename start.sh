#!/bin/bash

# Start Pure Data in headless mode with ALSA MIDI
/usr/bin/chrt -f 50 /usr/bin/pd -rt -nogui -alsa /home/pi/repos/emsys/main.pd &

# Wait for Pd to start
sleep 5

# Connect Elektron TM-1 to Pure Data
aconnect 28:0 128:0

# Wait for Pd to run indefinitely
wait

#!/bin/bash

# Start Pure Data in headless mode with ALSA MIDI
/usr/bin/chrt -f 50 /usr/bin/pd -rt -nogui -alsa /home/pi/repos/emsys/main.pd &

# Wait for Pd to start
sleep 5

# Connect MiniLab 3 to Pure Data
aconnect 32:0 128:0

# Connect TM-1 to Pure Data
aconnect 28:0 128:0

# Wait for Pd to run indefinitely
wait

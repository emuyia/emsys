#!/bin/bash

# Allow use of this script for pisound button:
# sudo ln -s /home/patch/repos/emsys/serv/em_sys.sh /usr/local/pisound/scripts/pisound-btn/em_sys.sh

source ~/.bashrc
export JACK_PROMISCUOUS_SERVER=jack
export DISPLAY=:0

PD_PATH="/home/patch/Applications/pdnext/bin/pd"
PD_PATCH="/home/patch/repos/emsys/main.pd"

# Check if Pd is running
PD_PID=$(pgrep -f "$PD_PATH.*$PD_PATCH")

if [ -z "$PD_PID" ]; then
    echo "Pd is not running, starting Pd..."
    # Start Pd
    $PD_PATH -jack -rt -nogui $PD_PATCH &
else
    echo "Pd is already running (PID: $PD_PID), stopping Pd..."
    # Stop Pd
    kill $PD_PID
    sleep 1  # Give it a moment to close properly

    # Optionally restart Pd
    echo "Restarting Pd..."
    $PD_PATH -jack -rt -nogui $PD_PATCH &
fi

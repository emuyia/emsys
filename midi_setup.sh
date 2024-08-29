#!/bin/bash

# sudo ln -s /home/patch/repos/emsys/midi_setup.service /etc/systemd/system/midi_setup.service
# sudo systemctl daemon-reload && sudo systemctl enable midi_setup && sudo systemctl start midi_setup

# Function to get the client number by name
get_client_number() {
    aconnect -i | grep -B1 "$1" | grep -v "ctl" | grep "client" | awk '{print $2}' | tr -d ':'
}

# Function to connect ports if not already connected
connect_ports() {
    src_client=$1
    src_port=$2
    dest_client=$3
    dest_port=$4
    if ! aconnect -l | grep -q "$src_client:$src_port.*$dest_client:$dest_port"; then
        aconnect $src_client:$src_port $dest_client:$dest_port
        echo "Connected $src_client:$src_port to $dest_client:$dest_port"
    else
        echo "$src_client:$src_port is already connected to $dest_client:$dest_port"
    fi
}

while true; do
    # Dynamically find the clients
    MINILAB3_CLIENT=$(get_client_number "Minilab3")
    PISOUND_CLIENT=$(get_client_number "pisound")
    PD_CLIENT=$(get_client_number "Pure Data")

    # Log the found client numbers
    echo "Minilab3 Client: $MINILAB3_CLIENT"
    echo "Pisound Client: $PISOUND_CLIENT"
    echo "Pure Data Client: $PD_CLIENT"

    # Hardcoded port numbers based on consistent mapping
    MINILAB3_MIDI_OUT_PORT=0
    MINILAB3_MIDI_IN_PORT=0
    PISOUND_MIDI_OUT_PORT=0
    PISOUND_MIDI_IN_PORT=0
    PD_MIDI_IN_1=0
    PD_MIDI_OUT_1=3
    PD_MIDI_IN_2=1
    PD_MIDI_OUT_2=4

    # Check if all necessary clients are found
    if [[ -z $MINILAB3_CLIENT || -z $PISOUND_CLIENT || -z $PD_CLIENT ]]; then
        echo "One or more MIDI clients not found. Retrying..."
        sleep 5
        continue
    fi

    # Connect Pisound IN to PD IN 1
    connect_ports $PISOUND_CLIENT $PISOUND_MIDI_IN_PORT $PD_CLIENT $PD_MIDI_IN_1
    
    # Connect PD OUT 1 to Pisound OUT
    connect_ports $PD_CLIENT $PD_MIDI_OUT_1 $PISOUND_CLIENT $PISOUND_MIDI_OUT_PORT
    
    # Connect Minilab MIDI OUT to PD IN 2
    connect_ports $MINILAB3_CLIENT $MINILAB3_MIDI_OUT_PORT $PD_CLIENT $PD_MIDI_IN_2
    
    # Connect PD OUT 2 to Minilab MIDI IN
    connect_ports $PD_CLIENT $PD_MIDI_OUT_2 $MINILAB3_CLIENT $MINILAB3_MIDI_IN_PORT

    # Wait before rechecking connections
    sleep 5
done

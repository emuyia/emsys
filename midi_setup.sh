#!/bin/bash

# sudo ln -s /home/patch/repos/emsys/midi_setup.service /etc/systemd/system/midi_setup.service && sudo systemctl daemon-reload && sudo systemctl enable midi_setup && sudo systemctl start midi_setup

# Function to get the client number by name
get_client_number() {
    aconnect -i | grep -B1 "$1" | grep "client" | awk '{print $2}' | tr -d ':'
}

# Function to get the port number by client number and port name
get_port_number() {
    aconnect -i | grep -A1 "client $1:" | grep "$2" | awk '{print $1}' | tr -d ':'
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
    fi
}

while true; do
    # Get client numbers
    MINILAB3_CLIENT=$(get_client_number "Minilab3")
    MEGACMD_CLIENT=$(get_client_number "MegaCMD")
    PD_CLIENT=$(get_client_number "Pure Data")

    # Log the client numbers for debugging
    echo "Minilab3 Client: $MINILAB3_CLIENT"
    echo "MegaCMD Client: $MEGACMD_CLIENT"
    echo "Pure Data Client: $PD_CLIENT"

    # Check if clients are found
    if [[ -z $MINILAB3_CLIENT || -z $MEGACMD_CLIENT || -z $PD_CLIENT ]]; then
        echo "One or more MIDI devices not found."
        #sleep 5
        #continue
    fi

    # Get port numbers for Minilab3
    MINILAB3_MIDI=$(get_port_number $MINILAB3_CLIENT "Minilab3 Minilab3 MIDI")

    # Log the port numbers for debugging
    echo "Minilab3 MIDI Port: $MINILAB3_MIDI"

    # Check if port numbers are found
    if [[ -z $MINILAB3_MIDI ]]; then
        echo "One or more Minilab3 ports not found."
        #sleep 5
        #continue
    fi

    # Define the port numbers for Pure Data
    PD_MIDI_IN_1=0
    PD_MIDI_IN_2=1
    PD_MIDI_IN_3=2
    PD_MIDI_IN_4=3
    PD_MIDI_OUT_1=4
    PD_MIDI_OUT_2=5
    PD_MIDI_OUT_3=6
    PD_MIDI_OUT_4=7

    # Establish connections
    connect_ports $MINILAB3_CLIENT $MINILAB3_MIDI $PD_CLIENT $PD_MIDI_IN_2
    connect_ports $PD_CLIENT $PD_MIDI_OUT_1 $MEGACMD_CLIENT 0
    connect_ports $MEGACMD_CLIENT 0 $PD_CLIENT $PD_MIDI_IN_1

    # Wait before rechecking connections
    sleep 5
done

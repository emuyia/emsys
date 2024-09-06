import time
import subprocess
from mido import get_output_names, get_input_names

# Function to get the client number by name using aconnect
def get_client_number(client_name):
    result = subprocess.run(['aconnect', '-i'], capture_output=True, text=True)
    lines = result.stdout.splitlines()

    client_num = None
    for i, line in enumerate(lines):
        if client_name.lower() in line.lower():
            for previous_line in lines[max(0, i-1):i]:
                if "client" in previous_line and "ctl" not in previous_line:
                    client_num = previous_line.split()[1].strip(':')
                    break
    return client_num

# Function to check and connect ports if not already connected
def connect_ports(src_client, src_port, dest_client, dest_port):
    result = subprocess.run(['aconnect', '-l'], capture_output=True, text=True)
    if f'{src_client}:{src_port}' in result.stdout and f'{dest_client}:{dest_port}' in result.stdout:
        print(f"{src_client}:{src_port} is already connected to {dest_client}:{dest_port}")
    else:
        subprocess.run(['aconnect', f'{src_client}:{src_port}', f'{dest_client}:{dest_port}'])
        print(f"Connected {src_client}:{src_port} to {dest_client}:{dest_port}")

while True:
    # Dynamically find the clients
    MINILAB3_CLIENT = get_client_number("Minilab3")
    PISOUND_CLIENT = get_client_number("pisound")
    THRU_CLIENT = get_client_number("Midi Through")
    PD_CLIENT = get_client_number("Pure Data")

    # Log the found client numbers
    print(f"Minilab3 Client: {MINILAB3_CLIENT}")
    print(f"Pisound Client: {PISOUND_CLIENT}")
    print(f"Thru Client: {THRU_CLIENT}")
    print(f"Pure Data Client: {PD_CLIENT}")

    # Hardcoded port numbers based on consistent mapping
    MINILAB3_MIDI_OUT_PORT = 0
    MINILAB3_MIDI_IN_PORT = 0
    PISOUND_MIDI_OUT_PORT = 0
    PISOUND_MIDI_IN_PORT = 0
    THRU_MIDI_IN_PORT = 0
    THRU_MIDI_OUT_PORT = 0
    PD_MIDI_IN_1 = 0
    PD_MIDI_OUT_1 = 3
    PD_MIDI_IN_2 = 1
    PD_MIDI_OUT_2 = 4
    PD_MIDI_IN_3 = 2
    PD_MIDI_OUT_3 = 5

    # Check if all necessary clients are found
    if None in [MINILAB3_CLIENT, PISOUND_CLIENT, THRU_CLIENT, PD_CLIENT]:
        print("One or more MIDI clients not found. Retrying...")
        time.sleep(5)
        continue

    # Connect ports as needed
    connect_ports(THRU_CLIENT, THRU_MIDI_OUT_PORT, PD_CLIENT, PD_MIDI_IN_1)
    connect_ports(PD_CLIENT, PD_MIDI_OUT_1, THRU_CLIENT, THRU_MIDI_IN_PORT)

    connect_ports(PISOUND_CLIENT, PISOUND_MIDI_IN_PORT, PD_CLIENT, PD_MIDI_IN_2)
    connect_ports(PD_CLIENT, PD_MIDI_OUT_2, PISOUND_CLIENT, PISOUND_MIDI_OUT_PORT)

    connect_ports(MINILAB3_CLIENT, MINILAB3_MIDI_OUT_PORT, PD_CLIENT, PD_MIDI_IN_3)
    connect_ports(PD_CLIENT, PD_MIDI_OUT_3, MINILAB3_CLIENT, MINILAB3_MIDI_IN_PORT)

    # Wait before rechecking connections
    time.sleep(5)

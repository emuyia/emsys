import time
import subprocess
from mido import get_output_names, get_input_names

# Function to get the client number by name using aconnect
def get_client_number(client_name, input=True):
    command = ['aconnect', '-i'] if input else ['aconnect', '-o']
    result = subprocess.run(command, capture_output=True, text=True)
    lines = result.stdout.splitlines()

    client_num = None
    for line in lines:
        # Check for the client name in the current line
        if client_name.lower() in line.lower():
            #print(f"'{client_name}' found: {line}")
            # Extract the client number from this line itself (contains 'client')
            if "client" in line:
                client_num = line.split()[1].strip(':')
                #print(f"client_num: {client_num}")
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
    CLK_OUT_CLIENT = get_client_number("RtMidiOut Client", input=True)
    CLK_IN_CLIENT = get_client_number("RtMidiIn Client", input=False)
    PS_CLIENT = get_client_number("pisound")
    ML3_CLIENT = get_client_number("Minilab3")
    PD_CLIENT = get_client_number("Pure Data")

    # Log the found client numbers
    print(f"Clock Out Client: {CLK_OUT_CLIENT}")
    print(f"Clock In Client: {CLK_IN_CLIENT}")
    print(f"Pisound Client: {PS_CLIENT}")
    print(f"Minilab3 Client: {ML3_CLIENT}")
    print(f"Pure Data Client: {PD_CLIENT}")

    # Hardcoded port numbers based on consistent mapping
    CLK_OUT = 0
    CLK_IN = 0
    PS_OUT = 0
    PS_IN = 0
    ML3_OUT = 0
    ML3_IN = 0
    PD_IN_1 = 0
    PD_IN_2 = 1
    PD_IN_3 = 2
    PD_IN_4 = 3
    PD_OUT_1 = 4
    PD_OUT_2 = 5
    PD_OUT_3 = 6
    PD_OUT_4 = 7

    # Keep track of missing clients
    missing_clients = []

    # Pd 1 out to Clock In (bpm ctl)
    if PD_CLIENT and CLK_IN_CLIENT:
        connect_ports(PD_CLIENT, PD_OUT_1, CLK_IN_CLIENT, CLK_IN)
    else:
        missing_clients.append("Pure Data to Clock In")

    # Pd 2 out to Pisound (synth ctl)
    if PD_CLIENT and PS_CLIENT:
        connect_ports(PD_CLIENT, PD_OUT_2, PS_CLIENT, PS_IN)
    else:
        missing_clients.append("Pure Data to Pisound")

    # Pd 3 out to Minilab3 (sysex UI)
    if PD_CLIENT and ML3_CLIENT:
        connect_ports(PD_CLIENT, PD_OUT_3, ML3_CLIENT, ML3_IN)
    else:
        missing_clients.append("Pure Data to Minilab3")

    # Clock out to Pd 1 (bpm feedback)
    if CLK_OUT_CLIENT and PD_CLIENT:
        connect_ports(CLK_OUT_CLIENT, CLK_OUT, PD_CLIENT, PD_IN_1)
    else:
        missing_clients.append("Clock Out to Pure Data")

    # Clock out to Pisound (external hardware)
    if CLK_OUT_CLIENT and PS_CLIENT:
        connect_ports(CLK_OUT_CLIENT, CLK_OUT, PS_CLIENT, PS_IN)
    else:
        missing_clients.append("Clock Out to Pisound")

    # Pisound to Pd 2 (synth feedback)
    if PS_CLIENT and PD_CLIENT:
        connect_ports(PS_CLIENT, PS_OUT, PD_CLIENT, PD_IN_2)
    else:
        missing_clients.append("Pisound to Pure Data")

    # Minilab3 to Pd 3 (note/CC/transport ctl)
    if ML3_CLIENT and PD_CLIENT:
        connect_ports(ML3_CLIENT, ML3_OUT, PD_CLIENT, PD_IN_3)
    else:
        missing_clients.append("Minilab3 to Pure Data")

    # Report missing clients
    if missing_clients:
        print("The following connections were not established due to missing clients:")
        for client in missing_clients:
            print(f"  - {client}")
    else:
        print("All clients connected successfully.")

    # Wait before rechecking connections
    time.sleep(5)

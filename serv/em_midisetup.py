import subprocess
import time

# Function to get the client number by name using aconnect
def get_client_number_cache(client_name, input=True):
    command = ['aconnect', '-i'] if input else ['aconnect', '-o']
    result = subprocess.run(command, capture_output=True, text=True)
    lines = result.stdout.splitlines()

    client_num = None
    for line in lines:
        if client_name.lower() in line.lower() and "client" in line:
            client_num = line.split()[1].strip(':')
            break
    return client_num

# Function to get all current connections using aconnect -l
def get_all_connections():
    result = subprocess.run(['aconnect', '-l'], capture_output=True, text=True)
    return result.stdout

# Function to check and connect ports if not already connected
def connect_ports(connections, src_client, src_port, dest_client, dest_port):
    if f'{src_client}:{src_port}' in connections and f'{dest_client}:{dest_port}' in connections:
        print(f"{src_client}:{src_port} is already connected to {dest_client}:{dest_port}")
    else:
        subprocess.run(['aconnect', f'{src_client}:{src_port}', f'{dest_client}:{dest_port}'])
        print(f"Connected {src_client}:{src_port} to {dest_client}:{dest_port}")

while True:
    # Cache all client numbers
    client_cache = {
        "CLK_OUT_CLIENT": get_client_number_cache("em_clock_out", input=True),
        "CLK_IN_CLIENT": get_client_number_cache("em_clock_in", input=False),
        "PS_CLIENT": get_client_number_cache("pisound"),
        "MCL_CLIENT": get_client_number_cache("MegaCMD"),
        "ML3_CLIENT": get_client_number_cache("Minilab3"),
        "PD_CLIENT": get_client_number_cache("Pure Data")
    }

    # Log the found client numbers
    for client_name, client_num in client_cache.items():
        print(f"{client_name}: {client_num}")

    # Hardcoded port numbers - assumes we have Pd ports set to 4/4
    CLK_OUT, CLK_IN, PS_OUT, PS_IN, ML3_OUT, ML3_IN, MCL_OUT, MCL_IN = 0, 0, 0, 0, 0, 0, 0, 0
    PD_IN_1, PD_IN_2, PD_IN_3, PD_IN_4, PD_OUT_1, PD_OUT_2, PD_OUT_3, PD_OUT_4 = 0, 1, 2, 3, 4, 5, 6, 7

    # Get all current connections once per loop
    connections = get_all_connections()

    # Try connecting ports, reusing client_cache and connections
    missing_clients = []

    # Pd 1 to Clock In (bpm ctl)
    if client_cache["PD_CLIENT"] and client_cache["CLK_IN_CLIENT"]:
        connect_ports(connections, client_cache["PD_CLIENT"], PD_OUT_1, client_cache["CLK_IN_CLIENT"], CLK_IN)
    else:
        missing_clients.append("Pure Data to Clock In")

    # Pd 2 to Pisound (synth ctl)
    if client_cache["PD_CLIENT"] and client_cache["PS_CLIENT"]:
        connect_ports(connections, client_cache["PD_CLIENT"], PD_OUT_2, client_cache["PS_CLIENT"], PS_IN)
    else:
        missing_clients.append("Pure Data to Pisound")

    # Pd 3 to Minilab3 (sysex UI)
    if client_cache["PD_CLIENT"] and client_cache["ML3_CLIENT"]:
        connect_ports(connections, client_cache["PD_CLIENT"], PD_OUT_3, client_cache["ML3_CLIENT"], ML3_IN)
    else:
        missing_clients.append("Pure Data to Minilab3")

    # Clock Out to Pd 1 (bpm feedback)
    if client_cache["CLK_OUT_CLIENT"] and client_cache["PD_CLIENT"]:
        connect_ports(connections, client_cache["CLK_OUT_CLIENT"], CLK_OUT, client_cache["PD_CLIENT"], PD_IN_1)
    else:
        missing_clients.append("Clock Out to Pure Data")

    # Clock Out to Pisound (external hardware)
    if client_cache["CLK_OUT_CLIENT"] and client_cache["PS_CLIENT"]:
        connect_ports(connections, client_cache["CLK_OUT_CLIENT"], CLK_OUT, client_cache["PS_CLIENT"], PS_IN)
    else:
        missing_clients.append("Clock Out to Pisound")

    # Clock Out to MCL via USB
    if client_cache["CLK_OUT_CLIENT"] and client_cache["MCL_CLIENT"]:
        connect_ports(connections, client_cache["CLK_OUT_CLIENT"], CLK_OUT, client_cache["MCL_CLIENT"], MCL_IN)
    else:
        missing_clients.append("Clock Out to MCL USB")

    # Pisound to Pd 2 (synth feedback)
    if client_cache["PS_CLIENT"] and client_cache["PD_CLIENT"]:
        connect_ports(connections, client_cache["PS_CLIENT"], PS_OUT, client_cache["PD_CLIENT"], PD_IN_2)
    else:
        missing_clients.append("Pisound to Pure Data")

    # Minilab3 to Pd 3 (note/CC/transport ctl)
    if client_cache["ML3_CLIENT"] and client_cache["PD_CLIENT"]:
        connect_ports(connections, client_cache["ML3_CLIENT"], ML3_OUT, client_cache["PD_CLIENT"], PD_IN_3)
    else:
        missing_clients.append("Minilab3 to Pure Data")

    # MCL to Pd 4 (external hardware - extra functionality)
    if client_cache["MCL_CLIENT"] and client_cache["PD_CLIENT"]:
        connect_ports(connections, client_cache["MCL_CLIENT"], MCL_OUT, client_cache["PD_CLIENT"], PD_IN_4)
    else:
        missing_clients.append("MCL to Pure Data")
    
    # MCL to Pd 4 (external hardware - extra functionality)
    if client_cache["MCL_CLIENT"] and client_cache["PD_CLIENT"]:
        connect_ports(connections, client_cache["PD_CLIENT"], PD_OUT_4, client_cache["MCL_CLIENT"], MCL_IN)
    else:
        missing_clients.append("Pure Data to MCL USB")
    
    if client_cache["PS_CLIENT"] and client_cache["MCL_CLIENT"]:
        connect_ports(connections, client_cache["PS_CLIENT"], PS_OUT, client_cache["MCL_CLIENT"], MCL_IN)
    else:
        missing_clients.append("Pisound to MCL USB")

    # Report missing clients
    if missing_clients:
        print("The following connections were not established due to missing clients:")
        for client in missing_clients:
            print(f"  - {client}")
    else:
        print("All clients connected successfully.")

    print("====")
    
    # Wait before rechecking connections
    time.sleep(5)

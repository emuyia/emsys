#!/usr/bin/env python3
import mido
import time
import sys
import glob
import argparse
import os

# The keyword to identify the MIDI port.
PORT_KEYWORD = 'pisound'
# Get the absolute path of the directory where the script is located.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def find_midi_port(keyword, direction='input'):
    """Finds the first available MIDI port containing the keyword."""
    port_names = mido.get_input_names() if direction == 'input' else mido.get_output_names()
    for port_name in port_names:
        if keyword in port_name:
            print(f"Found MIDI {direction} port: '{port_name}'")
            return port_name
    return None

def receive_sysex(port_name):
    """
    Listens for a MIDI SysEx message and saves it to a .syx file in the script's directory.
    """
    print(f"Opening MIDI input port: '{port_name}'")
    try:
        with mido.open_input(port_name) as inport:
            print("Waiting for SysEx message...")
            for msg in inport:
                if msg.type == 'sysex':
                    print("SysEx message received!")
                    # Create the filename path inside the script's directory
                    filename = os.path.join(SCRIPT_DIR, f"sysex_dump_{int(time.time())}.syx")
                    with open(filename, 'wb') as f:
                        f.write(bytearray(msg.bytes()))
                    print(f"SysEx data saved to {filename}")
                    print(f"Message length: {len(msg.bytes())} bytes")
                    break
    except (OSError, IOError) as e:
        print(f"Error: Could not open MIDI port '{port_name}'. ({e})")
        sys.exit(1)

def send_sysex(port_name):
    """Lists .syx files from the script's directory and sends the selected one."""
    # Search for .syx files only in the script's directory
    search_path = os.path.join(SCRIPT_DIR, '*.syx')
    syx_files = sorted(glob.glob(search_path))
    
    if not syx_files:
        print(f"Error: No .syx files found in the script directory ({SCRIPT_DIR}).")
        sys.exit(1)

    print("\nAvailable .syx files:")
    for i, f_path in enumerate(syx_files):
        # Show only the filename to the user, not the full path
        print(f"  {i + 1}: {os.path.basename(f_path)}")

    try:
        choice = int(input(f"\nEnter the number of the file to send (1-{len(syx_files)}): ")) - 1
        if not 0 <= choice < len(syx_files):
            raise ValueError
    except (ValueError, IndexError):
        print("Invalid selection.")
        sys.exit(1)

    filename = syx_files[choice]
    print(f"Preparing to send '{os.path.basename(filename)}'...")

    try:
        with open(filename, 'rb') as f:
            sysex_data = f.read()
        
        msg = mido.Message.from_bytes(sysex_data)
        if msg.type != 'sysex':
            print(f"Error: The file '{os.path.basename(filename)}' does not appear to be a valid SysEx file.")
            sys.exit(1)

        print(f"Opening MIDI output port: '{port_name}'")
        with mido.open_output(port_name) as outport:
            print("Sending SysEx message...")
            outport.send(msg)
            time.sleep(0.1)
            print("Message sent successfully.")

    except (OSError, IOError) as e:
        print(f"Error: Could not open or read file/port. ({e})")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A tool to record and send MIDI SysEx files.")
    parser.add_argument('action', choices=['receive', 'send'], help="Choose to 'receive' a new SysEx file or 'send' an existing one.")
    parser.add_argument('--port', type=str, help="Specify the MIDI port name directly, overriding the automatic search.")
    args = parser.parse_args()

    port_to_use = args.port
    if not port_to_use:
        direction = 'input' if args.action == 'receive' else 'output'
        print(f"Searching for MIDI {direction} port containing '{PORT_KEYWORD}'...")
        port_to_use = find_midi_port(PORT_KEYWORD, direction=direction)

    if not port_to_use:
        print(f"\nError: Could not find a MIDI {direction} port containing '{PORT_KEYWORD}'.")
        print("Please check if the MIDI device is connected.")
        sys.exit(1)

    if args.action == 'receive':
        receive_sysex(port_to_use)
    elif args.action == 'send':
        send_sysex(port_to_use)
#!/usr/bin/env python3
import mido
import time
import sys

# The keyword to identify the MIDI port.
# This should be a unique part of your MIDI device's name as listed by `mido-ports`.
PORT_KEYWORD = 'pisound'

def find_midi_port(keyword):
    """Finds the first available MIDI input port containing the keyword."""
    for port_name in mido.get_input_names():
        if keyword in port_name:
            print(f"Found MIDI port: '{port_name}'")
            return port_name
    return None

def sysex_recorder(port_name):
    """
    Listens for a MIDI SysEx message from the specified port and saves it to a .syx file.
    """
    print(f"Opening MIDI port: '{port_name}'")
    try:
        with mido.open_input(port_name) as inport:
            print("Waiting for SysEx message...")
            for msg in inport:
                if msg.type == 'sysex':
                    print("SysEx message received!")
                    # Generate a filename with a timestamp
                    filename = f"sysex_dump_{int(time.time())}.syx"
                    
                    # The mido sysex message includes the framing bytes (F0 and F7).
                    # A standard .syx file should contain the raw sysex message,
                    # including the F0 start and F7 end bytes.
                    # mido's `msg.bytes()` gives the full raw message.
                    
                    with open(filename, 'wb') as f:
                        f.write(bytearray(msg.bytes()))
                    
                    print(f"SysEx data saved to {filename}")
                    print(f"Message length: {len(msg.bytes())} bytes")
                    
                    # We'll just capture one message and then exit.
                    # Remove the 'break' if you want to capture multiple messages.
                    break
    except (OSError, IOError) as e:
        print(f"Error: Could not open MIDI port '{port_name}'.")
        print(f"({e})")
        print("Please check if the MIDI device is connected and the port name is correct.")
        sys.exit(1)

if __name__ == "__main__":
    port_to_use = None
    if len(sys.argv) > 1:
        # User can override by providing a specific port name
        port_to_use = sys.argv[1]
        print(f"Using specified MIDI port: '{port_to_use}'")
    else:
        # Try to find the port automatically
        print(f"Searching for MIDI port containing '{PORT_KEYWORD}'...")
        port_to_use = find_midi_port(PORT_KEYWORD)

    if port_to_use:
        sysex_recorder(port_to_use)
    else:
        print(f"\nError: Could not find a MIDI input port containing '{PORT_KEYWORD}'.")
        print("Please check if the MIDI device is connected.")
        print("\nAvailable input ports are:")
        available_ports = mido.get_input_names()
        if available_ports:
            for port in available_ports:
                print(f"  - {port}")
        else:
            print("  (No MIDI input ports found)")
        print("\nYou can also specify a port name manually, for example:")
        print(f"  python3 {sys.argv[0]} 'My MIDI Port Name'")
        sys.exit(1)
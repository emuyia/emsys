#!/usr/bin/env python3
import mido
import time
import sys
import argparse

# --- Constants ---
PORT_KEYWORD = 'pisound'
SYSEX_HEADER = [0x00, 0x20, 0x3c, 0x03, 0x00]

# Monomachine SysEx Command IDs
CMD_SET_STATUS = 0x71
CMD_REQUEST_STATUS = 0x70
CMD_STATUS_RESPONSE = 0x72

# Monomachine SysEx Parameter IDs
PARAM_PATTERN = 0x04
PARAM_KIT = 0x02

# --- Helper Functions ---

def find_midi_port(keyword, direction='input'):
    """Finds the first available MIDI port containing the keyword."""
    port_names = mido.get_input_names() if direction == 'input' else mido.get_output_names()
    for port_name in port_names:
        if keyword in port_name:
            print(f"Found MIDI {direction} port: '{port_name}'")
            return port_name
    return None

def pattern_index_to_name(index):
    """Converts a pattern index (0-127) to its name (e.g., 'A01', 'H16')."""
    if not 0 <= index <= 127:
        return "Invalid"
    bank = chr(ord('A') + (index // 16))
    number = (index % 16) + 1
    return f"{bank}{number:02d}"

# --- Main Logic ---

def get_kit_map(in_port_name, out_port_name):
    """
    Iterates through all Monomachine patterns to build a map of which kit is used by each pattern.
    """
    kit_map = {}
    try:
        with mido.open_input(in_port_name) as inport, mido.open_output(out_port_name) as outport:
            print("Successfully opened MIDI ports.")
            print("Starting scan of 128 patterns. This will take about a minute...")

            for i in range(128):
                pattern_name = pattern_index_to_name(i)
                print(f"Checking pattern {pattern_name} ({i+1}/128)...", end='', flush=True)

                # 1. Send message to change the current pattern
                set_pattern_msg = mido.Message('sysex', data=SYSEX_HEADER + [CMD_SET_STATUS, PARAM_PATTERN, i])
                outport.send(set_pattern_msg)
                time.sleep(0.20) # Give the Monomachine time to load the pattern's data

                # 2. Send message to request the current kit number
                request_kit_msg = mido.Message('sysex', data=SYSEX_HEADER + [CMD_REQUEST_STATUS, PARAM_KIT])
                outport.send(request_kit_msg)
                
                # 3. Listen for the response
                response_received = False
                start_time = time.time()
                while time.time() - start_time < 2: # 2-second timeout for a response
                    msg = inport.poll()
                    if msg and msg.type == 'sysex' and msg.data[0:7] == tuple(SYSEX_HEADER + [CMD_STATUS_RESPONSE, PARAM_KIT]):
                        # SysEx data is 0-127, device screen is 1-128. Add 1 to match screen.
                        kit_number = msg.data[7] + 1
                        kit_map[pattern_name] = kit_number
                        print(f" -> Kit {kit_number:03d}")
                        response_received = True
                        break
                
                if not response_received:
                    print(" -> No response from Monomachine. Aborting.")
                    break
                
                time.sleep(0.05) # Small delay before the next request

    except (OSError, IOError) as e:
        print(f"\nError: Could not open MIDI ports. ({e})")
        sys.exit(1)

    print("\n--- Kit Map Scan Complete ---")
    if kit_map:
        # Group by kit number for readability
        kits_to_patterns = {}
        for pattern, kit in kit_map.items():
            if kit not in kits_to_patterns:
                kits_to_patterns[kit] = []
            kits_to_patterns[kit].append(pattern)
        
        print("--- Used Kits ---")
        for kit in sorted(kits_to_patterns.keys()):
            patterns = ", ".join(sorted(kits_to_patterns[kit]))
            print(f"Kit {kit:03d}: Used by patterns: {patterns}")
        
        print("\n--- Unused Kits ---")
        used_kits = set(kits_to_patterns.keys())
        all_kits = set(range(1, 129)) # Kits are 1-128
        unused_kits = sorted(list(all_kits - used_kits))

        if unused_kits:
            print("The following kit slots are not used by any pattern:")
            # Format output into neat rows
            lines = []
            line = []
            for kit in unused_kits:
                line.append(f"{kit:03d}")
                if len(line) >= 10:
                    lines.append(", ".join(line))
                    line = []
            if line:
                lines.append(", ".join(line))
            print("\n".join(lines))
        else:
            print("All kit slots (1-128) are in use by at least one pattern.")

    else:
        print("No data was collected.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scans a Monomachine to map which kit is used by each pattern.")
    parser.add_argument('--in-port', type=str, help="Specify the MIDI input port name directly.")
    parser.add_argument('--out-port', type=str, help="Specify the MIDI output port name directly.")
    args = parser.parse_args()

    in_port = args.in_port or find_midi_port(PORT_KEYWORD, 'input')
    out_port = args.out_port or find_midi_port(PORT_KEYWORD, 'output')

    if not in_port or not out_port:
        print("\nError: Could not find required MIDI ports.")
        if not in_port: print(f"  - Input port containing '{PORT_KEYWORD}' not found.")
        if not out_port: print(f"  - Output port containing '{PORT_KEYWORD}' not found.")
        sys.exit(1)

    get_kit_map(in_port, out_port)
import mido
import time
import logging

logger = logging.getLogger(__name__)

# --- Constants ---
PORT_KEYWORD = 'pisound'
SYSEX_HEADER = [0x00, 0x20, 0x3c, 0x03, 0x00]
CMD_SET_STATUS = 0x71
CMD_REQUEST_STATUS = 0x70
CMD_STATUS_RESPONSE = 0x72
PARAM_PATTERN = 0x04
PARAM_KIT = 0x02

def _find_midi_port(keyword, direction='input'):
    """Finds the first available MIDI port containing the keyword."""
    port_names = mido.get_input_names() if direction == 'input' else mido.get_output_names()
    for port_name in port_names:
        if keyword in port_name:
            logger.info(f"Found MIDI {direction} port: '{port_name}'")
            return port_name
    logger.warning(f"MIDI {direction} port with keyword '{keyword}' not found.")
    return None

def _pattern_index_to_name(index):
    """Converts a pattern index (0-127) to its name (e.g., 'A01', 'H16')."""
    if not 0 <= index <= 127: return "Invalid"
    bank = chr(ord('A') + (index // 16))
    number = (index % 16) + 1
    return f"{bank}{number:02d}"

def get_kit_map():
    """
    Iterates through all Monomachine patterns to build a map of which kit is used by each pattern.
    Returns a dictionary like {'A01': 7, 'A02': 7, ...} or None on failure.
    """
    kit_map = {}
    in_port_name = _find_midi_port(PORT_KEYWORD, 'input')
    out_port_name = _find_midi_port(PORT_KEYWORD, 'output')

    if not in_port_name or not out_port_name:
        logger.error("Could not find required MIDI ports for kit scan.")
        return None

    try:
        with mido.open_input(in_port_name) as inport, mido.open_output(out_port_name) as outport:
            logger.info("Starting Monomachine kit map scan...")
            # Give ports a moment to open
            time.sleep(0.1)
            
            for i in range(128):
                logger.debug(f"Scanning pattern {i+1}/128...")
                # 1. Set pattern
                set_pattern_msg = mido.Message('sysex', data=SYSEX_HEADER + [CMD_SET_STATUS, PARAM_PATTERN, i])
                outport.send(set_pattern_msg)
                time.sleep(0.15) # Time for MnM to process the change

                # 2. Request kit
                request_kit_msg = mido.Message('sysex', data=SYSEX_HEADER + [CMD_REQUEST_STATUS, PARAM_KIT])
                outport.send(request_kit_msg)
                
                # 3. Listen for response with a timeout
                response_found = False
                start_time = time.time()
                while time.time() - start_time < 1.0: # 1 second timeout
                    msg = inport.poll() # Poll without arguments
                    if msg and msg.type == 'sysex' and msg.data[0:7] == tuple(SYSEX_HEADER + [CMD_STATUS_RESPONSE, PARAM_KIT]):
                        kit_number = msg.data[7] + 1
                        pattern_name = _pattern_index_to_name(i)
                        kit_map[pattern_name] = kit_number
                        response_found = True
                        break # Exit the while loop
                    time.sleep(0.01) # Prevent CPU hogging

                if not response_found:
                    logger.warning(f"No valid response for pattern {_pattern_index_to_name(i)}. Aborting scan.")
                    return None
    except (OSError, IOError) as e:
        logger.error(f"MIDI port error during kit scan: {e}")
        return None

    logger.info("Kit map scan complete.")
    return kit_map
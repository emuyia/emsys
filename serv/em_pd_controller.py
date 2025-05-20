import mido
import subprocess
import os
import time
import logging
import signal
import sys

MIDI_DEVICE_NAME_SUBSTRING = "MINILAB3 MIDI"
PD_PATH = "/home/patch/Applications/pdnext/bin/pd"
PD_PATCH = "/home/patch/repos/emsys/main.pd"
USER_HOME = "/home/patch"

# MIDI CC numbers
CC_MODIFIER = 109  # Held to enable other actions
CC_START_PATCH = 107
CC_STOP_PATCH = 106
CC_REBOOT = 105

# State
cc_modifier_held = False
_midi_input_port_ref = None
_midi_output_port_ref = None

# SysEx Configuration
# User provided init SysEx (decimal): 240 0 32 107 127 66 2 2 64 106 33 247
# Data part for mido (tuple of integers):
SYSEX_INIT_DATA_TUPLE = (0, 32, 107, 127, 66, 2, 2, 64, 106, 33)

SYSEX_ARTURIA_HEADER = (0x00, 0x20, 0x6B, 0x7F, 0x42) # Standard Arturia Manufacturer ID
SYSEX_TEXT_CMD_PREFIX = SYSEX_ARTURIA_HEADER + (0x04, 0x02, 0x60) # Command to set text

SYSEX_LINE1_TEXT = "Pd Ctrl Ready" # Keep lines short
SYSEX_LINE2_TEXT = "Shift+Tab+Y/N"

# Logging - for systemd, this will go to journald
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def get_pd_pid():
    """Checks if Pd is running using a pattern matching PD_PATH and PD_PATCH, returns its PID or None."""
    try:
        pattern = f"{PD_PATH}.*{PD_PATCH}"
        result = subprocess.run(['pgrep', '-f', pattern], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split('\n')[0])
        return None
    except Exception as e:
        logging.error(f"Error checking Pd PID: {e}")
        return None

def start_pd():
    """Starts the Pure Data patch if not already running."""
    # global _midi_output_port_ref # No longer needed here for SysEx
    pid = get_pd_pid()
    if pid:
        logging.info(f"Pd is already running with PID {pid}. Start command ignored.")
        return
    logging.info(f"Attempting to start Pd: {PD_PATH} with patch {PD_PATCH}")
    pd_env = os.environ.copy()
    pd_env["JACK_PROMISCUOUS_SERVER"] = "jack"
    pd_env["DISPLAY"] = ":0"
    pd_env["HOME"] = USER_HOME
    command = [PD_PATH, "-jack", "-rt", "-nogui", PD_PATCH]
    try:
        subprocess.Popen(command, env=pd_env)
        logging.info("Pd start command issued.")
        time.sleep(1)
        new_pid = get_pd_pid()
        if new_pid:
            logging.info(f"Pd started successfully with PID {new_pid}.")
            # SysEx sending on PD start removed as per user request
        else:
            logging.warning("Pd process not found after start command.")
    except FileNotFoundError:
        logging.error(f"Failed to start Pd: PD_PATH '{PD_PATH}' not found.")
    except Exception as e:
        logging.error(f"Failed to start Pd: {e}")

def stop_pd():
    """Stops the Pure Data patch if running and updates Minilab3 display."""
    global _midi_output_port_ref # Access the global output port
    pid = get_pd_pid()
    if not pid:
        logging.info("Pd is not running. Stop command ignored.")
        return

    logging.info(f"Attempting to stop Pd with PID {pid}.")
    pd_stopped_successfully = False
    try:
        subprocess.run(['kill', str(pid)], check=True)
        logging.info(f"Sent SIGTERM to Pd PID {pid}. Waiting...")
        for _ in range(5): # Check for up to 5 seconds
            time.sleep(1)
            if get_pd_pid() != pid:
                logging.info(f"Pd PID {pid} stopped successfully.")
                pd_stopped_successfully = True
                break
        
        if not pd_stopped_successfully:
            logging.warning(f"Pd PID {pid} did not stop with SIGTERM. Sending SIGKILL.")
            subprocess.run(['kill', '-9', str(pid)], check=True) # Sends SIGKILL
            time.sleep(1)
            if get_pd_pid() != pid:
                logging.info(f"Pd PID {pid} stopped successfully with SIGKILL.")
                pd_stopped_successfully = True
            else:
                logging.error(f"Failed to stop Pd PID {pid} even with SIGKILL.")
            
    except subprocess.CalledProcessError as e:
        logging.warning(f"Error during 'kill' command for Pd PID {pid}: {e}. It might have already stopped.")
        if get_pd_pid() != pid: 
             logging.info(f"Pd PID {pid} appears to be stopped despite previous error.")
             pd_stopped_successfully = True
    except Exception as e:
        logging.error(f"An unexpected error occurred while stopping Pd: {e}")

    if pd_stopped_successfully:
        if _midi_output_port_ref and not _midi_output_port_ref.closed:
            logging.info("Pd stopped. Resending SysEx and original text to Minilab3 display.")
            send_sysex_message(_midi_output_port_ref, SYSEX_INIT_DATA_TUPLE, "Minilab3 Init on PD Stop")
            # Resend the original text
            text_data = construct_text_sysex(SYSEX_LINE1_TEXT, SYSEX_LINE2_TEXT)
            if text_data:
                send_sysex_message(_midi_output_port_ref, text_data, "Minilab3 Display Original Text on PD Stop")
        else:
            logging.warning("MIDI output port not available to update display on PD stop.")

def reboot_system():
    """Reboots the system."""
    logging.info("Reboot command received. Initiating system reboot...")
    try:
        subprocess.run(['sudo', 'reboot'], check=True)
    except Exception as e:
        logging.error(f"Failed to reboot system: {e}. Ensure passwordless sudo for 'reboot'.")

def find_midi_input_port_name(device_substring):
    """Finds the MIDI input port by a substring in its name (case-insensitive)."""
    try:
        for port_name in mido.get_input_names():
            if device_substring.lower() in port_name.lower():
                logging.info(f"Found MIDI input port: '{port_name}' matching substring '{device_substring}'")
                return port_name
        logging.warning(f"MIDI input port containing '{device_substring}' not found. Available: {mido.get_input_names()}")
    except Exception as e:
        logging.error(f"Error enumerating MIDI input ports: {e}")
    return None

def find_midi_output_port_name(device_substring):
    """Finds the MIDI output port by a substring in its name (case-insensitive)."""
    try:
        for port_name in mido.get_output_names():
            if device_substring.lower() in port_name.lower():
                logging.info(f"Found MIDI output port: '{port_name}' matching substring '{device_substring}'")
                return port_name
        logging.warning(f"MIDI output port containing '{device_substring}' not found. Available: {mido.get_output_names()}")
    except Exception as e:
        logging.error(f"Error enumerating MIDI output ports: {e}")
    return None

def send_sysex_message(out_port, sysex_data_tuple, description="SysEx"):
    """Sends a SysEx message using the provided mido output port."""
    try:
        msg = mido.Message('sysex', data=sysex_data_tuple)
        out_port.send(msg)
        logging.info(f"Sent {description} message.") # msg object can be verbose
        time.sleep(0.1)  # Small delay after sending SysEx
    except Exception as e:
        logging.error(f"Failed to send {description} message: {e}")

def construct_text_sysex(line1_text, line2_text):
    """Constructs the data tuple for a Minilab3 text display SysEx message."""
    try:
        s1_bytes = tuple(ord(c) for c in line1_text)
        s2_bytes = tuple(ord(c) for c in line2_text)
        # SysEx structure: F0 <Header+Cmd> 01 <S1> 00 02 <S2> F7
        # Data for mido: <Header+Cmd> 01 <S1> 00 02 <S2>
        text_data = SYSEX_TEXT_CMD_PREFIX + \
                    (0x01,) + s1_bytes + (0x00,) + \
                    (0x02,) + s2_bytes
        return text_data
    except Exception as e:
        logging.error(f"Error constructing text SysEx: {e}")
        return None

def process_midi_input(in_port):
    """Processes incoming MIDI messages from the given port. Returns True if reboot is triggered."""
    global cc_modifier_held # Make sure to use the global
    for msg in in_port:
        logging.debug(f"Received MIDI message: {msg}")
        if msg.type == 'control_change':
            if msg.control == CC_MODIFIER:
                new_state_held = (msg.value > 0)
                if new_state_held != cc_modifier_held:
                    cc_modifier_held = new_state_held
                    logging.info(f"Modifier CC {CC_MODIFIER} is now {'HELD' if cc_modifier_held else 'RELEASED'} (value: {msg.value})")
            elif cc_modifier_held and msg.value > 0:
                if msg.control == CC_START_PATCH:
                    logging.info(f"Start Patch (CC {CC_START_PATCH}, val {msg.value}) with modifier.")
                    start_pd()
                elif msg.control == CC_STOP_PATCH:
                    logging.info(f"Stop Patch (CC {CC_STOP_PATCH}, val {msg.value}) with modifier.")
                    stop_pd()
                elif msg.control == CC_REBOOT:
                    logging.info(f"Reboot (CC {CC_REBOOT}, val {msg.value}) with modifier.")
                    reboot_system()
                    logging.info("Exiting script after reboot command.")
                    return True # Signal to exit main_loop
    return False # Continue processing

def signal_handler(sig, frame):
    global _midi_input_port_ref, _midi_output_port_ref
    logging.info(f"Signal {signal.Signals(sig).name} received, shutting down...")
    if _midi_input_port_ref and hasattr(_midi_input_port_ref, 'close') and not _midi_input_port_ref.closed:
        try: _midi_input_port_ref.close(); logging.info("MIDI input port closed.")
        except Exception as e: logging.error(f"Error closing MIDI input port: {e}")
    if _midi_output_port_ref and hasattr(_midi_output_port_ref, 'close') and not _midi_output_port_ref.closed:
        try: _midi_output_port_ref.close(); logging.info("MIDI output port closed.")
        except Exception as e: logging.error(f"Error closing MIDI output port: {e}")
    sys.exit(0)

def main_loop():
    global cc_modifier_held, _midi_input_port_ref, _midi_output_port_ref

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    target_input_port_name = None
    target_output_port_name = None
    initial_display_sent = False # Flag to send initial display text only once per output port connection

    while True:
        if not target_input_port_name:
            target_input_port_name = find_midi_input_port_name(MIDI_DEVICE_NAME_SUBSTRING)
            if not target_input_port_name:
                logging.info(f"Input port '{MIDI_DEVICE_NAME_SUBSTRING}' not found. Retrying in 10s...")
                # If input is lost, we might lose output too, reset flag
                if _midi_output_port_ref and _midi_output_port_ref.closed: 
                    initial_display_sent = False
                time.sleep(10)
                continue
        
        # Try to find/re-find output port if not set or if the reference is closed
        if not target_output_port_name or (_midi_output_port_ref and _midi_output_port_ref.closed):
            if _midi_output_port_ref and _midi_output_port_ref.closed: # If it was closed, clear ref and name
                 _midi_output_port_ref = None
                 target_output_port_name = None
                 initial_display_sent = False # Reset flag as port needs reopening

            target_output_port_name = find_midi_output_port_name(MIDI_DEVICE_NAME_SUBSTRING)
            if not target_output_port_name:
                logging.warning(f"Output port '{MIDI_DEVICE_NAME_SUBSTRING}' not found. SysEx will not be sent.")
                initial_display_sent = False 
            else:
                # Output port name found, but don't open it here yet.
                # Reset initial_display_sent so it sends when port is confirmed open.
                initial_display_sent = False


        try:
            with mido.open_input(target_input_port_name) as in_port:
                _midi_input_port_ref = in_port
                logging.info(f"Successfully opened MIDI input on '{in_port.name}'")
                cc_modifier_held = False 

                # Manage output port within the input port's 'with' block if possible,
                # or handle it being None if not found/opened.
                if target_output_port_name and (not _midi_output_port_ref or _midi_output_port_ref.closed):
                    try:
                        _midi_output_port_ref = mido.open_output(target_output_port_name)
                        logging.info(f"Successfully opened MIDI output on '{_midi_output_port_ref.name}'")
                        initial_display_sent = False # Ensure display is sent on new successful open
                    except Exception as e_out_open:
                        logging.error(f"Failed to open MIDI output port '{target_output_port_name}' in main loop: {e_out_open}. SysEx disabled for now.")
                        _midi_output_port_ref = None # Clear ref
                        target_output_port_name = None # Force re-find next iteration
                        initial_display_sent = False

                if _midi_output_port_ref and not _midi_output_port_ref.closed and not initial_display_sent:
                    send_sysex_message(_midi_output_port_ref, SYSEX_INIT_DATA_TUPLE, "Minilab3 Init")
                    text_sysex_data = construct_text_sysex(SYSEX_LINE1_TEXT, SYSEX_LINE2_TEXT)
                    if text_sysex_data:
                        send_sysex_message(_midi_output_port_ref, text_sysex_data, "Minilab3 Initial Display Text")
                    initial_display_sent = True
                
                if process_midi_input(in_port): 
                    return 
        
        except OSError as e:
            logging.error(f"MIDI port OS error (input: '{target_input_port_name}'): {e}. Reconnecting...")
            if _midi_input_port_ref and not _midi_input_port_ref.closed: _midi_input_port_ref.close()
            # Output port is closed by its own 'with' or if _midi_output_port_ref.close() is called
            if _midi_output_port_ref and not _midi_output_port_ref.closed: _midi_output_port_ref.close()
            _midi_input_port_ref = None
            _midi_output_port_ref = None 
            target_input_port_name = None
            target_output_port_name = None 
            initial_display_sent = False 
            time.sleep(5)
        except Exception as e:
            logging.error(f"Unexpected error in main loop: {e}")
            if _midi_input_port_ref and not _midi_input_port_ref.closed: _midi_input_port_ref.close()
            if _midi_output_port_ref and not _midi_output_port_ref.closed: _midi_output_port_ref.close()
            _midi_input_port_ref = None
            _midi_output_port_ref = None
            target_input_port_name = None
            target_output_port_name = None
            initial_display_sent = False
            time.sleep(5)

if __name__ == '__main__':
    logging.info("Pd Controller Script starting...")
    if not os.path.exists(PD_PATH):
        logging.error(f"Critical: Pd executable not found at '{PD_PATH}'. Exiting.")
        sys.exit(1)
    if not os.path.exists(PD_PATCH):
        logging.error(f"Critical: Pd patch file not found at '{PD_PATCH}'. Exiting.")
        sys.exit(1)
        
    main_loop()
    logging.info("Pd Controller Script finished.")
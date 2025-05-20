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
# To store the mido port object for closing in signal_handler
_midi_input_port_ref = None 

# Logging - for systemd, this will go to journald
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def get_pd_pid():
    """Checks if Pd is running using a pattern matching PD_PATH and PD_PATCH, returns its PID or None."""
    try:
        pattern = f"{PD_PATH}.*{PD_PATCH}"
        result = subprocess.run(['pgrep', '-f', pattern], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            # pgrep might return multiple PIDs if the pattern is too broad, take the first.
            return int(result.stdout.strip().split('\n')[0])
        return None
    except Exception as e:
        logging.error(f"Error checking Pd PID: {e}")
        return None

def start_pd():
    """Starts the Pure Data patch if not already running."""
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
        logging.info("Pd start command issued. Check Pd logs for status.")
        time.sleep(1) # Brief pause to allow process to initialize
        new_pid = get_pd_pid()
        if new_pid:
            logging.info(f"Pd started successfully with PID {new_pid}.")
        else:
            logging.warning("Pd start command issued, but Pd process not found immediately. It might be starting or have failed.")
    except FileNotFoundError:
        logging.error(f"Failed to start Pd: PD_PATH '{PD_PATH}' not found. Ensure Pd is installed correctly.")
    except Exception as e:
        logging.error(f"Failed to start Pd: {e}")

def stop_pd():
    """Stops the Pure Data patch if running."""
    pid = get_pd_pid()
    if not pid:
        logging.info("Pd is not running. Stop command ignored.")
        return

    logging.info(f"Attempting to stop Pd with PID {pid}.")
    try:
        subprocess.run(['kill', str(pid)], check=True) # Sends SIGTERM
        logging.info(f"Sent SIGTERM to Pd PID {pid}. Waiting for shutdown...")
        
        for _ in range(5): # Check for up to 5 seconds
            time.sleep(1)
            if get_pd_pid() != pid:
                logging.info(f"Pd PID {pid} stopped successfully.")
                return
        
        logging.warning(f"Pd PID {pid} did not stop with SIGTERM. Sending SIGKILL.")
        subprocess.run(['kill', '-9', str(pid)], check=True) # Sends SIGKILL
        time.sleep(1)
        if get_pd_pid() != pid:
            logging.info(f"Pd PID {pid} stopped successfully with SIGKILL.")
        else:
            logging.error(f"Failed to stop Pd PID {pid} even with SIGKILL.")
            
    except subprocess.CalledProcessError as e:
        logging.warning(f"Error during 'kill' command for Pd PID {pid}: {e}. It might have already stopped.")
        if get_pd_pid() != pid: 
             logging.info(f"Pd PID {pid} appears to be stopped despite previous error.")
    except Exception as e:
        logging.error(f"An unexpected error occurred while stopping Pd: {e}")

def reboot_system():
    """Reboots the system. Requires passwordless sudo for 'reboot' command."""
    logging.info("Reboot command received. Initiating system reboot...")
    try:
        subprocess.run(['sudo', 'reboot'], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to reboot system: {e}. Ensure passwordless sudo is configured for 'reboot'.")
    except FileNotFoundError:
        logging.error("Failed to reboot system: 'sudo' or 'reboot' command not found.")
    except Exception as e:
        logging.error(f"An unexpected error occurred during reboot: {e}")

def find_midi_input_port_name(device_substring):
    """Finds the MIDI input port by a substring in its name (case-insensitive)."""
    try:
        input_ports = mido.get_input_names()
        for port_name in input_ports:
            if device_substring.lower() in port_name.lower(): # Changed to case-insensitive
                logging.info(f"Found MIDI input port: '{port_name}' matching substring '{device_substring}'")
                return port_name
        logging.warning(f"MIDI input port containing '{device_substring}' not found. Available ports: {input_ports}")
    except Exception as e:
        logging.error(f"Error enumerating MIDI input ports: {e}")
    return None

def signal_handler(sig, frame):
    global _midi_input_port_ref
    logging.info(f"Signal {signal.Signals(sig).name} received, shutting down gracefully...")
    if _midi_input_port_ref and hasattr(_midi_input_port_ref, 'close') and not _midi_input_port_ref.closed:
        try:
            _midi_input_port_ref.close()
            logging.info("MIDI port closed.")
        except Exception as e:
            logging.error(f"Error closing MIDI port during shutdown: {e}")
    sys.exit(0)

def main_loop():
    global cc_modifier_held, _midi_input_port_ref

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    target_port_name = None

    while True: 
        if not target_port_name:
            target_port_name = find_midi_input_port_name(MIDI_DEVICE_NAME_SUBSTRING)
            if not target_port_name:
                logging.info(f"'{MIDI_DEVICE_NAME_SUBSTRING}' MIDI device not found. Retrying in 10 seconds...")
                time.sleep(10)
                continue
        
        try:
            with mido.open_input(target_port_name) as port:
                _midi_input_port_ref = port 
                logging.info(f"Successfully opened and listening for MIDI messages on '{port.name}'")
                cc_modifier_held = False 

                for msg in port: 
                    logging.debug(f"Received MIDI message: {msg}") 
                    if msg.type == 'control_change':
                        if msg.control == CC_MODIFIER:
                            new_state_held = (msg.value > 0) # MODIFIER: Check if value > 0
                            if new_state_held != cc_modifier_held: 
                                cc_modifier_held = new_state_held
                                logging.info(f"Modifier CC {CC_MODIFIER} is now {'HELD' if cc_modifier_held else 'RELEASED'} (value: {msg.value})")
                        
                        elif cc_modifier_held and msg.value > 0: # ACTION: Check if modifier held AND value > 0
                            if msg.control == CC_START_PATCH:
                                logging.info(f"Start Patch command (CC {CC_START_PATCH}, value {msg.value}) received while modifier (CC {CC_MODIFIER}) is HELD.")
                                start_pd()
                            elif msg.control == CC_STOP_PATCH:
                                logging.info(f"Stop Patch command (CC {CC_STOP_PATCH}, value {msg.value}) received while modifier (CC {CC_MODIFIER}) is HELD.")
                                stop_pd()
                            elif msg.control == CC_REBOOT:
                                logging.info(f"Reboot command (CC {CC_REBOOT}, value {msg.value}) received while modifier (CC {CC_MODIFIER}) is HELD.")
                                reboot_system()
                                logging.info("Exiting script after reboot command.")
                                return 

        except OSError as e: 
            logging.error(f"MIDI port OS error on '{target_port_name}': {e}. Attempting to find and reconnect...")
            if _midi_input_port_ref and hasattr(_midi_input_port_ref, 'close') and not _midi_input_port_ref.closed:
                try:
                    _midi_input_port_ref.close()
                except Exception as ex_close:
                    logging.error(f"Error closing MIDI port during OSError handling: {ex_close}")
            _midi_input_port_ref = None
            target_port_name = None 
            time.sleep(5) 
        except Exception as e:
            logging.error(f"An unexpected error occurred in the MIDI processing loop: {e}")
            time.sleep(5)

if __name__ == '__main__':
    logging.info("Pd Controller Script starting...")
    if not os.path.exists(PD_PATH):
        logging.error(f"Critical: Pd executable not found at '{PD_PATH}'. Please check configuration. Exiting.")
        sys.exit(1)
    if not os.path.exists(PD_PATCH):
        logging.error(f"Critical: Pd patch file not found at '{PD_PATCH}'. Please check configuration. Exiting.")
        sys.exit(1)
        
    main_loop()
    logging.info("Pd Controller Script finished.")

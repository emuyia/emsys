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

PYTHON_EXEC = "/home/patch/repos/emsys/.venv/bin/python"
EMBLISS_PACKAGE_PARENT_DIR = "/home/patch/repos/emsys" 
EMBLISS_MODULE_NAME = "embliss.main" 
EMBLISS_MAIN_SCRIPT = os.path.join(EMBLISS_PACKAGE_PARENT_DIR, "embliss", "main.py") # For PID check

# MIDI CC numbers
CC_MODIFIER = 109
CC_START_PD = 107       
CC_START_EMBLISS = 108  
CC_STOP_APP = 106       
CC_REBOOT = 105

# State
cc_modifier_held = False
_midi_input_port_ref = None
_midi_output_port_ref = None
active_application = None  # "pd", "embliss", or None
embliss_process = None     

# SysEx Configuration
SYSEX_INIT_DATA_TUPLE = (0, 32, 107, 127, 66, 2, 2, 64, 106, 33)
SYSEX_ARTURIA_HEADER = (0x00, 0x20, 0x6B, 0x7F, 0x42)
SYSEX_TEXT_CMD_PREFIX = SYSEX_ARTURIA_HEADER + (0x04, 0x02, 0x60)

# Default display texts for when NO app is active
TEXT_CTRL_READY_L1 = "Shift+Tap+ P5:exit" 
TEXT_CTRL_READY_L2 = "P6:sys P7:bliss" # S+P6 for Pd, S+P7 for Embliss (Set Mgmt)
# TEXT_PD_ACTIVE_L1/L2 and TEXT_EMBLISS_ACTIVE_L1/L2 are removed as controller won't manage display when apps are active.


logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def flash_pisound_leds_on_startup():
    # ... (implementation remains the same)
    logging.info("Attempting to flash Pisound LEDs for startup notification...")
    common_sh_path = "/usr/local/pisound/scripts/common/common.sh"
    if not os.path.exists(common_sh_path):
        logging.warning(f"Pisound common script not found at {common_sh_path}. Cannot flash LEDs.")
        return
    command_to_run = (
        f". {common_sh_path} && "
        "for i in 1 2 3; do flash_leds 1; sleep 0.1; done && "
        "log 'em_pd_controller.py: Startup notification LEDs flashed.'"
    )
    try:
        result = subprocess.run(['bash', '-c', command_to_run], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            logging.info("Pisound LEDs flashed successfully.")
        else:
            logging.error(f"Failed to flash Pisound LEDs. stderr: {result.stderr.strip()}")
    except Exception as e:
        logging.error(f"An error occurred while trying to flash Pisound LEDs: {e}")


def get_pd_pid():
    # ... (implementation remains the same)
    try:
        pattern = f"{PD_PATH}.*{PD_PATCH}"
        result = subprocess.run(['pgrep', '-f', pattern], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split('\n')[0])
        return None
    except Exception as e:
        logging.error(f"Error checking Pd PID: {e}")
        return None

def get_embliss_pid():
    # ... (implementation remains the same)
    global embliss_process
    if embliss_process and embliss_process.poll() is None: 
        return embliss_process.pid
    try:
        pattern = f"{PYTHON_EXEC}.*-m.*{EMBLISS_MODULE_NAME.split('.')[0]}" # Adjusted pgrep pattern for -m
        # Or more specific: pattern = f"{PYTHON_EXEC} -m {EMBLISS_MODULE_NAME}"
        # If embliss/main.py is unique enough: pattern = f"python.*{EMBLISS_MAIN_SCRIPT}"
        result = subprocess.run(['pgrep', '-f', pattern], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split('\n')[0])
        return None
    except Exception as e:
        logging.error(f"Error checking embliss PID with pgrep: {e}")
        return None

def update_minilab_display_if_idle(line1, line2):
    """Updates display ONLY if no other application is supposed to be active."""
    if active_application is None:
        if _midi_output_port_ref and not _midi_output_port_ref.closed:
            text_data = construct_text_sysex(line1, line2)
            if text_data:
                send_sysex_message(_midi_output_port_ref, text_data, "Minilab3 Display Update (Idle)")
        else:
            logging.warning("Cannot update Minilab display: Output port not available.")
    else:
        logging.debug(f"Display update suppressed: App '{active_application}' is active.")


def start_pd_app():
    global active_application
    if active_application is not None:
        logging.warning(f"Cannot start Pd: App '{active_application}' is already active. Stop it first.")
        # Optionally, send a message to display like "Stop app first"
        # update_minilab_display_if_idle("Stop current app", f"Then S+P6:PD") # This would show if idle
        return

    pid = get_pd_pid()
    if pid:
        logging.info(f"Pd is already running (PID {pid}), but not marked active. Marking active.")
        active_application = "pd"
        # No display update here; Pd will control its display.
        return
    
    logging.info(f"Attempting to start Pd: {PD_PATH} with patch {PD_PATCH}")
    pd_env = os.environ.copy()
    pd_env["JACK_PROMISCUOUS_SERVER"] = "jack"; pd_env["DISPLAY"] = ":0"; pd_env["HOME"] = USER_HOME
    command = [PD_PATH, "-jack", "-rt", "-nogui", PD_PATCH]
    try:
        subprocess.Popen(command, env=pd_env)
        logging.info("Pd start command issued.")
        time.sleep(1.5) # Increased sleep to allow Pd to potentially take over display
        if get_pd_pid():
            logging.info("Pd started successfully.")
            active_application = "pd"
            # NO display update from controller - Pd is now in charge of the screen
        else:
            logging.warning("Pd process not found after start command.")
            active_application = None # Ensure state is None
            update_minilab_display_if_idle(TEXT_CTRL_READY_L1, TEXT_CTRL_READY_L2)
    except Exception as e:
        logging.error(f"Failed to start Pd: {e}")
        active_application = None
        update_minilab_display_if_idle(TEXT_CTRL_READY_L1, TEXT_CTRL_READY_L2)

def stop_pd_app():
    global active_application
    pid = get_pd_pid()
    if not pid:
        logging.info("Pd is not running. Stop command ignored.")
        if active_application == "pd": # Correct state if it was marked active
            active_application = None
            update_minilab_display_if_idle(TEXT_CTRL_READY_L1, TEXT_CTRL_READY_L2)
        return

    logging.info(f"Attempting to stop Pd with PID {pid}.")
    try:
        subprocess.run(['kill', str(pid)], check=True) 
        time.sleep(0.5) 
        if get_pd_pid() is None:
            logging.info(f"Pd PID {pid} stopped successfully with SIGTERM.")
        else: 
            logging.warning(f"Pd PID {pid} did not stop with SIGTERM. Sending SIGKILL.")
            subprocess.run(['kill', '-9', str(pid)], check=True)
            time.sleep(0.5)
            if get_pd_pid() is None: logging.info(f"Pd PID {pid} stopped successfully with SIGKILL.")
            else: logging.error(f"Failed to stop Pd PID {pid} even with SIGKILL.")
    except Exception as e:
        logging.error(f"Error stopping Pd: {e}")

    if get_pd_pid() is None: 
        logging.info("Pd confirmed stopped.")
        if active_application == "pd": active_application = None
        update_minilab_display_if_idle(TEXT_CTRL_READY_L1, TEXT_CTRL_READY_L2)
    else:
        logging.error("Pd failed to stop. State may be inconsistent.")
        # Don't update display, as Pd might still be controlling it or in a bad state.

def start_embliss_app():
    global active_application, embliss_process
    if active_application is not None:
        logging.warning(f"Cannot start Embliss: App '{active_application}' is already active. Stop it first.")
        return

    if get_embliss_pid(): # Check if it's somehow already running
        logging.info(f"Embliss is already running (PID {get_embliss_pid()}), but not marked active. Marking active.")
        active_application = "embliss"
        embliss_process = None # We don't have the handle, so pgrep will be used by get_embliss_pid
        # No display update here; Embliss will control its display.
        return

    logging.info(f"Attempting to start Embliss: {PYTHON_EXEC} -m {EMBLISS_MODULE_NAME}")
    try:
        embliss_process = subprocess.Popen(
            [PYTHON_EXEC, "-m", EMBLISS_MODULE_NAME], 
            cwd=EMBLISS_PACKAGE_PARENT_DIR
        )
        logging.info("Embliss start command issued.")
        time.sleep(1.5) # Increased sleep
        if embliss_process.poll() is None: 
            logging.info(f"Embliss started successfully with PID {embliss_process.pid}.")
            active_application = "embliss"
            # NO display update from controller - Embliss is in charge
        else:
            logging.warning(f"Embliss process not found or exited quickly. Exit code: {embliss_process.returncode}")
            embliss_process = None
            active_application = None
            update_minilab_display_if_idle(TEXT_CTRL_READY_L1, TEXT_CTRL_READY_L2)
    except Exception as e:
        logging.error(f"Failed to start Embliss: {e}", exc_info=True)
        embliss_process = None
        active_application = None
        update_minilab_display_if_idle(TEXT_CTRL_READY_L1, TEXT_CTRL_READY_L2)

def stop_embliss_app():
    global active_application, embliss_process
    pid_check = get_embliss_pid() # Use the function that checks both handle and pgrep
    
    if not pid_check:
        logging.info("Embliss is not running. Stop command ignored.")
        if embliss_process: embliss_process = None 
        if active_application == "embliss":
            active_application = None
            update_minilab_display_if_idle(TEXT_CTRL_READY_L1, TEXT_CTRL_READY_L2)
        return

    actual_pid_to_stop = embliss_process.pid if embliss_process and embliss_process.poll() is None else pid_check
    logging.info(f"Attempting to stop Embliss with PID {actual_pid_to_stop}.")
    
    try:
        if embliss_process and embliss_process.pid == actual_pid_to_stop : # If we have the correct Popen object
            embliss_process.terminate() 
            try: embliss_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                logging.warning(f"Embliss PID {actual_pid_to_stop} (handle) did not terminate. Killing.")
                embliss_process.kill(); embliss_process.wait(timeout=1)
        else: # Fallback to command line kill
            subprocess.run(['kill', str(actual_pid_to_stop)], check=True) 
            time.sleep(0.5)
            if get_embliss_pid() is None: logging.info(f"Embliss PID {actual_pid_to_stop} (cmd) stopped with SIGTERM.")
            else:
                subprocess.run(['kill', '-9', str(actual_pid_to_stop)], check=True); time.sleep(0.5)
                if get_embliss_pid() is None: logging.info(f"Embliss PID {actual_pid_to_stop} (cmd) stopped with SIGKILL.")
                else: logging.error(f"Failed to stop Embliss PID {actual_pid_to_stop} (cmd) with SIGKILL.")
    except Exception as e:
        logging.error(f"Error stopping Embliss: {e}")
    finally:
        embliss_process = None 

    if get_embliss_pid() is None: 
        logging.info("Embliss confirmed stopped.")
        if active_application == "embliss": active_application = None
        update_minilab_display_if_idle(TEXT_CTRL_READY_L1, TEXT_CTRL_READY_L2)
    else:
        logging.error("Embliss failed to stop. State may be inconsistent.")

def stop_currently_active_app():
    # ... (implementation remains similar, calls stop_pd_app or stop_embliss_app) ...
    global active_application
    logging.info(f"Stop active app command received. Current active: {active_application}")
    if active_application == "pd":
        stop_pd_app()
    elif active_application == "embliss":
        stop_embliss_app()
    else:
        logging.info("No application was marked as active to stop.")
        # Check and stop if any are running orphan
        pd_running = get_pd_pid()
        embliss_running = get_embliss_pid()
        if pd_running:
            logging.info(f"Found orphaned Pd (PID {pd_running}). Stopping it.")
            stop_pd_app()
        if embliss_running: # Check again after potential pd stop
            logging.info(f"Found orphaned Embliss (PID {embliss_running}). Stopping it.")
            stop_embliss_app()
        
        # If neither was running or after stopping orphans, ensure idle display
        if not get_pd_pid() and not get_embliss_pid():
             update_minilab_display_if_idle(TEXT_CTRL_READY_L1, TEXT_CTRL_READY_L2)


def reboot_system():
    # ... (implementation remains the same) ...
    logging.info("Reboot command received. Initiating system reboot...")
    try:
        if active_application == "pd": stop_pd_app()
        elif active_application == "embliss": stop_embliss_app()
        time.sleep(0.5) # Give a moment for apps to close
        subprocess.run(['sudo', 'reboot'], check=True)
    except Exception as e:
        logging.error(f"Failed to reboot system: {e}")

def find_midi_input_port_name(device_substring):
    # ... (implementation remains the same) ...
    try:
        for port_name in mido.get_input_names():
            if device_substring.lower() in port_name.lower():
                logging.info(f"Found MIDI input port: '{port_name}'")
                return port_name
        logging.warning(f"MIDI input port containing '{device_substring}' not found. Available: {mido.get_input_names()}")
    except Exception as e: logging.error(f"Error enumerating MIDI input ports: {e}")
    return None

def find_midi_output_port_name(device_substring):
    # ... (implementation remains the same) ...
    try:
        for port_name in mido.get_output_names():
            if device_substring.lower() in port_name.lower():
                logging.info(f"Found MIDI output port: '{port_name}'")
                return port_name
        logging.warning(f"MIDI output port containing '{device_substring}' not found. Available: {mido.get_output_names()}")
    except Exception as e: logging.error(f"Error enumerating MIDI output ports: {e}")
    return None

def send_sysex_message(out_port, sysex_data_tuple, description="SysEx"):
    # ... (implementation remains the same) ...
    try:
        msg = mido.Message('sysex', data=sysex_data_tuple)
        out_port.send(msg)
        logging.debug(f"Sent {description} (data: {sysex_data_tuple})") 
        time.sleep(0.05) 
    except Exception as e: logging.error(f"Failed to send {description} message: {e}")

def construct_text_sysex(line1_text, line2_text):
    # ... (implementation remains the same) ...
    try:
        s1_bytes = tuple(ord(c) for c in line1_text[:16]) 
        s2_bytes = tuple(ord(c) for c in line2_text[:16]) 
        text_data = SYSEX_TEXT_CMD_PREFIX + (0x01,) + s1_bytes + (0x00,) + (0x02,) + s2_bytes
        return text_data
    except Exception as e: logging.error(f"Error constructing text SysEx: {e}"); return None

def process_midi_input(in_port):
    # ... (implementation remains the same, calls new start/stop functions) ...
    global cc_modifier_held
    for msg in in_port:
        logging.debug(f"Received MIDI message: {msg}")
        if msg.type == 'control_change':
            if msg.control == CC_MODIFIER:
                new_state_held = (msg.value > 0)
                if new_state_held != cc_modifier_held:
                    cc_modifier_held = new_state_held
                    logging.info(f"Modifier CC {CC_MODIFIER} is now {'HELD' if cc_modifier_held else 'RELEASED'}")
            elif cc_modifier_held and msg.value > 0: 
                if msg.control == CC_START_PD:
                    logging.info(f"Start Pd command (CC {CC_START_PD}) with modifier.")
                    start_pd_app()
                elif msg.control == CC_START_EMBLISS:
                    logging.info(f"Start Embliss command (CC {CC_START_EMBLISS}) with modifier.")
                    start_embliss_app()
                elif msg.control == CC_STOP_APP:
                    logging.info(f"Stop Active App command (CC {CC_STOP_APP}) with modifier.")
                    stop_currently_active_app()
                elif msg.control == CC_REBOOT:
                    logging.info(f"Reboot command (CC {CC_REBOOT}) with modifier.")
                    reboot_system()
                    logging.info("Exiting script after reboot command.")
                    return True 
    return False 

def signal_handler_main(sig, frame):
    # ... (implementation remains similar, ensures embliss_process is handled) ...
    global _midi_input_port_ref, _midi_output_port_ref, embliss_process
    logging.info(f"Signal {signal.Signals(sig).name} received, em_pd_controller shutting down...")
    
    if embliss_process and embliss_process.poll() is None:
        logging.info("Attempting to stop Embliss subprocess before exiting...")
        embliss_process.terminate()
        try: embliss_process.wait(timeout=1)
        except subprocess.TimeoutExpired: embliss_process.kill()
        logging.info("Embliss subprocess stop attempt complete.")
    
    if _midi_output_port_ref and not _midi_output_port_ref.closed: # Check output port first for final message
        try: 
            update_minilab_display_if_idle("Controller", "Exiting...") 
            time.sleep(0.1)
        except Exception as e: logging.error(f"Error sending exit message: {e}")
        finally: # Ensure port is closed even if message fails
            try: _midi_output_port_ref.close(); logging.info("MIDI output port closed.")
            except Exception as e: logging.error(f"Error closing MIDI output port: {e}")
            _midi_output_port_ref = None # Clear ref

    if _midi_input_port_ref and hasattr(_midi_input_port_ref, 'close') and not _midi_input_port_ref.closed:
        try: _midi_input_port_ref.close(); logging.info("MIDI input port closed.")
        except Exception as e: logging.error(f"Error closing MIDI input port: {e}")
        _midi_input_port_ref = None # Clear ref
    sys.exit(0)

def main_loop():
    # ... (Initial display logic needs to use update_minilab_display_if_idle) ...
    global _midi_input_port_ref, _midi_output_port_ref, active_application

    signal.signal(signal.SIGINT, signal_handler_main)
    signal.signal(signal.SIGTERM, signal_handler_main)

    target_input_port_name = None
    target_output_port_name = None
    
    # Determine initial state without sending display updates yet,
    # as MIDI ports might not be open.
    if get_pd_pid():
        active_application = "pd"
        logging.info("Found Pd running on startup.")
    elif get_embliss_pid():
        active_application = "embliss"
        logging.info("Found Embliss running on startup.")
    else:
        active_application = None
        logging.info("No app found running on startup.")
    # The first display update will happen when the output port is confirmed open.

    while True:
        # ... (MIDI port finding logic remains similar) ...
        if not target_input_port_name:
            target_input_port_name = find_midi_input_port_name(MIDI_DEVICE_NAME_SUBSTRING)
            if not target_input_port_name: time.sleep(10); continue
        
        if not target_output_port_name or (_midi_output_port_ref and _midi_output_port_ref.closed):
            if _midi_output_port_ref and _midi_output_port_ref.closed:
                 _midi_output_port_ref = None; target_output_port_name = None
            
            new_target_output_port_name = find_midi_output_port_name(MIDI_DEVICE_NAME_SUBSTRING)
            if not new_target_output_port_name:
                logging.warning(f"Output port '{MIDI_DEVICE_NAME_SUBSTRING}' not found.")
                if target_output_port_name: # It was previously found but now lost
                    target_output_port_name = None 
            elif new_target_output_port_name != target_output_port_name : # New port found or first time
                target_output_port_name = new_target_output_port_name
                try:
                    # Close if already open (e.g. changed port)
                    if _midi_output_port_ref and not _midi_output_port_ref.closed: _midi_output_port_ref.close()
                    _midi_output_port_ref = mido.open_output(target_output_port_name)
                    logging.info(f"Successfully opened MIDI output on '{_midi_output_port_ref.name}' for main loop.")
                    send_sysex_message(_midi_output_port_ref, SYSEX_INIT_DATA_TUPLE, "Minilab3 Init on Port Open")
                    update_minilab_display_if_idle(TEXT_CTRL_READY_L1, TEXT_CTRL_READY_L2) # Update based on current idle state
                except Exception as e_out_open:
                    logging.error(f"Failed to open MIDI output port '{target_output_port_name}': {e_out_open}")
                    _midi_output_port_ref = None; target_output_port_name = None
        
        # If output port is still not available after checks, SysEx dependent operations will be skipped by helper functions
        # So, we can proceed to open input port.

        try:
            with mido.open_input(target_input_port_name) as in_port:
                _midi_input_port_ref = in_port # Assign to global for signal handler
                if not _midi_output_port_ref and target_output_port_name: # Try to open output if not already
                    try:
                        _midi_output_port_ref = mido.open_output(target_output_port_name)
                        logging.info(f"MIDI output '{_midi_output_port_ref.name}' confirmed open within input context.")
                        # If it's just opened, send init and idle display
                        send_sysex_message(_midi_output_port_ref, SYSEX_INIT_DATA_TUPLE, "Minilab3 Init")
                        update_minilab_display_if_idle(TEXT_CTRL_READY_L1, TEXT_CTRL_READY_L2)
                    except Exception as e:
                        logging.error(f"Error opening output port '{target_output_port_name}' in input context: {e}")
                        _midi_output_port_ref = None


                logging.info(f"Successfully opened MIDI input on '{in_port.name}'")
                cc_modifier_held = False 
                
                if process_midi_input(in_port): 
                    return 
        
        except OSError as e:
            logging.error(f"MIDI port OS error (input: '{target_input_port_name}'): {e}. Reconnecting...")
            if _midi_input_port_ref and not _midi_input_port_ref.closed: _midi_input_port_ref.close(); _midi_input_port_ref = None
            if _midi_output_port_ref and not _midi_output_port_ref.closed: _midi_output_port_ref.close(); _midi_output_port_ref = None
            target_input_port_name, target_output_port_name = None, None
            time.sleep(5)
        except Exception as e:
            logging.error(f"Unexpected error in main loop: {e}", exc_info=True)
            if _midi_input_port_ref and not _midi_input_port_ref.closed: _midi_input_port_ref.close(); _midi_input_port_ref = None
            if _midi_output_port_ref and not _midi_output_port_ref.closed: _midi_output_port_ref.close(); _midi_output_port_ref = None
            target_input_port_name, target_output_port_name = None, None
            time.sleep(5)


if __name__ == '__main__':
    # ... (startup checks remain the same) ...
    logging.info("em_pd_controller.py starting...")
    flash_pisound_leds_on_startup()

    if not os.path.exists(PD_PATH): logging.error(f"Critical: Pd executable not found at '{PD_PATH}'.")
    if not os.path.exists(PYTHON_EXEC): logging.error(f"Critical: Python for embliss not found at '{PYTHON_EXEC}'.")
    if not os.path.exists(EMBLISS_MAIN_SCRIPT): logging.error(f"Critical: Embliss main script not found at '{EMBLISS_MAIN_SCRIPT}'.")
        
    main_loop()
    logging.info("em_pd_controller.py finished.")
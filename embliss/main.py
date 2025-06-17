import time
import logging
import signal
import sys

from . import config
from .midi_handler import MidiHandler
from .set_manager import SetManager
from .screen_manager import ScreenManager
from .screens.set_list_screen import SetListScreen

# --- Logging Setup ---
# Basic configuration, can be expanded (e.g., file logging)
logging.basicConfig(
    level=logging.DEBUG,  # Set to logging.INFO for less verbose output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout  # Log to standard output
)
logger = logging.getLogger(__name__) # Logger for this main module

# --- Global Variables ---
running = True
midi_handler_instance = None # To be accessible by signal_handler

# --- Signal Handler for Graceful Exit ---
def signal_handler(sig, frame):
    global running, midi_handler_instance
    logger.info(f"Signal {signal.Signals(sig).name} received. Shutting down Embliss...")
    running = False
    # Cleanup will happen in the finally block of the main loop

def main():
    global running, midi_handler_instance
    logger.info("Starting Embliss Set Management Application...")

    # Initialize core components
    midi_handler_instance = MidiHandler()
    set_manager_instance = SetManager() # Loads sets on init

    # Check if MIDI connection was successful
    if not midi_handler_instance.is_connected():
        logger.warning("MIDI ports not connected. Display/control will be unavailable.")
        # Decide if you want to proceed or exit. For now, let's proceed but it won't be very useful.
        # You might want a loop here to retry connection or wait.
        # For simplicity, we'll let it run, and the midi_handler will keep trying.

    # Initialize ScreenManager with the initial screen
    # Pass set_manager to ScreenManager if screens need it (SetListScreen does)
    screen_manager_instance = ScreenManager(midi_handler_instance, 
                                            initial_screen_class=SetListScreen,
                                            set_manager=set_manager_instance)

    # Register signal handlers for SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Embliss initialized. Entering main loop...")
    try:
        while running:
            # 1. Ensure MIDI ports are open (attempt reconnect if necessary)
            if not midi_handler_instance.ensure_ports_open():
                # If still not connected after trying, wait before next attempt
                logger.debug(f"MIDI not connected. Waiting {config.RECONNECT_INTERVAL}s to retry.")
                time.sleep(config.RECONNECT_INTERVAL)
                continue # Skip processing this iteration if no MIDI

            # 2. Process incoming MIDI messages
            message = midi_handler_instance.get_message() # Non-blocking poll
            if message:
                logger.debug(f"MIDI In: {message}")
                screen_manager_instance.process_midi_input(message)

            # 3. Allow current screen to update itself (if needed for animations, etc.)
            screen_manager_instance.update_current_screen()
            
            # 4. Sleep for a short interval to prevent high CPU usage
            time.sleep(config.POLLING_INTERVAL)

    except Exception as e:
        logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
    finally:
        logger.info("Exiting Embliss main loop.")
        if midi_handler_instance:
            logger.info("Clearing Minilab3 display...")
            midi_handler_instance.update_display(" ", " ") # Clear display
            logger.info("Closing MIDI ports...")
            midi_handler_instance.close_ports()
        logger.info("Embliss shutdown complete.")

if __name__ == '__main__':
    main()
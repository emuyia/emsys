import mido
import time
import logging
from . import config

# Configure logging for this module
logger = logging.getLogger(__name__)

class MidiHandler:
    def __init__(self, device_name_substring=config.MIDI_DEVICE_NAME_SUBSTRING):
        self.device_name_substring = device_name_substring
        self.in_port = None
        self.out_port = None
        self._connect_ports()

    def _find_midi_port_name(self, port_names_func, port_type="input"):
        """Generic function to find a MIDI port by substring in its name."""
        try:
            for port_name in port_names_func():
                if self.device_name_substring.lower() in port_name.lower():
                    logger.info(f"Found MIDI {port_type} port: '{port_name}'")
                    return port_name
            logger.warning(f"MIDI {port_type} port containing '{self.device_name_substring}' not found. Available: {port_names_func()}")
        except Exception as e:
            logger.error(f"Error enumerating MIDI {port_type} ports: {e}")
        return None

    def _connect_ports(self):
        """Attempts to find and open MIDI input and output ports."""
        input_port_name = self._find_midi_port_name(mido.get_input_names, "input")
        output_port_name = self._find_midi_port_name(mido.get_output_names, "output")

        opened_input = False
        opened_output = False

        if input_port_name:
            try:
                self.in_port = mido.open_input(input_port_name)
                logger.info(f"Successfully opened MIDI input on '{self.in_port.name}'")
                opened_input = True
            except Exception as e:
                logger.error(f"Failed to open MIDI input port '{input_port_name}': {e}")
                self.in_port = None
        
        if output_port_name:
            try:
                self.out_port = mido.open_output(output_port_name)
                logger.info(f"Successfully opened MIDI output on '{self.out_port.name}'")
                opened_output = True
            except Exception as e:
                logger.error(f"Failed to open MIDI output port '{output_port_name}': {e}")
                self.out_port = None
        
        if opened_input and opened_output:
            logger.info("Both MIDI ports opened. Sending initial SysEx configuration.")
            self.send_sysex_message(config.SYSEX_INIT_DATA_TUPLE, "Minilab3 Init Data")
            # Optionally, send a default screen message here too if desired,
            # but screens themselves will manage their initial display.
        elif not self.in_port or not self.out_port:
            logger.warning("One or both MIDI ports could not be opened. Retrying will be necessary.")


    def send_sysex_message(self, sysex_data_tuple, description="SysEx"):
        """Sends a SysEx message using the provided mido output port."""
        if not self.out_port or self.out_port.closed:
            logger.warning(f"Cannot send {description}: Output port not available or closed.")
            return
        try:
            msg = mido.Message('sysex', data=sysex_data_tuple)
            self.out_port.send(msg)
            logger.debug(f"Sent {description} message (data: {sysex_data_tuple})")
            time.sleep(0.05)  # Small delay after sending SysEx, can be tuned
        except Exception as e:
            logger.error(f"Failed to send {description} message: {e}")

    def construct_text_sysex_data(self, line1_text="", line2_text=""):
        """Constructs the data tuple for a Minilab3 text display SysEx message."""
        try:
            # Truncate lines if they are too long
            s1 = line1_text[:config.SCREEN_LINE_1_MAX_CHARS]
            s2 = line2_text[:config.SCREEN_LINE_2_MAX_CHARS]

            s1_bytes = tuple(ord(c) for c in s1)
            s2_bytes = tuple(ord(c) for c in s2)
            
            # SysEx structure for Minilab 3 text:
            # F0 <ArturiaHeader> <TextCommandPrefix> 01 <Line1TextBytes> 00 02 <Line2TextBytes> F7
            # Data for mido.Message data field:
            # <ArturiaHeader> <TextCommandPrefix> 01 <Line1TextBytes> 00 02 <Line2TextBytes>
            
            text_data = config.SYSEX_TEXT_CMD_PREFIX + \
                        (0x01,) + s1_bytes + (0x00,) + \
                        (0x02,) + s2_bytes
            return text_data
        except Exception as e:
            logger.error(f"Error constructing text SysEx data: {e}")
            return None

    def update_display(self, line1, line2):
        """Constructs and sends the SysEx message to update the Minilab3 display."""
        sysex_data = self.construct_text_sysex_data(line1, line2)
        if sysex_data:
            self.send_sysex_message(sysex_data, "Minilab3 Display Update")
        else:
            logger.warning("Could not update display because SysEx data construction failed.")
            
    def get_message(self, block=False):
        """Gets a MIDI message from the input port."""
        if self.in_port and not self.in_port.closed:
            return self.in_port.poll() # Non-blocking
            # For blocking, use: return self.in_port.receive(block=True)
        return None

    def ensure_ports_open(self):
        """Checks if ports are open and tries to reconnect if not."""
        if (self.in_port is None or self.in_port.closed) or \
           (self.out_port is None or self.out_port.closed):
            logger.warning("MIDI ports are not open. Attempting to reconnect...")
            self.close_ports() # Ensure clean state before reconnecting
            self._connect_ports()
            return self.is_connected()
        return True

    def is_connected(self):
        """Checks if both input and output ports are open and usable."""
        return (self.in_port is not None and not self.in_port.closed) and \
               (self.out_port is not None and not self.out_port.closed)

    def close_ports(self):
        """Closes MIDI input and output ports if they are open."""
        if self.in_port and not self.in_port.closed:
            try:
                self.in_port.close()
                logger.info("MIDI input port closed.")
            except Exception as e:
                logger.error(f"Error closing MIDI input port: {e}")
        self.in_port = None

        if self.out_port and not self.out_port.closed:
            try:
                self.out_port.close()
                logger.info("MIDI output port closed.")
            except Exception as e:
                logger.error(f"Error closing MIDI output port: {e}")
        self.out_port = None

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Testing MidiHandler...")
    handler = MidiHandler()
    if handler.is_connected():
        logger.info("MIDI ports seem to be connected.")
        handler.update_display("Embliss Test", "Line 2 Ready")
        logger.info("Sent test display message. Check Minilab3.")
        logger.info("Listening for MIDI messages for 10 seconds...")
        start_time = time.time()
        try:
            while time.time() - start_time < 10:
                msg = handler.get_message()
                if msg:
                    logger.info(f"Received MIDI: {msg}")
                time.sleep(0.01)
        except KeyboardInterrupt:
            logger.info("Test interrupted.")
        finally:
            handler.update_display("", "") # Clear display
            handler.close_ports()
    else:
        logger.warning("Could not connect to MIDI ports for testing.")
    logger.info("MidiHandler test finished.")
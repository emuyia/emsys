from time import perf_counter, sleep
from multiprocessing import Process, Value, freeze_support
import mido
import logging
import sys

logging.basicConfig(level=logging.DEBUG)

class MidiClockGen:
    def __init__(self):
        self.shared_bpm = Value('i', 120)
        self._run_code = Value('i', 1)
        self.pulse_rate = Value('d', 60.0 / (self.shared_bpm.value * 24))
        self.clock_running = Value('i', 1)
        self.midi_process = None

    def update_pulse_rate(self):
        self.pulse_rate.value = 60.0 / (self.shared_bpm.value * 24)

    @staticmethod
    def _midi_clock_generator(out_port_name, pulse_rate, run, clock_running):
        try:
            # Cross-platform port handling
            if sys.platform == 'win32':
                midi_output = mido.open_output(out_port_name)
            else:
                midi_output = mido.open_output(out_port_name, virtual=True)

            clock_tick = mido.Message('clock')
            while run.value:
                if clock_running.value:
                    midi_output.send(clock_tick)
                    t1 = perf_counter()
                    sleep(pulse_rate.value * 0.8)
                    t2 = perf_counter()
                    while (t2 - t1) < pulse_rate.value:
                        t2 = perf_counter()
                else:
                    sleep(0.1)
        except Exception as e:
            logging.error(f"Error in MIDI clock generator: {e}")

    def launch_process(self, out_port_name):
        if self.midi_process:
            self.end_process()
        self._run_code.value = 1
        self.clock_running.value = 1
        self.midi_process = Process(target=self._midi_clock_generator,
                                    args=(out_port_name, self.pulse_rate, self._run_code, self.clock_running))
        self.midi_process.start()

    def end_process(self):
        if self.midi_process is not None:
            self._run_code.value = 0
            self.midi_process.join()
            self.midi_process = None

def midi_bpm_listener(shared_bpm, run_code, clock_running, pulse_rate, in_port_name, cc_bpm=40, cc_start_stop=41):
    try:
        # Cross-platform port handling
        if sys.platform == 'win32':
            midi_input = mido.open_input(in_port_name)
        else:
            midi_input = mido.open_input(in_port_name, virtual=True)

        while run_code.value:
            for msg in midi_input.iter_pending():
                if msg.type == 'control_change':
                    if msg.control == cc_bpm:
                        new_bpm = int(30 + (msg.value * (300 - 30) / 127))
                        shared_bpm.value = new_bpm
                        pulse_rate.value = 60.0 / (new_bpm * 24)
                        logging.debug(f"set bpm: {new_bpm}")
                    elif msg.control == cc_start_stop:
                        clock_running.value = 1 if msg.value >= 64 else 0
            sleep(0.1)
    except Exception as e:
        logging.error(f"Error in MIDI BPM listener: {e}")

class MidiClockApp:
    def __init__(self):
        self.mcg = MidiClockGen()

    def clean_exit(self):
        if self.mcg.midi_process:
            self.mcg.end_process()

    def start(self):
        # Platform-specific port configuration
        if sys.platform == 'win32':
            # Find loopMIDI ports on Windows
            input_ports = mido.get_input_names()
            output_ports = mido.get_output_names()
            virtual_in_port = next((p for p in input_ports if 'em_clock' in p), None)
            virtual_out_port = next((p for p in output_ports if 'em_clock' in p), None)
            
            if not virtual_in_port or not virtual_out_port:
                raise RuntimeError("Couldn't find loopMIDI ports. Ensure they're created in loopMIDI.")
        else:
            # Linux/macOS configuration
            virtual_in_port = "em_clock_in"
            virtual_out_port = "em_clock_out"

        try:
            logging.debug(f"Using MIDI ports: In='{virtual_in_port}', Out='{virtual_out_port}'")
            self.mcg.launch_process(virtual_out_port)

            midi_listener_process = Process(target=midi_bpm_listener, args=(
                self.mcg.shared_bpm, self.mcg._run_code, self.mcg.clock_running, 
                self.mcg.pulse_rate, virtual_in_port))
            midi_listener_process.start()

            logging.info("MIDI clock is running. Press Ctrl+C to stop.")
            while True:
                sleep(1)
        except KeyboardInterrupt:
            logging.info("Stopping MIDI clock...")
        finally:
            self.clean_exit()
            logging.info("MIDI clock stopped.")

if __name__ == '__main__':
    freeze_support()
    app = MidiClockApp()
    app.start()

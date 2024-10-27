from time import perf_counter, sleep
from multiprocessing import Process, Value, freeze_support
import mido
import logging

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

def midi_bpm_listener(shared_bpm, run_code, clock_running, in_port_name, cc_bpm=1, cc_start_stop=2):
    try:
        midi_input = mido.open_input(in_port_name, virtual=True)
        while run_code.value:
            for msg in midi_input.iter_pending():
                if msg.type == 'control_change':
                    if msg.control == cc_bpm:
                        new_bpm = int(30 + (msg.value * (300 - 30) / 127))
                        shared_bpm.value = new_bpm
                    elif msg.control == cc_start_stop:
                        if msg.value >= 64:
                            clock_running.value = 1
                        else:
                            clock_running.value = 0
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
        virtual_out_port = "Virtual-MIDI-Out"
        virtual_in_port = "Virtual-MIDI-In"

        try:
            logging.debug(f"Creating virtual MIDI ports: '{virtual_in_port}' (input), '{virtual_out_port}' (output)")
            self.mcg.launch_process(virtual_out_port)

            midi_listener_process = Process(target=midi_bpm_listener, args=(
                self.mcg.shared_bpm, self.mcg._run_code, self.mcg.clock_running, virtual_in_port))
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
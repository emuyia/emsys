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

class MidiClockApp:
    def __init__(self):
        self.mcg = MidiClockGen()

    def clean_exit(self):
        if self.mcg.midi_process:
            self.mcg.end_process()

    def start(self):
        virtual_out_port = "Virtual-MIDI-Out"
        try:
            logging.debug(f"Creating virtual MIDI ports: '{virtual_out_port}'")
            self.mcg.launch_process(virtual_out_port)
            logging.info("MIDI clock is running. Press Ctrl+C to stop.")
            while True:
                sleep(1)
        except KeyboardInterrupt:
            logging.info("\nStopping MIDI clock...")
        finally:
            self.clean_exit()
            logging.info("MIDI clock stopped.")

if __name__ == '__main__':
    freeze_support()
    app = MidiClockApp()
    app.start()
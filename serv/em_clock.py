from time import perf_counter, sleep
from multiprocessing import Process, Value, freeze_support
import mido # type: ignore


class MidiClockGen:
    def __init__(self):
        self.shared_bpm = Value('i', 120)
        self._run_code = Value('i', 1)
        self.pulse_rate = Value('d', 60.0 / (self.shared_bpm.value * 24))  # Correct pulse rate for MIDI clock
        self.midi_process = None

    def update_pulse_rate(self):
        """Update pulse rate when BPM changes."""
        self.pulse_rate.value = 60.0 / (self.shared_bpm.value * 24)
        #print(f"Updated pulse rate: {self.pulse_rate.value:.6f} seconds per clock pulse")

    @staticmethod
    def _midi_clock_generator(out_port, pulse_rate, run):
        midi_output = mido.open_output(out_port, virtual=True)  # Ensure the virtual port is created
        clock_tick = mido.Message('clock')
        while run.value:
            midi_output.send(clock_tick)
            t1 = perf_counter()

            sleep(pulse_rate.value * 0.8)  # Sleep for 80% of the pulse rate duration
            t2 = perf_counter()

            while (t2 - t1) < pulse_rate.value:
                t2 = perf_counter()


    def launch_process(self, out_port):
        if self.midi_process:
            self.end_process()
        self._run_code.value = 1
        self.midi_process = Process(target=self._midi_clock_generator,
                                    args=(out_port, self.pulse_rate, self._run_code))
        self.midi_process.start()

    def end_process(self):
        """Terminate the MIDI clock generation process."""
        if self.midi_process is not None:
            self._run_code.value = 0  # Set the flag to stop the process
            self.midi_process.join()  # Wait for the process to terminate
            self.midi_process = None


def midi_bpm_listener(mcg, in_port_name, cc_number=1):
    midi_input = mido.open_input(in_port_name, virtual=True)
    while mcg._run_code.value:
        for msg in midi_input.iter_pending():
            if msg.type == 'control_change' and msg.control == cc_number:
                new_bpm = int(30 + (msg.value * (300 - 30) / 127))
                mcg.shared_bpm.value = new_bpm
                #print(f"BPM changed to {new_bpm}")
                mcg.update_pulse_rate()  # Update pulse rate when BPM changes
        
        sleep(0.1)  # Sleep for 100 ms to reduce CPU load


class MidiClockApp:
    def __init__(self):
        self.mcg = MidiClockGen()

    def clean_exit(self):
        if self.mcg.midi_process:
            self.mcg.end_process()  # Stop the main MIDI process

    def start(self):
        virtual_out_port = "Virtual-MIDI-Out"
        virtual_in_port = "Virtual-MIDI-In"

        print(f"Creating virtual MIDI ports: '{virtual_in_port}' (input), '{virtual_out_port}' (output)")
        
        # Launch the clock process
        self.mcg.launch_process(virtual_out_port)

        # Start MIDI BPM listener on the virtual input
        midi_process = Process(target=midi_bpm_listener, args=(self.mcg, virtual_in_port))
        midi_process.start()

        try:
            print("MIDI clock is running. Press Ctrl+C to stop.")
            while True:
                sleep(1)
        except KeyboardInterrupt:
            print("\nStopping MIDI clock...")
        finally:
            self.clean_exit()  # Cleanly exit and terminate both processes
            print("MIDI clock stopped.")


if __name__ == '__main__':
    freeze_support()
    app = MidiClockApp()
    app.start()

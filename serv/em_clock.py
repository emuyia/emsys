import sys
from time import perf_counter, sleep
from multiprocessing import Process, Value, freeze_support
import mido

class MidiClockGen:
    def __init__(self):
        self.shared_bpm = Value('i', 120)
        self._run_code = Value('i', 1)
        self.pulse_rate = Value('d', 60.0 / (self.shared_bpm.value * 24))  # Pre-calculate pulse rate
        self.midi_process = None

    def update_pulse_rate(self):
        """Update pulse rate when BPM changes."""
        self.pulse_rate.value = 60.0 / (self.shared_bpm.value * 24)

    @staticmethod
    def _midi_clock_generator(out_port, pulse_rate, run):
        midi_output = mido.open_output(out_port)
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
        self._run_code.value = 0
        if self.midi_process:
            self.midi_process.join()
            self.midi_process.close()

def midi_bpm_listener(mcg, in_port_name, cc_number=1):
    while True:
        try:
            midi_input = mido.open_input(in_port_name)
            break
        except OSError:
            print(f"Port '{in_port_name}' not available. Retrying...")
            sleep(2)

    while mcg._run_code.value:
        for msg in midi_input.iter_pending():
            if msg.type == 'control_change' and msg.control == cc_number:
                new_bpm = int(30 + (msg.value * (300 - 30) / 127))
                mcg.shared_bpm.value = new_bpm
                mcg.update_pulse_rate()  # Update pulse rate when BPM changes
        
        sleep(0.1)  # Sleep for 100 ms to reduce CPU load

class MidiClockApp:
    def __init__(self, port_name, midi_in_port_name):
        self.mcg = MidiClockGen()
        self.port_name = port_name
        self.midi_in_port_name = midi_in_port_name

    def start(self):
        midi_ports = mido.get_output_names()
        if not midi_ports:
            print("No MIDI output ports available.")
            return

        matching_ports = [port for port in midi_ports if self.port_name.lower() in port.lower()]
        if not matching_ports:
            print(f"Error: No matching MIDI output port found for '{self.port_name}'.")
            print("Available MIDI output ports:")
            for port in midi_ports:
                print(f"- {port}")
            return

        selected_port = matching_ports[0]
        self.mcg.launch_process(selected_port)
        
        midi_process = Process(target=midi_bpm_listener, args=(self.mcg, self.midi_in_port_name))
        midi_process.start()
        
        try:
            print("MIDI clock is running. Press Ctrl+C to stop.")
            while True:
                sleep(1)
        except KeyboardInterrupt:
            print("\nStopping MIDI clock...")
        finally:
            self.mcg.end_process()
            midi_process.terminate()
            print("MIDI clock stopped.")

if __name__ == '__main__':
    freeze_support()
    if len(sys.argv) < 3:
        print("Usage: python main.py 'MIDI Out Port Name' 'MIDI In Port Name'")
        print(mido.get_input_names())
        sys.exit(1)

    port_name_arg = sys.argv[1]
    midi_in_port_name_arg = sys.argv[2]
    app = MidiClockApp(port_name_arg, midi_in_port_name_arg)
    app.start()

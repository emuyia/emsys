import logging
from .base_screen import BaseScreen
from .. import config 
import time 

logger = logging.getLogger(__name__)

class SetListScreen(BaseScreen):
    def __init__(self, screen_manager, midi_handler, set_manager):
        super().__init__(screen_manager, midi_handler)
        self.set_manager = set_manager
        self.current_set_index = 0
        self.set_names = []
        self._load_sets()

        # For display throttling
        self.last_actual_display_time = 0
        self.display_update_pending = False
        # Min interval between display SysEx sends (e.g., 75ms = ~13 FPS for display)
        # Adjust this value based on observed performance.
        self.display_refresh_interval = 0.075 

    def _load_sets(self):
        self.set_manager.load_set_files() 
        self.set_names = self.set_manager.get_set_names()
        if not self.set_names:
            self.current_set_index = -1 
        elif self.current_set_index >= len(self.set_names) or self.current_set_index == -1:
            self.current_set_index = 0 

    def display(self):
        if not self.active: return

        line1 = "No sets found"
        line2 = "Check sets dir"
        
        if self.set_names and self.current_set_index != -1:
            total_sets = len(self.set_names)
            current_set_name = self.set_names[self.current_set_index]
            line1 = f"{self.current_set_index + 1}/{total_sets}: {current_set_name}"
            line1 = line1[:config.SCREEN_LINE_1_MAX_CHARS] 
            line2 = "Enc:Scroll P1:OK" 
            line2 = line2[:config.SCREEN_LINE_2_MAX_CHARS]

        self.midi_handler.update_display(line1, line2)
        logger.debug(f"Displaying SetListScreen: L1='{line1}', L2='{line2}'")
        self.last_actual_display_time = time.time() # Record time of actual SysEx send
        self.display_update_pending = False # Clear pending flag

    def handle_midi_input(self, message):
        if not self.active: return

        if message.type == 'control_change' and message.control == config.ENCODER_CC:
            if not self.set_names: return 

            previous_index = self.current_set_index
            if message.value == config.ENCODER_VALUE_UP: 
                self.current_set_index = (self.current_set_index + 1) % len(self.set_names)
                # logger.debug(f"Encoder 'UP' -> Scroll Down. New index: {self.current_set_index}") # Reduced logging verbosity
            elif message.value == config.ENCODER_VALUE_DOWN: 
                self.current_set_index = (self.current_set_index - 1 + len(self.set_names)) % len(self.set_names)
                # logger.debug(f"Encoder 'DOWN' -> Scroll Up. New index: {self.current_set_index}") # Reduced logging verbosity
            
            if self.current_set_index != previous_index:
                self.display_update_pending = True 
                # We don't call self.display() here directly anymore for encoder events.
                # The self.update() method will handle throttled display.
                logger.info(f"Set index changed to: {self.current_set_index}. Display update pending.")


        elif message.type == 'note_on' and message.note == config.PAD_1_NOTE:
            if self.set_names and self.current_set_index != -1:
                selected_set_name = self.set_names[self.current_set_index]
                logger.info(f"Pad 1 pressed: Selected set '{selected_set_name}' (index {self.current_set_index})")
                
                temp_line1 = selected_set_name[:config.SCREEN_LINE_1_MAX_CHARS]
                temp_line2 = "Selected: " + selected_set_name
                if len(temp_line2) > config.SCREEN_LINE_2_MAX_CHARS:
                    temp_line2 = "Selected!"
                temp_line2 = temp_line2[:config.SCREEN_LINE_2_MAX_CHARS]

                display_duration = 0.75  
                refresh_interval = 0.05 
                start_time = time.time()
                
                # This temporary display loop is for immediate feedback for the "Selected" message.
                # It has its own refresh rate.
                while time.time() - start_time < display_duration:
                    self.midi_handler.update_display(temp_line1, temp_line2)
                    time.sleep(refresh_interval) 
                
                # After the "Selected" animation, ensure the main display is updated.
                # Set pending flag so the update() method refreshes the main list view.
                self.display_update_pending = True
            else:
                logger.info("Pad 1 pressed, but no set selected or no sets available.")
        
    def update(self):
        """Called periodically by the ScreenManager from the main loop."""
        if not self.active:
            return

        current_time = time.time()
        if self.display_update_pending and \
           (current_time - self.last_actual_display_time >= self.display_refresh_interval):
            logger.debug(f"Throttled display update executing. Index: {self.current_set_index}")
            self.display() # This will use the latest self.current_set_index

    def activate(self):
        super().activate() 
        self._load_sets() 
        if not self.set_names:
             logger.warning("SetListScreen activated, but no sets found.")
        elif self.current_set_index == -1 and self.set_names: 
            self.current_set_index = 0
        # Initial display is handled by super().activate() which calls self.display()
        # We need to ensure last_actual_display_time is set correctly on activation.
        self.last_actual_display_time = time.time() 
        self.display_update_pending = True # Ensure the first display happens via update if needed
                                         # or rely on super().activate() calling display()
                                         # Let's ensure it by setting it pending.
                                         # Actually, super().activate() calls self.display(),
                                         # which will set last_actual_display_time and clear pending.
                                         # So, no extra logic needed here for initial display.
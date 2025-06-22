import logging
import time
from .base_screen import BaseScreen
from .. import config

logger = logging.getLogger(__name__)

class CopyInstructionsScreen(BaseScreen):
    """A screen to display bank mapping instructions after a track copy."""
    def __init__(self, screen_manager, midi_handler, mapping_data, original_screen):
        super().__init__(screen_manager, midi_handler)
        # Sort the data: md first, then mnm
        mapping_data.sort(key=lambda x: x['type'])
        self.mapping_data = mapping_data
        self.original_screen = original_screen
        self.current_index = 0
        self.display_update_pending = False
        self.last_actual_display_time = 0
        self.display_refresh_interval = 0.075

    def activate(self):
        self.active = True
        logger.info(f"Activating CopyInstructionsScreen with {len(self.mapping_data)} mappings.")
        self.display()

    def display(self):
        if not self.active: return
        
        if not self.mapping_data:
            # This case remains the same, but we should provide a default line1
            line1 = "Copy Complete!"
            line2 = "No banks mapped"
        else:
            item = self.mapping_data[self.current_index]
            current_type = item['type']

            # Calculate total for the current item's type
            total_for_type = sum(1 for i in self.mapping_data if i['type'] == current_type)
            
            # Calculate the current item's index within its type group
            current_in_type = sum(1 for i in self.mapping_data[:self.current_index + 1] if i['type'] == current_type)

            line1 = f"transfer {current_type} {current_in_type}/{total_for_type}:"
            line2 = f"{item['source']}->{item['dest']}"

        self.midi_handler.update_display(line1[:16], line2[:15])
        self.last_actual_display_time = time.time()
        self.display_update_pending = False

    def handle_midi_input(self, message):
        if not self.active: return

        if message.type == 'control_change' and message.control == config.ENCODER_CC:
            if self.mapping_data:
                if message.value == config.ENCODER_VALUE_UP:
                    self.current_index = (self.current_index + 1) % len(self.mapping_data)
                elif message.value == config.ENCODER_VALUE_DOWN:
                    self.current_index = (self.current_index - 1 + len(self.mapping_data)) % len(self.mapping_data)
                self.display_update_pending = True

        if message.type == 'note_on' and message.note == config.PAD_6_NOTE:
            logger.info("Exiting CopyInstructionsScreen.")
            self.original_screen.activate()
            self.screen_manager.change_screen(self.original_screen)

    def update(self):
        if not self.active: return
        if self.display_update_pending and (time.time() - self.last_actual_display_time >= self.display_refresh_interval):
            self.display()
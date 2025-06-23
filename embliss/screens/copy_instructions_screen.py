import logging
import time
from .base_screen import BaseScreen
from .. import config

logger = logging.getLogger(__name__)

class CopyInstructionsScreen(BaseScreen):
    """A screen to display bank mapping instructions and commit a track copy."""
    def __init__(self, screen_manager, midi_handler, mapping_data, original_screen, source_filename, track_name_to_copy, destination_filename, mnm_kit_map=None):
        super().__init__(screen_manager, midi_handler)
        mapping_data.sort(key=lambda x: x['type'])
        self.mapping_data = mapping_data
        self.original_screen = original_screen
        self.mnm_kit_map = mnm_kit_map or {}
        self.current_index = 0
        
        # Store the final copy plan details
        self.source_filename = source_filename
        self.track_name_to_copy = track_name_to_copy
        self.destination_filename = destination_filename

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
            line1 = "Ready to Save"
            line2 = "P5:Cancel P6:Save"
        else:
            item = self.mapping_data[self.current_index]
            current_type = item['type']
            total_for_type = sum(1 for i in self.mapping_data if i['type'] == current_type)
            current_in_type = sum(1 for i in self.mapping_data[:self.current_index + 1] if i['type'] == current_type)

            line1 = f"P5:C P6:S {current_type}{current_in_type}/{total_for_type}"
            
            if current_type == 'mnm' and self.mnm_kit_map:
                dest_pattern = item['dest']
                kit_number = self.mnm_kit_map.get(dest_pattern, '???')
                kit_str = f"{kit_number:03d}" if isinstance(kit_number, int) else kit_number
                line2 = f"{item['source']}>{item['dest']}/k{kit_str}"
            else:
                line2 = f"{item['source']}>{item['dest']}"

        self.midi_handler.update_display(line1[:16], line2[:15])
        self.last_actual_display_time = time.time()
        self.display_update_pending = False

    def _commit_changes(self):
        """Commits the planned track copy to the destination file."""
        logger.info(f"Committing copy of '{self.track_name_to_copy}' to {self.destination_filename}")
        self.midi_handler.update_display("Saving...", self.destination_filename[:15])
        
        # Call the new "commit" method from set_manager
        success, message = self.screen_manager.set_manager.commit_track_copy(
            source_filename=self.source_filename,
            track_name_to_copy=self.track_name_to_copy,
            dest_filename=self.destination_filename
        )

        if success:
            self.midi_handler.update_display("Save Complete!", ""); time.sleep(2)
        else:
            self.midi_handler.update_display("Save Failed!", message[:15]); time.sleep(2)

        self.original_screen.activate()
        self.screen_manager.change_screen(self.original_screen)

    def handle_midi_input(self, message):
        if not self.active: return

        if message.type == 'control_change' and message.control == config.ENCODER_CC:
            if self.mapping_data:
                if message.value == config.ENCODER_VALUE_UP:
                    self.current_index = (self.current_index + 1) % len(self.mapping_data)
                elif message.value == config.ENCODER_VALUE_DOWN:
                    self.current_index = (self.current_index - 1 + len(self.mapping_data)) % len(self.mapping_data)
                self.display_update_pending = True

        if message.type == 'note_on':
            if message.note == config.PAD_5_NOTE: # Cancel
                logger.info("Cancelling copy operation.")
                self.midi_handler.update_display("Cancelled", ""); time.sleep(1)
                self.original_screen.activate()
                self.screen_manager.change_screen(self.original_screen)
            
            elif message.note == config.PAD_6_NOTE: # Commit
                self._commit_changes()

    def update(self):
        if not self.active: return
        if self.display_update_pending and (time.time() - self.last_actual_display_time >= self.display_refresh_interval):
            self.display()
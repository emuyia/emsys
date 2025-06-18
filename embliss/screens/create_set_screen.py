import logging
import os
import time

from .base_name_editor_screen import BaseNameEditorScreen # Changed import
from .. import config

logger = logging.getLogger(__name__)

class CreateSetScreen(BaseNameEditorScreen): # Changed inheritance
    def __init__(self, screen_manager, midi_handler, set_manager):
        super().__init__(screen_manager, midi_handler, set_manager)
        # Default name is already set by BaseNameEditorScreen's __init__
        # self.chars = ['a', 'a', 'a', 'a']
        # self.version = 0
        # self.alphabet and self.max_version are also inherited

    def display(self):
        if not self.active: return

        name_str = self.get_current_name_string() # Use helper
        line1 = f"New: {name_str}{self.version:02d}"
        line1 = line1[:config.SCREEN_LINE_1_MAX_CHARS]
        
        line2 = "S1-4:Ch K8:V P7:Cr" # P7: Create
        line2 = line2[:config.SCREEN_LINE_2_MAX_CHARS]

        self.midi_handler.update_display(line1, line2)
        logger.debug(f"Displaying CreateSetScreen: L1='{line1}', L2='{line2}'")
        self.last_actual_display_time = time.time()
        self.display_update_pending = False

    def handle_midi_input(self, message):
        if not self.active: return

        if self._handle_name_editor_midi_input(message):
            return

        if message.type == 'note_on':
            if message.note == config.PAD_7_NOTE: # Create
                self._create_set_file()
            elif message.note == config.PAD_5_NOTE: # Back/Cancel
                logger.info("Create new set cancelled. Returning to SetListScreen.")
                from .set_list_screen import SetListScreen 
                self.screen_manager.change_screen(
                    SetListScreen(self.screen_manager, self.midi_handler, self.set_manager)
                )

    def _create_set_file(self):
        new_filename_base = self.get_current_filename_base() # Use helper
        new_filename = self.get_current_full_filename() # Use helper
        new_path = os.path.join(config.SETS_DIR_PATH, new_filename)

        # Check if the character part of the name is empty (all 'a's if that's your placeholder for empty)
        # Or, more robustly, check if the user actually changed any character from a default "empty" marker.
        # For now, let's assume any 4-char string is valid unless it's a specific "empty" pattern.
        # The current logic just checks if the resulting name part (without version) is empty.
        if not self.get_current_name_string().strip('a'): # Example: if all chars are 'a', it's considered empty
             logger.warning("Cannot create set: Name part appears empty or default.")
             self.midi_handler.update_display("Create Failed:", "Name Empty")
             time.sleep(2)
             self.display_update_pending = True
             return

        if os.path.exists(new_path):
            logger.warning(f"Cannot create set: Target file '{new_filename}' already exists.")
            self.midi_handler.update_display("Create Failed:", "Name exists")
            time.sleep(2)
            self.display_update_pending = True # Refresh display to show error then clear
        else:
            try:
                with open(new_path, 'w') as f:
                    pass 
                logger.info(f"Successfully created new set '{new_filename}'")
                self.set_manager.load_set_files() 
                self.midi_handler.update_display("Created:", new_filename_base[:config.SCREEN_LINE_2_MAX_CHARS-9])
                time.sleep(1)
                
                from .set_list_screen import SetListScreen
                self.screen_manager.change_screen(
                    SetListScreen(self.screen_manager, self.midi_handler, self.set_manager)
                )
                return 
            except OSError as e:
                logger.error(f"Error creating file: {e}")
                self.midi_handler.update_display("Create Error", str(e)[:config.SCREEN_LINE_2_MAX_CHARS])
                time.sleep(2)
                self.display_update_pending = True

    def activate(self):
        # Reset to default name every time this screen is activated
        self.chars = ['a', 'a', 'a', 'a'] 
        self.version = 0
        super().activate() # Calls display and sets display_update_pending
        # self.display_update_pending = True # Already handled by super().activate() calling display()

    # deactivate and update are inherited
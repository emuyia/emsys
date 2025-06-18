import logging
import os
import re
import time

from .base_name_editor_screen import BaseNameEditorScreen # Changed import
from .. import config

logger = logging.getLogger(__name__)

class RenameSetScreen(BaseNameEditorScreen): # Changed inheritance
    def __init__(self, screen_manager, midi_handler, set_manager, original_filename):
        super().__init__(screen_manager, midi_handler, set_manager) # Call superclass init
        self.original_filename = original_filename
        self._parse_original_filename() # Initialize chars and version from original_filename

    def _parse_original_filename(self):
        name_part = self.original_filename
        if name_part.endswith(config.MSET_FILE_EXTENSION):
            name_part = name_part[:-len(config.MSET_FILE_EXTENSION)]
        
        match = re.match(r'([a-zA-Z]{1,4})(\d*)$', name_part)
        if match:
            char_part_str = match.group(1).lower()
            version_str = match.group(2)

            # Initialize self.chars from parsed string
            for i in range(4): # Ensure all 4 chars are set
                if i < len(char_part_str):
                    self.chars[i] = char_part_str[i]
                else:
                    self.chars[i] = 'a' # Or some other default if name is short
            
            if version_str:
                try:
                    self.version = int(version_str)
                    if not (0 <= self.version <= self.max_version):
                        logger.warning(f"Parsed version {self.version} out of range (0-{self.max_version}). Clamping.")
                        self.version = max(0, min(self.version, self.max_version))
                except ValueError:
                    logger.warning(f"Could not parse version from '{version_str}'. Defaulting to 0.")
                    self.version = 0
            else: 
                self.version = 0
        else:
            logger.warning(f"Could not parse '{name_part}' for rename. Using defaults.")
            self.chars = ['a', 'a', 'a', 'a'] # Default if parsing fails
            self.version = 0

        logger.info(f"Parsed for rename: Chars={self.chars}, Version={self.version}")

    def display(self):
        if not self.active: return

        name_str = self.get_current_name_string() # Use helper from base
        line1 = f"{name_str}{self.version:02d}" 
        line1 = line1[:config.SCREEN_LINE_1_MAX_CHARS]
        
        line2 = "S1-4:Ch K8:V P7:Sv" # P7: Save
        line2 = line2[:config.SCREEN_LINE_2_MAX_CHARS]

        self.midi_handler.update_display(line1, line2)
        logger.debug(f"Displaying RenameSetScreen: L1='{line1}', L2='{line2}'")
        self.last_actual_display_time = time.time()
        self.display_update_pending = False

    def handle_midi_input(self, message):
        if not self.active: return
        
        # Let the base class handle common name editing controls first
        if self._handle_name_editor_midi_input(message):
            return # Message was handled by the name editor

        # Handle screen-specific controls (Save, Back/Cancel)
        if message.type == 'note_on':
            if message.note == config.PAD_7_NOTE: 
                self._save_changes()
            elif message.note == config.PAD_5_NOTE:
                logger.info("Rename cancelled. Returning to SetListScreen.")
                from .set_list_screen import SetListScreen 
                self.screen_manager.change_screen(
                    SetListScreen(self.screen_manager, self.midi_handler, self.set_manager)
                )

    def _save_changes(self):
        new_filename_base = self.get_current_filename_base() # Use helper
        new_filename = self.get_current_full_filename() # Use helper
        
        old_path = os.path.join(config.SETS_DIR_PATH, self.original_filename)
        new_path = os.path.join(config.SETS_DIR_PATH, new_filename)

        if old_path == new_path:
            logger.info("No change in filename. Nothing to save.")
            self.midi_handler.update_display(new_filename_base, "No change.")
            time.sleep(1)
            # Transition back, targeting the (unchanged) file
            from .set_list_screen import SetListScreen 
            self.screen_manager.change_screen(
                SetListScreen(self.screen_manager, self.midi_handler, self.set_manager, 
                              target_filename=self.original_filename) # Target original if no change
            )
        elif os.path.exists(new_path):
            logger.warning(f"Cannot rename: Target file '{new_filename}' already exists.")
            self.midi_handler.update_display("Save Failed:", "Name exists")
            time.sleep(2)
            # Stay on rename screen or go back to list targeting original? For now, stay.
            self.display_update_pending = True 
        else:
            try:
                os.rename(old_path, new_path)
                logger.info(f"Successfully renamed '{self.original_filename}' to '{new_filename}'")
                self.set_manager.load_set_files() 
                self.midi_handler.update_display(new_filename_base, "Saved!")
                time.sleep(1)
                from .set_list_screen import SetListScreen 
                self.screen_manager.change_screen(
                    SetListScreen(self.screen_manager, self.midi_handler, self.set_manager, 
                                  target_filename=new_filename) # Target the new filename
                )
            except OSError as e:
                logger.error(f"Error renaming file: {e}")
                self.midi_handler.update_display("Save Error", str(e)[:config.SCREEN_LINE_2_MAX_CHARS])
                time.sleep(2)
                self.display_update_pending = True # Stay on rename screen

    # activate and deactivate can be inherited if no specific logic is needed,
    # or overridden if necessary. The base activate calls display.
    # The base update method is also inherited.

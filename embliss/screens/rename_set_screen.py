import logging
import os
import re # For parsing filename
import string # For alphabet
import time

from .base_screen import BaseScreen
from .. import config

logger = logging.getLogger(__name__)

class RenameSetScreen(BaseScreen):
    def __init__(self, screen_manager, midi_handler, set_manager, original_filename):
        super().__init__(screen_manager, midi_handler)
        self.set_manager = set_manager
        self.original_filename = original_filename
        
        self.chars = ['A', 'A', 'A', 'A']
        self.version = 0
        
        # Define these before _parse_original_filename is called
        self.alphabet = string.ascii_uppercase # A-Z
        self.max_version = 63

        self._parse_original_filename() # Now self.max_version exists

        # For display throttling
        self.last_actual_display_time = 0
        self.display_update_pending = True # Update display on activation
        self.display_refresh_interval = 0.075  # Min interval for display updates

    def _parse_original_filename(self):
        name_part = self.original_filename
        if name_part.endswith(config.MSET_FILE_EXTENSION):
            name_part = name_part[:-len(config.MSET_FILE_EXTENSION)]
        
        # Regex to find trailing digits (version) and preceding characters
        match = re.match(r'([a-zA-Z]{1,4})(\d*)$', name_part)
        if match:
            char_part_str = match.group(1).upper()
            version_str = match.group(2)

            for i in range(min(len(char_part_str), 4)):
                self.chars[i] = char_part_str[i]
            
            if version_str:
                try:
                    self.version = int(version_str)
                    if not (0 <= self.version <= self.max_version):
                        logger.warning(f"Parsed version {self.version} out of range (0-{self.max_version}). Clamping.")
                        self.version = max(0, min(self.version, self.max_version))
                except ValueError:
                    logger.warning(f"Could not parse version from '{version_str}'. Defaulting to 0.")
                    self.version = 0
            else: # No version number in filename, default to 0
                self.version = 0
        else:
            logger.warning(f"Could not parse '{name_part}' into chars and version. Using defaults.")
            # Keep default self.chars = ['A', 'A', 'A', 'A'] and self.version = 0

        logger.info(f"Parsed for rename: Chars={self.chars}, Version={self.version}")


    def _value_to_char(self, value): # For sliders 0-127
        index = int((value / 127) * (len(self.alphabet) - 1))
        return self.alphabet[max(0, min(index, len(self.alphabet) - 1))]

    def _value_to_version(self, value): # For knob 0-127
        # Map 0-127 to 0-63
        return int((value / 127) * self.max_version)

    def display(self):
        if not self.active: return

        name_str = "".join(self.chars)
        line1 = f"{name_str}{self.version:02d}" # e.g., ABCD07, STMC10
        line1 = line1[:config.SCREEN_LINE_1_MAX_CHARS]
        
        line2 = "S1-4:Ch K8:V P7:Sv" # Sliders 1-4:Chars, Knob8:Version, Pad7:Save
        # Could add P8:Back if space allows, or assume it's known
        # line2 = "P7:Save P8:Back"
        line2 = line2[:config.SCREEN_LINE_2_MAX_CHARS]

        self.midi_handler.update_display(line1, line2)
        logger.debug(f"Displaying RenameSetScreen: L1='{line1}', L2='{line2}'")
        self.last_actual_display_time = time.time()
        self.display_update_pending = False

    def handle_midi_input(self, message):
        if not self.active: return
        
        changed = False
        if message.type == 'control_change':
            if message.control == config.SLIDER_1_CC:
                self.chars[0] = self._value_to_char(message.value)
                changed = True
            elif message.control == config.SLIDER_2_CC:
                self.chars[1] = self._value_to_char(message.value)
                changed = True
            elif message.control == config.SLIDER_3_CC:
                self.chars[2] = self._value_to_char(message.value)
                changed = True
            elif message.control == config.SLIDER_4_CC:
                self.chars[3] = self._value_to_char(message.value)
                changed = True
            elif message.control == config.KNOB_8_CC:
                self.version = self._value_to_version(message.value)
                changed = True
            
            if changed:
                self.display_update_pending = True
                logger.info(f"Rename edit: Chars={self.chars}, Version={self.version}. Update pending.")

        elif message.type == 'note_on':
            if message.note == config.PAD_7_NOTE: # Save
                self._save_changes()
            elif message.note == config.PAD_8_NOTE: # Back/Cancel
                logger.info("Rename cancelled. Returning to SetListScreen.")
                from .set_list_screen import SetListScreen # Local import
                self.screen_manager.change_screen(
                    SetListScreen(self.screen_manager, self.midi_handler, self.set_manager)
                )

    def _save_changes(self):
        new_name_base = "".join(self.chars) + str(self.version)
        new_filename = new_name_base + config.MSET_FILE_EXTENSION
        
        old_path = os.path.join(config.SETS_DIR_PATH, self.original_filename)
        new_path = os.path.join(config.SETS_DIR_PATH, new_filename)

        if old_path == new_path:
            logger.info("No change in filename. Nothing to save.")
            self.midi_handler.update_display(new_name_base, "No change.")
            time.sleep(1)
        elif os.path.exists(new_path):
            logger.warning(f"Cannot rename: Target file '{new_filename}' already exists.")
            self.midi_handler.update_display("Save Failed:", "Name exists")
            time.sleep(2)
        else:
            try:
                os.rename(old_path, new_path)
                logger.info(f"Successfully renamed '{self.original_filename}' to '{new_filename}'")
                self.set_manager.load_set_files() # Refresh the list in SetManager
                self.midi_handler.update_display(new_name_base, "Saved!")
                time.sleep(1)
            except OSError as e:
                logger.error(f"Error renaming file: {e}")
                self.midi_handler.update_display("Save Error", str(e)[:config.SCREEN_LINE_2_MAX_CHARS])
                time.sleep(2)

        # Return to SetListScreen regardless of save outcome for now
        from .set_list_screen import SetListScreen # Local import
        self.screen_manager.change_screen(
            SetListScreen(self.screen_manager, self.midi_handler, self.set_manager)
        )

    def update(self):
        if not self.active: return
        current_time = time.time()
        if self.display_update_pending and \
           (current_time - self.last_actual_display_time >= self.display_refresh_interval):
            logger.debug("Throttled display update for RenameSetScreen executing.")
            self.display()

    def activate(self):
        super().activate() # Calls self.display() which sets last_actual_display_time
        self.display_update_pending = True # Ensure display updates on activation

    def deactivate(self):
        super().deactivate()
        # Optional: Clear display or show a neutral message if needed when leaving this screen
        # self.midi_handler.update_display(" ", " ")
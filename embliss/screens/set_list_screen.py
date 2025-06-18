import logging
from .base_screen import BaseScreen
from .. import config 
import time 
import os # For deletion
import shutil # For duplication/iteration
import re # For iteration parsing
import glob

logger = logging.getLogger(__name__)

class SetListScreen(BaseScreen):
    def __init__(self, screen_manager, midi_handler, set_manager):
        super().__init__(screen_manager, midi_handler)
        self.set_manager = set_manager
        self.current_set_index = 0
        self.set_names = []
        self._load_sets()

        self.last_actual_display_time = 0
        self.display_update_pending = False
        self.display_refresh_interval = 0.075 

        self.shift_held = False # To track Shift button state

        # For delete confirmation
        self.awaiting_delete_confirm = False
        self.delete_target_filename = None
        self.first_del_press_time = 0
        self.delete_confirm_timeout = 3 # seconds

    def _load_sets(self):
        self.set_manager.load_set_files() 
        self.set_names = self.set_manager.get_set_names()
        if not self.set_names:
            self.current_set_index = -1 
        elif self.current_set_index >= len(self.set_names) or self.current_set_index == -1:
            self.current_set_index = 0 
        # If a deletion happened, current_set_index might be out of bounds
        if self.set_names and self.current_set_index >= len(self.set_names):
            self.current_set_index = len(self.set_names) - 1
        elif not self.set_names:
            self.current_set_index = -1


    def display(self):
        if not self.active: return

        line1 = "No sets found"
        line2 = "Check sets dir"
        
        if self.awaiting_delete_confirm and self.delete_target_filename:
            target_name_only = self.delete_target_filename[:-len(config.MSET_FILE_EXTENSION)] if self.delete_target_filename.endswith(config.MSET_FILE_EXTENSION) else self.delete_target_filename
            line1 = f"Del {target_name_only[:config.SCREEN_LINE_1_MAX_CHARS-4]}?"
            line2 = "S+P6:Confirm" # Shift+Pad6 to confirm
        elif self.set_names and self.current_set_index != -1:
            total_sets = len(self.set_names)
            current_set_name = self.set_names[self.current_set_index]
            line1 = f"{self.current_set_index + 1}/{total_sets}: {current_set_name}"
            line1 = line1[:config.SCREEN_LINE_1_MAX_CHARS] 
            if self.shift_held:
                line2 = "P5:Iter P6:Del P7:New" # P5=Iterate, P6=Delete, P7=New
            else:
                line2 = "Enc:Scroll P6:Ren" # Changed P6:OK to P6:Ren (Rename)
            line2 = line2[:config.SCREEN_LINE_2_MAX_CHARS]

        self.midi_handler.update_display(line1, line2)
        logger.debug(f"Displaying SetListScreen: L1='{line1}', L2='{line2}'")
        self.last_actual_display_time = time.time()
        self.display_update_pending = False

    def handle_midi_input(self, message):
        if not self.active: return

        # Handle Shift button state first
        if message.type == 'control_change' and message.control == config.SHIFT_BUTTON_CC:
            new_shift_state = message.value > 0
            if self.shift_held != new_shift_state:
                self.shift_held = new_shift_state
                logger.info(f"Shift button {'pressed' if self.shift_held else 'released'}")
                if not self.shift_held and self.awaiting_delete_confirm: # Cancel delete confirm if shift released
                    logger.info("Delete confirmation cancelled due to Shift release.")
                    self.awaiting_delete_confirm = False
                    self.delete_target_filename = None
                self.display_update_pending = True # Update display to reflect shift options
            return # Consume this message

        # If awaiting delete confirmation, prioritize that
        if self.awaiting_delete_confirm:
            if self.shift_held and message.type == 'control_change' and \
               message.control == config.SHIFT_PAD_5_CC and message.value > 0:
                logger.info(f"Delete confirmed for {self.delete_target_filename}")
                self._perform_delete(self.delete_target_filename)
                self.awaiting_delete_confirm = False
                self.delete_target_filename = None
            # Any other pad press or relevant CC while awaiting confirm could cancel it,
            # or rely on timeout/shift release. For now, only explicit confirm or cancel.
            self.display_update_pending = True # Keep display showing confirmation or update after action
            return


        if message.type == 'control_change':
            if message.control == config.ENCODER_CC:
                if not self.set_names: return 
                previous_index = self.current_set_index
                if message.value == config.ENCODER_VALUE_UP: 
                    self.current_set_index = (self.current_set_index + 1) % len(self.set_names)
                elif message.value == config.ENCODER_VALUE_DOWN: 
                    self.current_set_index = (self.current_set_index - 1 + len(self.set_names)) % len(self.set_names)
                if self.current_set_index != previous_index:
                    self.display_update_pending = True 
                    logger.info(f"Set index changed to: {self.current_set_index}. Display update pending.")
            
            # Shift+Pad actions
            elif self.shift_held and message.value > 0: # CC value > 0 means pad pressed
                if message.control == config.SHIFT_PAD_4_CC: # Iterate
                    if self.set_names and self.current_set_index != -1:
                        self._perform_iterate(self.set_manager.set_files[self.current_set_index])
                    else:
                        logger.warning("Iterate pressed but no set selected.")
                    self.display_update_pending = True
                elif message.control == config.SHIFT_PAD_5_CC: # Delete (first press)
                    if self.set_names and self.current_set_index != -1:
                        self.delete_target_filename = self.set_manager.set_files[self.current_set_index]
                        self.awaiting_delete_confirm = True
                        self.first_del_press_time = time.time()
                        logger.info(f"Delete initiated for {self.delete_target_filename}. Awaiting confirmation.")
                    else:
                        logger.warning("Delete pressed but no set selected.")
                    self.display_update_pending = True
                elif message.control == config.SHIFT_PAD_6_CC: # New Set
                    logger.info("New Set action triggered.")
                    from .create_set_screen import CreateSetScreen # Local import
                    self.screen_manager.change_screen(
                        CreateSetScreen(self.screen_manager, self.midi_handler, self.set_manager)
                    )
                    # No display_update_pending = True here as screen changes.

        elif message.type == 'note_on': # Actions without Shift
            if not self.shift_held and message.note == config.PAD_4_NOTE:
                if self.set_names and self.current_set_index != -1:
                    selected_set_name = self.set_names[self.current_set_index]
                    original_filename = self.set_manager.set_files[self.current_set_index]
                    logger.info(f"Pad 6 (Rename) pressed: Selected set '{selected_set_name}' (filename: {original_filename}) for rename.")
                    from .rename_set_screen import RenameSetScreen 
                    self.screen_manager.change_screen(
                        RenameSetScreen(self.screen_manager, self.midi_handler, self.set_manager, original_filename)
                    )
                else:
                    logger.info("Pad 6 (Rename) pressed, but no set selected or no sets available.")
        
    def update(self):
        if not self.active: return

        # Handle delete confirmation timeout
        if self.awaiting_delete_confirm and \
           (time.time() - self.first_del_press_time > self.delete_confirm_timeout):
            logger.info("Delete confirmation timed out.")
            self.awaiting_delete_confirm = False
            self.delete_target_filename = None
            self.display_update_pending = True # Update display to clear confirmation message

        current_time = time.time()
        if self.display_update_pending and \
           (current_time - self.last_actual_display_time >= self.display_refresh_interval):
            logger.debug(f"Throttled display update executing. Index: {self.current_set_index}")
            self.display()

    def _perform_delete(self, filename_to_delete):
        full_path = os.path.join(config.SETS_DIR_PATH, filename_to_delete)
        logger.info(f"Attempting to delete set: {full_path}")
        try:
            os.remove(full_path)
            logger.info(f"Successfully deleted {filename_to_delete}")
            self.midi_handler.update_display("Deleted:", filename_to_delete.split('.')[0][:config.SCREEN_LINE_2_MAX_CHARS-9])
            time.sleep(1)
        except OSError as e:
            logger.error(f"Error deleting file {filename_to_delete}: {e}")
            self.midi_handler.update_display("Delete Error", str(e)[:config.SCREEN_LINE_2_MAX_CHARS])
            time.sleep(2)
        finally:
            self._load_sets() # Reload sets to update list and current_set_index
            self.display_update_pending = True


    def _perform_iterate(self, original_filename_to_copy_from):
        logger.info(f"Attempting to iterate on set: {original_filename_to_copy_from}")

        match_original = re.match(r'([a-zA-Z]{1,4})(\d*)\.mset$', original_filename_to_copy_from.lower())
        if not match_original:
            logger.warning(f"Cannot iterate '{original_filename_to_copy_from}': Does not match expected pattern (e.g., name0.mset).")
            self.midi_handler.update_display("Iterate Fail:", "Bad Src Name")
            time.sleep(1.5)
            self.display_update_pending = True
            return

        base_name = match_original.group(1) 
        logger.debug(f"Iteration: Base name is '{base_name}'")

        highest_existing_version = -1
        glob_pattern = os.path.join(config.SETS_DIR_PATH, f"{base_name}*{config.MSET_FILE_EXTENSION}")
        
        logger.debug(f"Iteration: Globbing with pattern: {glob_pattern}")
        found_files = glob.glob(glob_pattern)
        logger.debug(f"Iteration: Found files for base name '{base_name}': {found_files}")

        # Corrected regex: Removed the erroneous backslash before re.escape for the extension
        # and ensured the dot in the extension is properly handled by re.escape itself.
        version_pattern_regex = rf"^{re.escape(base_name)}(\d+){re.escape(config.MSET_FILE_EXTENSION)}$"
        logger.debug(f"Iteration: Using regex pattern for version matching: {version_pattern_regex}")

        for existing_file_path in found_files:
            existing_filename_in_dir = os.path.basename(existing_file_path)
            # Match against the lowercase version of the filename in the directory
            version_match = re.match(version_pattern_regex, existing_filename_in_dir.lower())
            
            if version_match:
                try:
                    version_num_str = version_match.group(1)
                    version_num = int(version_num_str)
                    if version_num > highest_existing_version:
                        highest_existing_version = version_num
                    logger.debug(f"Iteration: Checked '{existing_filename_in_dir}', matched version string: '{version_num_str}', parsed num: {version_num}, current highest: {highest_existing_version}")
                except ValueError:
                    logger.warning(f"Iteration: Could not parse version string '{version_num_str}' from '{existing_filename_in_dir}'")
                    continue
            else:
                logger.debug(f"Iteration: File '{existing_filename_in_dir}' did not match version pattern for base '{base_name}'.")
        
        logger.info(f"Iteration: Highest existing version for base '{base_name}' is {highest_existing_version}")
        new_version_number = highest_existing_version + 1

        max_v = getattr(config, 'MAX_SET_VERSION', 63) 
        if new_version_number > max_v:
            logger.warning(f"Cannot iterate '{original_filename_to_copy_from}': New version {new_version_number} exceeds max {max_v}.")
            self.midi_handler.update_display(f"{base_name}{new_version_number}", "Max Version")
            time.sleep(1.5)
            self.display_update_pending = True
            return

        new_iterated_filename = f"{base_name}{new_version_number}{config.MSET_FILE_EXTENSION}"
        path_to_copy_from = os.path.join(config.SETS_DIR_PATH, original_filename_to_copy_from)
        new_iterated_path = os.path.join(config.SETS_DIR_PATH, new_iterated_filename)

        logger.info(f"Iteration: New filename will be '{new_iterated_filename}'")

        if os.path.exists(new_iterated_path):
            logger.error(f"Cannot iterate: Target file '{new_iterated_filename}' unexpectedly already exists. This shouldn't happen if logic is correct.")
            self.midi_handler.update_display("Iterate Fail:", "Exists?") 
            time.sleep(1.5)
            self.display_update_pending = True
            return
            
        try:
            shutil.copyfile(path_to_copy_from, new_iterated_path)
            logger.info(f"Successfully iterated (copied) '{original_filename_to_copy_from}' to '{new_iterated_filename}'")
            
            # Corrected display message for iteration
            line1_text = "Iterated to:"
            filename_base = new_iterated_filename.split('.')[0]
            available_space_for_name = config.SCREEN_LINE_2_MAX_CHARS - (len("") + 0) # No prefix on line 2 for the name itself
            
            # Display the new name on line 2, truncated if necessary
            self.midi_handler.update_display(line1_text, filename_base[:available_space_for_name])
            
            time.sleep(1) # Keep the confirmation message for a bit
            self._load_sets() 
            try:
                self.current_set_index = self.set_manager.set_files.index(new_iterated_filename)
                logger.info(f"Selected newly iterated set: '{new_iterated_filename}' at index {self.current_set_index}")
            except ValueError:
                logger.warning(f"Could not find newly iterated set '{new_iterated_filename}' in list after loading.")
        except OSError as e:
            logger.error(f"Error iterating (copying) file: {e}")
            self.midi_handler.update_display("Iterate Error", str(e)[:config.SCREEN_LINE_2_MAX_CHARS])
            time.sleep(2)
        finally:
            self.display_update_pending = True

    def activate(self):
        super().activate() 
        self._load_sets() 
        self.shift_held = False # Reset shift state on activation
        self.awaiting_delete_confirm = False # Reset delete confirm state
        if not self.set_names:
             logger.warning("SetListScreen activated, but no sets found.")
        elif self.current_set_index == -1 and self.set_names: 
            self.current_set_index = 0
        self.last_actual_display_time = time.time() 
        self.display_update_pending = True
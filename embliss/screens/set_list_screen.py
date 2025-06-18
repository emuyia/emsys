import logging
from .base_screen import BaseScreen
from .. import config 
import time 
import os 
import shutil 
import re 
import glob

logger = logging.getLogger(__name__)

class SetListScreen(BaseScreen):
    def __init__(self, screen_manager, midi_handler, set_manager):
        super().__init__(screen_manager, midi_handler)
        self.set_manager = set_manager

        self.browsing_mode = "base_names"  # "base_names" or "versions"
        
        self.base_names = []
        self.current_base_name_index = 0
        self.selected_base_name = None # Stores the string of the selected base name

        self.versions_for_selected_base = [] # List of full filenames for the selected base
        self.current_version_index = 0
        
        self.active_set_filename = None # Full filename of the "OK'd" version

        self._load_base_names_and_set_initial_index()

        self.last_actual_display_time = 0
        self.display_update_pending = False
        self.display_refresh_interval = 0.075 

        self.shift_held = False 

        self.awaiting_delete_confirm = False
        self.delete_target_filename = None # This will be set to active_set_filename for delete
        self.first_del_press_time = 0
        self.delete_confirm_timeout = 3 

    def _load_base_names_and_set_initial_index(self):
        self.set_manager.load_set_files() # Ensure full list is fresh
        self.base_names = self.set_manager.get_unique_base_names()
        if not self.base_names:
            self.current_base_name_index = -1
        else:
            self.current_base_name_index = 0
        self.browsing_mode = "base_names" # Default to base names
        self.selected_base_name = None
        self.versions_for_selected_base = []
        self.active_set_filename = None


    def _load_versions_for_selected_base(self):
        if self.selected_base_name:
            self.versions_for_selected_base = self.set_manager.get_versions_for_base_name(self.selected_base_name)
            if not self.versions_for_selected_base:
                self.current_version_index = -1
            else:
                self.current_version_index = 0
        else:
            self.versions_for_selected_base = []
            self.current_version_index = -1
        self.active_set_filename = None # Clear active set when loading new versions

    def display(self):
        if not self.active: return
        line1, line2 = "No sets found", "" # Default if no sets

        if self.awaiting_delete_confirm and self.delete_target_filename:
            target_name_only = self.delete_target_filename.replace(config.MSET_FILE_EXTENSION, "")
            line1 = f"Del {target_name_only[:config.SCREEN_LINE_1_MAX_CHARS-4]}?"
            line2 = "S+P6:Confirm" # Shift + Pad 6 (SHIFT_PAD_5_CC)
        
        elif self.browsing_mode == "base_names":
            if not self.base_names or self.current_base_name_index == -1:
                line1, line2 = "No sets found", "S+P7:New?"
            else:
                total_bases = len(self.base_names)
                current_base = self.base_names[self.current_base_name_index]
                line1 = f"{self.current_base_name_index + 1}/{total_bases}: {current_base}"
                if self.shift_held:
                    line2 = "S+P7:New" # Shift + Pad 7 (SHIFT_PAD_6_CC) for New
                else:
                    line2 = "Enc:Scroll P6:Sel" # Pad 6 (Note 41) to Select base
        
        elif self.browsing_mode == "versions":
            base_display_name = self.selected_base_name if self.selected_base_name else "???"
            if not self.versions_for_selected_base or self.current_version_index == -1:
                line1 = f"{base_display_name}: No vers"
                line2 = "P5:Back" # Pad 5 (Note 40) for Back
            else:
                current_version_filename = self.versions_for_selected_base[self.current_version_index]
                display_version_name = current_version_filename.replace(config.MSET_FILE_EXTENSION, "")
                
                line1 = f"{display_version_name}" # Show full version name on L1
                
                if self.active_set_filename == current_version_filename:
                    # This version is "selected/OK'd"
                    if self.shift_held:
                        line2 = "S+P5:Iter S+P6:Del" # S+P5(Iter), S+P6(Del)
                    else:
                        line2 = "P4:Ren P5:Back" # P4(Ren), P5(Back)
                else:
                    # Just browsing versions, not yet "OK'd" one
                    line2 = "Enc:Scroll P6:OK P5:Back" # P6(OK), P5(Back)
        
        line1 = line1[:config.SCREEN_LINE_1_MAX_CHARS]
        line2 = line2[:config.SCREEN_LINE_2_MAX_CHARS]
        self.midi_handler.update_display(line1, line2)
        logger.debug(f"Displaying SetListScreen: Mode='{self.browsing_mode}', L1='{line1}', L2='{line2}', ActiveSet='{self.active_set_filename}'")
        self.last_actual_display_time = time.time()
        self.display_update_pending = False

    def handle_midi_input(self, message):
        if not self.active: return

        if message.type == 'control_change' and message.control == config.SHIFT_BUTTON_CC:
            new_shift_state = message.value > 0
            if self.shift_held != new_shift_state:
                self.shift_held = new_shift_state
                logger.info(f"Shift button {'pressed' if self.shift_held else 'released'}")
                if not self.shift_held and self.awaiting_delete_confirm:
                    logger.info("Delete confirmation cancelled due to Shift release.")
                    self.awaiting_delete_confirm = False
                self.display_update_pending = True
            return

        if self.awaiting_delete_confirm: # Delete confirmation (Shift + Pad 6, which is SHIFT_PAD_5_CC)
            if self.shift_held and message.type == 'control_change' and \
               message.control == config.SHIFT_PAD_5_CC and message.value > 0:
                logger.info(f"Delete confirmed for {self.delete_target_filename}")
                self._perform_delete(self.delete_target_filename) # delete_target_filename was set before
                self.awaiting_delete_confirm = False
                self.active_set_filename = None # Clear active set if it was deleted
            self.display_update_pending = True 
            return

        # Encoder handling
        if message.type == 'control_change' and message.control == config.ENCODER_CC:
            if self.browsing_mode == "base_names":
                if self.base_names and self.current_base_name_index != -1:
                    prev_idx = self.current_base_name_index
                    if message.value == config.ENCODER_VALUE_UP:
                        self.current_base_name_index = (self.current_base_name_index + 1) % len(self.base_names)
                    elif message.value == config.ENCODER_VALUE_DOWN:
                        self.current_base_name_index = (self.current_base_name_index - 1 + len(self.base_names)) % len(self.base_names)
                    if prev_idx != self.current_base_name_index: self.display_update_pending = True
            elif self.browsing_mode == "versions":
                if self.versions_for_selected_base and self.current_version_index != -1:
                    prev_idx = self.current_version_index
                    if message.value == config.ENCODER_VALUE_UP:
                        self.current_version_index = (self.current_version_index + 1) % len(self.versions_for_selected_base)
                    elif message.value == config.ENCODER_VALUE_DOWN:
                        self.current_version_index = (self.current_version_index - 1 + len(self.versions_for_selected_base)) % len(self.versions_for_selected_base)
                    if prev_idx != self.current_version_index:
                        # If an active set was selected, and we scroll away, "unselect" it
                        if self.active_set_filename and self.active_set_filename != self.versions_for_selected_base[self.current_version_index]:
                            self.active_set_filename = None
                        self.display_update_pending = True
            return # Encoder message handled

        # Shift + Pad CC actions
        if self.shift_held and message.type == 'control_change' and message.value > 0:
            target_for_action = self.active_set_filename # Most shift actions need an active set
            
            if message.control == config.SHIFT_PAD_4_CC: # Iterate (S+P5)
                if target_for_action:
                    self._perform_iterate(target_for_action)
                else: logger.warning("Iterate: No active set.")
            elif message.control == config.SHIFT_PAD_5_CC: # Delete Init (S+P6)
                if target_for_action:
                    self.delete_target_filename = target_for_action # Set for confirmation
                    self.awaiting_delete_confirm = True
                    self.first_del_press_time = time.time()
                    logger.info(f"Delete initiated for {self.delete_target_filename}.")
                else: logger.warning("Delete: No active set.")
            elif message.control == config.SHIFT_PAD_6_CC: # New Set (S+P7)
                logger.info("New Set action triggered.")
                from .create_set_screen import CreateSetScreen
                self.screen_manager.change_screen(CreateSetScreen(self.screen_manager, self.midi_handler, self.set_manager))
                return # Screen changed
            self.display_update_pending = True
            return

        # Note On (No Shift) actions
        if not self.shift_held and message.type == 'note_on':
            if message.note == config.PAD_6_NOTE: # P6: Select Base Name / OK Version
                if self.browsing_mode == "base_names":
                    if self.base_names and self.current_base_name_index != -1:
                        self.selected_base_name = self.base_names[self.current_base_name_index]
                        self._load_versions_for_selected_base()
                        self.browsing_mode = "versions"
                        logger.info(f"Selected base: {self.selected_base_name}. Mode: versions.")
                    else: logger.info("P6: No base names to select.")
                elif self.browsing_mode == "versions":
                    if self.versions_for_selected_base and self.current_version_index != -1:
                        self.active_set_filename = self.versions_for_selected_base[self.current_version_index]
                        name = self.active_set_filename.replace(config.MSET_FILE_EXTENSION,"")
                        logger.info(f"Version OK'd: {self.active_set_filename}")
                        self.midi_handler.update_display("Selected:", name[:config.SCREEN_LINE_2_MAX_CHARS])
                        time.sleep(0.75) # Brief confirmation
                    else: logger.info("P6: No version to OK.")
                self.display_update_pending = True
            
            elif message.note == config.PAD_5_NOTE: # P5: Back (from versions to base)
                if self.browsing_mode == "versions":
                    self.browsing_mode = "base_names"
                    self.active_set_filename = None
                    self.selected_base_name = None # Clear selected base when going back
                    logger.info("P5: Back to base names. Mode: base_names.")
                    self.display_update_pending = True
            
            elif message.note == config.PAD_4_NOTE: # P4: Rename
                if self.active_set_filename:
                    logger.info(f"Rename action for: {self.active_set_filename}")
                    from .rename_set_screen import RenameSetScreen
                    self.screen_manager.change_screen(RenameSetScreen(self.screen_manager, self.midi_handler, self.set_manager, self.active_set_filename))
                    return # Screen changed
                else:
                    logger.info("P4: Rename pressed, but no active set selected.")
                    self.midi_handler.update_display("Rename Fail:", "No Set OK'd")
                    time.sleep(1)
                    self.display_update_pending = True
            return

    def update(self):
        if not self.active: return
        if self.awaiting_delete_confirm and (time.time() - self.first_del_press_time > self.delete_confirm_timeout):
            logger.info("Delete confirmation timed out.")
            self.awaiting_delete_confirm = False
            self.display_update_pending = True
        
        current_time = time.time()
        if self.display_update_pending and (current_time - self.last_actual_display_time >= self.display_refresh_interval):
            self.display()

    def _perform_delete(self, filename_to_delete):
        # ... (implementation is the same, uses filename_to_delete)
        full_path = os.path.join(config.SETS_DIR_PATH, filename_to_delete)
        logger.info(f"Attempting to delete set: {full_path}")
        try:
            os.remove(full_path)
            logger.info(f"Successfully deleted {filename_to_delete}")
            line1_text = "Deleted:"
            filename_base = filename_to_delete.split('.')[0]
            self.midi_handler.update_display(line1_text, filename_base[:config.SCREEN_LINE_2_MAX_CHARS])
            time.sleep(1)
        except OSError as e:
            logger.error(f"Error deleting file {filename_to_delete}: {e}")
            self.midi_handler.update_display("Delete Error", str(e)[:config.SCREEN_LINE_2_MAX_CHARS])
            time.sleep(2)
        finally:
            self._load_base_names_and_set_initial_index() # Reload base names
            self.active_set_filename = None # Clear active set
            self.display_update_pending = True


    def _perform_iterate(self, original_filename_to_copy_from):
        # ... (implementation is the same, uses original_filename_to_copy_from)
        logger.info(f"Attempting to iterate on set: {original_filename_to_copy_from}")
        match_original = re.match(r'([a-zA-Z]{1,4})(\d*)\.mset$', original_filename_to_copy_from.lower())
        if not match_original:
            logger.warning(f"Cannot iterate '{original_filename_to_copy_from}': Does not match expected pattern.")
            self.midi_handler.update_display("Iterate Fail:", "Bad Src Name")
            time.sleep(1.5); self.display_update_pending = True; return
        base_name = match_original.group(1)
        highest_existing_version = -1
        glob_pattern = os.path.join(config.SETS_DIR_PATH, f"{base_name}*{config.MSET_FILE_EXTENSION}")
        version_pattern_regex = rf"^{re.escape(base_name)}(\d+){re.escape(config.MSET_FILE_EXTENSION)}$"
        for existing_file_path in glob.glob(glob_pattern):
            existing_filename_in_dir = os.path.basename(existing_file_path)
            version_match = re.match(version_pattern_regex, existing_filename_in_dir.lower())
            if version_match:
                try:
                    version_num = int(version_match.group(1))
                    if version_num > highest_existing_version: highest_existing_version = version_num
                except ValueError: continue
        new_version_number = highest_existing_version + 1
        max_v = getattr(config, 'MAX_SET_VERSION', 63)
        if new_version_number > max_v:
            self.midi_handler.update_display(f"{base_name}{new_version_number}", "Max Version")
            time.sleep(1.5); self.display_update_pending = True; return
        new_iterated_filename = f"{base_name}{new_version_number}{config.MSET_FILE_EXTENSION}"
        path_to_copy_from = os.path.join(config.SETS_DIR_PATH, original_filename_to_copy_from)
        new_iterated_path = os.path.join(config.SETS_DIR_PATH, new_iterated_filename)
        if os.path.exists(new_iterated_path):
            self.midi_handler.update_display("Iterate Fail:", "Exists?")
            time.sleep(1.5); self.display_update_pending = True; return
        try:
            shutil.copyfile(path_to_copy_from, new_iterated_path)
            line1_text = "Iterated to:"
            filename_base_disp = new_iterated_filename.split('.')[0]
            self.midi_handler.update_display(line1_text, filename_base_disp[:config.SCREEN_LINE_2_MAX_CHARS])
            time.sleep(1)
            self._load_base_names_and_set_initial_index() # Reload all
            # Try to select the new iterated set's base and then the version
            self.selected_base_name = base_name
            self._load_versions_for_selected_base()
            self.browsing_mode = "versions"
            try:
                self.current_version_index = self.versions_for_selected_base.index(new_iterated_filename)
                self.active_set_filename = new_iterated_filename # Make it active
            except ValueError:
                logger.warning(f"Could not find/select new '{new_iterated_filename}'.")
        except OSError as e:
            self.midi_handler.update_display("Iterate Error", str(e)[:config.SCREEN_LINE_2_MAX_CHARS])
            time.sleep(2)
        finally:
            self.display_update_pending = True

    def activate(self):
        super().activate() 
        self._load_base_names_and_set_initial_index()
        self.shift_held = False 
        self.awaiting_delete_confirm = False 
        self.last_actual_display_time = time.time() 
        self.display_update_pending = True
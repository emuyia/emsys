import logging
import time
from .base_screen import BaseScreen
from .. import config
from .copy_instructions_screen import CopyInstructionsScreen
from .mnm_kit_scan_prompt_screen import MnmKitScanPromptScreen

logger = logging.getLogger(__name__)

class CopyTrackScreen(BaseScreen):
    """A screen for selecting a destination set to copy a track to."""
    def __init__(self, screen_manager, midi_handler, set_manager, source_filename, source_track_name, original_screen):
        super().__init__(screen_manager, midi_handler)
        self.set_manager = set_manager
        self.source_filename = source_filename
        self.source_track_name = source_track_name
        self.original_screen = original_screen

        # Logic for browsing sets, similar to SetListScreen
        self.browsing_mode = "base_names"
        self.base_names = []
        self.current_base_name_index = -1
        self.selected_base_name = None
        self.versions_for_selected_base = []
        self.current_version_index = -1
        
        self.display_update_pending = False
        self.last_actual_display_time = 0
        self.display_refresh_interval = 0.075

    def activate(self):
        self.active = True
        logger.info(f"Activating CopyTrackScreen to copy track '{self.source_track_name}'")
        self._load_base_names()
        self.display_update_pending = True
        self.display()

    def _load_base_names(self):
        self.set_manager.load_set_files()
        self.base_names = self.set_manager.get_unique_base_names()
        self.current_base_name_index = 0 if self.base_names else -1

    def _load_versions_for_selected_base(self):
        if self.selected_base_name:
            self.versions_for_selected_base = self.set_manager.get_versions_for_base_name(self.selected_base_name)
            self.current_version_index = 0 if self.versions_for_selected_base else -1
        else:
            self.versions_for_selected_base = []
            self.current_version_index = -1

    def display(self):
        if not self.active: return
        line1 = f"Copy '{self.source_track_name}'"
        line2 = ""

        if self.browsing_mode == "base_names":
            if self.current_base_name_index == -1:
                line2 = "No sets found"
            else:
                base_name = self.base_names[self.current_base_name_index]
                line2 = f"To: {base_name}.. P6:Y"
        
        elif self.browsing_mode == "versions":
            if self.current_version_index == -1:
                line2 = "No versions"
            else:
                filename = self.versions_for_selected_base[self.current_version_index]
                set_name = filename.replace(config.MSET_FILE_EXTENSION, "")
                line2 = f"To: {set_name} P6:Y"

        self.midi_handler.update_display(line1[:16], line2[:15])
        self.last_actual_display_time = time.time()
        self.display_update_pending = False

    def handle_midi_input(self, message):
        if not self.active: return

        if message.type == 'control_change' and message.control == config.ENCODER_CC:
            if self.browsing_mode == "base_names" and self.base_names:
                if message.value == config.ENCODER_VALUE_UP: self.current_base_name_index = (self.current_base_name_index + 1) % len(self.base_names)
                elif message.value == config.ENCODER_VALUE_DOWN: self.current_base_name_index = (self.current_base_name_index - 1 + len(self.base_names)) % len(self.base_names)
            elif self.browsing_mode == "versions" and self.versions_for_selected_base:
                if message.value == config.ENCODER_VALUE_UP: self.current_version_index = (self.current_version_index + 1) % len(self.versions_for_selected_base)
                elif message.value == config.ENCODER_VALUE_DOWN: self.current_version_index = (self.current_version_index - 1 + len(self.versions_for_selected_base)) % len(self.versions_for_selected_base)
            self.display_update_pending = True

        if message.type == 'note_on':
            if message.note == config.PAD_6_NOTE: # Select Base Name or Confirm Copy
                if self.browsing_mode == "base_names" and self.current_base_name_index != -1:
                    self.selected_base_name = self.base_names[self.current_base_name_index]
                    self._load_versions_for_selected_base()
                    self.browsing_mode = "versions"
                elif self.browsing_mode == "versions" and self.current_version_index != -1:
                    destination_filename = self.versions_for_selected_base[self.current_version_index]
                    self._perform_copy(destination_filename)
                self.display_update_pending = True
            
            elif message.note == config.PAD_5_NOTE: # Go Back or Cancel
                if self.browsing_mode == "versions":
                    self.browsing_mode = "base_names"
                    self.selected_base_name = None
                else:
                    self.screen_manager.change_screen(self.original_screen)
                self.display_update_pending = True

    def _perform_copy(self, destination_filename):
        logger.info(f"Attempting to copy track '{self.source_track_name}' from {self.source_filename} to {destination_filename}")
        
        success, result = self.set_manager.copy_track_to_set(
            source_filename=self.source_filename,
            track_name_to_copy=self.source_track_name,
            dest_filename=destination_filename
        )

        if success:
            # result is the list of mappings
            if result: # Check if there are any mappings to display
                self.midi_handler.update_display("Copy Complete!", "..."); time.sleep(1)
                
                # --- MODIFICATION: Go to the new prompt screen ---
                # Check if there are any 'mnm' mappings that require a scan
                has_mnm_mappings = any(item['type'] == 'mnm' for item in result)

                if has_mnm_mappings:
                    # Go to the prompt screen to start the kit scan
                    self.screen_manager.change_screen(
                        MnmKitScanPromptScreen(
                            self.screen_manager,
                            self.midi_handler,
                            mapping_data=result,
                            original_screen=self.original_screen
                        )
                    )
                else:
                    # If no mnm mappings, go directly to instructions (original behavior)
                    self.screen_manager.change_screen(
                        CopyInstructionsScreen(
                            self.screen_manager,
                            self.midi_handler,
                            mapping_data=result,
                            original_screen=self.original_screen
                        )
                    )
            else: # No mappings, just show success and return
                self.midi_handler.update_display("Track Copied", "No banks mapped"); time.sleep(2)
                self.original_screen.activate()
                self.screen_manager.change_screen(self.original_screen)
        else:
            # result is the error message string
            self.midi_handler.update_display("Copy Failed", result[:15]); time.sleep(2)
            self.original_screen.activate()
            self.screen_manager.change_screen(self.original_screen)

    def update(self):
        if not self.active: return
        if self.display_update_pending and (time.time() - self.last_actual_display_time >= self.display_refresh_interval):
            self.display()
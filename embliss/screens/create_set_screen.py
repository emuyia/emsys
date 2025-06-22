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
        
        line2 = "Input: S1-4, K8" # P7: Create
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
            if message.note == config.PAD_6_NOTE: # Create
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

        if not self.get_current_name_string().strip('a'): 
             logger.warning("Cannot create set: Name part appears empty or default.")
             self.midi_handler.update_display("Create Failed:", "Name Empty")
             time.sleep(2)
             self.display_update_pending = True
             return

        if os.path.exists(new_path):
            logger.warning(f"Cannot create set: Target file '{new_filename}' already exists.")
            self.midi_handler.update_display("Create Failed:", "Name exists")
            time.sleep(2)
            self.display_update_pending = True 
        else:
            try:
                # Define the default content
                default_content = "md A01 mnm A01 rep 1 len 32 tin 0 bpm 150 bpmr 0 poly 0;\n" # Added newline at the end
                
                with open(new_path, 'w') as f:
                    f.write(default_content) # Write the default content
                                    
                logger.info(f"Successfully created new set '{new_filename}' with default segment.")
                self.set_manager.load_set_files() 
                self.midi_handler.update_display("Created:", new_filename_base[:config.SCREEN_LINE_2_MAX_CHARS-9])
                time.sleep(1)
                
                from .set_list_screen import SetListScreen
                self.screen_manager.change_screen(
                    SetListScreen(self.screen_manager, self.midi_handler, self.set_manager, 
                                  target_filename=new_filename) 
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
import logging
import time
from .base_name_editor_screen import BaseNameEditorScreen
from .. import config

logger = logging.getLogger(__name__)

class EditSegmentTrackScreen(BaseNameEditorScreen):
    def __init__(self, screen_manager, midi_handler, set_manager, set_filename, segment_index, original_trk_name):
        super().__init__(screen_manager, midi_handler, set_manager)
        self.set_filename = set_filename
        self.segment_index = segment_index
        self.original_trk_name = original_trk_name
        self._parse_original_trk_name()

    def _parse_original_trk_name(self):
        """Populates the editor's character array from the original track name."""
        self.chars = ['a', 'a', 'a', 'a']
        if self.original_trk_name:
            for i in range(min(len(self.original_trk_name), 4)):
                self.chars[i] = self.original_trk_name[i].lower()
        self.version = -1 # Version is not used for track names
        logger.info(f"Parsed for track edit: Chars={self.chars}")

    def display(self):
        if not self.active: return

        name_str = self.get_current_name_string()
        line1 = f"Edit Trk: {name_str}"
        line1 = line1[:config.SCREEN_LINE_1_MAX_CHARS]
        
        line2 = "P4:Unset P7:Save" # Updated help text
        line2 = line2[:config.SCREEN_LINE_2_MAX_CHARS]

        self.midi_handler.update_display(line1, line2)
        self.last_actual_display_time = time.time()
        self.display_update_pending = False

    def _handle_name_editor_midi_input(self, message):
        """Override base method to ignore the version knob (K8)."""
        changed = False
        if message.type == 'control_change':
            if message.control in [config.SLIDER_1_CC, config.SLIDER_2_CC, config.SLIDER_3_CC, config.SLIDER_4_CC]:
                if message.control == config.SLIDER_1_CC: self.chars[0] = self._value_to_char(message.value)
                elif message.control == config.SLIDER_2_CC: self.chars[1] = self._value_to_char(message.value)
                elif message.control == config.SLIDER_3_CC: self.chars[2] = self._value_to_char(message.value)
                elif message.control == config.SLIDER_4_CC: self.chars[3] = self._value_to_char(message.value)
                changed = True
            
            if changed:
                self.display_update_pending = True
                return True
        return False

    def handle_midi_input(self, message):
        if not self.active: return
        
        if self._handle_name_editor_midi_input(message):
            return

        if message.type == 'note_on':
            if message.note == config.PAD_7_NOTE: # Save
                self._save_changes()
            elif message.note == config.PAD_4_NOTE: # Unset
                logger.info("Unset track command received.")
                self._save_changes(unset=True)
            elif message.note == config.PAD_5_NOTE: # Cancel
                logger.info("Track edit cancelled. Returning to SegmentListScreen.")
                from .segment_list_screen import SegmentListScreen 
                self.screen_manager.change_screen(
                    SegmentListScreen(
                        self.screen_manager, self.midi_handler, self.set_manager, 
                        self.set_filename, restore_index=self.segment_index
                    )
                )

    def _save_changes(self, unset=False):
        if unset:
            new_trk_name = ""
        else:
            new_trk_name = self.get_current_name_string()
        
        if not unset and new_trk_name == self.original_trk_name:
            logger.info("No change in track name. Nothing to save.")
        else:
            try:
                success = self.set_manager.update_segment_track(
                    self.set_filename, self.segment_index, new_trk_name
                )
                if success:
                    display_name = "Unset" if unset else new_trk_name
                    logger.info(f"Successfully updated track for segment {self.segment_index} to '{display_name}'")
                    self.midi_handler.update_display(display_name, "Saved!")
                    time.sleep(1)
                else:
                    raise IOError("Update failed in SetManager")
            except Exception as e:
                logger.error(f"Error saving track name: {e}")
                self.midi_handler.update_display("Save Error", "See logs")
                time.sleep(2)
                self.display_update_pending = True
                return

        from .segment_list_screen import SegmentListScreen 
        self.screen_manager.change_screen(
            SegmentListScreen(
                self.screen_manager, self.midi_handler, self.set_manager, 
                self.set_filename, restore_index=self.segment_index
            )
        )
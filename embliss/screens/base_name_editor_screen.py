import logging
import string
import time
from .base_screen import BaseScreen
from .. import config

logger = logging.getLogger(__name__)

class BaseNameEditorScreen(BaseScreen):
    def __init__(self, screen_manager, midi_handler, set_manager):
        super().__init__(screen_manager, midi_handler)
        self.set_manager = set_manager

        self.chars = ['a', 'a', 'a', 'a']
        self.version = 0
        self.alphabet = string.ascii_lowercase
        self.max_version = getattr(config, 'MAX_SET_VERSION', 63)

        # For display throttling
        self.last_actual_display_time = 0
        self.display_update_pending = True 
        self.display_refresh_interval = 0.075

    def _value_to_char(self, value):
        index = int((value / 127) * (len(self.alphabet) - 1))
        return self.alphabet[max(0, min(index, len(self.alphabet) - 1))]

    def _value_to_version(self, value):
        return int((value / 127) * self.max_version)

    def get_current_name_string(self):
        return "".join(self.chars).lower()

    def get_current_filename_base(self):
        return f"{self.get_current_name_string()}{self.version}"

    def get_current_full_filename(self):
        return self.get_current_filename_base() + config.MSET_FILE_EXTENSION

    def _handle_name_editor_midi_input(self, message):
        """Handles MIDI input common to name editing screens."""
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
                logger.info(f"Name editor: Chars={self.chars}, Version={self.version}. Update pending.")
                return True # Indicates that the message was handled by the name editor
        return False # Message not handled by name editor

    # Screens inheriting this must implement display() and handle_midi_input()
    # handle_midi_input() in subclasses should call self._handle_name_editor_midi_input()

    def update(self):
        if not self.active: return
        current_time = time.time()
        if self.display_update_pending and \
           (current_time - self.last_actual_display_time >= self.display_refresh_interval):
            logger.debug(f"Throttled display update for {self.__class__.__name__} executing.")
            self.display() # Call the subclass's display method

    def activate(self):
        super().activate() # This will call the subclass's display method
        self.display_update_pending = True # Ensure display updates on activation
        # Resetting chars/version should be done in subclass activate if needed (e.g., CreateSetScreen)
import logging
from .base_screen import BaseScreen
from .mnm_kit_scan_prompt_screen import MnmKitScanPromptScreen
from .. import config

logger = logging.getLogger(__name__)

class ConnectMnmToEmblissScreen(BaseScreen):
    """A screen to instruct the user to connect MnM I/O to embliss."""
    def __init__(self, screen_manager, midi_handler, mapping_data, original_screen, source_filename, track_name_to_copy, destination_filename):
        super().__init__(screen_manager, midi_handler)
        self.mapping_data = mapping_data
        self.original_screen = original_screen
        # Store the plan details
        self.source_filename = source_filename
        self.track_name_to_copy = track_name_to_copy
        self.destination_filename = destination_filename

    def activate(self):
        self.active = True
        self.display()

    def display(self):
        if not self.active: return
        line1 = "Conn MMIO>emb"
        line2 = "P5:C P6:Cont"
        self.midi_handler.update_display(line1, line2)

    def _proceed(self):
        """Proceeds to the kit scan prompt screen."""
        scan_prompt_screen = MnmKitScanPromptScreen(
            self.screen_manager,
            self.midi_handler,
            self.mapping_data,
            self.original_screen,
            source_filename=self.source_filename,
            track_name_to_copy=self.track_name_to_copy,
            destination_filename=self.destination_filename
        )
        self.screen_manager.change_screen(scan_prompt_screen)

    def handle_midi_input(self, message):
        if not self.active or message.type != 'note_on':
            return

        # Pad 5: Cancel/Exit
        if message.note == config.PAD_5_NOTE:
            logger.info("Exiting to original screen via Pad 5.")
            self.original_screen.activate()
            self.screen_manager.change_screen(self.original_screen)
            return

        # Pad 6: OK
        if message.note == config.PAD_6_NOTE:
            self._proceed()

    def update(self):
        pass
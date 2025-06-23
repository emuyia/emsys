import logging
from .base_screen import BaseScreen
from .copy_instructions_screen import CopyInstructionsScreen
from .. import config
from .. import mnm_sysex_manager

logger = logging.getLogger(__name__)

class MnmKitScanPromptScreen(BaseScreen):
    """A screen to prompt the user to initiate the MnM kit scan."""
    def __init__(self, screen_manager, midi_handler, mapping_data, original_screen):
        super().__init__(screen_manager, midi_handler)
        self.mapping_data = mapping_data
        self.original_screen = original_screen
        self.status = "prompt" # 'prompt', 'scanning', 'failed'

    def activate(self):
        self.active = True
        self.display()

    def display(self):
        if not self.active: return
        if self.status == "prompt":
            line1 = "Load Dest on MnM"
            line2 = "P5:C P6:Scan"
        elif self.status == "scanning":
            line1 = "Scanning MnM..."
            line2 = "Please wait."
        elif self.status == "failed":
            line1 = "Scan Failed."
            line2 = "P5:C P6:Retry"
        self.midi_handler.update_display(line1, line2)

    def _start_scan(self):
        """Initiates the scanning process."""
        self.status = "scanning"
        self.display()
        
        # Run the scan
        mnm_kit_map = mnm_sysex_manager.get_kit_map()
        
        if mnm_kit_map is None:
            # Handle scan failure
            self.status = "failed"
            self.display()
            return

        # On success, transition to the final instructions screen
        instructions_screen = CopyInstructionsScreen(
            self.screen_manager,
            self.midi_handler,
            self.mapping_data,
            self.original_screen,
            mnm_kit_map=mnm_kit_map
        )
        self.screen_manager.change_screen(instructions_screen)

    def handle_midi_input(self, message):
        if not self.active or message.type != 'note_on':
            return

        # Pad 5: Cancel/Exit
        if message.note == config.PAD_5_NOTE:
            logger.info("Exiting scan prompt via Pad 5.")
            self.original_screen.activate()
            self.screen_manager.change_screen(self.original_screen)
            return

        # Pad 6: Scan/Retry
        if message.note == config.PAD_6_NOTE:
            if self.status == "prompt":
                self._start_scan()
            elif self.status == "failed":
                logger.info("Retrying MnM kit scan.")
                self._start_scan()

    def update(self):
        pass
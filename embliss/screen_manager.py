import logging

logger = logging.getLogger(__name__)

class ScreenManager:
    def __init__(self, midi_handler, initial_screen_class=None, set_manager=None):
        self.midi_handler = midi_handler
        self.set_manager = set_manager # Pass set_manager if screens need it
        self.current_screen = None
        if initial_screen_class and self.set_manager:
            self.change_screen(initial_screen_class(self, self.midi_handler, self.set_manager))
        elif initial_screen_class:
             self.change_screen(initial_screen_class(self, self.midi_handler))


    def change_screen(self, new_screen_instance):
        if self.current_screen:
            self.current_screen.deactivate()
        
        self.current_screen = new_screen_instance
        logger.info(f"Changed screen to: {self.current_screen.__class__.__name__}")
        if self.current_screen:
            self.current_screen.activate() # This will call display()

    def process_midi_input(self, message):
        if self.current_screen:
            # The screen's handle_midi_input might return a new screen instance
            # or an instruction to change screen. For now, let's assume it
            # handles the change itself by calling self.screen_manager.change_screen()
            self.current_screen.handle_midi_input(message)
            # If a screen needs to change, it should call self.screen_manager.change_screen()

    def update_current_screen(self):
        """Periodically update the current screen if it has an update method."""
        if self.current_screen and hasattr(self.current_screen, 'update'):
            self.current_screen.update()
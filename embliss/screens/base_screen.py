from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class BaseScreen(ABC):
    def __init__(self, screen_manager, midi_handler):
        self.screen_manager = screen_manager
        self.midi_handler = midi_handler
        self.active = False

    @abstractmethod
    def display(self):
        """
        Updates the Minilab3 display with the current screen's content.
        This method should call self.midi_handler.update_display(line1, line2).
        """
        pass

    @abstractmethod
    def handle_midi_input(self, message):
        """
        Processes an incoming MIDI message.
        Args:
            message: A mido MIDI message object.
        Returns:
            None, or a new screen instance if a screen change is required.
        """
        pass

    def activate(self):
        """Called when the screen becomes active."""
        logger.info(f"Activating screen: {self.__class__.__name__}")
        self.active = True
        self.display() # Show the screen content when activated

    def deactivate(self):
        """Called when the screen is no longer active."""
        logger.info(f"Deactivating screen: {self.__class__.__name__}")
        self.active = False
        # Optionally, clear the screen or show a default message on deactivation
        # self.midi_handler.update_display("", "")

    def update(self):
        """
        Called periodically if the screen needs to update its state
        or display even without direct MIDI input (e.g., for animations, polling).
        By default, does nothing. Screens can override this if needed.
        """
        pass
# src/display/screens/base_screen.py

from abc import ABC, abstractmethod
import logging

class BaseScreen(ABC):
    def __init__(self, display_manager, mode_manager):
        self.display_manager = display_manager
        self.mode_manager = mode_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)
    
    @abstractmethod
    def start_mode(self):
        """Activate the screen."""
        pass
    
    @abstractmethod
    def stop_mode(self):
        """Deactivate the screen."""
        pass
    
    @abstractmethod
    def update_display(self, data):
        """Update the screen with new data."""
        pass

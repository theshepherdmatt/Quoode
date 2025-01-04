# src/managers/manager_factory.py

import logging
from .menus.playlist_manager import PlaylistManager
from .menus.radio_manager import RadioManager
from .menus.library_manager import LibraryManager
from .menus.usb_library_manager import USBLibraryManager
from display.screens.modern_screen import ModernScreen
from display.screens.original_screen import OriginalScreen


class ManagerFactory:
    def __init__(self, display_manager, moode_listener, mode_manager, config):
        self.display_manager = display_manager
        self.moode_listener = moode_listener
        self.mode_manager = mode_manager
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.info("ManagerFactory initialized.")

        # Initialize manager instances as None
        self.original_screen = None
        self.menu_manager = None
        self.playlist_manager = None
        self.radio_manager = None
        self.library_manager = None
        self.usb_library_manager = None
        self.modern_screen = None


    def setup_mode_manager(self):
        """Set up all parts of the ModeManager."""
        # Create managers
        self.original_screen = self.create_original_screen()
        self.menu_manager = self.create_menu_manager()
        self.playlist_manager = self.create_playlist_manager()
        self.radio_manager = self.create_radio_manager()
        self.library_manager = self.create_library_manager()
        self.usb_library_manager = self.create_usb_library_manager()
        self.modern_screen = self.create_modern_screen()

        # Assign the managers to mode_manager
        self.mode_manager.set_original_screen(self.original_screen)
        self.mode_manager.set_menu_manager(self.menu_manager)
        self.mode_manager.set_playlist_manager(self.playlist_manager)
        self.mode_manager.set_radio_manager(self.radio_manager)
        self.mode_manager.set_library_manager(self.library_manager)
        self.mode_manager.set_usb_library_manager(self.usb_library_manager)
        self.mode_manager.set_modern_screen(self.modern_screen)


        self.logger.info("ModeManager fully configured.")

    def create_menu_manager(self):
        from managers.menu_manager import MenuManager
        return MenuManager(self.display_manager, self.moode_listener, self.mode_manager)

    def create_playlist_manager(self):
        self.logger.debug("Creating PlaybackManager instance.")
        return PlaylistManager(self.display_manager, self.moode_listener, self.mode_manager)

    def create_radio_manager(self):
        self.logger.debug("Creating RadioPlayback instance.")
        return RadioManager(self.display_manager, self.moode_listener, self.mode_manager)

    def create_library_manager(self):
        moode_config = self.config.get('volumio', {})
        return LibraryManager(self.display_manager, moode_config, self.mode_manager)

    def create_usb_library_manager(self):
        return USBLibraryManager(self.display_manager, self.moode_listener, self.mode_manager)

    def create_modern_screen(self):
        return ModernScreen(self.display_manager, self.moode_listener, self.mode_manager)

    def create_original_screen(self):
        return OriginalScreen(self.display_manager, self.moode_listener, self.mode_manager)

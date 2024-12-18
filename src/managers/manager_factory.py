# src/managers/manager_factory.py

import logging
from .menus.tidal_manager import TidalManager
from .menus.qobuz_manager import QobuzManager
from .menus.playlist_manager import PlaylistManager
from .menus.radio_manager import RadioManager
from .menus.library_manager import LibraryManager
from .menus.spotify_manager import SpotifyManager
from .menus.usb_library_manager import USBLibraryManager
from display.screens.webradio_screen import WebRadioScreen
from display.screens.modern_screen import ModernScreen
from display.screens.original_screen import OriginalScreen


class ManagerFactory:
    def __init__(self, display_manager, volumio_listener, mode_manager, config):
        self.display_manager = display_manager
        self.volumio_listener = volumio_listener
        self.mode_manager = mode_manager
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.info("ManagerFactory initialized.")

        # Initialize manager instances as None
        self.original_screen = None
        self.webradio_screen = None
        self.menu_manager = None
        self.playlist_manager = None
        self.radio_manager = None
        self.tidal_manager = None
        self.qobuz_manager = None
        self.spotify_manager = None
        self.library_manager = None
        self.usb_library_manager = None
        self.modern_screen = None


    def setup_mode_manager(self):
        """Set up all parts of the ModeManager."""
        # Create managers
        self.original_screen = self.create_original_screen()
        self.webradio_screen = self.create_webradio_screen()
        self.menu_manager = self.create_menu_manager()
        self.playlist_manager = self.create_playlist_manager()
        self.radio_manager = self.create_radio_manager()
        self.tidal_manager = self.create_tidal_manager()
        self.qobuz_manager = self.create_qobuz_manager()
        self.spotify_manager = self.create_spotify_manager()
        self.library_manager = self.create_library_manager()
        self.usb_library_manager = self.create_usb_library_manager()
        self.modern_screen = self.create_modern_screen()

        # Assign the managers to mode_manager
        self.mode_manager.set_original_screen(self.original_screen)
        self.mode_manager.set_webradio_screen(self.webradio_screen)
        self.mode_manager.set_menu_manager(self.menu_manager)
        self.mode_manager.set_playlist_manager(self.playlist_manager)
        self.mode_manager.set_radio_manager(self.radio_manager)
        self.mode_manager.set_tidal_manager(self.tidal_manager)
        self.mode_manager.set_qobuz_manager(self.qobuz_manager)
        self.mode_manager.set_spotify_manager(self.spotify_manager)
        self.mode_manager.set_library_manager(self.library_manager)
        self.mode_manager.set_usb_library_manager(self.usb_library_manager)
        self.mode_manager.set_modern_screen(self.modern_screen)


        self.logger.info("ModeManager fully configured.")

    def create_menu_manager(self):
        from managers.menu_manager import MenuManager
        return MenuManager(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_playlist_manager(self):
        self.logger.debug("Creating PlaybackManager instance.")
        return PlaylistManager(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_radio_manager(self):
        self.logger.debug("Creating RadioPlayback instance.")
        return RadioManager(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_tidal_manager(self):
        return TidalManager(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_qobuz_manager(self):
        return QobuzManager(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_spotify_manager(self):
        return SpotifyManager(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_library_manager(self):
        volumio_config = self.config.get('volumio', {})
        return LibraryManager(self.display_manager, volumio_config, self.mode_manager)

    def create_usb_library_manager(self):
        return USBLibraryManager(self.display_manager, self.volumio_listener, self.mode_manager)


    def create_webradio_screen(self):
        return WebRadioScreen(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_modern_screen(self):
        return ModernScreen(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_original_screen(self):
        return OriginalScreen(self.display_manager, self.volumio_listener, self.mode_manager)

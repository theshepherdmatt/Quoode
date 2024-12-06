import logging
from .tidal_manager import TidalManager
from .qobuz_manager import QobuzManager
from .playlist_manager import PlaylistManager
from .radio_manager import RadioManager
from .library_manager import LibraryManager
from .spotify_manager import SpotifyManager
from .usb_library_manager import USBLibraryManager
from .screen_manager import ScreenManager
from .radioplayback_manager import RadioPlaybackManager
from .detailed_playback_manager import DetailedPlaybackManager

class ManagerFactory:
    def __init__(self, display_manager, volumio_listener, mode_manager):
        self.display_manager = display_manager
        self.volumio_listener = volumio_listener
        self.mode_manager = mode_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.info("ManagerFactory initialized.")

    def create_menu_manager(self):
        from .menu_manager import MenuManager
        return MenuManager(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_playlist_manager(self):
        return PlaylistManager(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_radio_manager(self):
        return RadioManager(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_tidal_manager(self):
        return TidalManager(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_qobuz_manager(self):
        return QobuzManager(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_spotify_manager(self):
        return SpotifyManager(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_library_manager(self):
        return LibraryManager(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_usb_library_manager(self):
        return USBLibraryManager(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_screen_manager(self):
        return ScreenManager(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_radioplayback_manager(self):
        return RadioPlaybackManager(self.display_manager, self.volumio_listener, self.mode_manager)

    def create_detailed_playback_manager(self):
        return DetailedPlaybackManager(self.display_manager, self.volumio_listener, self.mode_manager)

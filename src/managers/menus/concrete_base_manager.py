# src/managers/concrete_base_manager.py

from managers.base_manager import BaseManager
from display.playback_manager import PlaybackManager
from managers.menu_manager import MenuManager
from managers.playlist_manager import PlaylistManager
from managers.radio_manager import RadioManager
from managers.tidal_manager import TidalManager
from managers.qobuz_manager import QobuzManager
from managers.spotify_manager import SpotifyManager
from managers.library_manager import LibraryManager
from managers.usb_library_manager import USBLibraryManager


import logging

class ConcreteBaseManager(BaseManager):
    def __init__(
        self,
        display_manager,
        volumio_listener,
        mode_manager,
        playback_manager: PlaybackManager,
        menu_manager: MenuManager,
        playlist_manager: PlaylistManager,
        radio_manager: RadioManager,
        tidal_manager: TidalManager,
        library_manager: LibraryManager,
        usb_library_manager: USBLibraryManager,
        qobuz_manager: QobuzManager,
        spotify_manager: SpotifyManager,
    ):
        # Initialize BaseManager with required parameters
        super().__init__(display_manager, volumio_listener, mode_manager)
        
        # Initialize logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)  # Set to INFO or DEBUG as needed
        self.logger.info("ConcreteBaseManager initialized.")

        # Store individual managers
        self.playback_manager = playback_manager
        self.menu_manager = menu_manager
        self.playlist_manager = playlist_manager
        self.radio_manager = radio_manager
        self.tidal_manager = tidal_manager
        self.qobuz_manager = qobuz_manager
        self.spotify_manager = spotify_manager
        self.library_manager = library_manager
        self.usb_library_manager = usb_library_manager

        self.logger.debug("Stored all manager instances.")

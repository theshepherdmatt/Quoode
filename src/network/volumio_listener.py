# src/network/volumio_listener.py

import socketio
import logging
import time
import threading
from blinker import Signal

class VolumioListener:
    def __init__(self, host='localhost', port=3000, reconnect_delay=5):
        """
        Initialize the VolumioListener.
        """
        self.logger = logging.getLogger("VolumioListener")
        self.logger.setLevel(logging.DEBUG)  # Set to DEBUG for detailed logs
        self.logger.debug("[VolumioListener] Initializing...")

        self.host = host
        self.port = port
        self.reconnect_delay = reconnect_delay
        self.socketIO = socketio.Client(logger=False, engineio_logger=False, reconnection=True)

        # Define Blinker signals
        self.connected = Signal('connected')
        self.disconnected = Signal('disconnected')
        self.state_changed = Signal('state_changed')
        self.track_changed = Signal('track_changed')
        self.toast_message_received = Signal('toast_message_received')
        self.navigation_received = Signal()

        # Navigation signals for managers
        self.playlists_navigation_received = Signal('playlists_navigation_received')
        self.webradio_navigation_received = Signal('webradio_navigation_received')
        self.qobuz_navigation_received = Signal('qobuz_navigation_received')
        self.tidal_navigation_received = Signal('tidal_navigation_received')
        self.spotify_navigation_received = Signal('spotify_navigation_received')
        self.library_navigation_received = Signal('library_navigation_received')
        self.usb_library_navigation_received = Signal('usb_library_navigation_received')

        # Internal state
        self.current_state = {}
        self.state_lock = threading.Lock()
        self._running = True
        self._reconnect_attempt = 1

        # Tracking browseLibrary requests
        self.browse_lock = threading.Lock()
        self.last_browse_service = None
        self.last_browse_uri = None

        self.register_socketio_events()
        self.connect()

    def register_socketio_events(self):
        """Register events to listen to from the SocketIO server."""
        self.logger.info("[VolumioListener] Registering SocketIO events...")
        self.socketIO.on('connect', self.on_connect)
        self.socketIO.on('disconnect', self.on_disconnect)
        self.socketIO.on('pushState', self.on_push_state)
        self.socketIO.on('pushBrowseLibrary', self.on_push_browse_library)
        self.socketIO.on('pushTrack', self.on_push_track)
        self.socketIO.on('pushToastMessage', self.on_push_toast_message)
        self.socketIO.on('volume', self.set_volume)
    
    def set_volume(self, value):
        """Set the volume to a specific value, increase/decrease, or mute/unmute."""
        valid_values = ['+', '-', 'mute', 'unmute']
        if isinstance(value, int) and 0 <= value <= 100:
            self.logger.info(f"[VolumioListener] Setting volume to: {value}")
            self.socketIO.emit('volume', value)
        elif value in valid_values:
            self.logger.info(f"[VolumioListener] Sending volume command: {value}")
            self.socketIO.emit('volume', value)
        else:
            self.logger.warning(f"[VolumioListener] Invalid volume value: {value}")

    def increase_volume(self):
        """Increase the volume by emitting '+'."""
        self.set_volume('+')

    def decrease_volume(self):
        """Decrease the volume by emitting '-'."""
        self.set_volume('-')

    def mute_volume(self):
        """Mute the volume."""
        self.set_volume('mute')

    def unmute_volume(self):
        """Unmute the volume."""
        self.set_volume('unmute')


    def on_push_toast_message(self, data):
        """Handle 'pushToastMessage' events."""
        self.logger.info("[VolumioListener] Received pushToastMessage event.")
        if data:
            self.logger.debug(f"Toast Message Data: {data}")
            self.toast_message_received.send(self, message=data)
        else:
            self.logger.warning("[VolumioListener] Received empty toast message.")

    def connect(self):
        """Connect to the Volumio server."""
        if self.socketIO.connected:
            self.logger.info("[VolumioListener] Already connected.")
            return
        try:
            self.logger.info(f"[VolumioListener] Connecting to Volumio at {self.host}:{self.port}...")
            self.socketIO.connect(f"http://{self.host}:{self.port}")
            self.logger.info("[VolumioListener] Successfully connected.")
        except Exception as e:
            self.logger.error(f"[VolumioListener] Connection error: {e}")
            self.schedule_reconnect()

    def on_connect(self):
        """Handle successful connection."""
        self.connected.send(self)
        self.logger.info("[VolumioListener] Connected to Volumio.")
        self._reconnect_attempt = 1  # Reset reconnect attempts
        self.socketIO.emit('getState')

    def is_connected(self):
        """Check if the client is connected to Volumio."""
        return self.socketIO.connected

    def on_disconnect(self):
        """Handle disconnection."""
        self.disconnected.send(self)
        self.logger.warning("[VolumioListener] Disconnected from Volumio.")
        self.schedule_reconnect()

    def schedule_reconnect(self):
        """Schedule a reconnection attempt."""
        delay = min(self.reconnect_delay * self._reconnect_attempt, 60)
        self.logger.info(f"[VolumioListener] Reconnecting in {delay} seconds...")
        threading.Thread(target=self._reconnect_after_delay, args=(delay,), daemon=True).start()

    def _reconnect_after_delay(self, delay):
        """Reconnect after a specified delay."""
        time.sleep(delay)
        if not self.socketIO.connected and self._running:
            self._reconnect_attempt += 1
            self.connect()

    def on_push_state(self, data):
        """Handle playback state changes."""
        self.logger.info("[VolumioListener] Received pushState event.")
        with self.state_lock:
            self.current_state = data  # Store the current state
        self.state_changed.send(self, state=data)  # Emit the signal with sender and state


    def on_push_browse_library(self, data):
        """Handle 'pushBrowseLibrary' events."""
        self.logger.info("[VolumioListener] Received pushBrowseLibrary event.")
        navigation = data.get("navigation", {})
        if not navigation:
            self.logger.warning("[VolumioListener] No navigation data received.")
            return

        with self.browse_lock:
            service = self.last_browse_service
            uri = self.last_browse_uri
            # Reset the tracking after using
            self.last_browse_service = None
            self.last_browse_uri = None

        self.logger.debug(f"[VolumioListener] Using URI: {uri}, Service: {service}")

        if not service or not uri:
            # If service or uri was not tracked, attempt to infer
            uri = navigation.get('uri', '').strip().lower()
            if not uri:
                uri = data.get('uri', '').strip().lower()
            self.logger.debug(f"[VolumioListener] Processing URI from event data: {uri}")
            service = self.get_service_from_uri(uri)
            self.logger.debug(f"[VolumioListener] Inferred Service: {service}")

        # Emit a generic navigation_received signal with service and uri
        self.navigation_received.send(self, navigation=navigation, service=service, uri=uri)



    def on_push_track(self, data):
        """Handle 'pushTrack' events."""
        self.logger.info("[VolumioListener] Received pushTrack event.")
        track_info = self.extract_track_info(data)
        self.track_changed.send(self, track_info=track_info)

    def extract_track_info(self, data):
        """Extract track info."""
        track = data.get('track', {})
        return {
            'title': track.get('title', 'Unknown Title'),
            'artist': track.get('artist', 'Unknown Artist'),
            'albumart': track.get('albumart', ''),
            'uri': track.get('uri', '')
        }

    def get_current_state(self):
        with self.state_lock:
            return self.current_state.copy()  # Return a copy to prevent external modifications

    def stop(self):
        """Stop the VolumioListener."""
        self._running = False
        self.socketIO.disconnect()
        self.logger.info("[VolumioListener] Listener stopped.")

    def fetch_browse_library(self, uri):
        if self.socketIO.connected:
            service = self.get_service_from_uri(uri)
            with self.browse_lock:
                self.last_browse_service = service
                self.last_browse_uri = uri
                self.logger.debug(f"[VolumioListener] Tracking browseLibrary URI: {uri}, Service: {service}")
            self.socketIO.emit("browseLibrary", {"uri": uri})
            self.logger.debug(f"[VolumioListener] Emitted 'browseLibrary' for URI: {uri}")
        else:
            self.logger.warning("[VolumioListener] Cannot emit 'browseLibrary' - not connected to Volumio.")

    def get_service_from_uri(self, uri):
        self.logger.debug(f"Determining service for URI: {uri}")
        
        # Normalize Spotify URIs to handle both types consistently
        if uri.startswith("spotify") or uri.startswith("spop"):
            self.logger.debug("Identified service: spotify")
            return 'spotify'

        if uri.startswith("qobuz://"):
            self.logger.debug("Identified service: qobuz")
            return 'qobuz'
        elif uri.startswith("tidal://"):
            self.logger.debug("Identified service: tidal")
            return 'tidal'
        elif uri.startswith("radio/"):
            self.logger.debug("Identified service: webradio")
            return 'webradio'
        elif uri.startswith("playlists") or uri.startswith("playlist://"):
            self.logger.debug("Identified service: playlists")
            return 'playlists'
        elif uri.startswith("music-library/NAS"):
            self.logger.debug("Identified service: library")
            return 'library'
        elif uri.startswith("music-library/USB"):
            self.logger.debug("Identified service: usblibrary")
            return 'usblibrary'
        else:
            self.logger.warning(f"Unrecognized URI scheme: {uri}")
            return None
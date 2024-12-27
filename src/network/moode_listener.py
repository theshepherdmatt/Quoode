# src/network/moode_listener.py

import logging
import time
import threading
from blinker import Signal
from mpd import MPDClient, CommandError

class MoodeListener:
    """
    A 'listener' class for moOde that uses MPD (port 6600) to track playback state, 
    control volume, and provide signals akin to the VolumioListener approach.
    """

    def __init__(self, host='localhost', port=6600, reconnect_delay=5, mode_manager=None, auto_connect=False, moode_ready_event=None):
        """
        Initialize the MoodeListener.
        """
        self.logger = logging.getLogger("MoodeListener")
        self.logger.setLevel(logging.DEBUG)
        self.logger.debug("[MoodeListener] Initializing...")

        self.host = host
        self.port = port
        self.reconnect_delay = reconnect_delay
        self.mode_manager = mode_manager

        # MPD client
        self.client = MPDClient()
        self.client.timeout = 10  # mpd command timeout (seconds)

        # Blinker signals
        self.connected = Signal('connected')
        self.disconnected = Signal('disconnected')
        self.state_changed = Signal('state_changed')
        self.track_changed = Signal('track_changed')
        # Additional signals can be added as needed

        self.current_state = {}
        self.state_lock = threading.Lock()
        self._running = True

        self.moode_ready_event = moode_ready_event  # Store the event

        # Create a background thread that calls `idle` on MPD
        self.listener_thread = threading.Thread(
            target=self._listener_loop, daemon=True
        )

        if auto_connect:
            self.connect()
            self.listener_thread.start()

    def init_listener(self):
        """Connect + start the thread once we have mode_manager assigned."""
        if not self.is_connected():
            self.connect()
        if not self.listener_thread.is_alive():
            self.listener_thread.start()

    def on_connect(self):
        self.logger.info("[MoodeListener] Successfully connected to MPD.")
        self._reconnect_attempt = 1

        # Fire the 'connected' signal for other usage
        self.connected.send(self)

        # Set the moode_ready_event if provided
        if self.moode_ready_event:
            self.logger.info("[MoodeListener] Setting moode_ready_event.")
            self.moode_ready_event.set()

    def connect(self):
        if self.is_connected():
            self.logger.debug("[MoodeListener] Already connected, skipping connect().")
            return
        try:
            self.logger.info(f"[MoodeListener] Connecting to MPD at {self.host}:{self.port}...")
            self.client.connect(self.host, self.port)
            self.on_connect()
        except Exception as e:
            self.logger.error(f"[MoodeListener] Connection error: {e}")
            self.schedule_reconnect()

    def schedule_reconnect(self):
        """Schedule a reconnection attempt after a delay."""
        if not self._running:
            return  # Don't reconnect if we've been stopped
        delay = min(self.reconnect_delay * self._reconnect_attempt, 60)
        self._reconnect_attempt += 1
        self.logger.info(f"[MoodeListener] Reconnecting in {delay} seconds...")
        threading.Thread(
            target=self._reconnect_after_delay, args=(delay,), daemon=True
        ).start()

    def _reconnect_after_delay(self, delay):
        """Reconnect after a specified delay."""
        time.sleep(delay)
        if self._running:
            self.connect()

    def is_connected(self):
        """Check if we are still connected to MPD."""
        try:
            # 'ping' or any MPD command to see if the connection is up
            self.client.ping()
            return True
        except:
            return False

    def _listener_loop(self):
        """
        Main loop that waits for MPD events using the idle command.
        Whenever there's a 'player' change, we fetch the new state.
        """
        while self._running:
            if not self.is_connected():
                # If disconnected, skip idle and try reconnect
                time.sleep(1)
                continue

            try:
                # Wait for something to change
                changes = self.client.idle()  # e.g. ['player', 'mixer', 'playlist', etc.]
                self.logger.debug(f"[MoodeListener] MPD changes: {changes}")

                if 'player' in changes or 'mixer' in changes:
                    self.on_push_state()

            except CommandError as e:
                self.logger.warning(f"[MoodeListener] MPD command error: {e}")
                time.sleep(1)  # small delay before trying again
            except Exception as e:
                self.logger.error(f"[MoodeListener] Unexpected error: {e}")
                self.disconnect()
                self.schedule_reconnect()

    def on_push_state(self):
        try:
            # Retrieve current status and currentsong
            status = self.client.status()
            currentsong = self.client.currentsong()

            # Log the retrieved data
            self.logger.debug(f"[MoodeListener] Retrieved status: {status}")
            self.logger.debug(f"[MoodeListener] Retrieved currentsong: {currentsong}")
            self.logger.debug(f"[MoodeListener] Currentsong keys: {list(currentsong.keys())}")

            # Initialize current_service
            current_service = None

            # Since 'outputs' are not supported, infer service from currentsong
            file_path = currentsong.get('file', '')
            if isinstance(file_path, str):
                if file_path.startswith('http'):
                    current_service = 'webradio'
                elif file_path.startswith(('NAS', 'USB')):
                    current_service = 'mpd'
                else:
                    current_service = 'unknown'
            else:
                self.logger.warning(f"[MoodeListener] 'file' in currentsong is not a string: {file_path}")
                current_service = 'unknown'

            self.logger.debug(f"[MoodeListener] Inferred current_service: {current_service}")

            # Structure the new state
            new_state = {
                'status': status,
                'current_service': current_service
            }

            # Assign 'currentsong' fields explicitly to avoid key conflicts
            for key, value in currentsong.items():
                if key not in new_state:
                    new_state[key] = value

            # Emit state_changed with comprehensive state
            self.state_changed.send(self, state=new_state)

            # If the track changed, emit track_changed
            old_track = self.current_state.get('title')
            new_track = new_state.get('title')
            self.current_state = new_state

            if old_track != new_track:
                self.track_changed.send(self, track_info=new_state)

            self.logger.info("[MoodeListener] State updated.")
        except Exception as e:
            self.logger.error(f"[MoodeListener] Error retrieving state: {e}")

    def disconnect(self):
        """Disconnect from MPD and emit 'disconnected' signal."""
        try:
            self.client.close()
            self.client.disconnect()
        except:
            pass
        self.disconnected.send(self)
        self.logger.warning("[MoodeListener] Disconnected from MPD.")

    def stop(self):
        """Stop the MoodeListener gracefully."""
        self._running = False
        self.disconnect()
        self.logger.info("[MoodeListener] Listener stopped.")

    # -----------------------------------------------------------------
    #                     VOLUME CONTROLS
    # -----------------------------------------------------------------
    def set_volume(self, value):
        """
        Set volume (0–100) or commands like:
          + (increment), - (decrement)
        """
        if not self.is_connected():
            self.logger.warning("[MoodeListener] Can't set volume, not connected.")
            return
        try:
            current_vol = int(self.client.status().get('volume', 50))
            if isinstance(value, int):
                # Force into 0-100 range
                new_vol = max(0, min(100, value))
                self.logger.info(f"[MoodeListener] Setting volume to {new_vol}")
                self.client.setvol(new_vol)
            elif value == '+':
                # Increase by 5 for example
                new_vol = min(100, current_vol + 5)
                self.logger.info(f"[MoodeListener] Increasing volume to {new_vol}")
                self.client.setvol(new_vol)
            elif value == '-':
                # Decrease by 5
                new_vol = max(0, current_vol - 5)
                self.logger.info(f"[MoodeListener] Decreasing volume to {new_vol}")
                self.client.setvol(new_vol)
            else:
                self.logger.warning(f"[MoodeListener] Invalid volume command: {value}")
        except Exception as e:
            self.logger.error(f"[MoodeListener] Error setting volume: {e}")

    def increase_volume(self):
        """Shorthand to increase volume."""
        self.set_volume('+')

    def decrease_volume(self):
        """Shorthand to decrease volume."""
        self.set_volume('-')

    # MoOde doesn’t have a 'mute' via MPD, but you could emulate by setting vol=0
    def mute_volume(self):
        self.logger.info("[MoodeListener] Muting (vol=0).")
        self.set_volume(0)

    def unmute_volume(self):
        # Up to you how you track the old volume
        self.logger.info("[MoodeListener] Unmute not tracked, setting vol=50.")
        self.set_volume(50)

    # -----------------------------------------------------------------
    #                 LIBRARY / BROWSE EXAMPLES (Optional)
    # -----------------------------------------------------------------
    def fetch_library(self, uri=""):
        """
        moOde doesn't have a pushBrowseLibrary event, so you typically query MPD:
          e.g. lsinfo for directories, or find/filter for songs.
        """
        try:
            self.logger.info(f"[MoodeListener] Browsing MPD for URI: {uri}")
            if uri:
                results = self.client.lsinfo(uri)
            else:
                results = self.client.lsinfo()
            # You’d parse 'results' as needed and emit a signal if desired
            self.logger.debug(f"[MoodeListener] Library results: {results}")
            return results
        except Exception as e:
            self.logger.error(f"[MoodeListener] Error browsing library: {e}")
            return []

    def get_current_state(self):
        """Returns a copy of the last known MPD state."""
        with self.state_lock:
            return dict(self.current_state)  # copy

import logging
import time
import threading
from blinker import Signal
from mpd import MPDClient, CommandError

class MoodeListener:
    """
    A 'listener' class for moOde that uses MPD (port 6600) to track
    playback state, control volume, and issue signals via blinker.
    """

    def __init__(
        self,
        host='localhost',
        port=6600,
        reconnect_delay=5,
        mode_manager=None,
        auto_connect=False,
        moode_ready_event=None
    ):
        self.logger = logging.getLogger("MoodeListener")
        self.logger.setLevel(logging.DEBUG)
        self.logger.debug("MoodeListener initializing...")

        self.host = host
        self.port = port
        self.reconnect_delay = reconnect_delay
        self.mode_manager = mode_manager

        self.client = MPDClient()
        self.client.timeout = 10  # seconds

        # Blinker signals
        self.connected = Signal('connected')
        self.disconnected = Signal('disconnected')
        self.state_changed = Signal('state_changed')
        self.track_changed = Signal('track_changed')

        self.current_state = {}
        self.state_lock = threading.Lock()
        self._running = True

        self.moode_ready_event = moode_ready_event
        self._reconnect_attempt = 1

        self.listener_thread = threading.Thread(target=self._listener_loop, daemon=True)

        if auto_connect:
            self.connect()
            self.listener_thread.start()

    def init_listener(self):
        """Call this once the mode_manager is assigned; connects & starts the thread."""
        if not self.is_connected():
            self.connect()
        if not self.listener_thread.is_alive():
            self.listener_thread.start()

    def on_connect(self):
        self.logger.info("MoodeListener: Connected to MPD.")
        self._reconnect_attempt = 1
        self.connected.send(self)

        if self.moode_ready_event:
            self.logger.info("MoodeListener: Setting moode_ready_event (MPD ready).")
            self.moode_ready_event.set()

    def connect(self):
        if self.is_connected():
            self.logger.debug("MoodeListener: Already connected.")
            return
        try:
            self.logger.info(f"MoodeListener: Connecting to MPD {self.host}:{self.port}...")
            self.client.connect(self.host, self.port)
            self.on_connect()
        except Exception as e:
            self.logger.error(f"MoodeListener: Connection error: {e}")
            self.schedule_reconnect()

    def schedule_reconnect(self):
        if not self._running:
            return
        delay = min(self.reconnect_delay * self._reconnect_attempt, 60)
        self._reconnect_attempt += 1
        self.logger.info(f"MoodeListener: Reconnecting in {delay} seconds.")
        t = threading.Thread(target=self._reconnect_after_delay, args=(delay,), daemon=True)
        t.start()

    def _reconnect_after_delay(self, delay):
        time.sleep(delay)
        if self._running:
            self.connect()

    def is_connected(self):
        try:
            self.client.ping()
            return True
        except:
            return False

    def _listener_loop(self):
        while self._running:
            if not self.is_connected():
                time.sleep(1)
                continue
            try:
                changes = self.client.idle()  # e.g. ['player', 'mixer', ...]
                self.logger.debug(f"MoodeListener: MPD changes: {changes}")
                if 'player' in changes or 'mixer' in changes:
                    self.on_push_state()
            except CommandError as e:
                self.logger.warning(f"MoodeListener: MPD command error: {e}")
                time.sleep(1)
            except Exception as e:
                self.logger.error(f"MoodeListener: Unexpected error: {e}")
                self.disconnect()
                self.schedule_reconnect()

    def on_push_state(self):
        try:
            status = self.client.status()
            currentsong = self.client.currentsong()

            self.logger.debug(f"MoodeListener status={status}, currentsong={currentsong}")
            file_path = currentsong.get('file', '')
            if not isinstance(file_path, str):
                file_path = ''
                self.logger.warning("MoodeListener: 'file' in currentsong not a string.")

            if file_path.startswith('http'):
                current_service = 'webradio'
            elif file_path.startswith(('NAS', 'USB')):
                current_service = 'mpd'
            else:
                current_service = 'unknown'

            new_state = {'status': status, 'current_service': current_service}
            for key, val in currentsong.items():
                if key not in new_state:
                    new_state[key] = val

            self.state_changed.send(self, state=new_state)

            old_track = self.current_state.get('title')
            new_track = new_state.get('title')
            self.current_state = new_state

            if old_track != new_track:
                self.track_changed.send(self, track_info=new_state)

            self.logger.info("MoodeListener: MPD state updated.")
        except Exception as e:
            self.logger.error(f"MoodeListener: Error retrieving state: {e}")

    def disconnect(self):
        try:
            self.client.close()
            self.client.disconnect()
        except:
            pass
        self.disconnected.send(self)
        self.logger.warning("MoodeListener: Disconnected from MPD.")

    def stop(self):
        self._running = False
        self.disconnect()
        self.logger.info("MoodeListener: Listener stopped.")

    # Volume controls etc. remain unchanged
    def set_volume(self, value):
        if not self.is_connected():
            self.logger.warning("MoodeListener: Can't set volume; not connected.")
            return
        try:
            current_vol = int(self.client.status().get('volume', 50))
            if isinstance(value, int):
                new_vol = max(0, min(100, value))
                self.logger.info(f"MoodeListener: Setting volume to {new_vol}")
                self.client.setvol(new_vol)
            elif value == '+':
                new_vol = min(100, current_vol + 5)
                self.logger.info(f"MoodeListener: Increasing volume to {new_vol}")
                self.client.setvol(new_vol)
            elif value == '-':
                new_vol = max(0, current_vol - 5)
                self.logger.info(f"MoodeListener: Decreasing volume to {new_vol}")
                self.client.setvol(new_vol)
            else:
                self.logger.warning(f"MoodeListener: Invalid volume command: {value}")
        except Exception as e:
            self.logger.error(f"MoodeListener: Error setting volume: {e}")

    def increase_volume(self):
        self.set_volume('+')

    def decrease_volume(self):
        self.set_volume('-')

    def mute_volume(self):
        self.logger.info("MoodeListener: Muting volume to 0.")
        self.set_volume(0)

    def unmute_volume(self):
        self.logger.info("MoodeListener: Unmute not tracked; setting volume to 50.")
        self.set_volume(50)

    def fetch_library(self, uri=""):
        if not self.is_connected():
            return []
        try:
            self.logger.info(f"MoodeListener: Browsing library URI='{uri}'")
            return self.client.lsinfo(uri) if uri else self.client.lsinfo()
        except Exception as e:
            self.logger.error(f"MoodeListener: fetch_library error: {e}")
            return []

    def get_current_state(self):
        with self.state_lock:
            return dict(self.current_state)

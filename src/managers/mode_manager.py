import logging
import os
import json
import threading
from transitions import Machine

class ModeManager:
    """
    Manage the Quoode state machine, controlling transitions between:
    - boot (loading), clock, playback, webradio, menu, etc.
    - 'original' vs 'modern' screens for playback.
    """

    states = [
        {'name': 'boot', 'on_enter': 'enter_boot'},      # NEW: The initial "loading" state
        {'name': 'clock', 'on_enter': 'enter_clock'},
        {'name': 'playback', 'on_enter': 'enter_playback'},
        {'name': 'webradio', 'on_enter': 'enter_webradio_screen'},
        {'name': 'menu', 'on_enter': 'enter_menu'},
        {'name': 'radio', 'on_enter': 'enter_radio_manager'},
        {'name': 'playlists', 'on_enter': 'enter_playlists'},
        {'name': 'library', 'on_enter': 'enter_library'},
        {'name': 'usblibrary', 'on_enter': 'enter_usb_library'},
        {'name': 'original', 'on_enter': 'enter_original'},
        {'name': 'modern', 'on_enter': 'enter_modern'},
    ]

    def __init__(
        self,
        display_manager,
        clock,
        moode_listener,
        preference_file_path="screen_preference.json"
    ):
        """
        :param display_manager: DisplayManager instance
        :param clock: Clock screen (home screen)
        :param moode_listener: MoodeListener (MPD link)
        :param preference_file_path: JSON file to store 'original' vs 'modern' preference
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)
        self.logger.debug("ModeManager initializing...")

        self.display_manager = display_manager
        self.clock = clock
        self.moode_listener = moode_listener

        # Where to store "original" vs "modern"
        self.preference_file_path = os.path.join(os.path.dirname(__file__), preference_file_path)
        self.current_display_mode = self._load_screen_preference()

        # Will be set later by manager_factory
        self.original_screen = None
        self.menu_manager = None
        self.playlist_manager = None
        self.radio_manager = None
        self.webradio_screen = None
        self.library_manager = None
        self.usb_library_manager = None
        self.modern_screen = None

        # Setup transitions
        self.logger.debug("ModeManager: Setting up state machine with 'boot' as initial.")
        self.machine = Machine(
            model=self,
            states=ModeManager.states,
            initial='boot',  # IMPORTANT: Start in 'boot' (loading) state
            send_event=True
        )

        # Transitions
        self.machine.add_transition('to_clock',       source='*', dest='clock')
        self.machine.add_transition('to_playback',    source='*', dest='playback')
        self.machine.add_transition('to_webradio',    source='*', dest='webradio')
        self.machine.add_transition('to_menu',        source='*', dest='menu')
        self.machine.add_transition('to_radio',       source='*', dest='radio')
        self.machine.add_transition('to_playlists',   source='*', dest='playlists')
        self.machine.add_transition('to_library',     source='*', dest='library')
        self.machine.add_transition('to_usb_library', source='*', dest='usblibrary')
        self.machine.add_transition('to_original',    source='*', dest='original')
        self.machine.add_transition('to_modern',      source='*', dest='modern')

        self.suppress_state_changes = False
        self.lock = threading.Lock()

        # Connect signals from moode_listener if available
        if self.moode_listener is not None:
            self.moode_listener.state_changed.connect(self.process_state_change)
            self.logger.debug("ModeManager: Linked to moode_listener.state_changed.")
        else:
            self.logger.warning("ModeManager: moode_listener is None; not linking state_changed.")

        # Because initial state is 'boot', we do NOT call enter_clock() here.
        # We'll only transition to clock after loading events are done.

        # Track playback statuses
        self.is_track_changing = False
        self.track_change_in_progress = False
        self.current_status = None
        self.previous_status = None
        self.pause_stop_timer = None
        self.pause_stop_delay = 0.5  # e.g., half second

    # ---------------------------------------
    #  Boot State
    # ---------------------------------------
    def enter_boot(self, event):
        """
        The 'boot' (or 'loading') state. 
        No clock, no screens started. 
        The main script will eventually call `to_clock()` once ready.
        """
        self.logger.info("ModeManager: Entering 'boot' state. Waiting for system load...")

    # ---------------------------------------
    #  Preferences
    # ---------------------------------------
    def _load_screen_preference(self):
        """Load 'display_mode' (e.g., 'original' or 'modern') from JSON."""
        if os.path.exists(self.preference_file_path):
            try:
                with open(self.preference_file_path, "r") as f:
                    data = json.load(f)
                    mode = data.get("display_mode", "original")
                    self.logger.info(f"Loaded display mode preference: {mode}")
                    return mode
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"Failed to load preference; defaulting to 'original'. Error: {e}")
        else:
            self.logger.info("No preference file found; defaulting to 'original'.")
        return "original"

    def _save_screen_preference(self):
        """Save the current display mode to JSON."""
        data = {"display_mode": self.current_display_mode}
        try:
            with open(self.preference_file_path, "w") as f:
                json.dump(data, f)
            self.logger.info(f"Saved display mode preference: {self.current_display_mode}")
        except IOError as e:
            self.logger.error(f"Failed to save screen preference: {e}")

    def set_display_mode(self, mode_name):
        """Switch between 'original' and 'modern' screens."""
        if mode_name in ['original', 'modern']:
            self.current_display_mode = mode_name
            self.logger.info(f"ModeManager: Display mode set to {mode_name}")
            self._save_screen_preference()
        else:
            self.logger.warning(f"ModeManager: Unknown display mode '{mode_name}'")

    # ---------------------------------------
    #  Setting up references
    # ---------------------------------------
    def set_original_screen(self, original_screen):
        self.original_screen = original_screen

    def set_webradio_screen(self, webradio_screen):
        self.webradio_screen = webradio_screen

    def set_menu_manager(self, menu_manager):
        self.menu_manager = menu_manager

    def set_playlist_manager(self, playlist_manager):
        self.playlist_manager = playlist_manager

    def set_radio_manager(self, radio_manager):
        self.radio_manager = radio_manager

    def set_library_manager(self, library_manager):
        self.library_manager = library_manager

    def set_usb_library_manager(self, usb_library_manager):
        self.usb_library_manager = usb_library_manager

    def set_modern_screen(self, modern_screen):
        self.modern_screen = modern_screen

    def get_mode(self):
        return self.state

    # ---------------------------------------
    #  Entering states
    # ---------------------------------------
    def enter_clock(self, event):
        self.logger.info("ModeManager: Entering clock mode.")

        # Stop all other managers/screens
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
        if self.radio_manager and self.radio_manager.is_active:
            self.radio_manager.stop_mode()
        if self.playlist_manager and self.playlist_manager.is_active:
            self.playlist_manager.stop_mode()
        if self.library_manager and self.library_manager.is_active:
            self.library_manager.stop_mode()
        if self.usb_library_manager and self.usb_library_manager.is_active:
            self.usb_library_manager.stop_mode()
        if self.modern_screen and self.modern_screen.is_active:
            self.modern_screen.stop_mode()
        if self.webradio_screen and self.webradio_screen.is_active:
            self.webradio_screen.stop_mode()
        if self.original_screen and self.original_screen.is_active:
            self.logger.debug("Retaining original_screen if it's actively playing.")
        # Start clock
        if self.clock:
            self.clock.start()
        else:
            self.logger.error("ModeManager: No Clock instance available to start.")

    def enter_playback(self, event):
        self.logger.info("ModeManager: Entering playback mode.")
        if self.clock:
            self.clock.stop()

        if self.current_display_mode == 'modern':
            if self.modern_screen:
                self.modern_screen.start_mode()
            else:
                self.logger.error("ModeManager: modern_screen not set.")
        else:
            # fallback is 'original'
            if self.original_screen:
                self.original_screen.start_mode()
            else:
                self.logger.error("ModeManager: original_screen not set.")

    def enter_webradio_screen(self, event):
        self.logger.info("ModeManager: Entering webradio screen.")
        if self.clock:
            self.clock.stop()
        if self.original_screen and self.original_screen.is_active:
            self.original_screen.stop_mode()

        if self.webradio_screen:
            self.webradio_screen.start_mode()
        else:
            self.logger.error("ModeManager: webradio_screen is not set.")

    def enter_menu(self, event):
        self.logger.info("ModeManager: Entering menu mode.")
        if self.clock:
            self.clock.stop()
        if self.original_screen and self.original_screen.is_active:
            self.original_screen.stop_mode()
        if self.webradio_screen and self.webradio_screen.is_active:
            self.webradio_screen.stop_mode()

        if self.menu_manager:
            self.menu_manager.start_mode()
        else:
            self.logger.error("ModeManager: menu_manager is not set.")

    def enter_radio_manager(self, event):
        self.logger.info("ModeManager: Entering radio_manager mode.")
        if self.clock:
            self.clock.stop()
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()

        if self.radio_manager:
            self.radio_manager.stop_mode()  # ensure it's not double-started
            self.radio_manager.start_mode()
        else:
            self.logger.error("ModeManager: radio_manager is not set.")

    def enter_playlists(self, event):
        self.logger.info("ModeManager: Entering playlist mode.")
        if self.clock:
            self.clock.stop()
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()

        if self.playlist_manager:
            self.playlist_manager.start_mode()
        else:
            self.logger.error("ModeManager: playlist_manager is not set.")

    def enter_library(self, event):
        start_uri = event.kwargs.get('start_uri', None)
        self.logger.info(f"ModeManager: Entering library mode (uri={start_uri}).")
        if self.clock:
            self.clock.stop()
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()

        if self.library_manager:
            self.library_manager.start_mode(start_uri=start_uri)
        else:
            self.logger.error("ModeManager: library_manager is not set.")

    def enter_usb_library(self, event):
        start_uri = event.kwargs.get('start_uri', None)
        self.logger.info(f"ModeManager: Entering USB library (uri={start_uri}).")
        if self.clock:
            self.clock.stop()
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()

        if self.usb_library_manager:
            self.usb_library_manager.start_mode(start_uri=start_uri)
        else:
            self.logger.error("ModeManager: usb_library_manager is not set.")

    def enter_original(self, event):
        self.logger.info("ModeManager: Entering Original mode.")
        if self.clock:
            self.clock.stop()
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()

        if self.original_screen:
            self.original_screen.start_mode()
        else:
            self.logger.error("ModeManager: original_screen is not set.")

    def enter_modern(self, event):
        self.logger.info("ModeManager: Entering Modern mode.")
        if self.clock:
            self.clock.stop()
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()

        if self.modern_screen:
            self.modern_screen.start_mode()
        else:
            self.logger.error("ModeManager: modern_screen is not set.")

    # ---------------------------------------
    #  Additional transitions
    # ---------------------------------------
    def switch_to_library_mode(self, start_uri=None):
        self.logger.info(f"ModeManager: -> library mode (uri={start_uri}).")
        self.machine.trigger('to_library', start_uri=start_uri)

    def switch_to_usb_library_mode(self, start_uri=None):
        self.logger.info(f"ModeManager: -> USB library mode (uri={start_uri}).")
        self.machine.trigger('to_usb_library', start_uri=start_uri)

    # ---------------------------------------
    #  Suppression logic (optional)
    # ---------------------------------------
    def suppress_state_change(self):
        with self.lock:
            self.suppress_state_changes = True
            self.logger.debug("ModeManager: State changes suppressed.")

    def allow_state_change(self):
        with self.lock:
            self.suppress_state_changes = False
            self.logger.debug("ModeManager: State changes allowed.")

    def is_state_change_suppressed(self):
        return self.suppress_state_changes

    # ---------------------------------------
    #  Processing MPD updates
    # ---------------------------------------
    def process_state_change(self, sender, state, **kwargs):
        with self.lock:
            if self.suppress_state_changes:
                self.logger.debug("ModeManager: State change is suppressed.")
                return

            self.logger.debug(f"ModeManager: process_state_change -> {state}")
            status_dict = state.get('status', {})
            new_status = status_dict.get('state', '').lower()  # "play", "pause", "stop"

            self.previous_status = self.current_status
            self.current_status = new_status

            if self.previous_status == "play" and self.current_status == "stop":
                self._handle_track_change()
            elif self.previous_status == "stop" and self.current_status == "play":
                self._handle_track_resumed()

            self._handle_playback_states(new_status)

    def _handle_track_change(self):
        """
        Possibly the transition from 'play' to 'stop' indicates track end.
        We start a timer to see if we remain in stop or move to another track.
        """
        self.is_track_changing = True
        self.track_change_in_progress = True

        if not self.pause_stop_timer:
            self.pause_stop_timer = threading.Timer(
                self.pause_stop_delay,
                self.switch_to_clock_if_still_stopped_or_paused
            )
            self.pause_stop_timer.start()
            self.logger.debug("ModeManager: Started stop verification timer.")

    def _handle_track_resumed(self):
        """If we jumped from 'stop' to 'play', cancel the stop timer."""
        self.is_track_changing = False
        self.track_change_in_progress = False
        self.logger.debug("ModeManager: Track resumed from 'stop' to 'play'.")

        if self.pause_stop_timer:
            self.pause_stop_timer.cancel()
            self.pause_stop_timer = None
            self.logger.debug("ModeManager: Canceled stop verification timer.")

    def _handle_playback_states(self, status):
        """Deal with 'play', 'pause', 'stop' states globally."""
        if status == "play":
            self._cancel_pause_timer()
            self.is_track_changing = False
            self.track_change_in_progress = False

            # Optionally detect webradio vs local, or just do:
            if self.current_display_mode == 'modern':
                self.to_modern()
            else:
                self.to_original()

        elif status == "pause":
            self._start_pause_timer()

        elif status == "stop" and not self.track_change_in_progress:
            self.logger.debug("ModeManager: 'stop' with no track change -> go clock.")
            self._cancel_pause_timer()
            self.to_clock()

    def _cancel_pause_timer(self):
        if self.pause_stop_timer:
            self.pause_stop_timer.cancel()
            self.pause_stop_timer = None
            self.logger.debug("ModeManager: Canceled pause/stop timer.")

    def _start_pause_timer(self):
        if not self.pause_stop_timer:
            self.pause_stop_timer = threading.Timer(
                self.pause_stop_delay,
                self.switch_to_clock_if_still_stopped_or_paused
            )
            self.pause_stop_timer.start()
            self.logger.debug("ModeManager: Started pause timer.")
        else:
            self.logger.debug("ModeManager: Pause timer already running.")

    def switch_to_clock_if_still_stopped_or_paused(self):
        """If we're still paused or stopped, move to clock after a delay."""
        with self.lock:
            if self.current_status in ["pause", "stop"]:
                self.to_clock()
                self.logger.debug("ModeManager: Switched to clock after timer.")
            else:
                self.logger.debug("ModeManager: Playback resumed; staying in current mode.")
            self.pause_stop_timer = None

    def trigger(self, event_name, **kwargs):
        """Expose the underlying state machine trigger."""
        self.machine.trigger(event_name, **kwargs)

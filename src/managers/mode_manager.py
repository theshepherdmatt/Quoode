
# src/managers/mode_manager.py

import logging
from transitions import Machine
import threading

class ModeManager:
    states = [
        {'name': 'clock', 'on_enter': 'enter_clock'},
        {'name': 'playback', 'on_enter': 'enter_playback'},
        {'name': 'radioplayback', 'on_enter': 'enter_radioplayback'},        
        {'name': 'menu', 'on_enter': 'enter_menu'},
        {'name': 'webradio', 'on_enter': 'enter_webradio'},
        {'name': 'playlists', 'on_enter': 'enter_playlists'},
        {'name': 'tidal', 'on_enter': 'enter_tidal'},
        {'name': 'qobuz', 'on_enter': 'enter_qobuz'},
        {'name': 'library', 'on_enter': 'enter_library'},
        {'name': 'usblibrary', 'on_enter': 'enter_usb_library'},
        {'name': 'spotify', 'on_enter': 'enter_spotify'},
        {'name': 'fm4', 'on_enter': 'enter_fm4'},
        {'name': 'modern', 'on_enter': 'enter_modern'},
    ]

    def __init__(
        self,
        display_manager,
        clock,
        volumio_listener
    ):
        self.display_manager = display_manager
        self.clock = clock
        self.volumio_listener = volumio_listener

        # Managers will be set later
        self.playback_manager = None
        self.menu_manager = None
        self.playlist_manager = None
        self.radio_manager = None
        self.radioplayback_manager = None
        self.tidal_manager = None
        self.qobuz_manager = None
        self.library_manager = None
        self.usb_library_manager = None
        self.spotify_manager = None
        self.detailed_playback_manager = None  


        # Initialize logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)  # Set to DEBUG level for detailed logs
        self.logger.debug("ModeManager initialized.")

        # Initialize state machine
        self.machine = Machine(
            model=self,
            states=ModeManager.states,
            initial='clock',
            send_event=True
        )

        # Define transitions
        self.machine.add_transition(trigger='to_playback', source='*', dest='playback')
        self.machine.add_transition(trigger='to_radioplayback', source='*', dest='radioplayback')
        self.machine.add_transition(trigger='to_menu', source='*', dest='menu')
        self.machine.add_transition(trigger='to_webradio', source='*', dest='webradio')
        self.machine.add_transition(trigger='to_playlists', source='*', dest='playlists')
        self.machine.add_transition(trigger='to_tidal', source='*', dest='tidal')
        self.machine.add_transition(trigger='to_qobuz', source='*', dest='qobuz')
        self.machine.add_transition(trigger='to_library', source='*', dest='library')
        self.machine.add_transition(trigger='to_usb_library', source='*', dest='usblibrary')
        self.machine.add_transition(trigger='to_clock', source='*', dest='clock')
        self.machine.add_transition(trigger='to_spotify', source='*', dest='spotify')
        self.machine.add_transition(trigger='to_fm4', source='*', dest='fm4')
        self.machine.add_transition(trigger='to_modern', source='*', dest='modern')

        # Callback handling
        self.on_mode_change_callbacks = []
        self.lock = threading.Lock()  # Added lock for thread safety

        # Suppression mechanism
        self.suppress_state_changes = False  # Added suppression flag

        # Connect to VolumioListener's state_changed signal
        if self.volumio_listener is not None:
            self.volumio_listener.state_changed.connect(self.process_state_change)
            self.logger.debug("ModeManager: Connected to VolumioListener's state_changed signal.")
        else:
            self.logger.warning("ModeManager: VolumioListener is None, cannot connect to state_changed signal.")

        # Explicitly call enter_clock to initialize the clock mode
        self.enter_clock(None)

        # Initialize state tracking variables
        self.is_track_changing = False
        self.track_change_in_progress = False
        self.current_status = None
        self.previous_status = None
        self.pause_stop_timer = None
        self.pause_stop_delay = 0.5  # Delay in seconds before switching to clock mode

    # Add setter methods for the managers

    def get_active_manager(self):
        """Return the name of the currently active manager."""
        if self.playback_manager and self.playback_manager.is_active:
            return 'playback'
        elif self.radioplayback_manager and self.radioplayback_manager.is_active:
            return 'radioplayback'
        # Add other managers as needed
        return None


    def set_playback_manager(self, playback_manager):
        self.playback_manager = playback_manager

    def set_radioplayback_manager(self, radioplayback_manager):
        self.radioplayback_manager = radioplayback_manager

    def set_menu_manager(self, menu_manager):
        self.menu_manager = menu_manager

    def set_playlist_manager(self, playlist_manager):
        self.playlist_manager = playlist_manager

    def set_radio_manager(self, radio_manager):
        self.radio_manager = radio_manager

    def set_tidal_manager(self, tidal_manager):
        self.tidal_manager = tidal_manager

    def set_qobuz_manager(self, qobuz_manager):
        self.qobuz_manager = qobuz_manager

    def set_library_manager(self, library_manager):
        self.library_manager = library_manager

    def set_usb_library_manager(self, usb_library_manager):
        self.usb_library_manager = usb_library_manager

    def set_spotify_manager(self, spotify_manager):
        self.spotify_manager = spotify_manager

    def set_detailed_playback_manager(self, detailed_playback_manager):
        self.detailed_playback_manager = detailed_playback_manager


    def get_mode(self):
        return self.state

    def enter_clock(self, event):
        self.logger.info("ModeManager: Entering clock mode.")
        
        # Stop other active modes except playback and clock
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
            self.logger.info("ModeManager: Stopped menu mode.")
        if self.radio_manager and self.radio_manager.is_active:
            self.radio_manager.stop_mode()
            self.logger.info("ModeManager: Stopped webradio mode.")
        if self.playlist_manager and self.playlist_manager.is_active:
            self.playlist_manager.stop_mode()
            self.logger.info("ModeManager: Stopped playlist mode.")
        if self.tidal_manager and self.tidal_manager.is_active:
            self.tidal_manager.stop_mode()
            self.logger.info("ModeManager: Stopped Tidal mode.")
        if self.qobuz_manager and self.qobuz_manager.is_active:
            self.qobuz_manager.stop_mode()
            self.logger.info("ModeManager: Stopped Qobuz mode.")
        if self.spotify_manager and self.spotify_manager.is_active:
            self.spotify_manager.stop_mode()
            self.logger.info("ModeManager: Stopped Spotify mode.")
        if self.library_manager and self.library_manager.is_active:
            self.library_manager.stop_mode()
            self.logger.info("ModeManager: Stopped Library mode.")
        if self.usb_library_manager and self.usb_library_manager.is_active:
            self.usb_library_manager.stop_mode()
            self.logger.info("ModeManager: Stopped USBLibrary mode.")
        if self.detailed_playback_manager and self.detailed_playback_manager.is_active:
            self.detailed_playback_manager.stop_mode()
            self.logger.info("ModeManager: Stopped Detailed Playback mode.")

        # Ensure playback manager remains active if it is already playing or paused
        if self.playback_manager and self.playback_manager.is_active:
            self.logger.info("ModeManager: Retaining playback manager state in clock mode.")
        else:
            self.logger.info("ModeManager: Playback manager is not active.")

        # Start the clock display
        if self.clock:
            self.clock.start()
            self.logger.info("ModeManager: Clock started.")
        else:
            self.logger.error("ModeManager: Clock instance is not set.")


    def enter_playback(self, event):
        self.logger.info("ModeManager: Entering playback mode.")
        # Stop clock
        if self.clock:
            self.clock.stop()
            self.logger.info("ModeManager: Clock stopped.")
        else:
            self.logger.error("ModeManager: Clock instance is not set.")

        # Delegate screen handling to ScreenManager
        if self.screen_manager:
            self.screen_manager.handle_state_change("play", None)  # Passing 'play' to trigger screen activation
        else:
            self.logger.error("ModeManager: ScreenManager is not set.")


    def enter_radioplayback(self, event):
        self.logger.info("ModeManager: Entering radioplayback mode.")
        # Stop clock
        if self.clock:
            self.clock.stop()
            self.logger.info("ModeManager: Clock stopped.")
        else:
            self.logger.error("ModeManager: Clock instance is not set.")
        
        # Stop PlaybackManager if it's active
        if self.playback_manager and self.playback_manager.is_active:
            self.playback_manager.stop_mode()
            self.logger.info("ModeManager: Stopped playback mode.")
        
        # Start radioplayback display
        if self.radioplayback_manager:
            self.radioplayback_manager.start_mode()
            self.logger.info("ModeManager: RadioPlayback mode started.")
        else:
            self.logger.error("ModeManager: radioplayback_manager is not set.")


    def enter_menu(self, event):
        self.logger.info("ModeManager: Entering menu mode.")
        # Stop clock, playback, and radioplayback
        if self.clock:
            self.clock.stop()
            self.logger.info("ModeManager: Clock stopped.")
        else:
            self.logger.error("ModeManager: Clock instance is not set.")
        
        if self.playback_manager and self.playback_manager.is_active:
            self.playback_manager.stop_mode()
            self.logger.info("ModeManager: Stopped playback mode.")
        
        if self.radioplayback_manager and self.radioplayback_manager.is_active:
            self.radioplayback_manager.stop_mode()
            self.logger.info("ModeManager: Stopped radioplayback mode.")
        
        # Start menu
        if self.menu_manager:
            self.menu_manager.start_mode()
            self.logger.info("ModeManager: Menu mode started.")
        else:
            self.logger.error("ModeManager: menu_manager is not set.")


    def enter_webradio(self, event):
        self.logger.info("ModeManager: Entering webradio mode.")
        # Stop other modes
        if self.clock:
            self.clock.stop()
            self.logger.info("ModeManager: Clock stopped.")
        else:
            self.logger.error("ModeManager: Clock instance is not set.")
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
            self.logger.info("ModeManager: Stopped menu mode.")
        if self.radio_manager and self.radio_manager.is_active:
            self.radio_manager.stop_mode()
            self.logger.info("ModeManager: Stopped Webradio mode.")
        # Start webradio
        if self.radio_manager:
            self.radio_manager.start_mode()
            self.logger.info("ModeManager: Webradio mode started.")
        else:
            self.logger.error("ModeManager: radio_manager is not set.")

    def enter_playlists(self, event):
        self.logger.info("ModeManager: Entering playlist mode.")
        # Stop other modes
        if self.clock:
            self.clock.stop()
            self.logger.info("ModeManager: Clock stopped.")
        else:
            self.logger.error("ModeManager: Clock instance is not set.")
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
            self.logger.info("ModeManager: Stopped menu mode.")
        # Start playlist
        if self.playlist_manager:
            self.playlist_manager.start_mode()
            self.logger.info("ModeManager: Playlist mode started.")
        else:
            self.logger.error("ModeManager: playlist_manager is not set.")

    def enter_tidal(self, event):
        self.logger.info("ModeManager: Entering Tidal mode.")
        # Stop other modes
        if self.clock:
            self.clock.stop()
            self.logger.info("ModeManager: Clock stopped.")
        else:
            self.logger.error("ModeManager: Clock instance is not set.")
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
            self.logger.info("ModeManager: Stopped menu mode.")
        # Start Tidal
        if self.tidal_manager:
            self.tidal_manager.start_mode()
            self.logger.info("ModeManager: Tidal mode started.")
        else:
            self.logger.error("ModeManager: tidal_manager is not set.")

    def enter_qobuz(self, event):
        self.logger.info("ModeManager: Entering Qobuz mode.")
        # Stop other modes
        if self.clock:
            self.clock.stop()
            self.logger.info("ModeManager: Clock stopped.")
        else:
            self.logger.error("ModeManager: Clock instance is not set.")
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
            self.logger.info("ModeManager: Stopped menu mode.")
        # Start Qobuz
        if self.qobuz_manager:
            self.qobuz_manager.start_mode()
            self.logger.info("ModeManager: Qobuz mode started.")
        else:
            self.logger.error("ModeManager: qobuz_manager is not set.")

    def enter_library(self, event):
        start_uri = event.kwargs.get('start_uri', None)
        self.logger.info(f"ModeManager: Entering Library mode with start_uri: {start_uri}")
        # Stop other modes
        if self.clock:
            self.clock.stop()
            self.logger.info("ModeManager: Clock stopped.")
        else:
            self.logger.error("ModeManager: Clock instance is not set.")
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
            self.logger.info("ModeManager: Stopped menu mode.")
        # Start Library
        if self.library_manager:
            self.library_manager.start_mode(start_uri=start_uri)
            self.logger.info("ModeManager: Library mode started.")
        else:
            self.logger.error("ModeManager: library_manager is not set.")

    def enter_usb_library(self, event):
        start_uri = event.kwargs.get('start_uri', None)
        self.logger.info(f"ModeManager: Entering USB Library mode with start_uri: {start_uri}")
        # Stop other modes
        if self.clock:
            self.clock.stop()
            self.logger.info("ModeManager: Clock stopped.")
        else:
            self.logger.error("ModeManager: Clock instance is not set.")
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
            self.logger.info("ModeManager: Stopped menu mode.")
        # Start USB Library
        if self.usb_library_manager:
            self.usb_library_manager.start_mode(start_uri=start_uri)
            self.logger.info("ModeManager: USB Library mode started.")
        else:
            self.logger.error("ModeManager: usb_library_manager is not set.")

    def enter_spotify(self, event):
        self.logger.info("ModeManager: Entering Spotify mode.")
        # Stop other modes
        if self.clock:
            self.clock.stop()
            self.logger.info("ModeManager: Clock stopped.")
        else:
            self.logger.error("ModeManager: Clock instance is not set.")
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
            self.logger.info("ModeManager: Stopped menu mode.")
        # Start Spotify
        if self.spotify_manager:
            self.spotify_manager.start_mode()
            self.logger.info("ModeManager: Spotify mode started.")
        else:
            self.logger.error("ModeManager: spotify_manager is not set.")

    def enter_fm4(self, event):
        self.logger.info("ModeManager: Entering FM4 mode.")

        # Stop clock
        if self.clock:
            self.clock.stop()
            self.logger.info("ModeManager: Clock stopped.")
        else:
            self.logger.error("ModeManager: Clock instance is not set.")

        # Stop menu mode if active
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
            self.logger.info("ModeManager: Stopped menu mode.")

        # Delegate screen handling to ScreenManager
        if self.screen_manager:
            self.screen_manager.set_current_screen("playback")  # Activates FM4 playback screen
            self.logger.info("ModeManager: ScreenManager handled FM4 screen activation.")
        else:
            self.logger.error("ModeManager: ScreenManager is not set. Cannot activate FM4 screen.")


    def enter_modern(self, event):
        self.logger.info("ModeManager: Entering Modern mode.")

        # Stop clock
        if self.clock:
            self.clock.stop()
            self.logger.info("ModeManager: Clock stopped.")
        else:
            self.logger.error("ModeManager: Clock instance is not set.")

        # Stop menu mode if active
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
            self.logger.info("ModeManager: Stopped menu mode.")

        # Delegate screen handling to ScreenManager
        if self.screen_manager:
            self.screen_manager.set_current_screen("detailed_playback")  # Activates Modern screen
            self.logger.info("ModeManager: ScreenManager handled Modern screen activation.")
        else:
            self.logger.error("ModeManager: ScreenManager is not set. Cannot activate Modern screen.")


    # Adjusted methods to avoid conflicts with triggers
    def switch_to_library_mode(self, start_uri=None):
        self.logger.info(f"ModeManager: Switching to Library mode with start_uri: {start_uri}")
        self.machine.trigger('to_library', start_uri=start_uri)

    def switch_to_usb_library_mode(self, start_uri=None):
        self.logger.info(f"ModeManager: Switching to USB Library mode with start_uri: {start_uri}")
        self.machine.trigger('to_usb_library', start_uri=start_uri)

    def suppress_state_change(self):
        """Suppress state changes temporarily."""
        with self.lock:
            self.suppress_state_changes = True
            self.logger.debug("ModeManager: State changes are now suppressed.")

    def allow_state_change(self):
        """Allow state changes."""
        with self.lock:
            self.suppress_state_changes = False
            self.logger.debug("ModeManager: State changes are now allowed.")

    def is_state_change_suppressed(self):
        return self.suppress_state_changes

    def process_state_change(self, sender, state, **kwargs):
        """Process playback state changes from Volumio."""
        with self.lock:
            if self.suppress_state_changes:
                self.logger.debug("ModeManager: State change suppressed.")
                return

            # Extract current status and service
            status = state.get("status", "").lower()
            service = state.get("service", "").lower()
            self.logger.debug(f"ModeManager: Processing state change, Volumio status: {status}, service: {service}")

            # Update status tracking
            self.previous_status = self.current_status
            self.current_status = status
            self.logger.debug(f"ModeManager: Updated current_status from {self.previous_status} to {self.current_status}")

            # Delegate screen activation to ScreenManager
            if self.screen_manager:
                self.screen_manager.handle_state_change(status, service)
            else:
                self.logger.error("ModeManager: ScreenManager is not set.")

            # Handle transitions for specific status changes
            if self.previous_status == "play" and self.current_status == "stop":
                self._handle_track_change()
            elif self.previous_status == "stop" and self.current_status == "play":
                self._handle_track_resumed()

            # Handle global playback states
            self._handle_playback_states(status, service)

        self.logger.debug("ModeManager: Completed state change processing.")


    def _handle_track_change(self):
        """Handle logic for track change when transitioning from play to stop."""
        self.is_track_changing = True
        self.track_change_in_progress = True
        self.logger.debug("ModeManager: Possible track change detected.")

        if not self.pause_stop_timer:
            self.pause_stop_timer = threading.Timer(
                self.pause_stop_delay, self.switch_to_clock_if_still_stopped_or_paused
            )
            self.pause_stop_timer.start()
            self.logger.debug("ModeManager: Started stop verification timer.")

    def _handle_track_resumed(self):
        """Handle logic for track resumed when transitioning from stop to play."""
        self.is_track_changing = False
        self.track_change_in_progress = False
        self.logger.debug("ModeManager: Track change completed.")

        if self.pause_stop_timer:
            self.pause_stop_timer.cancel()
            self.logger.debug("ModeManager: Canceled stop verification timer.")
            self.pause_stop_timer = None

    def _handle_playback_states(self, status, service):
        """Handle general playback states like play, pause, or stop."""
        if status == "play":
            self._cancel_pause_timer()
            self.is_track_changing = False
            self.track_change_in_progress = False

            if service == "webradio":
                self.to_radioplayback()
            else:
                self.to_playback()

        elif status == "pause":
            self._start_pause_timer()

        elif status == "stop" and not self.track_change_in_progress:
            self.logger.debug("ModeManager: Playback stopped; switching to clock mode.")
            self._cancel_pause_timer()
            self.to_clock()

    def _cancel_pause_timer(self):
        """Cancel the pause/stop timer if running."""
        if self.pause_stop_timer:
            self.pause_stop_timer.cancel()
            self.logger.debug("ModeManager: Canceled existing pause/stop timer.")
            self.pause_stop_timer = None

    def _start_pause_timer(self):
        """Start a timer to switch to clock mode after a delay if not already running."""
        if not self.pause_stop_timer:
            self.pause_stop_timer = threading.Timer(
                self.pause_stop_delay, self.switch_to_clock_if_still_stopped_or_paused
            )
            self.pause_stop_timer.start()
            self.logger.debug("ModeManager: Started pause timer.")
        else:
            self.logger.debug("ModeManager: Pause timer is already running.")


    def switch_to_clock_if_still_stopped_or_paused(self):
        """Switch to clock mode if the state is still paused or stopped after a delay."""
        with self.lock:
            self.logger.debug(f"ModeManager: Timer expired, current_status is '{self.current_status}'")
            if self.current_status in ["pause", "stop"]:
                # Only switch to clock if it is still in stop or pause
                self.to_clock()
                self.logger.debug("ModeManager: Switched to clock mode after delay.")
            else:
                # If playback resumed or state changed, do not switch to clock
                self.logger.debug("ModeManager: Playback resumed or status changed; staying in current mode.")
            self.pause_stop_timer = None


    def trigger(self, event_name, **kwargs):
        """Trigger a state transition using the state machine."""
        self.machine.trigger(event_name, **kwargs)

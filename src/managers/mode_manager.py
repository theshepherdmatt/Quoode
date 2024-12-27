# src/managers/mode_manager.py

import logging
from transitions import Machine
import threading
import os
import json

class ModeManager:
    states = [
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
        # Initialize logger FIRST
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)  # Set to DEBUG level for detailed logs
        self.logger.debug("ModeManager initializing...")

        self.display_manager = display_manager
        self.clock = clock
        self.moode_listener = moode_listener
        self.preference_file_path = os.path.join(os.path.dirname(__file__), preference_file_path)

        # Load persisted preferences after logger is ready
        self.current_display_mode = self._load_screen_preference()

        # Managers will be set later
        self.original_screen = None
        self.menu_manager = None
        self.playlist_manager = None
        self.radio_manager = None
        self.webradio_screen = None
        self.library_manager = None
        self.usb_library_manager = None
        self.modern_screen = None

        self.logger.debug("ModeManager: Initializing state machine...")

        # Initialize state machine
        self.machine = Machine(
            model=self,
            states=ModeManager.states,
            initial='clock',
            send_event=True
        )

        # Define transitions
        self.machine.add_transition(trigger='to_playback', source='*', dest='playback')
        self.machine.add_transition(trigger='to_webradio', source='*', dest='webradio')
        self.machine.add_transition(trigger='to_menu', source='*', dest='menu')
        self.machine.add_transition(trigger='to_radio', source='*', dest='radio')
        self.machine.add_transition(trigger='to_playlists', source='*', dest='playlists')
        self.machine.add_transition(trigger='to_library', source='*', dest='library')
        self.machine.add_transition(trigger='to_usb_library', source='*', dest='usblibrary')
        self.machine.add_transition(trigger='to_clock', source='*', dest='clock')
        self.machine.add_transition(trigger='to_original', source='*', dest='original')
        self.machine.add_transition(trigger='to_modern', source='*', dest='modern')

        # Callback handling
        self.on_mode_change_callbacks = []
        self.lock = threading.Lock()  # Added lock for thread safety

        # Suppression mechanism
        self.suppress_state_changes = False  # Added suppression flag

        # Connect to moodeListener's state_changed signal
        if self.moode_listener is not None:
            self.moode_listener.state_changed.connect(self.process_state_change)
            self.logger.debug("ModeManager: Connected to moodeListener's state_changed signal.")
        else:
            self.logger.warning("ModeManager: moodeListener is None, cannot connect to state_changed signal.")

        # Explicitly call enter_clock to initialize the clock mode
        self.enter_clock(None)

        # Initialize state tracking variables
        self.is_track_changing = False
        self.track_change_in_progress = False
        self.current_status = None
        self.previous_status = None
        self.pause_stop_timer = None
        self.pause_stop_delay = 0.5  # Delay in seconds before switching to clock mode

    def _load_screen_preference(self):
        """Load the display mode preference from JSON file if available."""
        if os.path.exists(self.preference_file_path):
            try:
                with open(self.preference_file_path, "r") as f:
                    data = json.load(f)
                    mode = data.get("display_mode", "original")
                    self.logger.info(f"ModeManager: Loaded display mode preference: {mode}")
                    return mode
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"ModeManager: Failed to load screen preference, using default. Error: {e}")
        else:
            self.logger.info("ModeManager: No preference file found, using default display mode 'original'.")
        return "original"

    def _save_screen_preference(self):
        """Save the current display mode preference to JSON file."""
        data = {"display_mode": self.current_display_mode}
        try:
            with open(self.preference_file_path, "w") as f:
                json.dump(data, f)
            self.logger.info(f"ModeManager: Saved display mode preference: {self.current_display_mode}")
        except IOError as e:
            self.logger.error(f"ModeManager: Failed to save screen preference. Error: {e}")

    def set_display_mode(self, mode_name):
        """Set the current display mode to either 'original' or 'modern', and persist it."""
        if mode_name in ['original', 'modern']:
            self.current_display_mode = mode_name
            self.logger.info(f"ModeManager: Display mode set to {mode_name}.")
            self._save_screen_preference()  # Persist to file
        else:
            self.logger.warning(f"ModeManager: Attempted to set unknown display mode: {mode_name}")


    def get_active_manager(self):
        """Return the name of the currently active manager."""
        if self.original_screen and self.original_screen.is_active:
            return 'original_screen'
        elif self.webradio_screen and self.webradio_screen.is_active:
            return 'webradio_screen'
        # Add other managers as needed
        return None


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

    def enter_clock(self, event):
        self.logger.info("ModeManager: Entering clock mode.")
        
        # Stop other active modes except playback and clock
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
            self.logger.info("ModeManager: Stopped menu mode.")
        if self.radio_manager and self.radio_manager.is_active:
            self.radio_manager.stop_mode()
            self.logger.info("ModeManager: Stopped radio mode.")
        if self.playlist_manager and self.playlist_manager.is_active:
            self.playlist_manager.stop_mode()
            self.logger.info("ModeManager: Stopped playlist mode.")
        if self.library_manager and self.library_manager.is_active:
            self.library_manager.stop_mode()
            self.logger.info("ModeManager: Stopped Library mode.")
        if self.usb_library_manager and self.usb_library_manager.is_active:
            self.usb_library_manager.stop_mode()
            self.logger.info("ModeManager: Stopped USBLibrary mode.")
        if self.modern_screen and self.modern_screen.is_active:
            self.modern_screen.stop_mode()
            self.logger.info("ModeManager: Stopped Modern Screen mode.")

        # Ensure playback manager remains active if it is already playing or paused
        if self.original_screen and self.original_screen.is_active:
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

        # Start the chosen display mode’s screen
        if self.current_display_mode == 'modern':
            if self.modern_screen:
                self.modern_screen.start_mode()
                self.logger.info("ModeManager: ModernScreen mode started.")
            else:
                self.logger.error("ModeManager: modern_screen is not set.")
        else:
            # Default to original if not modern
            if self.original_screen:
                self.original_screen.start_mode()
                self.logger.info("ModeManager: OriginalScreen mode started.")
            else:
                self.logger.error("ModeManager: original_screen is not set.")



    def enter_webradio_screen(self, event):
        self.logger.info("ModeManager: Entering webradio_screen mode.")
        # Stop clock
        if self.clock:
            self.clock.stop()
            self.logger.info("ModeManager: Clock stopped.")
        else:
            self.logger.error("ModeManager: Clock instance is not set.")
        
        # Stop PlaybackManager if it's active
        if self.original_screen and self.original_screen.is_active:
            self.original_screen.stop_mode()
            self.logger.info("ModeManager: Stopped playback mode.")
        
        # Start webradio_screen display
        if self.webradio_screen:
            self.webradio_screen.start_mode()
            self.logger.info("ModeManager: WebRadioScreen mode started.")
        else:
            self.logger.error("ModeManager: webradio_screen is not set.")


    def enter_menu(self, event):
        self.logger.info("ModeManager: Entering menu mode.")
        # Stop clock, playback, and WebRadioScreen
        if self.clock:
            self.clock.stop()
            self.logger.info("ModeManager: Clock stopped.")
        else:
            self.logger.error("ModeManager: Clock instance is not set.")
        
        if self.original_screen and self.original_screen.is_active:
            self.original_screen.stop_mode()
            self.logger.info("ModeManager: Stopped playback mode.")
        
        if self.webradio_screen and self.webradio_screen.is_active:
            self.webradio_screen.stop_mode()
            self.logger.info("ModeManager: Stopped WebRadioScreen mode.")
        
        # Start menu
        if self.menu_manager:
            self.menu_manager.start_mode()
            self.logger.info("ModeManager: Menu mode started.")
        else:
            self.logger.error("ModeManager: menu_manager is not set.")


    def enter_radio_manager(self, event):
        self.logger.info("ModeManager: Entering radio_manager mode.")
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
            self.logger.info("ModeManager: Stopped radio_manager mode.")
        # Start radio_manager
        if self.radio_manager:
            self.radio_manager.start_mode()
            self.logger.info("ModeManager: radio_manager mode started.")
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


    def enter_original(self, event):
        self.logger.info("ModeManager: Entering Original mode.")

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

        # Start OriginalScreen
        if self.original_screen:
            self.original_screen.start_mode()
            self.logger.info("ModeManager: OriginalScreen mode started.")
        else:
            self.logger.error("ModeManager: original_screen is not set.")


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

        # Start ModernScreen
        if self.modern_screen:
            self.modern_screen.start_mode()
            self.logger.info("ModeManager: ModernScreen mode started.")
        else:
            self.logger.error("ModeManager: modern_screen is not set.")

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
        with self.lock:
            if self.suppress_state_changes:
                self.logger.debug("ModeManager: State change suppressed.")
                return

            # Log the entire state for debugging
            self.logger.debug(f"ModeManager: Received state: {state}")

            # Extract 'status' from state
            status_dict = state.get("status", {})
            service_list = state.get("service", [])

            # Extract the 'state' from status_dict
            status = status_dict.get("state", "").lower()
            if not isinstance(status, str):
                self.logger.error("ModeManager: 'state' is missing or not a string.")
                return

            # Determine the active service
            active_service = 'default'  # Fallback if no service is active
            for service in service_list:
                outputname = service.get("outputname", "")
                outputenabled = service.get("outputenabled", "0")
                self.logger.debug(f"ModeManager: Service - Output Name: {outputname}, Enabled: {outputenabled}")
                if outputenabled == "1" and outputname:
                    if isinstance(outputname, str):
                        active_service = outputname.lower()
                        break  # Assume only one active service
                    else:
                        self.logger.warning(f"ModeManager: 'outputname' is not a string: {outputname}")
                        active_service = 'default'

            self.logger.debug(f"ModeManager: Processing state change, moode status: {status}, service: {active_service}")

            # Update status tracking
            self.previous_status = self.current_status
            self.current_status = status
            self.logger.debug(f"ModeManager: Updated current_status from {self.previous_status} to {self.current_status}")

            # Handle transitions for specific status changes
            if self.previous_status == "play" and self.current_status == "stop":
                self._handle_track_change()
            elif self.previous_status == "stop" and self.current_status == "play":
                self._handle_track_resumed()

            # Handle global playback states
            self._handle_playback_states(status, active_service)

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
                self.to_webradio()
            else:
                if self.current_display_mode == 'modern':
                    self.to_modern()
                else:
                    self.to_original()

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

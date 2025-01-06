# src/managers/mode_manager.py

import logging
import os
import json
import threading
from transitions import Machine

class ModeManager:
    """
    Manage the Quoode state machine, controlling transitions between:
      - boot (loading), clock, playback, menu, clockmenu, etc.
      - 'original' vs 'modern' screens for playback.

    Also stores a config dictionary (`self.config`) that can hold user
    preferences such as 'clock_font_key' or 'show_seconds'.
    """

    states = [
        {'name': 'boot',       'on_enter': 'enter_boot'},
        {'name': 'clock',      'on_enter': 'enter_clock'},
        {'name': 'playback',   'on_enter': 'enter_playback'},
        {'name': 'menu',       'on_enter': 'enter_menu'},
        {'name': 'clockmenu',  'on_enter': 'enter_clockmenu'},
        {'name': 'original',   'on_enter': 'enter_original'},
        {'name': 'modern',     'on_enter': 'enter_modern'},
        {'name': 'screensaver', 'on_enter': 'enter_screensaver'}
    ]

    def __init__(
        self,
        display_manager,
        clock,
        moode_listener,
        preference_file_path="../preference.json",
        config=None
    ):
        """
        :param display_manager: DisplayManager instance
        :param clock: Clock screen (home screen)
        :param moode_listener: MoodeListener (MPD link)
        :param preference_file_path: JSON file to store display_mode and/or other preference
        :param config: (optional) a merged config dict loaded from YAML + user preference
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)
        self.logger.debug("ModeManager initializing...")

        self.display_manager = display_manager
        self.clock = clock
        self.moode_listener = moode_listener

        # Store config dictionary (contains user settings like show_seconds, clock_font_key, etc.)
        self.config = config or {}

        # Preferences file path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.preference_file_path = os.path.join(script_dir, preference_file_path)

        # Load or fallback for display mode preference
        self.current_display_mode = self._load_screen_preference()

        # References to other managers/screens
        self.original_screen = None
        self.modern_screen = None
        self.menu_manager = None
        self.clock_menu = None
        self.snakescreensaver = None

        # Set up the transitions state machine
        self.logger.debug("ModeManager: Setting up state machine with 'boot' as the initial state.")
        self.machine = Machine(
            model=self,
            states=ModeManager.states,
            initial='boot',
            send_event=True
        )

        # Define transitions
        self.machine.add_transition('to_clock',       source='*', dest='clock')
        self.machine.add_transition('to_playback',    source='*', dest='playback')
        self.machine.add_transition('to_menu',        source='*', dest='menu')
        self.machine.add_transition('to_clockmenu',   source='*', dest='clockmenu')
        self.machine.add_transition('to_original',    source='*', dest='original')
        self.machine.add_transition('to_modern',      source='*', dest='modern')
        self.machine.add_transition('to_screensaver', source='*', dest='screensaver')

        # A lock for thread safety
        self.suppress_state_changes = False
        self.lock = threading.Lock()

        # Connect MoodeListener signals if available
        if self.moode_listener is not None:
            self.moode_listener.state_changed.connect(self.process_state_change)
            self.logger.debug("ModeManager: Linked to moode_listener.state_changed.")
        else:
            self.logger.warning("ModeManager: moode_listener is None; not linking state_changed.")

        # Tracking playback statuses
        self.is_track_changing = False
        self.track_change_in_progress = False
        self.current_status = None
        self.previous_status = None

        # Timer for pause/stop transitions
        self.pause_stop_timer = None
        self.pause_stop_delay = 0.5  # half-second delay for switching back to clock if paused/stopped

    # -----------------------------------------------------------------
    #  Boot State
    # -----------------------------------------------------------------
    def enter_boot(self, event):
        """
        The 'boot' (loading) state.
        The main script will call self.to_clock() once everything is loaded.
        """
        self.logger.info("ModeManager: Entering 'boot' state. Waiting for system load...")

    # -----------------------------------------------------------------
    #  Preferences: loading & saving
    # -----------------------------------------------------------------
    def _load_screen_preference(self):
        """
        Load 'display_mode' (e.g. 'original' or 'modern') from JSON.
        Return 'original' if file missing or broken.
        """
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
            self.logger.info(f"No preference file found at {self.preference_file_path}; defaulting to 'original'.")

        return "original"

    def _save_screen_preference(self):
        """
        Save the current display mode (original/modern) to the JSON file.
        This is a minimal example. If you want to store other clock settings
        like show_seconds or clock_font_key, you can do that here or in save_preferences().
        """
        data = {
            "display_mode": self.current_display_mode,
            # You could also store "clock_font_key", "show_seconds", etc. here:
            # "clock_font_key": self.config.get("clock_font_key", "clock_digital"),
            # "show_seconds": self.config.get("show_seconds", False),
        }
        try:
            with open(self.preference_file_path, "w") as f:
                json.dump(data, f, indent=2)
            self.logger.info(f"Saved display mode preference: {self.current_display_mode}")
        except IOError as e:
            self.logger.error(f"Failed to save screen preference: {e}")

    def set_display_mode(self, mode_name):
        """
        Switch the user preference between 'original' or 'modern'.
        Then immediately save to the preference file.
        """
        if mode_name in ['original', 'modern']:
            self.current_display_mode = mode_name
            self.logger.info(f"ModeManager: Display mode set to '{mode_name}'.")
            self._save_screen_preference()
        else:
            self.logger.warning(f"ModeManager: Unknown display mode '{mode_name}'")

    def save_preferences(self):
        """
        Writes out the entire 'self.config' dict to JSON,
        so user toggles for clock menu (show_seconds, font_key, etc.) are preserved next time.
        """
        if not self.preference_file_path:
            return

        try:
            # Attempt to load existing data
            if os.path.exists(self.preference_file_path):
                with open(self.preference_file_path, "r") as f:
                    data = {}
                    try:
                        data = json.load(f)
                    except (json.JSONDecodeError, IOError):
                        pass
            else:
                data = {}

            # Keep the existing 'display_mode' or override
            data["display_mode"] = self.current_display_mode

            # Copy other user preferences from self.config
            # e.g. clock_font_key, show_seconds, show_date, etc.
            if "clock_font_key" in self.config:
                data["clock_font_key"] = self.config["clock_font_key"]
            if "show_seconds" in self.config:
                data["show_seconds"] = self.config["show_seconds"]
            if "show_date" in self.config:
                data["show_date"] = self.config["show_date"]

            # Write back to file
            with open(self.preference_file_path, "w") as f:
                json.dump(data, f, indent=2)
            self.logger.info(f"ModeManager: Successfully saved user prefs to {self.preference_file_path}.")
        except IOError as e:
            self.logger.warning(f"ModeManager: Could not write to {self.preference_file_path}. Error: {e}")

    # -----------------------------------------------------------------
    #  Setting references
    # -----------------------------------------------------------------
    def set_original_screen(self, original_screen):
        """Assign the OriginalScreen instance."""
        self.original_screen = original_screen

    def set_modern_screen(self, modern_screen):
        """Assign the ModernScreen instance."""
        self.modern_screen = modern_screen

    def set_menu_manager(self, menu_manager):
        """Assign the main MenuManager instance."""
        self.menu_manager = menu_manager

    def set_clock_menu(self, clock_menu):
        """Assign the specialized ClockMenu manager instance."""
        self.clock_menu = clock_menu

    def set_snakescreensaver(self, snakescreensaver):
        """Assign the specialized ClockMenu manager instance."""
        self.snakescreensaver = snakescreensaver

    # -----------------------------------------------------------------
    #  Helper
    # -----------------------------------------------------------------
    def get_mode(self):
        """
        Return the current state name (e.g. 'clock', 'menu', 'clockmenu', etc.).
        """
        return self.state

    # -----------------------------------------------------------------
    #  State Entry Methods
    # -----------------------------------------------------------------
    def enter_clock(self, event):
        """
        Called when the state machine transitions to 'clock'.
        Stop all other screens/managers and start the clock.
        """
        self.logger.info("ModeManager: Entering clock mode.")

        # Stop other managers
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
        if self.clock_menu and self.clock_menu.is_active:
            self.clock_menu.stop_mode()
        if self.modern_screen and self.modern_screen.is_active:
            self.modern_screen.stop_mode()
        if self.original_screen and self.original_screen.is_active:
            self.logger.debug("Retaining original_screen if actively playing.")

        # Start the clock
        if self.clock:
            self.clock.config = self.config  
            self.clock.start()
        else:
            self.logger.error("ModeManager: No Clock instance to start.")

    def enter_playback(self, event):
        """
        Called when we go to 'playback'.
        We stop the clock and pick original vs. modern screen based on user preference.
        """
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

    def enter_menu(self, event):
        """
        Called when we go to 'menu'.
        We stop the clock and start the main MenuManager.
        """
        self.logger.info("ModeManager: Entering menu mode.")
        if self.clock:
            self.clock.stop()
        if self.original_screen and self.original_screen.is_active:
            self.original_screen.stop_mode()
        if self.modern_screen and self.modern_screen.is_active:
            self.modern_screen.stop_mode()
        if self.clock_menu and self.clock_menu.is_active:
            self.clock_menu.stop_mode()

        if self.menu_manager:
            self.menu_manager.start_mode()
        else:
            self.logger.error("ModeManager: menu_manager is not set.")

    def enter_clockmenu(self, event):
        """
        Called when we go to 'clockmenu'.
        This is a specialized sub-menu for clock settings (fonts, show_seconds, etc.).
        """
        self.logger.info("ModeManager: Entering clockmenu mode.")
        if self.clock:
            self.clock.stop()
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
        if self.modern_screen and self.modern_screen.is_active:
            self.modern_screen.stop_mode()
        if self.original_screen and self.original_screen.is_active:
            self.original_screen.stop_mode()

        if self.clock_menu:
            self.clock_menu.start_mode()
        else:
            self.logger.error("ModeManager: clock_menu is not set.")

    def enter_original(self, event):
        """
        Called when we go to 'original' mode,
        which typically means the user is playing audio on the original screen.
        """
        self.logger.info("ModeManager: Entering Original mode.")
        if self.clock:
            self.clock.stop()
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
        if self.clock_menu and self.clock_menu.is_active:
            self.clock_menu.stop_mode()

        if self.original_screen:
            self.original_screen.start_mode()
        else:
            self.logger.error("ModeManager: original_screen is not set.")

    def enter_modern(self, event):
        """
        Called when we go to 'modern' mode,
        which typically means the user is playing audio on the modern screen.
        """
        self.logger.info("ModeManager: Entering Modern mode.")
        if self.clock:
            self.clock.stop()
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
        if self.clock_menu and self.clock_menu.is_active:
            self.clock_menu.stop_mode()

        if self.modern_screen:
            self.modern_screen.start_mode()
        else:
            self.logger.error("ModeManager: modern_screen is not set.")


    def enter_screensaver(self, event):
        self.logger.info("ModeManager: Entering screensaver mode.")

        # Stop clock or other modes
        if self.clock: 
            self.clock.stop()
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
        # etc. depending on your system

        # Create and start if not existing
        if not hasattr(self, 'snakescreensaver'):
            self.snake_screensaver = SnakeScreensaver(self.display_manager, update_interval=0.04)
        self.snake_screensaver.start_screensaver()

    def exit_screensaver(self):
        self.logger.info("ModeManager: Exiting screensaver mode.")
        if self.snake_screensaver:
            self.snake_screensaver.stop_screensaver()

        # Then transition back to clock or whichever mode you want:
        self.to_clock()

    # -----------------------------------------------------------------
    #  Suppression logic (optional)
    # -----------------------------------------------------------------
    def suppress_state_change(self):
        """
        Temporarily ignore state transitions if needed 
        (e.g., while changing tracks to avoid flickering).
        """
        with self.lock:
            self.suppress_state_changes = True
            self.logger.debug("ModeManager: State changes suppressed.")

    def allow_state_change(self):
        """Re-allow normal state transitions."""
        with self.lock:
            self.suppress_state_changes = False
            self.logger.debug("ModeManager: State changes allowed.")

    def is_state_change_suppressed(self):
        return self.suppress_state_changes

    # -----------------------------------------------------------------
    #  Processing MPD updates
    # -----------------------------------------------------------------
    def process_state_change(self, sender, state, **kwargs):
        """
        Called by moode_listener when there's an MPD state update (e.g. play, pause, stop).
        """
        with self.lock:
            if self.suppress_state_changes:
                self.logger.debug("ModeManager: State change is suppressed.")
                return

            self.logger.debug(f"ModeManager: process_state_change -> {state}")
            status_dict = state.get('status', {})
            new_status = status_dict.get('state', '').lower()  # "play", "pause", or "stop"

            self.previous_status = self.current_status
            self.current_status = new_status

            # If we were playing and now we've stopped => track might have ended
            if self.previous_status == "play" and self.current_status == "stop":
                self._handle_track_change()
            # If we were stopped and now we're playing => track resumed
            elif self.previous_status == "stop" and self.current_status == "play":
                self._handle_track_resumed()

            self._handle_playback_states(new_status)

    def _handle_track_change(self):
        """
        Possibly the transition from 'play' to 'stop' indicates track end.
        We'll start a short timer to see if we remain in 'stop' or if we jump to a new track.
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
        """
        If a new track started playing, cancel the pause_stop_timer if it was running.
        """
        self.is_track_changing = False
        self.track_change_in_progress = False
        self.logger.debug("ModeManager: Track resumed from 'stop' to 'play'.")

        if self.pause_stop_timer:
            self.pause_stop_timer.cancel()
            self.pause_stop_timer = None
            self.logger.debug("ModeManager: Canceled stop verification timer.")

    def _handle_playback_states(self, status):
        """
        Automatically switch to original or modern screen on 'play', 
        or revert to clock on 'stop' (after a short delay if no new track).
        """
        if status == "play":
            self._cancel_pause_timer()
            self.is_track_changing = False
            self.track_change_in_progress = False

            # Switch to whichever screen the user last used (original or modern)
            if self.current_display_mode == 'modern':
                self.to_modern()
            else:
                self.to_original()

        elif status == "pause":
            self._start_pause_timer()

        elif status == "stop" and not self.track_change_in_progress:
            self.logger.debug("ModeManager: 'stop' with no track change => going to clock.")
            self._cancel_pause_timer()
            self.to_clock()

    def _cancel_pause_timer(self):
        if self.pause_stop_timer:
            self.pause_stop_timer.cancel()
            self.pause_stop_timer = None
            self.logger.debug("ModeManager: Canceled pause/stop timer.")

    def _start_pause_timer(self):
        """
        If the user paused, we might revert to the clock after a short delay 
        if they don't resume playing quickly.
        """
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
        """
        If we're still paused or stopped after the delay, go to clock.
        """
        with self.lock:
            if self.current_status in ["pause", "stop"]:
                self.to_clock()
                self.logger.debug("ModeManager: Switched to clock after timer.")
            else:
                self.logger.debug("ModeManager: Playback resumed; staying in current mode.")
            self.pause_stop_timer = None

    # Expose transitions programmatically if desired
    def trigger(self, event_name, **kwargs):
        self.machine.trigger(event_name, **kwargs)



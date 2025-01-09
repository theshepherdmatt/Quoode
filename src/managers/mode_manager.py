import logging
import os
import json
import threading
from transitions import Machine


class ModeManager:
    """
    Manage the Quoode state machine, controlling transitions between:
      - boot (loading), clock, playback, menu, clockmenu, displaymenu, etc.
      - 'original' vs 'modern' screens for playback.
      - 'screensaver' for idle display.
    """

    states = [
        {'name': 'boot',         'on_enter': 'enter_boot'},
        {'name': 'clock',        'on_enter': 'enter_clock'},
        {'name': 'playback',     'on_enter': 'enter_playback'},
        {'name': 'menu',         'on_enter': 'enter_menu'},
        {'name': 'clockmenu',    'on_enter': 'enter_clockmenu'},
        {'name': 'displaymenu',  'on_enter': 'enter_displaymenu'}, 
        {'name': 'original',     'on_enter': 'enter_original'},
        {'name': 'modern',       'on_enter': 'enter_modern'},
        {'name': 'screensaver',  'on_enter': 'enter_screensaver'},
        {'name': 'screensavermenu', 'on_enter': 'enter_screensavermenu'},
        {'name': 'systeminfo',   'on_enter':     'enter_systeminfo'}
    ]

    def __init__(
        self,
        display_manager,
        clock,
        moode_listener,
        preference_file_path="../preference.json",
        config=None
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)
        self.logger.debug("ModeManager initializing...")

        self.display_manager = display_manager
        self.clock = clock
        self.moode_listener = moode_listener

        # Store config dictionary (includes user settings like show_seconds, etc.)
        self.config = config or {}

        # Preferences file path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.preference_file_path = os.path.join(script_dir, preference_file_path)

        # Load or fallback for display mode preference
        self.current_display_mode = self._load_screen_preference()

        # References to other managers/screens
        self.original_screen = None
        self.modern_screen = None
        self.system_info_screen = None
        self.menu_manager = None
        self.clock_menu = None
        self.display_menu = None  # <--- important
        self.screensaver = None
        self.screensaver_menu = None

        # State machine
        self.logger.debug("ModeManager: Setting up transitions with 'boot' as initial state.")
        self.machine = Machine(
            model=self,
            states=ModeManager.states,
            initial='boot',
            send_event=True
        )

        # Define transitions
        self.machine.add_transition('to_clock',         source='*', dest='clock')
        self.machine.add_transition('to_playback',      source='*', dest='playback')
        self.machine.add_transition('to_menu',          source='*', dest='menu')
        self.machine.add_transition('to_clockmenu',     source='*', dest='clockmenu')
        self.machine.add_transition('to_displaymenu',   source='*', dest='displaymenu')  # <--- important
        self.machine.add_transition('to_original',      source='*', dest='original')
        self.machine.add_transition('to_modern',        source='*', dest='modern')
        self.machine.add_transition('to_screensaver',   source='*', dest='screensaver')
        self.machine.add_transition('to_screensavermenu', source='*', dest='screensavermenu')
        self.machine.add_transition('to_systeminfo',     source='*',   dest='systeminfo')

        # Lock for thread safety
        self.suppress_state_changes = False
        self.lock = threading.Lock()

        # Connect MoodeListener signals if available
        if self.moode_listener is not None:
            self.moode_listener.state_changed.connect(self.process_state_change)
            self.logger.debug("ModeManager: Linked to moode_listener.state_changed.")
        else:
            self.logger.warning("ModeManager: moode_listener is None; not linking state_changed.")

        # Playback status tracking
        self.is_track_changing = False
        self.track_change_in_progress = False
        self.current_status = None
        self.previous_status = None

        # Timer for pause/stop transitions
        self.pause_stop_timer = None
        self.pause_stop_delay = 0.5  # half-second

        # Idle / screensaver logic (optional)
        self.idle_timer = None
        self.idle_timeout = self.config.get("screensaver_timeout", 360)

    # -----------------------------------------------------------------
    #  Boot State
    # -----------------------------------------------------------------
    def enter_boot(self, event):
        self.logger.info("ModeManager: Entering 'boot' state. Waiting for system load...")

    # -----------------------------------------------------------------
    #  Preferences: loading & saving
    # -----------------------------------------------------------------
    def _load_screen_preference(self):
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
        data = {
            "display_mode": self.current_display_mode
        }
        try:
            with open(self.preference_file_path, "w") as f:
                json.dump(data, f, indent=2)
            self.logger.info(f"Saved display mode preference: {self.current_display_mode}")
        except IOError as e:
            self.logger.error(f"Failed to save screen preference: {e}")

    def set_display_mode(self, mode_name):
        if mode_name in ['original', 'modern']:
            self.current_display_mode = mode_name
            self.logger.info(f"ModeManager: Display mode set to '{mode_name}'.")
            self._save_screen_preference()
        else:
            self.logger.warning(f"ModeManager: Unknown display mode '{mode_name}'")

    def save_preferences(self):
        if not self.preference_file_path:
            return
        try:
            if os.path.exists(self.preference_file_path):
                with open(self.preference_file_path, "r") as f:
                    data = {}
                    try:
                        data = json.load(f)
                    except (json.JSONDecodeError, IOError):
                        pass
            else:
                data = {}

            data["display_mode"] = self.current_display_mode

            for key in ("clock_font_key", "show_seconds", "show_date", "screensaver_enabled",
                        "screensaver_type", "screensaver_timeout", "oled_brightness", "display_mode",):
                if key in self.config:
                    data[key] = self.config[key]

            with open(self.preference_file_path, "w") as f:
                json.dump(data, f, indent=2)
            self.logger.info(f"ModeManager: Successfully saved user prefs to {self.preference_file_path}.")
        except IOError as e:
            self.logger.warning(f"ModeManager: Could not write to {self.preference_file_path}. Error: {e}")

    # -----------------------------------------------------------------
    #  Setting references
    # -----------------------------------------------------------------
    def set_original_screen(self, original_screen):
        self.original_screen = original_screen

    def set_modern_screen(self, modern_screen):
        self.modern_screen = modern_screen

    def set_system_info_screen(self, system_info_screen):
        self.system_info_screen = system_info_screen        

    def set_menu_manager(self, menu_manager):
        self.menu_manager = menu_manager

    def set_clock_menu(self, clock_menu):
        self.clock_menu = clock_menu

    def set_display_menu(self, display_menu):
        self.display_menu = display_menu

    def set_screensaver(self, screensaver):
        self.screensaver = screensaver

    def set_screensaver_menu(self, screensaver_menu):
        self.screensaver_menu = screensaver_menu


    # -----------------------------------------------------------------
    #  Helper
    # -----------------------------------------------------------------
    def get_mode(self):
        return self.state

    # -----------------------------------------------------------------
    #  State Entry Methods
    # -----------------------------------------------------------------
    def enter_clock(self, event):
        self.logger.info("ModeManager: Entering clock mode.")
        # stop other managers
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
        if self.clock_menu and self.clock_menu.is_active:
            self.clock_menu.stop_mode()
        if self.display_menu and self.display_menu.is_active:
            self.display_menu.stop_mode()
        if self.screensaver_menu and self.screensaver_menu.is_active:
            self.screensaver_menu.stop_mode()
        if self.system_info_screen and self.system_info_screen.is_active:
            self.system_info_screen.stop_mode()
        if self.modern_screen and self.modern_screen.is_active:
            self.modern_screen.stop_mode()
        if self.original_screen and self.original_screen.is_active:
            pass

        if self.screensaver:
            self.screensaver.stop_screensaver()

        # start digital clock
        if self.clock:
            self.clock.config = self.config
            self.clock.start()

            self.reset_idle_timer()
            
        else:
            self.logger.error("ModeManager: No Clock instance to start.")

    def enter_playback(self, event):
        self.logger.info("ModeManager: Entering playback mode.")
        if self.clock:
            self.clock.stop()

        if self.screensaver:
            self.screensaver.stop_screensaver()

        if self.current_display_mode == 'modern':
            if self.modern_screen:
                self.modern_screen.start_mode()
            else:
                self.logger.error("ModeManager: modern_screen not set.")
        else:
            if self.original_screen:
                self.original_screen.start_mode()

            else:
                self.logger.error("ModeManager: original_screen not set.")

            self.reset_idle_timer()

    def enter_menu(self, event):
        self.logger.info("ModeManager: Entering menu mode.")
        if self.clock:
            self.clock.stop()
        if self.original_screen and self.original_screen.is_active:
            self.original_screen.stop_mode()
        if self.modern_screen and self.modern_screen.is_active:
            self.modern_screen.stop_mode()
        if self.system_info_screen and self.system_info_screen.is_active:
            self.system_info_screen.stop_mode()
        if self.clock_menu and self.clock_menu.is_active:
            self.clock_menu.stop_mode()
        if self.display_menu and self.display_menu.is_active:
            self.display_menu.stop_mode()
        if self.screensaver_menu and self.screensaver_menu.is_active:
            self.screensaver_menu.stop_mode()

        if self.screensaver:
            self.screensaver.stop_screensaver()

        if self.menu_manager:
            self.menu_manager.start_mode()

            self.reset_idle_timer()

        else:
            self.logger.error("ModeManager: menu_manager is not set.")

        self.reset_idle_timer()

    def enter_clockmenu(self, event):
        self.logger.info("ModeManager: Entering clockmenu mode.")
        if self.clock:
            self.clock.stop()
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
        if self.modern_screen and self.modern_screen.is_active:
            self.modern_screen.stop_mode()
        if self.system_info_screen and self.system_info_screen.is_active:
            self.system_info_screen.stop_mode()
        if self.original_screen and self.original_screen.is_active:
            self.original_screen.stop_mode()
        if self.display_menu and self.display_menu.is_active:
            self.display_menu.stop_mode()

        if self.screensaver:
            self.screensaver.stop_screensaver()

        if self.clock_menu:
            self.clock_menu.start_mode()
        else:
            self.logger.error("ModeManager: clock_menu is not set.")

        self.reset_idle_timer()

    def enter_displaymenu(self, event):
        """
        Called when the state machine transitions to 'displaymenu'.
        We stop other screens if necessary, then start our DisplayMenu.
        """
        self.logger.info("ModeManager: Entering displaymenu state.")

        # Stop the clock if running
        if self.clock:
            self.clock.stop()

        # Stop any other menus or screens
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
        if self.clock_menu and self.clock_menu.is_active:
            self.clock_menu.stop_mode()
        if self.screensaver_menu and self.screensaver_menu.is_active:
            self.screensaver_menu.stop_mode()
        if self.modern_screen and self.modern_screen.is_active:
            self.modern_screen.stop_mode()
        if self.system_info_screen and self.system_info_screen.is_active:
            self.system_info_screen.stop_mode()
        if self.original_screen and self.original_screen.is_active:
            self.original_screen.stop_mode()

        # Stop screensaver if running
        if self.screensaver:
            self.screensaver.stop_screensaver()

        # Finally, start the display menu if it exists
        if self.display_menu:
            self.display_menu.start_mode()
        else:
            self.logger.warning("ModeManager: No display_menu object is set.")

        self.reset_idle_timer()

    def enter_screensavermenu(self, event):
        self.logger.info("ModeManager: Entering screensavermenu state.")

        if self.clock:
            self.clock.stop()
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
        if self.clock_menu and self.clock_menu.is_active:
            self.clock_menu.stop_mode()
        if self.display_menu and self.display_menu.is_active:
            self.display_menu.stop_mode()
        if self.original_screen and self.original_screen.is_active:
            self.original_screen.stop_mode()
        if self.modern_screen and self.modern_screen.is_active:
            self.modern_screen.stop_mode()
        if self.system_info_screen and self.system_info_screen.is_active:
            self.system_info_screen.stop_mode()

        if self.screensaver:
            self.screensaver.stop_screensaver()

        if self.screensaver_menu:
            self.screensaver_menu.start_mode()
        else:
            self.logger.warning("ModeManager: No screensaver_menu object is set.")

        self.reset_idle_timer()

    def enter_original(self, event):
        self.logger.info("ModeManager: Entering Original mode.")
        if self.clock:
            self.clock.stop()
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
        if self.clock_menu and self.clock_menu.is_active:
            self.clock_menu.stop_mode()
        if self.display_menu and self.display_menu.is_active:
            self.display_menu.stop_mode()
        if self.screensaver_menu and self.screensaver_menu.is_active:
            self.screensaver_menu.stop_mode()

        if self.screensaver:
            self.screensaver.stop_screensaver()

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
        if self.clock_menu and self.clock_menu.is_active:
            self.clock_menu.stop_mode()
        if self.display_menu and self.display_menu.is_active:
            self.display_menu.stop_mode()
        if self.screensaver_menu and self.screensaver_menu.is_active:
            self.screensaver_menu.stop_mode()

        if self.screensaver:
            self.screensaver.stop_screensaver()

        if self.modern_screen:
            self.modern_screen.start_mode()
        else:
            self.logger.error("ModeManager: modern_screen is not set.")

    def enter_systeminfo(self, event):
        self.logger.info("ModeManager: Entering System Info mode.")
        if self.clock:
            self.clock.stop()
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
        if self.clock_menu and self.clock_menu.is_active:
            self.clock_menu.stop_mode()
        if self.display_menu and self.display_menu.is_active:
            self.display_menu.stop_mode()
        if self.original_screen and self.original_screen.is_active:
            self.original_screen.stop_mode()
        if self.modern_screen and self.modern_screen.is_active:
            self.modern_screen.stop_mode()
        if self.screensaver_menu and self.screensaver_menu.is_active:
            self.screensaver_menu.stop_mode()

        if self.screensaver:
            self.screensaver.stop_screensaver()

        if self.system_info_screen:
            self.system_info_screen.start_mode()
        else:
            self.logger.error("ModeManager: system_info_screen is not set.")

        self.reset_idle_timer()

    def enter_screensaver(self, event):
        self.logger.info("ModeManager: Entering screensaver mode.")

        if self.clock:
            self.clock.stop()
        if self.menu_manager and self.menu_manager.is_active:
            self.menu_manager.stop_mode()
        if self.clock_menu and self.clock_menu.is_active:
            self.clock_menu.stop_mode()
        if self.display_menu and self.display_menu.is_active:
            self.display_menu.stop_mode()
        if self.screensaver_menu and self.screensaver_menu.is_active:
            self.screensaver_menu.stop_mode()
        if self.original_screen and self.original_screen.is_active:
            self.original_screen.stop_mode()
        if self.modern_screen and self.modern_screen.is_active:
            self.modern_screen.stop_mode()
        if self.system_info_screen and self.system_info_screen.is_active:
            self.system_info_screen.stop_mode()

        # Re-create a screensaver instance
        screensaver_type = self.config.get("screensaver_type", "generic").lower()
        self.logger.debug(f"ModeManager: screensaver_type = {screensaver_type}")

        from display.screensavers.snake_screensaver import SnakeScreensaver
        from display.screensavers.starfield_screensaver import StarfieldScreensaver
        from display.screensavers.bouncing_text_screensaver import BouncingTextScreensaver
        from display.screensavers.screensaver import Screensaver

        if screensaver_type == "snake":
            self.logger.info("ModeManager: Creating fresh SnakeScreensaver instance.")
            self.screensaver = SnakeScreensaver(self.display_manager, update_interval=0.04)
        elif screensaver_type in ("stars", "starfield"):
            self.logger.info("ModeManager: Creating fresh StarfieldScreensaver instance.")
            self.screensaver = StarfieldScreensaver(
                display_manager=self.display_manager,
                num_stars=40,
                update_interval=0.05
            )
        elif screensaver_type in ("quoode", "bouncing_text"):
            self.logger.info("ModeManager: Creating fresh BouncingTextScreensaver instance.")
            self.screensaver = BouncingTextScreensaver(
                display_manager=self.display_manager,
                text="Quoode",
                update_interval=0.06
            )
        else:
            self.logger.info("ModeManager: Creating a generic Screensaver instance.")
            self.screensaver = Screensaver(
                display_manager=self.display_manager,
                update_interval=0.04
            )

        self.screensaver.start_screensaver()

    def exit_screensaver(self):
        self.logger.info("ModeManager: Exiting screensaver mode.")
        if self.screensaver:
            self.screensaver.stop_screensaver()
        self.to_clock()

    # -----------------------------------------------------------------
    #  Idle / Screensaver Timer Logic (Optional)
    # -----------------------------------------------------------------
    def reset_idle_timer(self):
        screensaver_enabled = self.config.get("screensaver_enabled", True)
        if not screensaver_enabled:
            self._cancel_idle_timer()
            return
        self._cancel_idle_timer()
        self._start_idle_timer()

    def _start_idle_timer(self):
        if self.idle_timeout <= 0:
            return
        self.idle_timer = threading.Timer(self.idle_timeout, self._idle_timeout_reached)
        self.idle_timer.start()
        self.logger.debug(f"ModeManager: Started idle timer for {self.idle_timeout}s.")

    def _cancel_idle_timer(self):
        if self.idle_timer:
            self.idle_timer.cancel()
            self.idle_timer = None
            self.logger.debug("ModeManager: Cancelled idle timer.")

    def _idle_timeout_reached(self):
        with self.lock:
            current_mode = self.get_mode()
            if current_mode == "clock":
                self.logger.debug("ModeManager: Idle timeout -> switching to screensaver (only in clock mode).")
                self.to_screensaver()
            else:
                self.logger.debug(f"ModeManager: Idle timeout in '{current_mode}' mode; NOT going to screensaver.")

    # -----------------------------------------------------------------
    #  Suppression logic
    # -----------------------------------------------------------------
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

    # -----------------------------------------------------------------
    #  Processing MPD updates
    # -----------------------------------------------------------------
    def process_state_change(self, sender, state, **kwargs):
        with self.lock:
            if self.suppress_state_changes:
                self.logger.debug("ModeManager: State change is suppressed.")
                return

            self.logger.debug(f"ModeManager: process_state_change -> {state}")
            status_dict = state.get('status', {})
            new_status = status_dict.get('state', '').lower()

            self.previous_status = self.current_status
            self.current_status = new_status

            if self.previous_status == "play" and self.current_status == "stop":
                self._handle_track_change()
            elif self.previous_status == "stop" and self.current_status == "play":
                self._handle_track_resumed()

            self._handle_playback_states(new_status)

    def _handle_track_change(self):
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
        self.is_track_changing = False
        self.track_change_in_progress = False
        self.logger.debug("ModeManager: Track resumed from 'stop' to 'play'.")
        if self.pause_stop_timer:
            self.pause_stop_timer.cancel()
            self.pause_stop_timer = None
            self.logger.debug("ModeManager: Cancelled stop verification timer.")

    def _handle_playback_states(self, status):
        if status == "play":
            self._cancel_pause_timer()
            self.is_track_changing = False
            self.track_change_in_progress = False

            if self.current_display_mode == 'modern':
                self.to_modern()
            else:
                self.to_original()

            self.reset_idle_timer()

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
            self.logger.debug("ModeManager: Cancelled pause/stop timer.")

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
        with self.lock:
            if self.current_status in ["pause", "stop"]:
                self.to_clock()
                self.logger.debug("ModeManager: Switched to clock after timer.")
            else:
                self.logger.debug("ModeManager: Playback resumed; staying in current mode.")
            self.pause_stop_timer = None

    def trigger(self, event_name, **kwargs):
        self.machine.trigger(event_name, **kwargs)

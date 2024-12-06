# src/display/screen_manager.py

import json
import os
import logging

class ScreenManager:
    def __init__(self, playback_manager, detailed_playback_manager, preference_file_path="/home/volumio/Quadify/src/screen_preference.json"):
        # Managers for different playback screens
        self.playback_manager = playback_manager
        self.detailed_playback_manager = detailed_playback_manager
        self.preference_file_path = preference_file_path

        # Set up logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)

        # Load the screen preference from file or set default
        self.current_screen_name = self.load_preference()
        self.logger.info(f"ScreenManager initialized with screen: {self.current_screen_name}")

    def load_preference(self):
        """
        Load the screen preference from a JSON file.
        """
        if os.path.exists(self.preference_file_path):
            try:
                with open(self.preference_file_path, "r") as file:
                    data = json.load(file)
                    screen_name = data.get("current_screen", "playback")
                    self.logger.info(f"Loaded screen preference: {screen_name}")
                    return screen_name
            except (json.JSONDecodeError, IOError) as e:
                self.logger.error(f"Error loading screen preference: {e}")
        # Default to "playback" if no preference is saved
        return "playback"

    def save_preference(self):
        """
        Save the current screen preference to a JSON file.
        """
        try:
            with open(self.preference_file_path, "w") as file:
                json.dump({"current_screen": self.current_screen_name}, file)
                self.logger.info(f"Saved screen preference: {self.current_screen_name}")
        except IOError as e:
            self.logger.error(f"Error saving screen preference: {e}")

    def handle_state_change(self, status, service):
        """
        Handle playback state changes and decide the active screen.
        """
        self.logger.debug(f"ScreenManager: Handling state change, status: {status}, service: {service}")

        if status == "play":
            # Activate the appropriate screen
            if self.current_screen_name == "playback":
                self.playback_manager.start_mode()
                self.logger.info("ScreenManager: Activated playback screen.")
            elif self.current_screen_name == "detailed_playback":
                self.detailed_playback_manager.start_mode()
                self.logger.info("ScreenManager: Activated detailed playback screen.")
        elif status in ["pause", "stop"]:
            # Deactivate the active screen
            if self.current_screen_name == "playback":
                self.playback_manager.stop_mode()
                self.logger.info("ScreenManager: Deactivated playback screen.")
            elif self.current_screen_name == "detailed_playback":
                self.detailed_playback_manager.stop_mode()
                self.logger.info("ScreenManager: Deactivated detailed playback screen.")
        else:
            self.logger.warning(f"ScreenManager: Unhandled status '{status}'")

    def get_current_screen(self):
        """
        Get the current screen preference.
        """
        return self.current_screen_name

    def set_current_screen(self, screen_name):
        if screen_name not in ["playback", "detailed_playback"]:
            self.logger.warning(f"Invalid screen name: {screen_name}. Must be 'playback' or 'detailed_playback'.")
            return

        # Deactivate the current screen manager if it is active
        if self.current_screen_name == "playback" and self.playback_manager.is_active:
            self.playback_manager.stop_mode()
            self.logger.info("ScreenManager: Stopped playback screen.")
        elif self.current_screen_name == "detailed_playback" and self.detailed_playback_manager.is_active:
            self.detailed_playback_manager.stop_mode()
            self.logger.info("ScreenManager: Stopped detailed playback screen.")

        # Set the new screen
        self.current_screen_name = screen_name

        # Activate the new screen manager
        if screen_name == "playback":
            self.playback_manager.start_mode()
            self.logger.info("ScreenManager: Started playback screen.")
        elif screen_name == "detailed_playback":
            self.detailed_playback_manager.start_mode()
            self.logger.info("ScreenManager: Started detailed playback screen.")

    def switch_screen(self):
        """
        Toggle between playback and detailed playback screens.
        """
        new_screen = "detailed_playback" if self.current_screen_name == "playback" else "playback"
        self.set_current_screen(new_screen)
        self.logger.info(f"ScreenManager: Switched to {new_screen} screen.")

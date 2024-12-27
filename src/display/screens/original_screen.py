# src/managers/menus/original_screen.py

from managers.menus.base_manager import BaseManager
import logging
from PIL import Image, ImageDraw, ImageFont
import re
import threading

class OriginalScreen(BaseManager):
    def __init__(self, display_manager, moode_listener, mode_manager):
        super().__init__(display_manager, moode_listener, mode_manager)
        self.mode_manager = mode_manager  # Ensure this is set
        self.moode_listener = moode_listener  # Assign the listener
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)

        self.previous_service = None

        # State management attributes
        self.latest_state = None
        self.state_lock = threading.Lock()
        self.update_event = threading.Event()
        self.stop_event = threading.Event()

        # Start the background update thread
        self.update_thread = threading.Thread(target=self.update_display_loop, daemon=True)
        self.update_thread.start()
        self.logger.info("OriginalScreen: Started background update thread.")

        # Register a callback for Moode state changes
        self.moode_listener.state_changed.connect(self.on_moode_state_change)
        self.logger.info("OriginalScreen initialized.")

    def on_moode_state_change(self, sender, state, **kwargs):
        """
        Callback to handle state changes from MoodeListener.
        Only process state changes when this manager is active and the mode is 'original'.
        """
        if not self.is_active or self.mode_manager.get_mode() != "original":
            self.logger.debug("OriginalScreen: Ignoring state change since not active or not in 'original' mode.")
            return

        # Check if the service is webradio, and ignore it in OriginalScreen
        if state.get("current_service", "").lower() == "webradio":
            self.logger.debug("OriginalScreen: Ignoring state change for webradio service.")
            return

        # Only suppress state changes during specific operations
        if self.mode_manager and self.mode_manager.is_state_change_suppressed():
            self.logger.debug("OriginalScreen: State change suppressed, not updating display.")
            return

        self.logger.debug(f"OriginalScreen: Received state change from {sender}: {state}")
        with self.state_lock:
            self.latest_state = state
        self.update_event.set()
        self.logger.debug("OriginalScreen: Signaled update thread with new state.")

    def update_display_loop(self):
        """
        Background thread loop that waits for state changes and updates the display at a controlled rate.
        """
        while not self.stop_event.is_set():
            triggered = self.update_event.wait(timeout=0.1)

            if triggered:
                with self.state_lock:
                    state_to_process = self.latest_state
                    self.latest_state = None

                self.update_event.clear()

                # Only update display if active and in 'original' mode
                if self.is_active and self.mode_manager.get_mode() == "original":
                    if state_to_process:
                        if self.mode_manager and self.mode_manager.is_state_change_suppressed():
                            self.logger.debug("OriginalScreen: State change suppressed during update loop, not updating display.")
                            continue
                        self.draw_display(state_to_process)
                else:
                    self.logger.debug("OriginalScreen: Skipping display update as it is inactive or not in 'original' mode.")

    def adjust_volume(self, volume_change):
        """
        Adjust the volume based on the volume_change parameter.
        """
        if self.latest_state is None:
            self.logger.warning("[OriginalScreen] latest_state is None, initializing with default volume of 100.")
            self.latest_state = {"volume": 100}

        with self.state_lock:
            current_volume = self.latest_state.get("volume", 100)
            new_volume = max(0, min(int(current_volume) + volume_change, 100))

        self.logger.info(f"OriginalScreen: Adjusting volume from {current_volume} to {new_volume}.")

        try:
            if volume_change > 0:
                self.moode_listener.set_volume('+')
                self.logger.info("OriginalScreen: Emitted volume increase command.")
            elif volume_change < 0:
                self.moode_listener.set_volume('-')
                self.logger.info("OriginalScreen: Emitted volume decrease command.")
            else:
                self.moode_listener.set_volume(new_volume)
                self.logger.info(f"OriginalScreen: Emitted volume set command with value {new_volume}.")
        except Exception as e:
            self.logger.error(f"OriginalScreen: Failed to adjust volume - {e}")
            self.display_error_message("Playback Error", f"Could not toggle playback: {e}")

    def display_playback_info(self):
        """Initialize playback display based on the current state."""
        current_state = self.moode_listener.get_current_state()
        if current_state:
            self.draw_display(current_state)
        else:
            self.logger.warning("OriginalScreen: No current state available to display.")

    def draw_display(self, data):
        """Draw the display based on the Moode state."""
        # Removed .lower() calls to prevent AttributeError
        track_type = data.get("trackType", "")
        current_service = data.get("current_service", "")
        status = data.get("status", "")

        self.logger.debug(f"Current service: '{current_service}'")

        if status in ["pause", "stop"] and not current_service:
            current_service = self.previous_service or "default"
            self.logger.debug(f"OriginalScreen: Player is {status}. Using previous service '{current_service}'.")
        else:
            if current_service:
                if current_service != self.previous_service:
                    self.display_manager.clear_screen()
                    self.logger.info(f"OriginalScreen: Service changed to '{current_service}'. Screen cleared.")
                self.previous_service = current_service
            else:
                current_service = self.previous_service or "default"

        base_image = Image.new("RGB", self.display_manager.oled.size, "black")
        draw = ImageDraw.Draw(base_image)

        # Draw volume indicator
        volume = max(0, min(int(data.get("volume", 0)), 100))
        filled_squares = round((volume / 100) * 6)
        square_size = 3
        row_spacing = 5
        padding_bottom = 6
        columns = [10, 26]

        for x in columns:
            for row in range(filled_squares):
                y = self.display_manager.oled.height - padding_bottom - ((row + 1) * (square_size + row_spacing))
                draw.rectangle([x, y, x + square_size, y + square_size], fill="white")
        self.logger.info(f"OriginalScreen: Drew volume bars with {filled_squares} filled squares.")

        self.draw_general_playback(draw, base_image, data, current_service)

        self.display_manager.oled.display(base_image)
        self.logger.info("OriginalScreen: Display updated.")

    def draw_general_playback(self, draw, base_image, data, current_service):
        samplerate = data.get("samplerate", "")
        self.logger.debug(f"Received data: {data}")

        # Parse sample rate
        try:
            if samplerate:
                match = re.match(r"([\d\.]+)\s*(\w+)", samplerate)
                if match:
                    sample_rate_value = float(match.group(1))
                    sample_rate_unit_text = match.group(2).lower()
                    sample_rate_num = int(sample_rate_value)
                else:
                    raise ValueError("Sample rate format is unexpected")
            else:
                raise ValueError("Empty samplerate string")
        except (ValueError, IndexError) as e:
            self.logger.warning(f"OriginalScreen: Failed to parse sample rate: '{samplerate}' - Error: {e}")
            sample_rate_num = "N/A"
            sample_rate_unit_text = ""

        # Normalize the unit text
        if sample_rate_unit_text in ["khz", "hz"]:
            sample_rate_unit_text = sample_rate_unit_text.upper()
        elif sample_rate_unit_text == "kbps":
            sample_rate_unit_text = "kbps"
        else:
            sample_rate_unit_text = "kHz"  # default fallback

        sample_rate_num_text = str(sample_rate_num)
        font_sample_num = self.display_manager.fonts.get('sample_rate', ImageFont.load_default())
        font_sample_unit = self.display_manager.fonts.get('sample_rate_khz', ImageFont.load_default())

        sample_rate_block_right_x = self.display_manager.oled.width - 70
        sample_rate_y = 32

        # Use getbbox for accurate text size measurement
        bbox_num = self.display_manager.fonts['sample_rate'].getbbox(sample_rate_num_text)
        num_width = bbox_num[2] - bbox_num[0] if bbox_num else 0
        bbox_unit = self.display_manager.fonts['sample_rate_khz'].getbbox(sample_rate_unit_text)
        unit_width = bbox_unit[2] - bbox_unit[0] if bbox_unit else 0

        sample_rate_num_x = sample_rate_block_right_x - unit_width - num_width - 4
        draw.text((sample_rate_num_x, sample_rate_y), sample_rate_num_text, font=font_sample_num, fill="white", anchor="lm")

        unit_x = sample_rate_num_x + num_width + 1
        draw.text((unit_x, sample_rate_y + 18), sample_rate_unit_text, font=font_sample_unit, fill="white", anchor="lm")

        self.logger.info("OriginalScreen: Drew sample rate.")

        # Draw service icon
        icon = self.display_manager.icons.get(current_service)
        if icon:
            if icon.mode == "RGBA":
                background = Image.new("RGB", icon.size, (0, 0, 0))
                background.paste(icon, mask=icon.split()[3])
                icon = background

            icon_padding_right = 12
            icon_padding_top = 6
            icon_x = self.display_manager.oled.width - icon.width - icon_padding_right
            icon_y = icon_padding_top
            base_image.paste(icon, (icon_x, icon_y))
            self.logger.info(f"OriginalScreen: Pasted icon for '{current_service}' at position ({icon_x}, {icon_y}).")
        else:
            # Fallback to default icon if none is found
            icon = self.display_manager.default_icon
            if icon:
                if icon.mode == "RGBA":
                    background = Image.new("RGB", icon.size, (0, 0, 0))
                    background.paste(icon, mask=icon.split()[3])
                    icon = background
                icon_x = self.display_manager.oled.width - icon.width - 20
                icon_y = 5
                base_image.paste(icon, (icon_x, icon_y))
                self.logger.info(f"OriginalScreen: Pasted default icon at position ({icon_x}, {icon_y}).")
            else:
                self.logger.warning("OriginalScreen: No default icon available.")

        # Draw Bit Depth
        bitdepth = data.get("bitdepth", "N/A")
        format_bitdepth_text = f"{bitdepth}"
        font_info = self.display_manager.fonts.get('playback_small', ImageFont.load_default())
        padding = 15
        x_position = self.display_manager.oled.width - padding
        draw.text((x_position, 50), format_bitdepth_text, font=font_info, fill="white", anchor="rm")
        self.logger.info("OriginalScreen: Drew audio format and bitdepth.")

    def start_mode(self):
        """
        Activate the OriginalScreen and initialize the playback display.
        """
        if self.mode_manager.get_mode() != "original":
            self.logger.warning("OriginalScreen: Attempted to start, but the current mode is not 'original'.")
            return

        self.is_active = True
        self.logger.info("OriginalScreen: Starting playback display for 'original' mode.")
        self.display_playback_info()

    def stop_mode(self):
        """
        Deactivate the OriginalScreen and stop the playback display.
        """
        if not self.is_active:
            self.logger.info("OriginalScreen: stop_mode called, but was not active.")
            return

        self.is_active = False
        self.stop_event.set()
        self.update_event.set()

        try:
            if self.update_thread.is_alive():
                self.update_thread.join(timeout=1)
                if self.update_thread.is_alive():
                    self.logger.warning("OriginalScreen: Failed to terminate update thread in time.")
        except Exception as e:
            self.logger.error(f"OriginalScreen: Error stopping update thread - {e}")

        self.display_manager.clear_screen()
        self.logger.info("OriginalScreen: Stopped playback display and cleared the screen.")

    def toggle_play_pause(self):
        """Emit the play/pause command to Moode."""
        self.logger.info("OriginalScreen: Toggling play/pause.")
        if not self.moode_listener.is_connected():
            self.logger.warning("OriginalScreen: Cannot toggle playback - not connected to Moode.")
            self.display_error_message("Connection Error", "Not connected to Moode.")
            return

        try:
            self.moode_listener.toggle_play_pause()
            self.logger.debug("OriginalScreen: 'toggle_play_pause' method called successfully.")
        except Exception as e:
            self.logger.error(f"OriginalScreen: Failed to toggle play/pause - {e}")
            self.display_error_message("Playback Error", f"Could not toggle playback: {e}")

    def update_playback_metrics(self, state):
        """Update the playback metrics (sample rate, bit depth, and volume) on the display."""
        self.logger.info("OriginalScreen: Updating playback metrics display.")

        sample_rate = state.get("samplerate", "Unknown Sample Rate")
        bitdepth = state.get("bitdepth", "Unknown Bit Depth")
        volume = state.get("volume", "Unknown Volume")

        # Update internal state variables or trigger a refresh of the display
        self.latest_sample_rate = sample_rate
        self.latest_bitdepth = bitdepth
        self.latest_volume = volume

        self.update_event.set()
        self.logger.info(f"OriginalScreen: Updated metrics - Sample Rate: {sample_rate}, Bit Depth: {bitdepth}, Volume: {volume}")

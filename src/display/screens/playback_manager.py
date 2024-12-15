# src/managers/playback_manager.py

from managers.menus.base_manager import BaseManager
import logging
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
import requests
from io import BytesIO
import hashlib
import os
import threading
import time
import re


class PlaybackManager(BaseManager):
    def __init__(self, display_manager, volumio_listener, mode_manager):
        super().__init__(display_manager, volumio_listener, mode_manager)
        self.mode_manager = mode_manager  # Ensure this is set
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
        self.logger.info("PlaybackManager: Started background update thread.")

        # Register a callback for Volumio state changes
        self.volumio_listener.state_changed.connect(self.on_volumio_state_change)
        self.logger.info("PlaybackManager initialized.")
        
    
    def on_volumio_state_change(self, sender, state):
        """
        Callback to handle state changes from VolumioListener.
        Only process state changes when this manager is active and the screen is set to 'playback'.
        """
        # Check if the PlaybackManager is active and the screen is correct
        if not self.is_active or self.mode_manager.screen_manager.get_current_screen() != "playback":
            self.logger.debug("PlaybackManager: Ignoring state change since it is not active or the current screen is not 'playback'.")
            return

        # Check if the service is webradio, and ignore it in PlaybackManager
        if state.get("service") == "webradio":
            self.logger.debug("PlaybackManager: Ignoring state change for webradio service.")
            return

        # Only suppress state changes during specific operations
        if self.mode_manager and self.mode_manager.is_state_change_suppressed():
            self.logger.debug("PlaybackManager: State change suppressed, not updating display.")
            return

        self.logger.debug(f"PlaybackManager: Received state change from {sender}: {state}")
        with self.state_lock:
            self.latest_state = state
        self.update_event.set()
        self.logger.debug("PlaybackManager: Signaled update thread with new state.")


    def update_display_loop(self):
        """
        Background thread loop that waits for state changes and updates the display at a controlled rate.
        """
        while not self.stop_event.is_set():
            # Wait for an update signal or timeout after 0.1 seconds
            triggered = self.update_event.wait(timeout=0.1)

            if triggered:
                with self.state_lock:
                    state_to_process = self.latest_state
                    self.latest_state = None  # Reset the latest_state

                self.update_event.clear()

                # Only update display if active and on the correct screen
                if self.is_active and self.mode_manager.screen_manager.get_current_screen() == "playback":
                    if state_to_process:
                        if self.mode_manager and self.mode_manager.is_state_change_suppressed():
                            self.logger.debug("PlaybackManager: State change suppressed during update loop, not updating display.")
                            continue
                        self.draw_display(state_to_process)
                else:
                    self.logger.debug("PlaybackManager: Skipping display update as it is inactive or on a different screen.")



    def adjust_volume(self, volume_change):
        """
        Adjusts the volume based on the volume_change parameter.

        :param volume_change: Integer representing the change in volume.
                              Positive values increase volume, negative values decrease it.
        """
        # Ensure `self.latest_state` is not None
        if self.latest_state is None:
            self.logger.warning("[PlaybackManager] latest_state is None, initializing with default volume of 100.")
            self.latest_state = {"volume": 100}

        # Adjust volume using current state
        with self.state_lock:
            current_volume = self.latest_state.get("volume", 100)  # Default to 100 if volume is not set
            new_volume = max(0, min(int(current_volume) + volume_change, 100))

        self.logger.info(f"PlaybackManager: Adjusting volume from {current_volume} to {new_volume}.")

        try:
            if volume_change > 0:
                # Emit a volume increase command using '+'
                self.volumio_listener.socketIO.emit("volume", "+")
                self.logger.info(f"PlaybackManager: Emitted volume increase command.")
            elif volume_change < 0:
                # Emit a volume decrease command using '-'
                self.volumio_listener.socketIO.emit("volume", "-")
                self.logger.info(f"PlaybackManager: Emitted volume decrease command.")
            else:
                # If volume_change is zero, emit the direct volume level
                self.volumio_listener.socketIO.emit("volume", new_volume)
                self.logger.info(f"PlaybackManager: Emitted volume set command with value {new_volume}.")

        except Exception as e:
            self.logger.error(f"PlaybackManager: Failed to adjust volume - {e}")

    def display_playback_info(self):
        """Initialize playback display based on the current state."""
        current_state = self.volumio_listener.get_current_state()
        if current_state:
            self.draw_display(current_state)
        else:
            self.logger.warning("PlaybackManager: No current state available to display.")

    def draw_display(self, data):
        """Draw the display based on the Volumio state."""
        # Retrieve necessary fields from data
        track_type = data.get("trackType", "").lower()
        service = data.get("service", "").lower()
        status = data.get("status", "").lower()

        # Determine current_service based on conditions
        if service == "mpd":
            # When service is 'mpd', set current_service to 'mpd'
            current_service = "mpd"
        else:
            # For other services, use 'trackType' if available, else use 'service'
            current_service = track_type or service or "default"

        self.logger.debug(f"Current service: '{current_service}'")

        # Handle paused or stopped states
        if status in ["pause", "stop"] and not current_service:
            current_service = self.previous_service or "default"
            self.logger.debug(f"PlaybackManager: Player is {status}. Using previous service '{current_service}'.")
        else:
            if current_service:
                if current_service != self.previous_service:
                    self.display_manager.clear_screen()
                    self.logger.info(f"PlaybackManager: Service changed to '{current_service}'. Screen cleared.")
                self.previous_service = current_service
            else:
                current_service = self.previous_service or "default"

        # Create an image to draw on
        base_image = Image.new("RGB", self.display_manager.oled.size, "black")
        draw = ImageDraw.Draw(base_image)

        # Draw volume indicator
        volume = max(0, min(int(data.get("volume", 0)), 100))
        filled_squares = round((volume / 100) * 6)
        square_size = 3
        row_spacing = 5
        padding_bottom = 6  # Adjust as needed
        columns = [10, 26]  # X positions for two columns

        for x in columns:
            for row in range(filled_squares):
                y = self.display_manager.oled.height - padding_bottom - ((row + 1) * (square_size + row_spacing))
                draw.rectangle([x, y, x + square_size, y + square_size], fill="white")
        self.logger.info(f"PlaybackManager: Drew volume bars with {filled_squares} filled squares.")

        # Handle general playback drawing
        self.draw_general_playback(draw, base_image, data, current_service)

        # Display the final composed image
        self.display_manager.oled.display(base_image)
        self.logger.info("PlaybackManager: Display updated.")

    
    def draw_general_playback(self, draw, base_image, data, current_service):
        """
        Draws the general playback information (sample rate, service icon, audio type, bitdepth).
        """
        import re  # Import re at the top of the file if not already imported

        # Draw Sample Rate with 'kHz' or 'kbps' in separate fonts
        sample_rate = data.get("samplerate", "")
        self.logger.debug(f"Received data: {data}")

        # Extract the numeric value and unit from the sample rate string
        try:
            if sample_rate:
                # Use regex to extract number and unit
                match = re.match(r"([\d\.]+)\s*(\w+)", sample_rate)
                if match:
                    sample_rate_value = float(match.group(1))
                    sample_rate_unit_text = match.group(2).lower()
                    sample_rate_num = int(sample_rate_value)
                else:
                    raise ValueError("Sample rate format is unexpected")
            else:
                raise ValueError("Empty samplerate string")
        except (ValueError, IndexError) as e:
            self.logger.warning(f"PlaybackManager: Failed to parse sample rate: '{sample_rate}' - Error: {e}")
            sample_rate_num = "N/A"
            sample_rate_unit_text = ""

        # Normalize unit text
        if sample_rate_unit_text in ["khz", "hz"]:
            sample_rate_unit_text = sample_rate_unit_text.upper()
        elif sample_rate_unit_text == "kbps":
            sample_rate_unit_text = "kbps"
        else:
            sample_rate_unit_text = "kHz"  # Default to 'kHz' if unit is unexpected

        # Prepare the sample rate number text
        sample_rate_num_text = str(sample_rate_num)

        # Adjust the fonts
        font_sample_num = self.display_manager.fonts.get('sample_rate', ImageFont.load_default())
        font_sample_unit = self.display_manager.fonts.get('sample_rate_khz', ImageFont.load_default())

        # Define the overall rightmost fixed position for the sample rate block
        sample_rate_block_right_x = self.display_manager.oled.width - 70  # Adjust as needed
        sample_rate_y = 32  # Y-position for the text

        # Calculate the width of the numeric part and the unit part
        num_width, _ = draw.textsize(sample_rate_num_text, font=font_sample_num)
        unit_width, _ = draw.textsize(sample_rate_unit_text, font=font_sample_unit)

        # Calculate the starting x-position for the numeric part
        sample_rate_num_x = sample_rate_block_right_x - unit_width - num_width - 4  # Leave a small gap

        # Draw the numeric part of the sample rate
        draw.text(
            (sample_rate_num_x, sample_rate_y),
            sample_rate_num_text,
            font=font_sample_num,
            fill="white",
            anchor="lm"  # Left aligned for drawing
        )

        # Draw the unit part immediately next to the numeric value
        unit_x = sample_rate_num_x + num_width + 1  # Small gap between number and unit
        draw.text(
            (unit_x, sample_rate_y + 18),  # Y-position adjustment if needed
            sample_rate_unit_text,
            font=font_sample_unit,
            fill="white",
            anchor="lm"  # Left aligned
        )

        self.logger.info("PlaybackManager: Drew sample rate.")

        # Draw Service Icon
        icon = self.display_manager.icons.get(current_service)
        if icon:
            # If the icon is in RGBA mode, convert it to RGB
            if icon.mode == "RGBA":
                background = Image.new("RGB", icon.size, (0, 0, 0))
                background.paste(icon, mask=icon.split()[3])
                icon = background

            # Calculate positions for the icon
            icon_padding_right = 12  # Adjust as needed
            icon_padding_top = 6     # Adjust as needed

            icon_x = self.display_manager.oled.width - icon.width - icon_padding_right
            icon_y = icon_padding_top

            # Paste the icon
            base_image.paste(icon, (icon_x, icon_y))
            self.logger.info(f"PlaybackManager: Pasted icon for '{current_service}' at position ({icon_x}, {icon_y}).")
        else:
            # Fallback to default icon if specific icon is not found
            icon = self.display_manager.default_icon
            if icon:
                if icon.mode == "RGBA":
                    background = Image.new("RGB", icon.size, (0, 0, 0))
                    background.paste(icon, mask=icon.split()[3])
                    icon = background

                icon_x = self.display_manager.oled.width - icon.width - 20
                icon_y = 5
                base_image.paste(icon, (icon_x, icon_y))
                self.logger.info(f"PlaybackManager: Pasted default icon at position ({icon_x}, {icon_y}).")
            else:
                self.logger.warning("PlaybackManager: No default icon available.")

        # Draw Bit Depth
        bitdepth = data.get("bitdepth", "N/A")
        format_bitdepth_text = f"{bitdepth}"

        # Font information
        font_info = self.display_manager.fonts.get('playback_small', ImageFont.load_default())

        # Calculate x-coordinate for right alignment
        padding = 15  # Space from the right edge
        x_position = self.display_manager.oled.width - padding

        draw.text(
            (x_position, 50),  # Adjust y-position as needed
            format_bitdepth_text,
            font=font_info,
            fill="white",
            anchor="rm"  # Right-aligned
        )

        self.logger.info("PlaybackManager: Drew audio format and bitdepth.")

    def display_playback_info(self):
        """Initialize playback display based on the current state."""
        current_state = self.volumio_listener.get_current_state()
        if current_state:
            self.draw_display(current_state)
        else:
            self.logger.warning("PlaybackManager: No current state available to display.")

    def start_mode(self):
        """
        Activate the PlaybackManager and initialize the playback display.
        """
        if self.mode_manager.screen_manager.get_current_screen() != "playback":
            self.logger.warning("PlaybackManager: Attempted to start, but the current screen is not 'playback'.")
            return

        self.is_active = True
        self.logger.info("PlaybackManager: Starting playback mode.")
        self.display_playback_info()

    def stop_mode(self):
        """
        Deactivate the PlaybackManager and stop the playback display.
        """
        if not self.is_active:
            self.logger.info("PlaybackManager: stop_mode called, but was not active.")
            return

        self.is_active = False
        self.stop_event.set()
        self.update_event.set()  # Unblock the update thread if waiting

        try:
            if self.update_thread.is_alive():
                self.update_thread.join(timeout=1)
                if self.update_thread.is_alive():
                    self.logger.warning("PlaybackManager: Failed to terminate update thread in time.")
        except Exception as e:
            self.logger.error(f"PlaybackManager: Error stopping update thread - {e}")

        self.display_manager.clear_screen()
        self.logger.info("PlaybackManager: Stopped playback mode and cleared the screen.")


    def toggle_play_pause(self):
        """Emit the play/pause command to Volumio."""
        self.logger.info("PlaybackManager: Toggling play/pause.")
        if not self.volumio_listener.is_connected():
            self.logger.warning("PlaybackManager: Cannot toggle playback - not connected to Volumio.")
            self.display_error_message("Connection Error", "Not connected to Volumio.")
            return
        
        try:
            self.volumio_listener.socketIO.emit("toggle", {})
            self.logger.debug("PlaybackManager: 'toggle' event emitted successfully.")
        except Exception as e:
            self.logger.error(f"PlaybackManager: Failed to emit 'toggle' event - {e}")
            self.display_error_message("Playback Error", f"Could not toggle playback: {e}")


    def update_playback_metrics(self, state):
        """Update the playback metrics (sample rate, bit depth, and volume) on the display."""
        self.logger.info("PlaybackManager: Updating playback metrics display.")

        # Extract relevant playback information
        sample_rate = state.get("samplerate", "Unknown Sample Rate")
        bitdepth = state.get("bitdepth", "Unknown Bit Depth")
        volume = state.get("volume", "Unknown Volume")

        # Update internal state variables or trigger a refresh of the display to reflect changes
        self.latest_sample_rate = sample_rate
        self.latest_bitdepth = bitdepth
        self.latest_volume = volume

        # Set the update event to refresh the display in the background loop
        self.update_event.set()

        self.logger.info(f"PlaybackManager: Updated metrics - Sample Rate: {sample_rate}, Bit Depth: {bitdepth}, Volume: {volume}")
# src/managers/webradio_screen.py

from managers.menus.base_manager import BaseManager

import os
import logging
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
import requests
from io import BytesIO
import threading

class WebRadioScreen(BaseManager):
    def __init__(self, display_manager, moode_listener, mode_manager):
        super().__init__(display_manager, moode_listener, mode_manager)
        self.mode_manager = mode_manager
        self.display_manager = display_manager
        self.moode_listener = moode_listener
        self.logger = logging.getLogger(self.__class__.__name__)
        self.is_active = False  # Initialize is_active as False

        self.local_album_art_path = "/home/matt/Quoode/src/assets/images/webradio.png"
        self.cache_dir = "/home/matt/Quoode/src/cache/album_art"
        os.makedirs(self.cache_dir, exist_ok=True)

        # Load the local BMP fallback album art once during initialization
        try:
            self.default_album_art = Image.open(self.local_album_art_path).resize((50, 50)).convert("RGBA")
        except IOError:
            self.logger.error("Local BMP album art not found. Please check the path.")
            self.default_album_art = None

        # Thread-related attributes
        self.state_lock = threading.Lock()
        self.update_event = threading.Event()
        self.stop_event = threading.Event()
        self.latest_state = None

        # Start the background update thread
        self.update_thread = threading.Thread(target=self.update_display_loop, daemon=True)
        self.update_thread.start()
        self.logger.info("WebRadioScreen: Started background update thread.")

        # Register a callback for moode state changes
        self.moode_listener.state_changed.connect(self.on_moode_state_change)
        self.logger.info("WebRadioScreen initialized.")

    def on_moode_state_change(self, sender, state):
        """Handle state changes from moode."""
        if state.get("service", "").lower() != "webradio":
            self.logger.debug("WebRadioScreen: Ignoring state change for non-webradio service.")
            return

        self.logger.debug(f"WebRadioScreen: Received state change for webradio: {state}")
        with self.state_lock:
            self.latest_state = state
        self.update_event.set()

    def update_display_loop(self):
        """
        Background thread loop that waits for state changes and updates the display.
        """
        while not self.stop_event.is_set():
            # Wait for an update signal or timeout after 0.1 seconds
            triggered = self.update_event.wait(timeout=0.1)

            if triggered:
                with self.state_lock:
                    state_to_process = self.latest_state
                    self.latest_state = None  # Reset the latest_state

                self.update_event.clear()

                if state_to_process:
                    self.draw_display(state_to_process)

    def start_mode(self):
        """Activate the WebRadioScreen display mode."""
        if self.mode_manager.get_mode() != "webradio":
            self.logger.warning("WebRadioScreen: Not in 'webradio' mode. Cannot start WebRadioScreen.")
            return

        if not self.is_active:
            self.is_active = True
            self.logger.info("WebRadioScreen: Starting WebRadioScreen mode.")
            self.display_radioplayback_info()
        else:
            self.logger.info("WebRadioScreen: start_mode called, but mode is already active.")

    def stop_mode(self):
        """Deactivate the WebRadioScreen display mode."""
        if self.is_active:
            self.is_active = False
            self.stop_event.set()
            self.update_event.set()  # Unblock the update thread if waiting
            if self.update_thread.is_alive():
                self.update_thread.join(timeout=1)
                if self.update_thread.is_alive():
                    self.logger.warning("WebRadioScreen: Failed to terminate update thread in time.")
            self.display_manager.clear_screen()
            self.logger.info("WebRadioScreen: Stopped WebRadioScreen mode and terminated update thread.")
        else:
            self.logger.info("WebRadioScreen: stop_mode called, but was not active.")

    def draw_volume_bars(self, draw, volume):
        """
        Draws volume bars on the display.
        :param draw: ImageDraw object to draw on.
        :param volume: Current volume level (0-100).
        """
        if not self.is_active:
            self.logger.info("WebRadioScreen: draw_volume_bars called, but mode is not active.")
            return

        filled_squares = round((volume / 100) * 6)
        square_size = 3
        row_spacing = 5
        padding_bottom = 6  # Adjust as needed
        columns = [10, 26]  # X positions for two columns

        for x in columns:
            for row in range(filled_squares):
                y = self.display_manager.oled.height - padding_bottom - ((row + 1) * (square_size + row_spacing))
                draw.rectangle([x, y, x + square_size, y + square_size], fill="white")
        self.logger.info(f"WebRadioScreen: Drew volume bars with {filled_squares} filled squares.")

    def draw(self, draw, data, base_image):
        if not self.is_active:
            self.logger.info("WebRadioScreen: draw called, but mode is not active.")
            return

        # Determine which station information to display
        station_name = data.get("title", "").strip() if data.get("title") else "WebRadio"
        artist_name = data.get("artist") or ""

        # If the station name contains song info and there's an artist field, prefer using the artist field as the station name
        if artist_name and station_name and ("-" in station_name or artist_name.lower() not in station_name.lower()):
            display_text = artist_name
        else:
            display_text = station_name

        # Truncate display text if too long to fit on the screen
        max_chars = 16  # Adjust based on your display's width
        if len(display_text) > max_chars:
            display_text = display_text[:max_chars - 3] + "..."

        # Determine if bitrate is available
        bitrate = data.get("bitrate", "")

        # Set position for the display label based on bitrate availability
        webradio_y_position = 15 if bitrate else 25  # Adjust position based on whether bitrate is shown

        # Draw the station name or artist at the calculated position
        font_display_text = self.display_manager.fonts.get('radio_title', ImageFont.load_default())
        draw.text((self.display_manager.oled.width // 2, webradio_y_position), 
                  display_text, font=font_display_text, fill="white", anchor="mm")

        # Display bitrate if available
        if bitrate:
            font_bitrate = self.display_manager.fonts.get('radio_bitrate', ImageFont.load_default())
            draw.text((self.display_manager.oled.width // 2, 35), bitrate, font=font_bitrate, fill="white", anchor="mm")

        # Attempt to load album art from URL
        album_art_url = data.get("albumart")
        album_art = None

        if album_art_url:
            try:
                response = requests.get(album_art_url, timeout=5)
                # Check if response contains image data
                if response.headers.get("Content-Type", "").startswith("image"):
                    album_art = Image.open(BytesIO(response.content)).resize((40, 40)).convert("RGBA")
                    
                    # Handle transparency if the album art is in RGBA mode
                    if album_art.mode == "RGBA":
                        background = Image.new("RGB", album_art.size, (0, 0, 0))
                        background.paste(album_art, mask=album_art.split()[3])
                        album_art = background

                else:
                    self.logger.warning("Album art URL did not return an image.")
            except requests.RequestException:
                self.logger.warning("Could not load album art (network error).")
            except (UnidentifiedImageError, IOError):
                self.logger.warning("Could not load album art (unsupported format).")

        # Use the local BMP fallback if URL fetching fails
        if album_art is None and self.default_album_art:
            album_art = self.default_album_art

        # Paste album art on display if available
        if album_art:
            album_art_x = self.display_manager.oled.width - album_art.width - 5
            album_art_y = 10
            base_image.paste(album_art, (album_art_x, album_art_y))
            self.logger.info(f"WebRadioScreen: Pasted album art at position ({album_art_x}, {album_art_y}).")
        else:
            self.logger.warning("WebRadioScreen: No album art available to display.")

        # Draw volume bars
        volume = max(0, min(int(data.get("volume", 0)), 100))
        self.draw_volume_bars(draw, volume)

    def draw_display(self, data):
        """Draw the display based on the moode state."""
        if not self.is_active:
            self.logger.info("WebRadioScreen: draw_display called, but mode is not active.")
            return

        # Create an image to draw on
        base_image = Image.new("RGB", self.display_manager.oled.size, "black")
        draw = ImageDraw.Draw(base_image)

        # Call the draw function to add playback info and volume bars
        self.draw(draw, data, base_image)

        # Display the final composed image
        self.display_manager.oled.display(base_image)
        self.logger.info("WebRadioScreen: Display updated.")

    def display_radioplayback_info(self):
        """Display the radioplayback information on the OLED."""
        if not self.is_active:
            self.logger.info("WebRadioScreen: display_radioplayback_info called, but mode is not active.")
            return
        
        current_state = self.moode_listener.get_current_state()
        if current_state:
            self.draw_display(current_state)
        else:
            self.logger.warning("WebRadioScreen: No current state available to display.")

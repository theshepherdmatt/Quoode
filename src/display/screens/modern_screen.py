# src/managers/modern_screen.py

from managers.menus.base_manager import BaseManager
import logging
from PIL import Image, ImageDraw, ImageFont
import threading
import time
import os

FIFO_PATH = "/tmp/display.fifo"  # Path to the FIFO for CAVA

class ModernScreen(BaseManager):
    def __init__(self, display_manager, moode_listener, mode_manager):
        super().__init__(display_manager, moode_listener, mode_manager)
        self.moode_listener = moode_listener  # Explicitly assign moode_listener
        self.mode_manager = mode_manager
        self.mode_name = "modern"  # Align with ModeManager's state
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)
        self.spectrum_bars = []
        self.running_spectrum = False
        self.spectrum_thread = None

        # Fonts
        self.font_title = self.display_manager.fonts.get('song_font', ImageFont.load_default())
        self.font_artist = self.display_manager.fonts.get('artist_font', ImageFont.load_default())
        self.font_info = self.display_manager.fonts.get('data_font', ImageFont.load_default())
        self.font_progress = self.display_manager.fonts.get('progress_bar', ImageFont.load_default())

        # Scrolling attributes
        self.scroll_offset_title = 0
        self.scroll_offset_artist = 0
        self.scroll_speed = 2  # Adjust for faster or slower scrolling

        # State attributes
        self.latest_state = None
        self.current_state = None  # Persistent current state
        self.state_lock = threading.Lock()
        self.update_event = threading.Event()
        self.stop_event = threading.Event()

        # Update thread
        self.update_thread = threading.Thread(target=self.update_display_loop, daemon=True)
        self.update_thread.start()
        self.logger.info("ModernScreen: Started background update thread.")

        # moode state change listener
        self.moode_listener.state_changed.connect(self.on_moode_state_change)
        self.logger.info("ModernScreen initialized.")

    def _read_fifo(self):
        """Read spectrum data from FIFO."""
        if not os.path.exists(FIFO_PATH):
            self.logger.error(f"FIFO {FIFO_PATH} does not exist.")
            return

        self.logger.info("Starting spectrum visualisation thread.")
        try:
            with open(FIFO_PATH, "r") as fifo:
                while self.running_spectrum:
                    line = fifo.readline().strip()
                    if line:
                        # Assuming spectrum data is semicolon-separated integers
                        bars = [int(x) for x in line.split(";") if x.isdigit()]
                        self.spectrum_bars = bars
        except Exception as e:
            self.logger.error(f"Error reading spectrum data: {e}")

    def _draw_spectrum(self, draw):
        """Draw spectrum bars on the screen."""
        width, height = self.display_manager.oled.size
        bars = self.spectrum_bars[::2]  # Downsample to reduce the number of bars
        bar_width = 2
        gap_width = 3
        max_height = height // 2
        start_x = (width - (len(bars) * (bar_width + gap_width))) // 2

        self.logger.debug(f"Number of bars: {len(bars)}")

        vertical_offset = -8  # Move up by 8 pixels

        for i, bar in enumerate(bars):
            bar_height = int((bar / 255) * max_height)
            x1 = start_x + i * (bar_width + gap_width)
            x2 = x1 + bar_width
            y1 = height - bar_height + vertical_offset
            y2 = height + vertical_offset
            draw.rectangle([x1, y1, x2, y2], fill="#303030")  # Grey colour

    def reset_scrolling(self):
        """Reset scrolling parameters."""
        self.logger.debug("ModernScreen: Resetting scrolling offsets.")
        self.scroll_offset_title = 0
        self.scroll_offset_artist = 0

    def update_scroll(self, text, font, max_width, scroll_offset):
        """Update scrolling offset for continuous scrolling."""
        # Use getlength instead of getsize to obtain text width
        try:
            text_width = font.getlength(text)
        except AttributeError:
            # Fallback for older Pillow versions
            bbox = font.getbbox(text)
            if bbox:
                text_width = bbox[2] - bbox[0]
            else:
                text_width = 0

        self.logger.debug(f"update_scroll: text='{text}', text_width={text_width}, max_width={max_width}, scroll_offset={scroll_offset}")

        # If the text width is less than the max width, no need to scroll
        if text_width <= max_width:
            return text, 0, False

        # Increment the scroll offset
        scroll_offset += self.scroll_speed

        # Reset the scroll offset if it has scrolled past the text
        if scroll_offset > text_width:
            scroll_offset = 0

        return text, scroll_offset, True

    def update_display_loop(self):
        """Background loop to update the display."""
        last_update_time = time.time()
        while not self.stop_event.is_set():
            triggered = self.update_event.wait(timeout=0.1)
            with self.state_lock:
                if triggered:
                    # State change received, update current_state
                    if self.latest_state:
                        self.current_state = self.latest_state.copy()
                        self.latest_state = None
                        last_update_time = time.time()  # Reset time for smooth progress
                        self.update_event.clear()
                        self.logger.debug("update_display_loop: State updated from latest_state.")
                elif self.current_state and "elapsed" in self.current_state and "duration" in self.current_state:
                    # Simulate seek progress
                    elapsed_time = time.time() - last_update_time
                    try:
                        self.current_state["elapsed"] = float(self.current_state["elapsed"]) + elapsed_time
                        last_update_time = time.time()
                        self.logger.debug(f"update_display_loop: Incremented elapsed by {elapsed_time:.3f}s to {self.current_state['elapsed']:.3f}s.")
                    except ValueError as e:
                        self.logger.error(f"ModernScreen: Error updating elapsed time - {e}")
                        self.current_state["elapsed"] = 0.0

            # Check if mode_manager mode is 'modern'
            if self.is_active and self.mode_manager.get_mode() == "modern" and self.current_state:
                self.logger.debug("ModernScreen: Redrawing playback screen.")
                self.draw_display(self.current_state)

    def draw_display(self, data):
        """Draw the ModernScreen display with smooth and continuous scrolling."""
        if data is None:
            self.logger.warning("ModernScreen: No data provided for display.")
            return

        base_image = Image.new("RGB", self.display_manager.oled.size, "black")
        draw = ImageDraw.Draw(base_image)

        # Draw spectrum bars
        self._draw_spectrum(draw)

        # Extract information
        song_title = data.get("title", "Unknown Title")
        artist_name = data.get("artist", "Unknown Artist")
        elapsed_str = data.get("elapsed", "0")  # '41.426'
        duration_str = data.get("duration", "1")  # '243.800'
        service = data.get("current_service", "default").lower()
        status = data.get("status", {})
        audio_info = status.get("audio", "N/A")
        samplerate = audio_info.split(":")[0] if isinstance(audio_info, str) and ':' in audio_info else "N/A"
        bitdepth = audio_info.split(":")[1] if isinstance(audio_info, str) and ':' in audio_info else "N/A"
        volume = int(data.get("volume", 50))  # Ensure volume is an integer

        # Format samplerate and bitdepth
        if samplerate != "N/A":
            try:
                samplerate_khz = f"{int(samplerate)/1000:.1f}kHz"
            except ValueError:
                self.logger.error(f"ModernScreen: Invalid samplerate value '{samplerate}'. Setting to 'N/A'.")
                samplerate_khz = "N/A"
        else:
            samplerate_khz = "N/A"

        if bitdepth != "N/A":
            try:
                bitdepth_bit = f"{int(bitdepth)}bit"
            except ValueError:
                self.logger.error(f"ModernScreen: Invalid bitdepth value '{bitdepth}'. Setting to 'N/A'.")
                bitdepth_bit = "N/A"
        else:
            bitdepth_bit = "N/A"

        info_text = f"{samplerate_khz} / {bitdepth_bit}"
        self.logger.debug(f"Formatted info_text: '{info_text}'")

        # Convert 'elapsed' and 'duration' to float
        try:
            elapsed = float(elapsed_str)
            duration = float(duration_str)
        except (ValueError, TypeError) as e:
            self.logger.error(f"ModernScreen: Error converting time strings to float - {e}")
            elapsed = 0.0
            duration = 1.0  # Avoid division by zero

        progress = max(0, min(elapsed / duration, 1))

        # Convert elapsed and duration to mm:ss format
        current_minutes = int(elapsed // 60)
        current_seconds = int(elapsed % 60)
        total_minutes = int(duration // 60)
        total_seconds = int(duration % 60)
        current_time = f"{current_minutes}:{current_seconds:02d}"
        total_duration = f"{total_minutes}:{total_seconds:02d}"

        self.logger.debug(
            f"ModernScreen: Progress bar data: elapsed={elapsed:.2f}s, duration={duration}s, progress={progress:.2%}"
        )

        screen_width = self.display_manager.oled.width
        screen_height = self.display_manager.oled.height
        margin = 5
        max_text_width = screen_width - 2 * margin

        # Progress bar dimensions
        progress_width = int(screen_width * 0.7)
        progress_x = (screen_width - progress_width) // 2
        progress_y = margin + 55

        positions = {
            "artist": {"x": screen_width // 2, "y": margin - 8},
            "title": {"x": screen_width // 2, "y": margin + 6},
            "info": {"x": screen_width // 2, "y": margin + 25},
            "progress": {"x": screen_width // 2, "y": progress_y},
        }

        # Artist scrolling
        artist_display, self.scroll_offset_artist, artist_scrolling = self.update_scroll(
            artist_name, self.font_artist, max_text_width, self.scroll_offset_artist
        )
        if artist_scrolling:
            artist_x = (screen_width // 2) - self.scroll_offset_artist
        else:
            bbox = self.font_artist.getbbox(artist_display)
            text_width = bbox[2] - bbox[0] if bbox else 0
            artist_x = (screen_width - text_width) // 2
        artist_y = positions["artist"]["y"]

        draw.text((artist_x, artist_y), artist_display, font=self.font_artist, fill="white")
        self.logger.debug(f"ModernScreen: Artist displayed at position ({artist_x}, {artist_y}).")

        # Title scrolling
        title_display, self.scroll_offset_title, title_scrolling = self.update_scroll(
            song_title, self.font_title, max_text_width, self.scroll_offset_title
        )
        if title_scrolling:
            title_x = (screen_width // 2) - self.scroll_offset_title
        else:
            bbox = self.font_title.getbbox(title_display)
            text_width = bbox[2] - bbox[0] if bbox else 0
            title_x = (screen_width - text_width) // 2
        title_y = positions["title"]["y"] - 2

        draw.text((title_x, title_y), title_display, font=self.font_title, fill="white")
        self.logger.debug(f"ModernScreen: Title displayed at position ({title_x}, {title_y}).")

        # Sample rate and bit depth
        info_width = self.font_info.getlength(info_text) if hasattr(self.font_info, 'getlength') else (self.font_info.getbbox(info_text)[2] - self.font_info.getbbox(info_text)[0])
        info_x = (screen_width - info_width) // 2
        info_y = positions["info"]["y"] - 6
        draw.text((info_x, info_y), info_text, font=self.font_info, fill="white")
        self.logger.debug(f"ModernScreen: Info displayed at position ({info_x}, {info_y}). Text: '{info_text}'")

        # Volume icon and text
        volume_icon = self.display_manager.icons.get('volume', self.display_manager.default_icon)
        volume_icon = volume_icon.resize((10, 10), Image.LANCZOS)
        volume_icon_x = progress_x - 30
        volume_icon_y = progress_y - 22
        base_image.paste(volume_icon, (volume_icon_x, volume_icon_y))

        volume_text = f"{volume}"
        volume_text_x = volume_icon_x + 12  # Adjusted to prevent overlapping
        volume_text_y = volume_icon_y - 2
        draw.text((volume_text_x, volume_text_y), volume_text, font=self.font_info, fill="white")
        self.logger.debug(f"ModernScreen: Volume icon and text displayed at ({volume_icon_x}, {volume_icon_y}). Text: '{volume_text}'")

        # Progress bar and times
        draw.text((progress_x - 30, progress_y - 9), current_time, font=self.font_info, fill="white")
        draw.text((progress_x + progress_width + 12, progress_y - 9), total_duration, font=self.font_info, fill="white")

        draw.line([progress_x, progress_y, progress_x + progress_width, progress_y], fill="white", width=1)
        indicator_x = progress_x + int(progress_width * progress)
        draw.line([indicator_x, progress_y - 2, indicator_x, progress_y + 2], fill="white", width=1)

        # Track type icon
        track_type = data.get('trackType', 'default')
        right_icon = self.display_manager.icons.get(track_type, self.display_manager.default_icon)
        right_icon = right_icon.resize((16, 16), Image.LANCZOS)
        right_icon_x = progress_x + progress_width + 15
        right_icon_y = progress_y - 26
        base_image.paste(right_icon, (right_icon_x, right_icon_y))

        # Update the display
        self.display_manager.oled.display(base_image)
        self.logger.info("Updated display with playback details and spectrum visualisation.")

    def on_moode_state_change(self, sender, state, **kwargs):
        """Handle state changes from moode."""
        # Process only if active and mode is 'modern'
        if not self.is_active or self.mode_manager.get_mode() != "modern":
            self.logger.debug("ModernScreen: Ignoring state change; not active or wrong mode.")
            return

        self.logger.debug(f"State change received: {state}")
        with self.state_lock:
            self.latest_state = state
        self.update_event.set()

    def start_mode(self):
        """Activate ModernScreen mode with spectrum visualisation."""
        if self.mode_manager.get_mode() != "modern":
            self.logger.warning("ModernScreen: Not on the correct mode for modern playback mode.")
            return

        self.is_active = True
        self.reset_scrolling()

        # Start spectrum thread
        if not self.spectrum_thread or not self.spectrum_thread.is_alive():
            self.running_spectrum = True
            self.spectrum_thread = threading.Thread(target=self._read_fifo, daemon=True)
            self.spectrum_thread.start()
            self.logger.info("Spectrum thread started.")

        # Ensure update thread is running
        if not self.update_thread.is_alive():
            self.stop_event.clear()
            self.update_thread = threading.Thread(target=self.update_display_loop, daemon=True)
            self.update_thread.start()
            self.logger.debug("ModernScreen: Update thread restarted.")

    def stop_mode(self):
        """Deactivate ModernScreen mode and stop spectrum visualisation."""
        if not self.is_active:
            self.logger.info("ModernScreen: stop_mode called, but was not active.")
            return

        self.is_active = False
        self.stop_event.set()

        # Stop spectrum thread
        self.running_spectrum = False
        if self.spectrum_thread and self.spectrum_thread.is_alive():
            self.spectrum_thread.join(timeout=1)
            self.logger.info("Spectrum thread stopped.")

        # Stop update thread
        if self.update_thread.is_alive():
            self.update_thread.join(timeout=1)
            self.logger.debug("ModernScreen: Update thread stopped.")

        self.display_manager.clear_screen()
        self.logger.info("ModernScreen: ModernScreen mode stopped and screen cleared.")

    def display_playback_info(self):
        """Display playback information from the current state."""
        current_state = self.moode_listener.get_current_state()
        if current_state:
            self.draw_display(current_state)
        else:
            self.logger.warning("ModernScreen: No current state available.")

    # Optional: Add methods for playback controls if needed
    def toggle_play_pause(self):
        """Emit the play/pause command to moode."""
        self.logger.info("ModernScreen: Toggling play/pause.")
        if not self.moode_listener.is_connected():
            self.logger.warning("ModernScreen: Cannot toggle playback - not connected to moode.")
            self.display_error_message("Connection Error", "Not connected to moode.")
            return

        try:
            # Use MoodeListener's MPDClient to toggle play/pause
            current_state = self.moode_listener.client.status().get('state', 'stop')
            if current_state == 'play':
                self.moode_listener.client.pause(1)
                self.logger.info("ModernScreen: Playback paused.")
            else:
                self.moode_listener.client.play()
                self.logger.info("ModernScreen: Playback started.")
        except Exception as e:
            self.logger.error(f"ModernScreen: Failed to toggle play/pause - {e}")
            self.display_error_message("Playback Error", f"Could not toggle playback: {e}")

    def display_error_message(self, title, message):
        """Display an error message on the OLED screen."""
        with self.display_manager.lock:
            image = Image.new("RGB", self.display_manager.oled.size, "black")
            draw = ImageDraw.Draw(image)
            font = self.display_manager.fonts.get('error_font', ImageFont.load_default())

            # Draw title
            try:
                if hasattr(font, 'getlength'):
                    title_width = font.getlength(title)
                else:
                    bbox = font.getbbox(title)
                    title_width = bbox[2] - bbox[0] if bbox else 0
            except Exception as e:
                self.logger.error(f"ModernScreen: Error calculating title width - {e}")
                title_width = 0
            title_x = (self.display_manager.oled.width - title_width) // 2
            title_y = 10
            draw.text((title_x, title_y), title, font=font, fill="red")

            # Draw message
            try:
                if hasattr(font, 'getlength'):
                    message_width = font.getlength(message)
                else:
                    bbox = font.getbbox(message)
                    message_width = bbox[2] - bbox[0] if bbox else 0
            except Exception as e:
                self.logger.error(f"ModernScreen: Error calculating message width - {e}")
                message_width = 0
            message_x = (self.display_manager.oled.width - message_width) // 2
            message_y = title_y + 20  # Adjust spacing as needed
            draw.text((message_x, message_y), message, font=font, fill="white")

            # Convert to match the OLED mode before displaying
            image = image.convert(self.display_manager.oled.mode)
            self.display_manager.oled.display(image)
            self.logger.info(f"Displayed error message: {title} - {message}")

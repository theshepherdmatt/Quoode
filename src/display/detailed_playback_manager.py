# src/managers/detailed_playback_manager.py

from managers.base_manager import BaseManager
import logging
from PIL import Image, ImageDraw, ImageFont
import threading
import time


class DetailedPlaybackManager(BaseManager):
    def __init__(self, display_manager, volumio_listener, mode_manager):
        super().__init__(display_manager, volumio_listener, mode_manager)
        self.mode_name = "detailed_playback"
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)

        # Fonts
        self.font_title = self.display_manager.fonts.get('song_font', ImageFont.load_default())
        self.font_artist = self.display_manager.fonts.get('artist_font', ImageFont.load_default())
        self.font_info = self.display_manager.fonts.get('data_font', ImageFont.load_default())
        self.font_progress = self.display_manager.fonts.get('progress_bar', ImageFont.load_default())

        # Scrolling attributes
        self.scroll_offset_title = 0
        self.scroll_offset_artist = 0
        self.scroll_speed = 2  # Adjust for faster or slower scrolling
        # Removed scroll_pause and related counters for continuous scrolling

        # State attributes
        self.latest_state = None
        self.current_state = None  # Persistent current state
        self.state_lock = threading.Lock()
        self.update_event = threading.Event()
        self.stop_event = threading.Event()

        # Update thread
        self.update_thread = threading.Thread(target=self.update_display_loop, daemon=True)
        self.update_thread.start()
        self.logger.info("DetailedPlaybackManager: Started background update thread.")

        # Volumio state change listener
        self.volumio_listener.state_changed.connect(self.on_volumio_state_change)
        self.logger.info("DetailedPlaybackManager initialized.")

    # Removed set_volume_overlay_manager method

    def reset_scrolling(self):
        """Reset scrolling parameters."""
        self.logger.debug("DetailedPlaybackManager: Resetting scrolling offsets.")
        self.scroll_offset_title = 0
        self.scroll_offset_artist = 0

    def update_scroll(self, text, font, max_width, scroll_offset):
        """Update scrolling offset for continuous scrolling."""
        text_width, _ = font.getsize(text)

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
                elif self.current_state and "seek" in self.current_state and "duration" in self.current_state:
                    # Simulate seek progress
                    elapsed_time = time.time() - last_update_time
                    self.current_state["seek"] += int(elapsed_time * 1000)  # Increment seek by elapsed ms
                    last_update_time = time.time()

            if self.is_active and self.mode_manager.screen_manager.get_current_screen() == "detailed_playback" and self.current_state:
                # Since VolumeOverlayManager is removed, always redraw the playback screen
                self.logger.debug("DetailedPlaybackManager: Redrawing playback screen.")
                self.draw_display(self.current_state)

    def draw_display(self, data):
        """Draw the detailed playback display with smooth and continuous scrolling."""
        if data is None:
            self.logger.warning("DetailedPlaybackManager: No data provided for display.")
            return

        base_image = Image.new("RGB", self.display_manager.oled.size, "black")
        draw = ImageDraw.Draw(base_image)

        # Extract information
        song_title = data.get("title", "Unknown Title")
        artist_name = data.get("artist", "Unknown Artist")
        seek = data.get("seek", 0) / 1000  # Convert from ms to seconds
        duration = data.get("duration", 1)  # Avoid division by zero
        progress = max(0, min(seek / duration, 1))  # Calculate progress and clamp it between 0 and 1
        service = data.get("service", "default")
        samplerate = data.get("samplerate", "N/A")
        bitdepth = data.get("bitdepth", "N/A")
        volume = data.get("volume", 50)  # Default volume to 50 if not available

        # Convert seek and duration to minutes and seconds for display
        current_minutes = int(seek // 60)
        current_seconds = int(seek % 60)
        total_minutes = int(duration // 60)
        total_seconds = int(duration % 60)

        # Format seek and duration times for display
        current_time = f"{current_minutes}:{current_seconds:02d}"
        total_duration = f"{total_minutes}:{total_seconds:02d}"

        # Log progress bar data
        self.logger.error(
            f"DetailedPlaybackManager: Progress bar data: seek={seek:.2f}s, duration={duration}s, progress={progress:.2%}"
        )

        screen_width = self.display_manager.oled.width
        screen_height = self.display_manager.oled.height
        margin = 5
        max_text_width = screen_width - 2 * margin  # Full width for centering

        # **Calculate Progress Bar Dimensions and Position** (move this earlier)
        progress_width = int(screen_width * 0.7)  # 70% of screen width
        progress_x = (screen_width - progress_width) // 2
        progress_y = margin + 50  # Updated fixed position for progress bar to avoid using `positions` later

        # **Define Positions for Each Element**
        positions = {
            "artist": {"x": screen_width // 2, "y": margin - 8},
            "title": {"x": screen_width // 2, "y": margin + 6},
            "info": {"x": screen_width // 2, "y": margin + 25},
            "progress": {"x": screen_width // 2, "y": progress_y},
        }

        # **B. Draw Artist Name with Continuous Scrolling**
        artist_display, self.scroll_offset_artist, artist_scrolling = self.update_scroll(
            artist_name, self.font_artist, max_text_width, self.scroll_offset_artist
        )
        artist_x = positions["artist"]["x"]
        artist_y = positions["artist"]["y"]

        if artist_scrolling:
            draw.text((artist_x - self.scroll_offset_artist, artist_y), artist_display, font=self.font_artist, fill="white")
            draw.text((artist_x - self.scroll_offset_artist + self.font_artist.getsize(artist_display)[0] + 20, artist_y), artist_display, font=self.font_artist, fill="white")
        else:
            artist_width, artist_height = self.font_artist.getsize(artist_display)
            artist_x = (screen_width - artist_width) // 2
            draw.text((artist_x, artist_y), artist_display, font=self.font_artist, fill="white")
        self.logger.debug(f"DetailedPlaybackManager: Artist displayed at position ({artist_x}, {artist_y}).")

        # **C. Draw Song Title with Continuous Scrolling**
        title_display, self.scroll_offset_title, title_scrolling = self.update_scroll(
            song_title, self.font_title, max_text_width, self.scroll_offset_title
        )
        title_x = positions["title"]["x"]
        title_y = positions["title"]["y"]

        if title_scrolling:
            draw.text((title_x - self.scroll_offset_title, title_y), title_display, font=self.font_title, fill="white")
            draw.text((title_x - self.scroll_offset_title + self.font_title.getsize(title_display)[0] + 20, title_y), title_display, font=self.font_title, fill="white")
        else:
            title_width, title_height = self.font_title.getsize(title_display)
            title_x = (screen_width - title_width) // 2
            draw.text((title_x, title_y), title_display, font=self.font_title, fill="white")
        self.logger.debug(f"DetailedPlaybackManager: Title displayed at position ({title_x}, {title_y}).")

        # **D. Draw Sample Rate and Bit Depth**
        info_text = f"{samplerate} / {bitdepth}"
        info_width, info_height = self.font_info.getsize(info_text)
        info_x = (screen_width - info_width) // 2
        info_y = positions["info"]["y"]
        draw.text((info_x, info_y), info_text, font=self.font_info, fill="white")
        self.logger.debug(f"DetailedPlaybackManager: Info displayed at position ({info_x}, {info_y}).")

        # **E. Draw Volume Icon and Data**
        volume_icon = self.display_manager.icons.get('volume', self.display_manager.default_icon)
        volume_icon = volume_icon.resize((10, 10), Image.LANCZOS)  # Resize to 10x10 px
        volume_icon_x = progress_x - 30  # Adjust the position to be left of the progress bar
        volume_icon_y = progress_y - 22  # Above the progress bar

        # Paste the volume icon
        base_image.paste(volume_icon, (volume_icon_x, volume_icon_y))

        # Draw volume level next to the icon
        volume_text = f"{volume}"
        volume_text_x = volume_icon_x + 10
        volume_text_y = volume_icon_y - 2
        draw.text((volume_text_x, volume_text_y), volume_text, font=self.font_info, fill="white")
        self.logger.debug(f"DetailedPlaybackManager: Volume icon and text displayed at ({volume_icon_x}, {volume_icon_y}).")

        # **F. Draw Progress Bar with Seek and Duration**
        # Draw current time on the left of the progress bar
        draw.text(
            (progress_x - 30, progress_y - 9),  # Adjust as needed to position correctly
            current_time,
            font=self.font_info,
            fill="white"
        )

        # Draw total duration on the right of the progress bar
        draw.text(
            (progress_x + progress_width + 12, progress_y - 9),  # Adjust as needed to position correctly
            total_duration,
            font=self.font_info,
            fill="white"
        )

        # Draw progress bar as a single line
        draw.line(
            [progress_x, progress_y, progress_x + progress_width, progress_y],
            fill="white", width=1
        )

        # Calculate the position of the moving line based on the progress value
        indicator_x = progress_x + int(progress_width * progress)

        # Draw a small vertical line to indicate progress
        draw.line(
            [indicator_x, progress_y - 2, indicator_x, progress_y + 2],
            fill="white", width=1
        )

        # **G. Draw Right-Side Icon Above Duration (Optional)**
        track_type = data.get('trackType', 'default')  # Use 'trackType' from Volumio data, fall back to 'default' if not available
        right_icon = self.display_manager.icons.get(track_type, self.display_manager.default_icon)
        right_icon = right_icon.resize((16, 16), Image.LANCZOS)  # Resize to 10x10 px
        right_icon_x = progress_x + progress_width + 15
        right_icon_y = progress_y - 26
        base_image.paste(right_icon, (right_icon_x, right_icon_y))

        # **H. Display the Final Image**
        self.display_manager.oled.display(base_image)
        self.logger.info("DetailedPlaybackManager: Updated display with volume icon, scrolling text, progress bar, and service icon.")

    def on_volumio_state_change(self, sender, state):
        """Handle state changes from Volumio."""
        if not self.is_active or self.mode_manager.screen_manager.get_current_screen() != "detailed_playback":
            self.logger.debug("DetailedPlaybackManager: Ignoring state change; not active or wrong screen.")
            return

        self.logger.debug(f"State change received: {state}")
        with self.state_lock:
            self.latest_state = state
        self.update_event.set()

    def start_mode(self):
        """Activate the detailed playback mode."""
        if self.mode_manager.screen_manager.get_current_screen() != "detailed_playback":
            self.logger.warning("DetailedPlaybackManager: Attempted to start, but the screen is not 'detailed_playback'.")
            return

        self.is_active = True
        self.reset_scrolling()
        self.logger.info("DetailedPlaybackManager: Started detailed playback mode.")

        # Start the update thread
        if not self.update_thread.is_alive():
            self.stop_event.clear()
            self.update_thread = threading.Thread(target=self.update_display_loop, daemon=True)
            self.update_thread.start()

    def stop_mode(self):
        """Deactivate the detailed playback mode."""
        if not self.is_active:
            self.logger.info("DetailedPlaybackManager: Already stopped.")
            return

        self.is_active = False
        self.stop_event.set()
        if self.update_thread.is_alive():
            self.update_thread.join(timeout=1)
            if self.update_thread.is_alive():
                self.logger.warning("DetailedPlaybackManager: Failed to terminate update thread.")

        self.display_manager.clear_screen()
        self.logger.info("DetailedPlaybackManager: Stopped detailed playback mode and cleared the screen.")

    def display_playback_info(self):
        """Display playback information from the current state."""
        current_state = self.volumio_listener.get_current_state()
        if current_state:
            self.draw_display(current_state)
        else:
            self.logger.warning("DetailedPlaybackManager: No current state available.")

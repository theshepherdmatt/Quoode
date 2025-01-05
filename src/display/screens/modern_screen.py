# src/managers/modern_screen.py

from managers.menus.base_manager import BaseManager
import logging
from PIL import Image, ImageDraw, ImageFont
import threading
import time

class ModernScreen(BaseManager):
    def __init__(self, display_manager, moode_listener, mode_manager):
        super().__init__(display_manager, moode_listener, mode_manager)
        self.moode_listener = moode_listener  # Explicitly assign moode_listener
        self.mode_manager = mode_manager
        self.mode_name = "modern"  # Align with ModeManager's state
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

    def adjust_volume(self, delta):
        """
        Adjust volume by the given delta. 
        Uses the moode_listener's MPD client to set the new volume.
        """
        if not self.moode_listener.is_connected():
            self.logger.warning("ModernScreen: Cannot adjust volume - not connected to moode.")
            return

        try:
            status = self.moode_listener.client.status()
            current_volume = int(status.get('volume', 50))  # Fallback to 50 if missing
            new_volume = current_volume + delta
            # Clamp between 0 and 100
            new_volume = max(0, min(100, new_volume))
            self.moode_listener.client.setvol(new_volume)
            self.logger.info(
                f"ModernScreen: Volume changed from {current_volume} to {new_volume}"
            )
        except Exception as e:
            self.logger.error(f"ModernScreen: Failed to adjust volume - {e}")

    def reset_scrolling(self):
        """Reset scrolling parameters."""
        self.logger.debug("ModernScreen: Resetting scrolling offsets.")
        self.scroll_offset_title = 0
        self.scroll_offset_artist = 0

    def update_scroll(self, text, font, max_width, scroll_offset):
        """Update scrolling offset for continuous scrolling."""
        try:
            text_width = font.getlength(text)
        except AttributeError:
            # Fallback for older Pillow versions
            bbox = font.getbbox(text)
            text_width = bbox[2] - bbox[0] if bbox else 0

        if text_width <= max_width:
            return text, 0, False

        scroll_offset += self.scroll_speed
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
                elif self.current_state and "elapsed" in self.current_state and "duration" in self.current_state:
                    # Simulate seek progress
                    elapsed_time = time.time() - last_update_time
                    try:
                        self.current_state["elapsed"] = float(self.current_state["elapsed"]) + elapsed_time
                        last_update_time = time.time()
                    except ValueError:
                        self.current_state["elapsed"] = 0.0

            # Only draw if active, in modern mode, and we have current_state
            if self.is_active and self.mode_manager.get_mode() == "modern" and self.current_state:
                self.draw_display(self.current_state)

    def draw_display(self, data):
        """Draw the ModernScreen display with smooth and continuous scrolling."""
        if data is None:
            return

        base_image = Image.new("RGB", self.display_manager.oled.size, "black")
        draw = ImageDraw.Draw(base_image)

        # Extract information
        song_title = data.get("title", "Unknown Title")
        artist_name = data.get("artist", "Unknown Artist")
        elapsed_str = data.get("elapsed", "0")
        duration_str = data.get("duration", "1")
        service = data.get("current_service", "default").lower()
        status = data.get("status", {})
        audio_info = status.get("audio", "N/A")
        samplerate = audio_info.split(":")[0] if ":" in audio_info else "N/A"
        bitdepth = audio_info.split(":")[1] if ":" in audio_info else "N/A"
        volume = int(data.get("volume", 50))

        # Format samplerate/bitdepth
        if samplerate != "N/A":
            try:
                samplerate_khz = f"{int(samplerate)/1000:.1f}kHz"
            except ValueError:
                samplerate_khz = "N/A"
        else:
            samplerate_khz = "N/A"

        if bitdepth != "N/A":
            try:
                bitdepth_bit = f"{int(bitdepth)}bit"
            except ValueError:
                bitdepth_bit = "N/A"
        else:
            bitdepth_bit = "N/A"

        info_text = f"{samplerate_khz} / {bitdepth_bit}"

        try:
            elapsed = float(elapsed_str)
            duration = float(duration_str)
        except (ValueError, TypeError):
            elapsed = 0.0
            duration = 1.0

        progress = max(0, min(elapsed / duration, 1))

        # Convert elapsed/duration to mm:ss
        current_minutes = int(elapsed // 60)
        current_seconds = int(elapsed % 60)
        total_minutes = int(duration // 60)
        total_seconds = int(duration % 60)
        current_time = f"{current_minutes}:{current_seconds:02d}"
        total_duration = f"{total_minutes}:{total_seconds:02d}"

        screen_width = self.display_manager.oled.width
        screen_height = self.display_manager.oled.height
        margin = 5
        max_text_width = screen_width - 2 * margin

        # Progress bar dims
        progress_width = int(screen_width * 0.7)
        progress_x = (screen_width - progress_width) // 2
        progress_y = margin + 55

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
        artist_y = (margin - 6)

        draw.text((artist_x, artist_y), artist_display, font=self.font_artist, fill="white")

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
        title_y = margin + 10 - 2

        draw.text((title_x, title_y), title_display, font=self.font_title, fill="white")

        # Info text (sample rate / bit depth)
        try:
            if hasattr(self.font_info, "getlength"):
                info_width = self.font_info.getlength(info_text)
            else:
                bbox = self.font_info.getbbox(info_text)
                info_width = bbox[2] - bbox[0] if bbox else 0
        except Exception as e:
            self.logger.error(f"ModernScreen: Error calculating info_text width - {e}")
            info_width = 0

        info_x = (screen_width - info_width) // 2
        info_y = margin + 32 - 6
        draw.text((info_x, info_y), info_text, font=self.font_info, fill="white")

        # Volume icon and text
        volume_icon = self.display_manager.icons.get("volume", self.display_manager.default_icon)
        volume_icon = volume_icon.resize((10, 10), Image.LANCZOS)
        volume_icon_x = progress_x - 32
        volume_icon_y = (progress_y - 22) - 2
        base_image.paste(volume_icon, (volume_icon_x, volume_icon_y))

        volume_text = f"{volume}"
        volume_text_x = volume_icon_x + 10
        volume_text_y = volume_icon_y - 2
        draw.text((volume_text_x, volume_text_y), volume_text, font=self.font_info, fill="white")

        # Current time & total duration next to progress bar
        draw.text((progress_x - 30, progress_y - 10), current_time, font=self.font_info, fill="white")
        draw.text((progress_x + progress_width + 12, progress_y - 10), total_duration, font=self.font_info, fill="white")

        # Draw the main progress bar
        progress_box_height = 4
        num_squares = 20
        outer_box = [
            progress_x,
            progress_y - progress_box_height,
            progress_x + progress_width,
            progress_y
        ]
        draw.rectangle(outer_box, outline="white", fill=None)

        # Fill squares for progress
        filled_squares = int(num_squares * progress)
        square_total_width = progress_width / num_squares
        square_spacing = 2
        square_fill_width = square_total_width - square_spacing

        for i in range(num_squares):
            left_edge = (progress_x + 1) + i * square_total_width
            right_edge = left_edge + square_fill_width
            square_box = [
                left_edge,
                (progress_y - progress_box_height) + 1,
                right_edge,
                progress_y - 1
            ]
            if i < filled_squares:
                draw.rectangle(square_box, outline=None, fill="#aaaaaa")
            else:
                draw.rectangle(square_box, outline=None, fill="black")

        # Service icon
        icon = self.display_manager.icons.get(service, self.display_manager.default_icon)
        if icon.size != (22, 22):
            icon = icon.resize((22, 22), Image.BICUBIC)
        if icon.mode == "RGBA":
            bg = Image.new("RGB", icon.size, (0, 0, 0))
            bg.paste(icon, mask=icon.split()[3])
            icon = bg
        right_icon_x = progress_x + progress_width + 10
        right_icon_y = progress_y - 30
        base_image.paste(icon, (right_icon_x, right_icon_y))

        # Finally update the screen
        self.display_manager.oled.display(base_image)

    def on_moode_state_change(self, sender, state, **kwargs):
        """Handle state changes from moode."""
        # Only process if active and currently in 'modern' mode
        if not self.is_active or self.mode_manager.get_mode() != "modern":
            return

        self.logger.debug(f"State change received: {state}")

        new_elapsed_str = state.get('elapsed', '0')
        status_dict = state.get("status", {})
        mpd_state = status_dict.get('state', '').lower()

        try:
            new_elapsed = float(new_elapsed_str)
        except ValueError:
            new_elapsed = 0.0

        new_id = state.get('id')
        old_id = None
        old_elapsed = 0.0

        with self.state_lock:
            if self.current_state and "elapsed" in self.current_state:
                old_id = self.current_state.get('id')
                old_elapsed = float(self.current_state.get('elapsed', 0.0))

            track_changed = (new_id is not None and new_id != old_id)

            if mpd_state == "play" and new_elapsed <= old_elapsed and not track_changed:
                self.logger.debug(
                    f"Ignoring new elapsed={new_elapsed} because old_elapsed={old_elapsed}, "
                    f"mpd_state=play, same track ID={old_id}."
                )
                return

            if track_changed:
                self.logger.debug(
                    f"Track changed (old_id={old_id}, new_id={new_id}); accepting smaller elapsed "
                    f"{new_elapsed} for new track."
                )
            else:
                self.logger.debug(
                    f"Accepting new elapsed={new_elapsed} (old_elapsed={old_elapsed}), mpd_state={mpd_state}."
                )

            self.latest_state = state

        # Trigger the update thread
        self.update_event.set()

    def start_mode(self):
        """Activate ModernScreen mode."""
        if self.mode_manager.get_mode() != "modern":
            self.logger.warning("ModernScreen: Not on the correct mode for modern playback mode.")
            return

        self.is_active = True
        self.reset_scrolling()

        # Ensure update thread is running
        if not self.update_thread.is_alive():
            self.stop_event.clear()
            self.update_thread = threading.Thread(target=self.update_display_loop, daemon=True)
            self.update_thread.start()
            self.logger.debug("ModernScreen: Update thread restarted.")

    def stop_mode(self):
        """Deactivate ModernScreen mode and stop its thread."""
        if not self.is_active:
            self.logger.info("ModernScreen: stop_mode called, but was not active.")
            return

        self.is_active = False
        self.stop_event.set()

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

    def toggle_play_pause(self):
        """Emit the play/pause command to moode."""
        self.logger.info("ModernScreen: Toggling play/pause.")
        if not self.moode_listener.is_connected():
            self.logger.warning("ModernScreen: Cannot toggle playback - not connected to moode.")
            self.display_error_message("Connection Error", "Not connected to moode.")
            return

        try:
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

            # Title
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

            # Message
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
            message_y = title_y + 20
            draw.text((message_x, message_y), message, font=font, fill="white")

            image = image.convert(self.display_manager.oled.mode)
            self.display_manager.oled.display(image)
            self.logger.info(f"Displayed error message: {title} - {message}")


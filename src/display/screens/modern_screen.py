# src/managers/modern_screen.py

import os
import logging
import threading
import time
from PIL import Image, ImageDraw, ImageFont
from managers.menus.base_manager import BaseManager

class ModernScreen(BaseManager):
    def __init__(self, display_manager, moode_listener, mode_manager):
        super().__init__(display_manager, moode_listener, mode_manager)
        self.moode_listener = moode_listener
        self.mode_manager = mode_manager
        self.mode_name = "modern"  
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)

        # Fonts
        self.font_title = display_manager.fonts.get('song_font', ImageFont.load_default())
        self.font_artist = display_manager.fonts.get('artist_font', ImageFont.load_default())
        self.font_info = display_manager.fonts.get('data_font', ImageFont.load_default())
        self.font_progress = display_manager.fonts.get('progress_bar', ImageFont.load_default())

        # Scrolling
        self.scroll_offset_title = 0
        self.scroll_offset_artist = 0
        self.scroll_speed = 1  # Use smaller increments for smoother scrolling

        # State
        self.latest_state = None
        self.current_state = None
        self.state_lock = threading.Lock()
        self.update_event = threading.Event()
        self.stop_event = threading.Event()

        # Update thread
        self.update_thread = threading.Thread(target=self.update_display_loop, daemon=True)
        self.update_thread.start()
        self.logger.info("ModernScreen: Started background update thread.")

        # moode listener
        self.moode_listener.state_changed.connect(self.on_moode_state_change)
        self.logger.info("ModernScreen initialized.")

    def adjust_volume(self, delta):
        """Adjust volume by the given delta."""
        if not self.moode_listener.is_connected():
            self.logger.warning("ModernScreen: Not connected to moode; cannot adjust volume.")
            return
        try:
            status = self.moode_listener.client.status()
            current_vol = int(status.get('volume', 50))
            new_vol = max(0, min(100, current_vol + delta))
            self.moode_listener.client.setvol(new_vol)
            self.logger.info(f"ModernScreen: Volume changed from {current_vol} to {new_vol}")
        except Exception as e:
            self.logger.error(f"ModernScreen: Failed to adjust volume - {e}")

    def reset_scrolling(self):
        """Reset scrolling offsets."""
        self.logger.debug("ModernScreen: Resetting scrolling offsets.")
        self.scroll_offset_title = 0
        self.scroll_offset_artist = 0

    def update_scroll(self, text, font, max_width, scroll_offset):
        """Scrolling logic for continuous text scrolling."""
        try:
            text_width = font.getlength(text)
        except AttributeError:
            bbox = font.getbbox(text)
            text_width = (bbox[2] - bbox[0]) if bbox else 0

        if text_width <= max_width:
            return text, 0, False

        scroll_offset += self.scroll_speed
        if scroll_offset > text_width:
            scroll_offset = 0
        return text, scroll_offset, True

    def update_display_loop(self):
        """Background loop to update the display (including scrolling + progress)."""
        last_update_time = time.time()
        while not self.stop_event.is_set():
            triggered = self.update_event.wait(timeout=0.03)  # ~33 FPS
            with self.state_lock:
                if triggered and self.latest_state:
                    self.current_state = self.latest_state.copy()
                    self.latest_state = None
                    self.update_event.clear()
                    last_update_time = time.time()
                elif (
                    self.current_state
                    and "elapsed" in self.current_state
                    and "duration" in self.current_state
                ):
                    # If not webradio, increment elapsed for local track progress
                    service = self.current_state.get("current_service", "").lower()
                    if service != "webradio":
                        elapsed_time = time.time() - last_update_time
                        try:
                            self.current_state["elapsed"] = float(self.current_state["elapsed"]) + elapsed_time
                        except ValueError:
                            self.current_state["elapsed"] = 0.0
                        last_update_time = time.time()

            if self.is_active and self.mode_manager.get_mode() == "modern" and self.current_state:
                self.draw_display(self.current_state)

    def draw_display(self, data):
        """
        Draw the ModernScreen:
          - For webradio => NO progress bar or seek/duration;
            also shift the artist/title downward to fill that gap.
          - For others => normal progress bar (drawn above the bottom row) + standard top positioning for artist/title
        """
        if not data:
            return

        base_image = Image.new("RGB", self.display_manager.oled.size, "black")
        draw = ImageDraw.Draw(base_image)

        # Basic info
        song_title = data.get("title", "Unknown Title")
        artist_name = data.get("artist", "Unknown Artist")
        service = data.get("current_service", "default").lower()

        # If the user is on webradio => interpret data["name"] as the station,
        # and data["title"] as the current track
        if service == "webradio":
            artist_name = data.get("name", "Unknown Station")
            song_title  = data.get("title", "Unknown Title")

        status = data.get("status", {})
        audio_info = status.get("audio", "N/A")
        samplerate = audio_info.split(":")[0] if ":" in audio_info else "N/A"
        bitdepth   = audio_info.split(":")[1] if ":" in audio_info else "N/A"
        volume     = int(data.get("volume", 50))


        # Convert samplerate/bitdepth
        samplerate_khz = "N/A"
        bitdepth_bit   = "N/A"
        try:
            if samplerate != "N/A":
                samplerate_khz = f"{int(samplerate)/1000:.1f}kHz"
            if bitdepth != "N/A":
                bitdepth_bit = f"{int(bitdepth)}bit"
        except ValueError:
            pass
        info_text = f"{samplerate_khz} / {bitdepth_bit}"

        screen_width  = self.display_manager.oled.width
        screen_height = self.display_manager.oled.height
        margin        = 5
        max_text_width = screen_width - 2 * margin

        # Decide if we shift artist/title down for webradio
        if service == "webradio":
            # SHIFT them down 15-20px from normal
            artist_y = margin + 1
            title_y  = artist_y + 14
        else:
            # Normal positions
            artist_y = margin - 6
            title_y  = margin + 10 - 2

        # --- Artist scrolling ---
        artist_display, self.scroll_offset_artist, artist_scrolling = self.update_scroll(
            artist_name, self.font_artist, max_text_width, self.scroll_offset_artist
        )
        if artist_scrolling:
            artist_x = (screen_width // 2) - self.scroll_offset_artist
        else:
            bbox = self.font_artist.getbbox(artist_display)
            text_width = (bbox[2] - bbox[0]) if bbox else 0
            artist_x   = (screen_width - text_width) // 2

        draw.text((artist_x, artist_y), artist_display, font=self.font_artist, fill="white")

        # --- Title scrolling ---
        title_display, self.scroll_offset_title, title_scrolling = self.update_scroll(
            song_title, self.font_title, max_text_width, self.scroll_offset_title
        )
        if title_scrolling:
            title_x = (screen_width // 2) - self.scroll_offset_title
        else:
            bbox = self.font_title.getbbox(title_display)
            text_width = (bbox[2] - bbox[0]) if bbox else 0
            title_x    = (screen_width - text_width) // 2

        draw.text((title_x, title_y), title_display, font=self.font_title, fill="white")

        # If NOT webradio => progress bar
        if service != "webradio":
            self.draw_progress_bar(draw, data, base_image)

        # Bottom row: volume icon & text (left), samplerate/bitdepth (center), service icon (right)
        # Volume icon
        volume_icon = self.display_manager.icons.get("volume", self.display_manager.default_icon)
        volume_icon = volume_icon.resize((10, 10))

        icon_x = margin
        icon_y = screen_height - (margin + 12)
        base_image.paste(volume_icon, (icon_x, icon_y))

        # Volume text
        vol_text = str(volume)
        text_x   = icon_x + 12
        text_y   = icon_y - 2
        draw.text((text_x, text_y), vol_text, font=self.font_info, fill="white")

        # Samplerate/bitdepth in bottom center
        try:
            if hasattr(self.font_info, "getlength"):
                info_width = self.font_info.getlength(info_text)
            else:
                bbox = self.font_info.getbbox(info_text)
                info_width = (bbox[2] - bbox[0]) if bbox else 0
        except Exception as e:
            self.logger.error(f"ModernScreen: error measuring info_text width - {e}")
            info_width = 0

        info_x = (screen_width - info_width) // 2
        info_y = screen_height - (margin + 15)
        draw.text((info_x, info_y), info_text, font=self.font_info, fill="white")

        # Service icon on bottom-right
        service_icon = self.display_manager.icons.get(service, self.display_manager.default_icon)
        if service_icon.size != (22, 22):
            service_icon = service_icon.resize((22, 22))
        # If it has alpha
        if service_icon.mode == "RGBA":
            bg = Image.new("RGB", service_icon.size, (0, 0, 0))
            bg.paste(service_icon, mask=service_icon.split()[3])
            service_icon = bg

        s_icon_x = screen_width - margin - 22
        s_icon_y = (screen_height - margin - 22) + 5
        base_image.paste(service_icon, (s_icon_x, s_icon_y))

        # Finally update screen
        self.display_manager.oled.display(base_image)

    def draw_progress_bar(self, draw, data, base_image):
        """
        Draw a progress bar + track times for non-webradio.
        Placed ~2/3 down from top (or wherever you like).
        """
        screen_width  = self.display_manager.oled.width
        screen_height = self.display_manager.oled.height
        margin        = 5

        elapsed_str  = data.get("elapsed", "0")
        duration_str = data.get("duration", "1")
        try:
            elapsed  = float(elapsed_str)
            duration = float(duration_str)
        except (ValueError, TypeError):
            elapsed  = 0.0
            duration = 1.0

        progress = max(0, min(elapsed / duration, 1))

        # Times
        cur_min = int(elapsed // 60)
        cur_sec = int(elapsed % 60)
        tot_min = int(duration // 60)
        tot_sec = int(duration % 60)
        current_time   = f"{cur_min}:{cur_sec:02d}"
        total_duration = f"{tot_min}:{tot_sec:02d}"

        progress_width = int(screen_width * 0.7)
        progress_box_h = 4
        progress_x     = (screen_width - progress_width) // 2
        progress_y     = int(screen_height * 0.62)  # e.g. 62% from top

        # Times next to bar
        draw.text((progress_x - 30, progress_y - 10), current_time, font=self.font_info, fill="white")
        draw.text((progress_x + progress_width + 12, progress_y - 10), 
                  total_duration, font=self.font_info, fill="white")

        # Outer box
        outer_box = [
            progress_x,
            progress_y - progress_box_h,
            progress_x + progress_width,
            progress_y
        ]
        draw.rectangle(outer_box, outline="white", fill=None)

        # Fill squares
        num_squares        = 20
        filled_squares     = int(num_squares * progress)
        square_total_width = progress_width / num_squares
        square_spacing     = 2
        square_fill_width  = square_total_width - square_spacing

        for i in range(num_squares):
            left_edge  = (progress_x + 1) + i * square_total_width
            right_edge = left_edge + square_fill_width
            square_box = [
                left_edge,
                (progress_y - progress_box_h) + 1,
                right_edge,
                progress_y - 1
            ]
            if i < filled_squares:
                draw.rectangle(square_box, outline=None, fill="#aaaaaa")
            else:
                draw.rectangle(square_box, outline=None, fill="black")

    def on_moode_state_change(self, sender, state, **kwargs):
        """Handle moOde state changes if in 'modern' mode."""
        if not self.is_active or self.mode_manager.get_mode() != "modern":
            return
        self.logger.debug(f"State change: {state}")

        with self.state_lock:
            self.latest_state = state

        self.update_event.set()

    def start_mode(self):
        """Activate the ModernScreen mode."""
        if self.mode_manager.get_mode() != "modern":
            self.logger.warning("ModernScreen: Not on 'modern' mode to start.")
            return

        self.is_active = True
        self.reset_scrolling()

        if not self.update_thread.is_alive():
            self.stop_event.clear()
            self.update_thread = threading.Thread(target=self.update_display_loop, daemon=True)
            self.update_thread.start()
            self.logger.debug("ModernScreen: Update thread restarted.")

    def stop_mode(self):
        """Deactivate ModernScreen mode."""
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
        """If needed, manually display the current state once."""
        current_state = self.moode_listener.get_current_state()
        if current_state:
            self.draw_display(current_state)
        else:
            self.logger.warning("ModernScreen: No current state available.")

    def toggle_play_pause(self):
        """Emit a play/pause command to moOde."""
        self.logger.info("ModernScreen: Toggling play/pause.")
        if not self.moode_listener.is_connected():
            self.logger.warning("ModernScreen: Not connected to moode.")
            self.display_error_message("Connection Error", "Not connected to moode.")
            return
        try:
            curr_state = self.moode_listener.client.status().get('state', 'stop')
            if curr_state == 'play':
                self.moode_listener.client.pause(1)
                self.logger.info("ModernScreen: Playback paused.")
            else:
                self.moode_listener.client.play()
                self.logger.info("ModernScreen: Playback started.")
        except Exception as e:
            self.logger.error(f"ModernScreen: toggle_play_pause failed - {e}")
            self.display_error_message("Playback Error", f"Could not toggle playback: {e}")

    def display_error_message(self, title, message):
        """Show an error message on the screen."""
        with self.display_manager.lock:
            image = Image.new("RGB", self.display_manager.oled.size, "black")
            draw = ImageDraw.Draw(image)
            font = self.display_manager.fonts.get('error_font', ImageFont.load_default())

            try:
                title_width = font.getlength(title)
            except AttributeError:
                bbox = font.getbbox(title)
                title_width = (bbox[2] - bbox[0]) if bbox else 0

            title_x = (self.display_manager.oled.width - title_width) // 2
            title_y = 10
            draw.text((title_x, title_y), title, font=font, fill="red")

            try:
                message_width = font.getlength(message)
            except AttributeError:
                bbox = font.getbbox(message)
                message_width = (bbox[2] - bbox[0]) if bbox else 0

            message_x = (self.display_manager.oled.width - message_width) // 2
            message_y = title_y + 20
            draw.text((message_x, message_y), message, font=font, fill="white")

            final_img = image.convert(self.display_manager.oled.mode)
            self.display_manager.oled.display(final_img)
            self.logger.info(f"Displayed error: {title} => {message}")

# src/managers/menus/original_screen.py

import logging
import re
import threading
import time
from PIL import Image, ImageDraw, ImageFont

from managers.menus.base_manager import BaseManager

class OriginalScreen(BaseManager):
    def __init__(self, display_manager, moode_listener, mode_manager):
        super().__init__(display_manager, moode_listener, mode_manager)
        self.mode_manager   = mode_manager
        self.moode_listener = moode_listener
        self.logger         = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)

        self.previous_service = None

        # State management
        self.latest_state  = None
        self.state_lock    = threading.Lock()
        self.update_event  = threading.Event()
        self.stop_event    = threading.Event()
        self.is_active     = False

        # Background update thread
        self.update_thread = threading.Thread(target=self.update_display_loop, daemon=True)
        self.update_thread.start()
        self.logger.info("OriginalScreen: Started background update thread.")

        # MoodeListener callback
        self.moode_listener.state_changed.connect(self.on_moode_state_change)
        self.logger.info("OriginalScreen initialized.")

    def on_moode_state_change(self, sender, state, **kwargs):
        """
        Callback for MoodeListener state changes.
        Only process if active & in 'original' mode, ignoring webradio states.
        """
        # If not active or not in 'original' mode, skip
        if not self.is_active or self.mode_manager.get_mode() != "original":
            self.logger.debug(
                "OriginalScreen: Ignoring state change since not active or not in 'original' mode."
            )
            return

        # If the service is webradio, ignore
        if state.get("current_service", "").lower() == "webradio":
            self.logger.debug("OriginalScreen: Ignoring state change for webradio service.")
            return

        # If ModeManager is suppressing changes, skip
        if self.mode_manager and self.mode_manager.is_state_change_suppressed():
            self.logger.debug("OriginalScreen: State change suppressed, not updating display.")
            return

        self.logger.debug(f"OriginalScreen: Received state change from {sender}: {state}")
        with self.state_lock:
            self.latest_state = state
        self.update_event.set()
        self.logger.debug("OriginalScreen: Signaled update thread with new state.")

    def update_display_loop(self):
        """Wait for state changes and update the display at a controlled rate."""
        while not self.stop_event.is_set():
            triggered = self.update_event.wait(timeout=0.1)
            if triggered:
                with self.state_lock:
                    state_to_process = self.latest_state
                    self.latest_state = None
                self.update_event.clear()

                # Only update if active and in 'original' mode
                if self.is_active and self.mode_manager.get_mode() == "original":
                    if state_to_process:
                        # Skip if state changes are suppressed
                        if self.mode_manager.is_state_change_suppressed():
                            self.logger.debug(
                                "OriginalScreen: State change suppressed during update loop."
                            )
                            continue
                        self.draw_display(state_to_process)
                else:
                    self.logger.debug(
                        "OriginalScreen: Skipping display update (inactive or not 'original')."
                    )

    def start_mode(self):
        """
        Activate this screen. Usually called by ModeManager -> 'enter_original'.
        """
        if self.mode_manager.get_mode() != "original":
            self.logger.warning(
                "OriginalScreen: Attempted to start, but current mode is not 'original'."
            )
            return
        self.is_active = True
        self.logger.info("OriginalScreen: Now active; drawing initial state.")
        current_state = self.moode_listener.get_current_state()
        if current_state:
            self.draw_display(current_state)

    def stop_mode(self):
        """
        Deactivate this screen, stop background updates.
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
        self.logger.info("OriginalScreen: Stopped and cleared display.")

    def update_playback_metrics(self, state):
        """(Optional) For external calls that update rate/bitdepth/volume, then triggers re-draw."""
        self.logger.info("OriginalScreen: Updating playback metrics display from external call.")
        with self.state_lock:
            self.latest_state = state
        self.update_event.set()

    def draw_display(self, data):
        """
        Main method: draws volume bars + sample rate + bit depth + service icon,
        preserving original sizing/format.
        """
        status          = data.get("status", {})
        current_service = data.get("current_service", "")
        volume_str      = data.get("volume", 0)
        volume          = int(volume_str) if str(volume_str).isdigit() else 0

        # If paused/stopped, keep old service
        if (status.get("state") in ["pause", "stop"]) and not current_service:
            current_service = self.previous_service or "default"
            self.logger.debug(f"OriginalScreen: Using previous service '{current_service}' for paused/stopped.")
        else:
            # If the service changed, clear screen once
            if current_service and (current_service != self.previous_service):
                self.display_manager.clear_screen()
                self.logger.info(
                    f"OriginalScreen: Service changed to '{current_service}'. Screen cleared."
                )
            self.previous_service = current_service or self.previous_service or "default"

        # Create black image to draw on
        base_image = Image.new("RGB", self.display_manager.oled.size, "black")
        draw       = ImageDraw.Draw(base_image)

        # 1) Draw volume bars
        self.draw_volume_bars(draw, volume)

        # 2) Figure out sample rate & bit depth
        #    - If the keys "samplerate" or "bitdepth" are missing, parse from "format" or "audio".
        samplerate = data.get("samplerate", "")
        bitdepth   = data.get("bitdepth", "")
        if not samplerate or not bitdepth or samplerate.lower() == 'n/a' or bitdepth.lower() == 'n/a':
            # Fallback to data["format"] or data["status"]["audio"]
            format_str = data.get("format", status.get("audio", ""))
            parsed_sr, parsed_bd = self.parse_samplerate_from_format(format_str)
            samplerate = parsed_sr
            bitdepth   = parsed_bd

        # 3) Draw sample rate & bit depth
        self.draw_sample_rate_and_bitdepth(draw, base_image, samplerate, bitdepth)

        # 4) Draw service icon
        self.draw_service_icon(draw, base_image, current_service)

        # 5) Finally update the OLED
        self.display_manager.oled.display(base_image)
        self.logger.info("OriginalScreen: Display updated.")

    def draw_volume_bars(self, draw, volume):
        """
        Same logic as your original code: draw up to 6 squares for volume.
        """
        volume = max(0, min(volume, 100))
        filled_squares = round((volume / 100) * 6)
        square_size    = 3
        row_spacing    = 5
        padding_bottom = 6
        columns = [10, 26]  # left column, right column

        for x in columns:
            for row in range(filled_squares):
                y = self.display_manager.oled.height - padding_bottom - ((row + 1) * (square_size + row_spacing))
                draw.rectangle([x, y, x + square_size, y + square_size], fill="white")

        self.logger.debug(f"OriginalScreen: Drew volume bars => {filled_squares} squares for volume={volume}.")

    def draw_sample_rate_and_bitdepth(self, draw, base_image, samplerate, bitdepth):
        """
        Updated approach to parse sample rate (like "44.1 kHz" or "192 kHz") and display.
        Also draw bit depth (e.g. "16bit", "24bit") beneath it.
        Preserves your layout & anchor usage from original code.
        """
        # 1) Parse samplerate (existing approach)
        sample_rate_num, sample_rate_unit_text = self.parse_samplerate(samplerate)

        # 2) Draw it at top-right or the same position you used
        sample_rate_block_right_x = self.display_manager.oled.width - 70
        sample_rate_y = 32

        font_sample_num  = self.display_manager.fonts.get('sample_rate', ImageFont.load_default())
        font_sample_unit = self.display_manager.fonts.get('sample_rate_khz', ImageFont.load_default())

        sample_rate_num_text = str(sample_rate_num)
        bbox_num = font_sample_num.getbbox(sample_rate_num_text)
        num_width = bbox_num[2] - bbox_num[0] if bbox_num else 0

        bbox_unit = font_sample_unit.getbbox(sample_rate_unit_text)
        unit_width = bbox_unit[2] - bbox_unit[0] if bbox_unit else 0

        sample_rate_num_x = sample_rate_block_right_x - (num_width + unit_width) - 4
        draw.text(
            (sample_rate_num_x, sample_rate_y),
            sample_rate_num_text,
            font=font_sample_num,
            fill="white",
            anchor="lm"
        )

        unit_x = sample_rate_num_x + num_width + 1
        draw.text(
            (unit_x, sample_rate_y + 18),
            sample_rate_unit_text,
            font=font_sample_unit,
            fill="white",
            anchor="lm"
        )

        self.logger.debug(
            f"OriginalScreen: Drew sample rate => {sample_rate_num} {sample_rate_unit_text}"
        )

        # 3) Draw bit depth at bottom-right
        format_bitdepth_text = str(bitdepth if bitdepth else "N/A")
        font_info = self.display_manager.fonts.get('playback_small', ImageFont.load_default())
        padding   = 15
        x_position= self.display_manager.oled.width - padding
        y_position= 50
        draw.text(
            (x_position, y_position),
            format_bitdepth_text,
            font=font_info,
            fill="white",
            anchor="rm"
        )
        self.logger.debug(f"OriginalScreen: Drew bit depth => {format_bitdepth_text} at (x={x_position}, y={y_position}).")

    def parse_samplerate(self, samplerate_str):
        """
        Safely parse something like "44.1 kHz" or "192 kHz" from moOde,
        returning (num, unit_text) => (44, "kHz").
        If invalid or empty, fallback to "N/A".
        """
        # Default fallback
        sample_rate_num       = "N/A"
        sample_rate_unit_text = "kHz"

        if samplerate_str:
            match = re.match(r"([\d\.]+)\s*(\w+)", samplerate_str)
            if match:
                try:
                    val  = float(match.group(1))
                    unit = match.group(2).lower()
                    sample_rate_num = int(val)
                    if unit in ["khz", "hz"]:
                        sample_rate_unit_text = unit.upper()
                    elif unit == "kbps":
                        sample_rate_unit_text = "kbps"
                    else:
                        sample_rate_unit_text = "kHz"  # fallback
                except ValueError:
                    self.logger.warning(f"OriginalScreen: Failed to parse numeric part from '{samplerate_str}'")
            else:
                self.logger.warning(f"OriginalScreen: Samplerate doesn't match pattern => '{samplerate_str}'")
        else:
            self.logger.warning("OriginalScreen: Samplerate string is empty or None.")

        return sample_rate_num, sample_rate_unit_text

    def draw_service_icon(self, draw, base_image, service):
        """Draw the service icon near the top-right, if available, same approach as original."""
        icon = self.display_manager.icons.get(service)
        if not icon:
            # fallback
            icon = self.display_manager.default_icon
            if not icon:
                self.logger.warning("OriginalScreen: No icon or default icon found.")
                return

        if icon.mode == "RGBA":
            background = Image.new("RGB", icon.size, (0, 0, 0))
            background.paste(icon, mask=icon.split()[3])
            icon = background

        icon_padding_right = 12
        icon_padding_top   = 6
        icon_x = self.display_manager.oled.width - icon.width - icon_padding_right
        icon_y = icon_padding_top
        base_image.paste(icon, (icon_x, icon_y))

        self.logger.debug(f"OriginalScreen: Pasted service icon '{service}' at (x={icon_x}, y={icon_y}).")

    def toggle_play_pause(self):
        """
        Short press => 'mpc toggle' or moode_listener.toggle_play_pause().
        """
        self.logger.info("OriginalScreen: Toggling play/pause.")
        if not self.moode_listener.is_connected():
            self.logger.warning("OriginalScreen: Not connected to moode; cannot toggle playback.")
            self.display_error_message("Connection Error", "Not connected to Moode.")
            return
        try:
            self.moode_listener.toggle_play_pause()
            self.logger.debug("OriginalScreen: 'toggle_play_pause' called successfully.")
        except Exception as e:
            self.logger.error(f"OriginalScreen: Failed to toggle play/pause - {e}")
            self.display_error_message("Playback Error", f"Could not toggle playback: {e}")

    def adjust_volume(self, volume_change):
        """
        Called if you want to adjust volume directly from this screen.
        """
        if self.latest_state is None:
            self.logger.warning("[OriginalScreen] No state, default volume=100.")
            self.latest_state = {"volume": 100}

        with self.state_lock:
            current_volume = self.latest_state.get("volume", 100)
            new_volume = max(0, min(int(current_volume) + volume_change, 100))

        self.logger.info(f"OriginalScreen: Adjusting volume from {current_volume} to {new_volume}.")

        try:
            if volume_change > 0:
                self.moode_listener.set_volume('+')
            elif volume_change < 0:
                self.moode_listener.set_volume('-')
            else:
                self.moode_listener.set_volume(new_volume)
        except Exception as e:
            self.logger.error(f"OriginalScreen: Failed to adjust volume - {e}")
            self.display_error_message("Playback Error", f"Could not toggle playback: {e}")

    def display_playback_info(self):
        """Manually display the current state if desired."""
        current_state = self.moode_listener.get_current_state()
        if current_state:
            self.draw_display(current_state)
        else:
            self.logger.warning("OriginalScreen: No current state available to display.")

    def display_error_message(self, title, message):
        """
        If you have an error, show it briefly on the OLED.
        """
        with self.display_manager.lock:
            img = Image.new("RGB", self.display_manager.oled.size, "black")
            draw = ImageDraw.Draw(img)
            font = self.display_manager.fonts.get('error_font', ImageFont.load_default())

            title_width = font.getlength(title)
            title_x = (self.display_manager.oled.width - title_width) // 2
            title_y = 10
            draw.text((title_x, title_y), title, font=font, fill="red")

            message_width = font.getlength(message)
            message_x = (self.display_manager.oled.width - message_width) // 2
            message_y = title_y + 20
            draw.text((message_x, message_y), message, font=font, fill="white")

            final_img = img.convert(self.display_manager.oled.mode)
            self.display_manager.oled.display(final_img)
            self.logger.info(f"OriginalScreen: Displayed error => {title}: {message}")
            time.sleep(2)
            # Re-draw the normal display or just clear. Up to you.

    def parse_samplerate_from_format(self, format_str):
        """
        Attempt to parse something like "44100:16:2" into ("44.1 kHz", "16bit").
        If it fails, return ("N/A", "N/A").
        """
        if not format_str:
            return ("N/A", "N/A")

        try:
            parts = format_str.split(':')
            if len(parts) < 2:
                return ("N/A", "N/A")

            samplerate_hz = float(parts[0])   # e.g. 44100
            bit_depth     = parts[1]         # e.g. "16"

            # Convert 44100 -> 44.1 (kHz)
            sr_khz = samplerate_hz / 1000.0
            sr_str = f"{sr_khz:.1f} kHz"

            # e.g. "16" -> "16bit"
            bitdepth_str = f"{bit_depth}bit"

            return (sr_str, bitdepth_str)
        except Exception as e:
            self.logger.warning(f"parse_samplerate_from_format: Could not parse '{format_str}': {e}")
            return ("N/A", "N/A")

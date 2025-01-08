import threading
import time
import logging
import psutil
import subprocess
import re
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from managers.menus.base_manager import BaseManager

class SystemInfoScreen(BaseManager):
    """
    Example 'System Information' screen with a layout like:
    
        System Information      <-- center
        192.168.0.142          <-- center
        07:00 AM  08/01/2025   <-- center
                             
        CPU: 12.3%   MEM: 45%   WIFI: 78.9%   CPU temp: 39c
    """

    def __init__(self, display_manager, moode_listener, mode_manager):
        super().__init__(display_manager, moode_listener, mode_manager)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)

        self.is_active = False
        self.stop_event = threading.Event()
        self.update_thread = None

        # Choose fonts/spacing to your taste:
        self.title_font_key = "menu_font_bold"       # e.g. a larger font for title
        self.info_font_key  = "data_font"      # middle lines
        self.stats_font_key = "data_font" # bottom line
        self.line_spacing   = 8
        self.title_spacing  = 2  # extra gap below the title
        self.stats_spacing  = 8  # vertical gap above the stats line
        self.left_margin    = 4

    def start_mode(self):
        if self.is_active:
            self.logger.debug("SystemInfoScreen: Already active.")
            return
        self.is_active = True
        self.logger.info("SystemInfoScreen: Starting system info display.")
        self.stop_event.clear()

        # Start the background thread that updates and draws
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()

    def stop_mode(self):
        if not self.is_active:
            self.logger.debug("SystemInfoScreen: Not active.")
            return
        self.is_active = False
        self.logger.info("SystemInfoScreen: Stopping system info display.")

        self.stop_event.set()
        if self.update_thread:
            self.update_thread.join(timeout=1)
            self.update_thread = None

        self.display_manager.clear_screen()

    def _update_loop(self):
        """Background loop: gather data -> draw -> sleep -> repeat."""
        while not self.stop_event.is_set():
            # 1) Gather system data
            cpu_usage = psutil.cpu_percent(interval=None)  # e.g. 12.3
            mem_info  = psutil.virtual_memory()            # e.g. total, used, percent
            mem_usage = mem_info.percent                   # e.g. 45.6
            cpu_temp  = self._get_cpu_temp()               # e.g. 39
            wifi_signal = self._get_wifi_signal()          # e.g. 78.9 or None
            ip_list   = self._get_ip_addresses()           # e.g. ["192.168.0.142"]

            # 2) Draw the layout
            self._draw_screen(cpu_usage, mem_usage, cpu_temp, wifi_signal, ip_list)

            # 3) Sleep for 3 seconds (or whatever interval you prefer)
            time.sleep(3)

    def _draw_screen(self, cpu_usage, mem_usage, cpu_temp, wifi_signal, ip_list):
        """Render the 'System Information' layout shown in your mockup."""
        w = self.display_manager.oled.width
        h = self.display_manager.oled.height

        # 1) Create black image
        img  = Image.new("RGB", (w, h), "black")
        draw = ImageDraw.Draw(img)

        # 2) Load some fonts (fallback to default if not found):
        title_font = self.display_manager.fonts.get(self.title_font_key) \
                     or ImageFont.load_default()
        info_font  = self.display_manager.fonts.get(self.info_font_key) \
                     or ImageFont.load_default()
        stats_font = self.display_manager.fonts.get(self.stats_font_key) \
                     or ImageFont.load_default()

        # 3) Title: "System Information" (centered at top)
        title_text = "System Information"
        y_cursor = 0
        y_cursor = self._draw_centered(draw, title_text, title_font, y_cursor, w)
        y_cursor += self.title_spacing

        # 4) Middle lines: e.g. IP, then time
        #    Center the first IP if multiple => pick the first, or join them
        #    Also center local time below
        ip_str = ", ".join(ip_list) if ip_list else "No IP"
        y_cursor = self._draw_centered(draw, ip_str, info_font, y_cursor, w)
        y_cursor += self.line_spacing

        # Local time line (or system time):
        now = time.localtime()
        time_str = time.strftime("%I:%M %p  %d/%m/%Y", now)  # e.g. "07:00 AM  08/01/2025"
        y_cursor = self._draw_centered(draw, time_str, info_font, y_cursor, w)
        y_cursor += self.stats_spacing

        # 5) Bottom line of stats, horizontally spaced:
        #    CPU: x% | MEM: x% | WIFI: x% | CPU temp: x
        #    We'll do them in one line, separated by ~some spaces
        #    Or we can compute widths and center the entire block horizontally.

        # Compose the stats line (some spacing between each label)
        # e.g. "CPU: 12.3%   MEM: 45%   WIFI: 78.9%   CPU temp: 39c"
        # If wifi_signal is None => "WIFI: N/A"
        if wifi_signal is None:
            wifi_str = "N/A"
        else:
            wifi_str = f"{wifi_signal:.1f}%"

        if cpu_temp is None:
            cpu_temp_str = "N/A"
        else:
            cpu_temp_str = f"{cpu_temp:.0f}c"

        stats_line = (
            f"CPU: {cpu_usage:.1f}%   "
            f"MEM: {mem_usage:.1f}%   "
            f"WIFI: {wifi_str}   "
            f"CPU temp: {cpu_temp_str}"
        )

        # We'll center this entire line in the screen:
        self._draw_centered(draw, stats_line, stats_font, y_cursor, w)

        # 6) Finally, push image to OLED
        final_img = img.convert(self.display_manager.oled.mode)
        self.display_manager.oled.display(final_img)

    def _draw_centered(self, draw, text, font, y_pos, screen_width):
        """
        Utility to measure `text` width with `font`, then position it so it’s
        horizontally centered at y_pos. Returns the next vertical y position 
        after drawing this line.
        """
        bbox = draw.textbbox((0,0), text, font=font)  # (left, top, right, bottom)
        text_w = bbox[2] - bbox[0]
        x_pos  = (screen_width - text_w)//2
        draw.text((x_pos, y_pos), text, font=font, fill="white")
        return y_pos + (bbox[3] - bbox[1])

    # -------------------------------------------------------------------
    # Helper methods for CPU temp, WiFi, IP
    # -------------------------------------------------------------------
    def _get_cpu_temp(self):
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        for key in ("cpu_thermal", "thermal_zone0", "soc_thermal"):
            if key in temps:
                return temps[key][0].current
        return None

    def _get_wifi_signal(self, interface="wlan0"):
        """
        Return Wi-Fi signal as a percentage (0–100) if found,
        or None if not found. (Also can parse as dBm or 0–70 scale.)
        """
        try:
            res = subprocess.run(["iwconfig", interface], capture_output=True, text=True, check=False)
            if res.returncode != 0:
                return None
            out = res.stdout.lower()

            # Try link quality=xx/yy => to percentage
            match_link = re.search(r"link quality=(\d+)/(\d+)", out)
            if match_link:
                q_now = int(match_link.group(1))
                q_max = int(match_link.group(2))
                return round((q_now / q_max) * 100, 1)
        except Exception:
            pass
        return None

    def _get_ip_addresses(self):
        try:
            res = subprocess.run(["hostname", "-I"], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                return res.stdout.strip().split()
        except Exception:
            pass
        return []

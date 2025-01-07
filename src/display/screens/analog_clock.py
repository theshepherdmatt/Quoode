import threading
import time
import math
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

class AnalogClock:
    """
    A simple analogue clock with hour, minute, and optional second hand.
    Draws onto the display every `update_interval` seconds.
    Supports a `scale` parameter for adjusting the clock size.
    """

    def __init__(self, display_manager, update_interval=1.0, scale=1.0):
        """
        :param display_manager:  The DisplayManager controlling the OLED.
        :param update_interval:  How often (in seconds) to update the clock.
        :param scale:            A multiplier for the clock's size (1.0 = default).
                                 Use <1.0 to shrink the clock, or >1.0 to enlarge if space permits.
        """
        self.display_manager = display_manager
        self.width = display_manager.oled.width
        self.height = display_manager.oled.height

        self.update_interval = update_interval
        self.scale = scale  # new parameter for resizing

        self.is_running = False
        self._thread = None
        self._stop_event = threading.Event()

        # Optional font for labeling or extra text
        self.font = ImageFont.load_default()

        # Base radius from the smaller screen dimension, minus a margin
        base_radius = (min(self.width, self.height) // 2) - 2
        self.radius = int(base_radius * self.scale)

    def start(self):
        """
        Start the analogue clock if not already running.
        """
        if self.is_running:
            return
        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """
        Stop the analogue clock, setting the stop event and joining the thread.
        """
        if not self.is_running:
            return
        self.is_running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join()
            self._thread = None

    def _run(self):
        """
        Main loop: draws the clock, then sleeps for `update_interval`.
        Exits when `_stop_event` is set (e.g. via `stop()`).
        """
        while not self._stop_event.is_set():
            self._draw_clock()
            time.sleep(self.update_interval)

    def _draw_clock(self):
        """
        1) Create a new black image
        2) Compute angles for hour/minute/second
        3) Draw the circular face, tick marks, and hands
        4) Display it on the OLED
        """
        # 1) Create a black image as our canvas
        img = Image.new("RGB", (self.width, self.height), "black")
        draw = ImageDraw.Draw(img)

        # Center coordinates
        cx, cy = self.width // 2, self.height // 2

        # 2) (Optional) draw the clock-face circle
        draw.ellipse(
            (cx - self.radius, cy - self.radius, cx + self.radius, cy + self.radius),
            outline="white", width=1
        )

        # Get the current time
        now = datetime.now()
        hour = now.hour % 12
        minute = now.minute
        second = now.second

        # 3) Compute angles for the three hands, in degrees
        #    Convert "12 o'clock" = 0 deg to a standard trig coordinate => -90 deg offset
        hour_angle = (hour + minute / 60.0) * 30 - 90
        minute_angle = minute * 6 - 90
        second_angle = second * 6 - 90

        # Convert angles to radians for math/trig
        hour_rad = math.radians(hour_angle)
        minute_rad = math.radians(minute_angle)
        second_rad = math.radians(second_angle)

        # Decide the lengths of each hand (shorter hour hand, etc.)
        hour_length = int(self.radius * 0.6)
        min_length = int(self.radius * 0.9)
        sec_length = int(self.radius * 0.95)

        # Hour hand
        hour_x = cx + hour_length * math.cos(hour_rad)
        hour_y = cy + hour_length * math.sin(hour_rad)
        draw.line((cx, cy, hour_x, hour_y), fill="white", width=3)

        # Minute hand
        min_x = cx + min_length * math.cos(minute_rad)
        min_y = cy + min_length * math.sin(minute_rad)
        draw.line((cx, cy, min_x, min_y), fill="white", width=2)

        # Second hand (optional)
        sec_x = cx + sec_length * math.cos(second_rad)
        sec_y = cy + sec_length * math.sin(second_rad)
        draw.line((cx, cy, sec_x, sec_y), fill="white", width=1)

        # 4) Draw hour tick marks (optional)
        #    E.g. a short line every 30 degrees for 12 hours
        for i in range(12):
            angle_deg = i * 30 - 90
            angle_rad = math.radians(angle_deg)
            outer_x = cx + self.radius * math.cos(angle_rad)
            outer_y = cy + self.radius * math.sin(angle_rad)
            tick_len = 8
            inner_x = cx + (self.radius - tick_len) * math.cos(angle_rad)
            inner_y = cy + (self.radius - tick_len) * math.sin(angle_rad)
            draw.line((outer_x, outer_y, inner_x, inner_y), fill="white", width=1)

        # Convert image to the OLED's mode and display
        final_img = img.convert(self.display_manager.oled.mode)
        with self.display_manager.lock:
            self.display_manager.oled.display(final_img)

import time
import threading
from PIL import Image, ImageDraw

class Clock:
    def __init__(self, display_manager, config):
        """
        :param display_manager:  Your DisplayManager controlling the OLED.
        :param config:           Dictionary with user toggles like:
                                  - 'clock_font_key' (e.g. 'clock_sans', 'clock_dots', 'clock_digital')
                                  - 'show_seconds'   (bool)
                                  - 'show_date'      (bool)
                                You can also add more toggles if needed.
        """
        self.display_manager = display_manager
        self.config = config  # includes user toggles like "clock_font_key", "show_seconds", "show_date"
        self.running = False
        self.thread  = None

        # Y-offset for each clock font, if you want to shift them up/down
        self.font_y_offsets = {
            "clock_sans":    -15,
            "clock_dots":    -10,
            "clock_digital":  0
        }

        # Additional spacing between time and date lines
        self.font_line_spacing = {
            "clock_sans":    15,
            "clock_dots":    10,
            "clock_digital":  8
        }

        # If you have separate date fonts:
        # e.g. 'clock_sans' => 'clockdate_sans'
        self.date_font_map = {
            "clock_sans":    "clockdate_sans",
            "clock_dots":    "clockdate_dots",
            "clock_digital": "clockdate_digital"
        }

    def draw_clock(self):
        """
        Render time (in large font) plus optional date (in smaller font).
        Centre it on the display, applying any font offsets or line spacing.
        """
        # 1) Determine which main clock font to use
        time_font_key = self.config.get("clock_font_key", "clock_digital")
        if time_font_key not in self.display_manager.fonts:
            print(f"Warning: '{time_font_key}' not loaded; fallback to 'clock_digital'")
            time_font_key = "clock_digital"

        # 2) Map the clock font to a date font
        date_font_key = self.date_font_map.get(time_font_key, "clockdate_digital")

        # 3) Check toggles for seconds and date
        show_seconds = self.config.get("show_seconds", False)
        time_str = time.strftime("%H:%M:%S") if show_seconds else time.strftime("%H:%M")

        show_date = self.config.get("show_date", False)
        date_str = time.strftime("%d %b %Y") if show_date else None

        # 4) Retrieve y-offset and line spacing for this clock font
        y_offset = self.font_y_offsets.get(time_font_key, 0)
        line_gap = self.font_line_spacing.get(time_font_key, 10)

        # 5) Make a blank image for the entire display
        w = self.display_manager.oled.width
        h = self.display_manager.oled.height
        img = Image.new("RGB", (w, h), "black")
        draw = ImageDraw.Draw(img)

        # 6) Load the actual PIL fonts for time & date
        time_font = self.display_manager.fonts[time_font_key]
        date_font = self.display_manager.fonts.get(date_font_key, time_font)

        # 7) Build a list of lines to draw (time, then optional date)
        lines = []
        if time_str:
            lines.append((time_str, time_font))
        if date_str:
            lines.append((date_str, date_font))

        # 8) Measure total height
        total_height = 0
        line_dims = []
        for (text, font) in lines:
            box = draw.textbbox((0, 0), text, font=font)  # textbbox => (left, top, right, bottom)
            lw  = box[2] - box[0]
            lh  = box[3] - box[1]
            line_dims.append((lw, lh, font))
            total_height += lh

        # Add extra spacing if we have 2 lines
        if len(lines) == 2:
            total_height += line_gap

        # 9) Compute a start_y to centre everything plus offset
        start_y = (h - total_height) // 2 + y_offset
        y_cursor = start_y

        # 10) Draw each line
        for i, (text, font) in enumerate(lines):
            lw, lh, the_font = line_dims[i]
            x_pos = (w - lw) // 2
            draw.text((x_pos, y_cursor), text, font=the_font, fill="white")
            y_cursor += lh
            if i < len(lines) - 1:
                y_cursor += line_gap

        # 11) Convert and display
        final_img = img.convert(self.display_manager.oled.mode)
        self.display_manager.oled.display(final_img)

    def start(self):
        """Begin updating the clock on a 1-second interval in a background thread."""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.update_clock, daemon=True)
            self.thread.start()
            print("Clock: Started.")

    def stop(self):
        """Stop updating the clock and clear the display."""
        if self.running:
            self.running = False
            self.thread.join()
            self.display_manager.clear_screen()
            print("Clock: Stopped.")

    def update_clock(self):
        """Loop that redraws the clock every second while running."""
        while self.running:
            self.draw_clock()
            time.sleep(1)

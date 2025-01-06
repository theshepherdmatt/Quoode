import time
import threading
from PIL import Image, ImageDraw

class Clock:
    def __init__(self, display_manager, config):
        self.display_manager = display_manager
        self.config = config  # includes user toggles like "clock_font_key", "show_seconds", "show_date", etc.
        self.running = False
        self.thread  = None

        # For your large clock fonts:
        self.font_y_offsets = {
            "clock_sans":    -15,
            "clock_dots":    -2,
            "clock_digital":  0
        }

        # The line spacing between time and date if both are shown
        self.font_line_spacing = {
            "clock_sans":    15,  
            "clock_dots":    6,  
            "clock_digital":  8
        }

        # **Map from time font to date font** (e.g. clock_sans => clockdate_sans)
        # Adjust as needed if you rename your date fonts.
        self.date_font_map = {
            "clock_sans":    "clockdate_sans",
            "clock_dots":    "clockdate_dots",
            "clock_digital": "clockdate_digital"
        }

    def draw_clock(self):
        """Render the time (in large font) and optional date (in smaller font)."""

        # 1) Which main clock font?
        time_font_key = self.config.get("clock_font_key", "clock_digital")
        #print(f"[DEBUG] draw_clock: using time font={time_font_key}")

        # If that font doesn't exist in self.display_manager.fonts, fallback
        if time_font_key not in self.display_manager.fonts:
            print(f"Warning: '{time_font_key}' not loaded; fallback to 'clock_digital'")
            time_font_key = "clock_digital"

        # 2) Figure out date font based on time font
        #    If no direct mapping, fallback to "clockdate_digital"
        date_font_key = self.date_font_map.get(time_font_key, "clockdate_digital")

        # 3) Possibly show seconds
        show_seconds = self.config.get("show_seconds", False)
        time_str = time.strftime("%H:%M:%S") if show_seconds else time.strftime("%H:%M")

        # 4) Possibly show date
        show_date = self.config.get("show_date", False)
        date_str = time.strftime("%d %b %Y") if show_date else None

        # 5) Offsets & spacing for the time font
        y_offset = self.font_y_offsets.get(time_font_key, 0)
        line_gap = self.font_line_spacing.get(time_font_key, 10) 

        # 6) Create a blank image for measuring
        w = self.display_manager.oled.width
        h = self.display_manager.oled.height
        img = Image.new("RGB", (w, h), "black")
        draw = ImageDraw.Draw(img)

        # 7) Load the actual PIL fonts
        #    - e.g. 'clock_sans' might be size=40, 'clockdate_sans' might be size=20
        time_font = self.display_manager.fonts[time_font_key]
        date_font = self.display_manager.fonts.get(date_font_key, time_font)  
        # fallback if date_font_key not loaded

        # We'll measure 1 or 2 lines, each with a possibly different font
        # - line 1 => (time_str, time_font)
        # - line 2 => (date_str, date_font) if date is enabled
        lines = []
        if time_str:
            lines.append((time_str, time_font))
        if date_str:
            lines.append((date_str, date_font))

        # 8) Measure each line
        total_height = 0
        line_dims = []
        for (text, font) in lines:
            # measure bounding box
            box = draw.textbbox((0,0), text, font=font)
            lw  = box[2] - box[0]
            lh  = box[3] - box[1]
            total_height += lh
            line_dims.append((lw, lh, font))

        # If 2 lines, add your line_gap
        if len(lines) == 2:
            total_height += line_gap

        # 9) Compute the vertical start => centered plus any offset
        start_y = (h - total_height) // 2 + y_offset
        y_cursor = start_y

        # 10) Render each line with its own font & size
        for i, (text, font) in enumerate(lines):
            lw, lh, the_font = line_dims[i]
            x_pos = (w - lw) // 2
            draw.text((x_pos, y_cursor), text, font=the_font, fill="white")

            y_cursor += lh
            if i < len(lines) - 1:
                # only add line_gap if there’s another line coming
                y_cursor += line_gap

        final_img = img.convert(self.display_manager.oled.mode)
        self.display_manager.oled.display(final_img)

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.update_clock, daemon=True)
            self.thread.start()
            print("Clock: Started.")

    def stop(self):
        if self.running:
            self.running = False
            self.thread.join()
            self.display_manager.clear_screen()
            print("Clock: Stopped.")

    def update_clock(self):
        while self.running:
            self.draw_clock()
            time.sleep(1)

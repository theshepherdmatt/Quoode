# src/display/screensavers/bouncing_text_screensaver.py

import time
import threading
from PIL import Image, ImageDraw, ImageFont

class BouncingTextScreensaver:
    """
    A screensaver that bounces the text "Quoode" around the screen
    with a small x,y velocity.
    """

    def __init__(self, display_manager, text="Quoode", update_interval=0.06):
        """
        :param display_manager:  DisplayManager instance
        :param text:             Which text to bounce
        :param update_interval:  Delay (in seconds) between frames
        """
        self.display_manager = display_manager
        self.width = display_manager.oled.width
        self.height = display_manager.oled.height
        self.text = text
        self.update_interval = update_interval

        self.is_running = False
        self.thread = None

        # Position and velocity
        self.x = self.width // 2
        self.y = self.height // 2
        self.vx = 1   # horizontal speed
        self.vy = 1   # vertical speed

        # Basic font for bouncing text
        # or retrieve one of your existing fonts from display_manager.fonts
        self.font = ImageFont.load_default()

    def start_screensaver(self):
        if self.is_running:
            return
        self.is_running = True
        self.x = self.width // 2
        self.y = self.height // 2
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop_screensaver(self):
        self.is_running = False
        if self.thread:
            self.thread.join()
            self.thread = None

    def run(self):
        while self.is_running:
            self.update_and_draw()
            time.sleep(self.update_interval)

    def update_and_draw(self):
        # 1) Move position
        self.x += self.vx
        self.y += self.vy

        # 2) Measure text size
        temp_img = Image.new("1", (self.width, self.height))
        draw_temp = ImageDraw.Draw(temp_img)
        tx, ty, tx2, ty2 = draw_temp.textbbox((0,0), self.text, font=self.font)
        text_w = tx2 - tx
        text_h = ty2 - ty

        # 3) Bounce if hitting edges
        if self.x < 0:
            self.x = 0
            self.vx = -self.vx
        elif self.x + text_w >= self.width:
            self.x = self.width - text_w
            self.vx = -self.vx

        if self.y < 0:
            self.y = 0
            self.vy = -self.vy
        elif self.y + text_h >= self.height:
            self.y = self.height - text_h
            self.vy = -self.vy

        # 4) Draw onto an image
        img = Image.new("RGB", (self.width, self.height), "black")
        draw = ImageDraw.Draw(img)
        draw.text((self.x, self.y), self.text, font=self.font, fill="white")

        final_img = img.convert(self.display_manager.oled.mode)
        with self.display_manager.lock:
            self.display_manager.oled.display(final_img)

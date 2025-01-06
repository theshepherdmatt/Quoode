# src/display/screensavers/starfield_screensaver.py

import random
import time
import threading
from PIL import Image, ImageDraw

class StarfieldScreensaver:
    """
    A screensaver that shows randomly placed stars
    that move 'down' (or up) every frame, then re-spawn at top when off-screen.
    """

    def __init__(self, display_manager, num_stars=40, update_interval=0.05):
        """
        :param display_manager:  Your DisplayManager instance
        :param num_stars:        How many stars to draw
        :param update_interval:  Delay (in seconds) between frames
        """
        self.display_manager = display_manager
        self.width = display_manager.oled.width
        self.height = display_manager.oled.height

        self.num_stars = num_stars
        self.update_interval = update_interval

        self.thread = None
        self.is_running = False

        # Each star is (x, y, speed)
        # speed is how many pixels it moves each frame
        self.stars = []

    def reset_stars(self):
        """(Re)Spawn all stars randomly."""
        self.stars = []
        for _ in range(self.num_stars):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            speed = random.uniform(0.5, 1.5)  # slow or fast
            self.stars.append([x, y, speed])

    def start_screensaver(self):
        if self.is_running:
            return
        self.is_running = True

        self.reset_stars()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop_screensaver(self):
        self.is_running = False
        if self.thread:
            self.thread.join()
            self.thread = None

    def run(self):
        while self.is_running:
            self.draw_frame()
            time.sleep(self.update_interval)

    def draw_frame(self):
        """
        Move stars downward, re-spawn if off bottom,
        then draw them as white dots or small lines.
        """
        # Move stars
        for star in self.stars:
            star[1] += star[2]  # star[2] is speed, star[1] is y
            # If off screen, re-spawn near top
            if star[1] >= self.height:
                star[0] = random.randint(0, self.width - 1)
                star[1] = 0
                star[2] = random.uniform(0.5, 1.5)

        # Draw to a black image
        img = Image.new("RGB", (self.width, self.height), "black")
        draw = ImageDraw.Draw(img)

        for (x, y, speed) in self.stars:
            # Draw star as a small dot
            # you can also vary brightness or size if you like
            draw.point((x, int(y)), fill="white")

        final_img = img.convert(self.display_manager.oled.mode)
        with self.display_manager.lock:
            self.display_manager.oled.display(final_img)

# snakescreensaver.py

import random
import time
import threading
from PIL import Image, ImageDraw


class SnakeScreensaver:
    """
    A Python-based "snake" screensaver inspired by your JS code.

    Basic idea:
      - A `count` increments each update.
      - A boolean `flip` toggles horizontal direction after traveling the screen width.
      - The snake’s position is (x, y).
      - There's a tail. Picking up 'random_pickups' extends it.
      - If it moves off-screen at the bottom, we reset.
    """

    def __init__(self, display_manager, update_interval=0.04):
        """
        :param display_manager: An instance of your DisplayManager 
                                (must have .oled.width, .oled.height, and .oled.display()).
        :param update_interval: Seconds between frames (0.04 ~ 40ms).
        """
        self.display_manager = display_manager
        self.update_interval = update_interval

        # Dimensions from the OLED
        self.width = display_manager.oled.width
        self.height = display_manager.oled.height

        # Tracking snake route
        self.count = 0
        self.flip = False
        self.tail = []
        self.tail_length = 10  # initial snake length
        self.random_pickups = []

        self.is_running = False
        self.thread = None

    def reset_animation(self):
        """Clears/Resets snake state, tail, pickups, etc."""
        self.tail = []
        self.count = 0
        self.tail_length = 10
        self.random_pickups = []

        # Create ~7 random pickups
        for _ in range(7):
            rx = random.randint(0, self.width - 1)
            # For partial JS similarity, y in multiples of 3:
            ry = random.randint(0, (self.height // 3) - 1) * 3
            self.random_pickups.append([rx, ry])

    def start_screensaver(self):
        """Begin the main loop in a background thread."""
        if self.is_running:
            return
        self.is_running = True

        # Reset to fresh state
        self.reset_animation()

        # Start a daemon thread
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop_screensaver(self):
        """Stop the loop and wait for thread to finish."""
        self.is_running = False
        if self.thread:
            self.thread.join()
            self.thread = None

    def run(self):
        """
        The main loop: calls `refresh_action()` 
        every self.update_interval until stopped.
        """
        while self.is_running:
            self.refresh_action()
            time.sleep(self.update_interval)

    def refresh_action(self):
        """
        The main logic for the snake:
          - Clear background
          - Determine (x, y)
          - Extend tail
          - Draw tail + pickups
          - If collision w/ pickup, increase tail length
          - If off bottom, reset.
        """
        # 1) Prepare an empty image + draw
        img = Image.new("RGB", (self.width, self.height), "black")
        draw = ImageDraw.Draw(img)

        # 2) Determine 'count' transitions
        #    if count % width == 0, flip = !flip
        if (self.count % self.width) == 0:
            self.flip = not self.flip

        # x depends on flip
        if self.flip:
            x = (self.count % self.width) + 1
        else:
            x = self.width - (self.count % self.width)

        # y = (count // width) * 3
        y = (self.count // self.width) * 3

        # 3) Add new head to tail, keep it at tail_length
        self.tail.append([x, y])
        if len(self.tail) > self.tail_length:
            self.tail.pop(0)

        # 4) Draw the tail
        #    In JS, fillRect(i[0], i[1]-1, 2, 3, 1).
        #    We'll just do 2x3 white rectangles:
        for (tx, ty) in self.tail:
            draw.rectangle([tx, ty - 1, tx + 1, ty + 1], fill="white")

        # 5) Loop pickups, check collision => tail_length += 5
        for pickup in self.random_pickups[:]:
            px, py = pickup
            # The JS collision logic:
            # if ((flip && x >= px) or (!flip && x <= px)) and y >= py:
            if ((self.flip and x >= px) or (not self.flip and x <= px)) and (y >= py):
                self.tail_length += 5
                self.random_pickups.remove(pickup)

            # Draw the pickup as a single pixel or small square
            # We'll do 1x1 pixel in white
            draw.point((px, py), fill="white")

        self.count += 1

        # If y > height => reset
        if y > self.height:
            self.reset_animation()

        # 6) Show on the OLED display
        final_img = img.convert(self.display_manager.oled.mode)
        with self.display_manager.lock:
            self.display_manager.oled.display(final_img)


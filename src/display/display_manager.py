import logging
from PIL import Image, ImageDraw, ImageFont, ImageSequence
import RPi.GPIO as GPIO
import threading
import os
import time

# Luma imports:
from luma.core.interface.serial import spi
from luma.oled.device import ssd1322

class DisplayManager:
    def __init__(self, config):
        """
        Initializes and configures the SSD1322 OLED via SPI, then loads fonts and icons.
        :param config: A dictionary containing user_home, icon_dir, fonts, etc.
        """
        self.install_user = config.get('install_user', 'matt')
        self.user_home = config.get('user_home', f"/home/{self.install_user}")
        self.icon_dir = config.get('icon_dir', os.path.join(self.user_home, "Quoode/src/assets/images"))

        # Optionally read the reset pin from config, or default to 25
        self.reset_gpio_pin = config.get('reset_gpio_pin', 25)

        # SPI + SSD1322 setup
        self.serial = spi(device=0, port=0)
        self.oled = ssd1322(self.serial, width=256, height=64, rotate=2)

        self.config = config
        self.lock = threading.Lock()

        # Logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.WARNING)

        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(ch)

        self.logger.info("DisplayManager initialized.")

        # Initialize fonts & icons
        self.fonts = {}
        self._load_fonts()

        self.icons = {}
        self.default_icon = self.load_default_icon()
        self._load_icons()

        # --- Setup GPIO for reset if you want to control it here ---
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.reset_gpio_pin, GPIO.OUT)
        # Usually set it high so the display is not held in reset:
        GPIO.output(self.reset_gpio_pin, GPIO.HIGH)

    def _load_fonts(self):
        """
        Loads fonts from config['fonts'] entries: { "font_key": { "path": "...", "size": ... }, ... }
        """
        fonts_config = self.config.get('fonts', {})
        default_font = ImageFont.load_default()

        for key, font_info in fonts_config.items():
            path = font_info.get('path')
            size = font_info.get('size', 12)
            if path and os.path.isfile(path):
                try:
                    self.fonts[key] = ImageFont.truetype(path, size=size)
                    self.logger.info(f"Loaded font '{key}' from '{path}' (size={size}).")
                except IOError as e:
                    self.logger.error(f"Error loading font '{key}' from '{path}': {e}")
                    self.fonts[key] = default_font
            else:
                self.logger.warning(
                    f"Font file not found for '{key}' at '{path}', using default font."
                )
                self.fonts[key] = default_font

        self.logger.info(f"Available fonts after loading: {list(self.fonts.keys())}")

    def _load_icons(self):
        """
        Load a known set of icons from self.icon_dir into self.icons dict.
        """
        # Example set of icons you want to load
        icon_names = ["clock", "shuffle", "repeat", "webradio", "data", "mpd",
                      "nas", "usb", "display", "volume", "screensaver", "contrast"]
        for name in icon_names:
            icon_path = os.path.join(self.icon_dir, f"{name}.png")
            try:
                img = Image.open(icon_path)
                if img.mode == "RGBA":
                    bg = Image.new("RGB", img.size, (0, 0, 0))
                    bg.paste(img, mask=img.split()[3])
                    img = bg
                img = img.resize((35, 35), Image.LANCZOS).convert("RGB")
                self.icons[name] = img
                self.logger.info(f"Loaded icon for '{name}' from '{icon_path}'.")
            except IOError:
                self.logger.warning(
                    f"Icon for '{name}' not found at '{icon_path}', using default icon."
                )
                self.icons[name] = self.default_icon

    def load_default_icon(self):
        default_icon_path = os.path.join(self.icon_dir, "default.png")
        try:
            icon = Image.open(default_icon_path)
            if icon.mode == "RGBA":
                background = Image.new("RGB", icon.size, (0,0,0))
                background.paste(icon, mask=icon.split()[3])
                icon = background
            icon = icon.resize((35,35), Image.LANCZOS).convert("RGB")
            self.logger.info(f"Loaded default icon from '{default_icon_path}'.")
            return icon
        except IOError:
            self.logger.warning("Default icon not found, using grey placeholder.")
            return Image.new("RGB", (35, 35), "grey")

    def clear_screen(self):
        """Clears OLED by displaying a solid black image."""
        with self.lock:
            blank_image = Image.new("RGB", self.oled.size, "black").convert(self.oled.mode)
            self.oled.display(blank_image)
            self.logger.info("Screen cleared.")

    def shutdown_display(self):
        """
        1) Clear screen in software (all black).
        2) Drive RESET pin LOW => physically hold the screen in reset (turned off).
        """
        with self.lock:
            self.clear_screen()
            time.sleep(0.05)  # small delay so user sees it go black
            GPIO.output(self.reset_gpio_pin, GPIO.LOW)
            self.logger.info(f"Display pinned to reset via GPIO {self.reset_gpio_pin} (LOW).")

    def display_image(self, image_path, resize=True, timeout=None):
        with self.lock:
            try:
                img = Image.open(image_path)
                if img.mode == "RGBA":
                    bg = Image.new("RGB", img.size, (0,0,0))
                    bg.paste(img, mask=img.split()[3])
                    img = bg
                if resize:
                    img = img.resize(self.oled.size, Image.LANCZOS)
                img = img.convert(self.oled.mode)
                self.oled.display(img)
                self.logger.info(f"Displayed image from '{image_path}'.")

                if timeout:
                    t = threading.Timer(timeout, self.clear_screen)
                    t.start()
                    self.logger.info(f"Set timeout to clear screen after {timeout}s.")
            except IOError:
                self.logger.error(f"Failed to load image '{image_path}'.")

    def draw_custom(self, draw_function):
        with self.lock:
            image = Image.new("RGB", self.oled.size, "black")
            draw_obj = ImageDraw.Draw(image)
            draw_function(draw_obj)
            image = image.convert(self.oled.mode)
            self.oled.display(image)
            self.logger.info("Custom drawing executed on OLED.")

    def show_logo(self):
        logo_path = self.config.get('logo_path')
        if logo_path:
            self.display_image(logo_path, timeout=5)
            self.logger.info("Displaying startup logo for 5 seconds.")
        else:
            self.logger.warning("No logo path specified in config, skipping.")


    def stop_mode(self):
        """
        Example method that stops a 'mode' if your architecture uses it.
        For now, just clears screen and logs.
        """
        # If your code uses self.is_active, we can set it false:
        self.is_active = False
        self.clear_screen()
        self.logger.info("Stopped current mode and cleared display.")

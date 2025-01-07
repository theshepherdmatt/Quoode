import logging
from PIL import Image, ImageDraw, ImageFont, ImageSequence, ImageFilter, ImageEnhance
from luma.core.interface.serial import spi
from luma.oled.device import ssd1322
import threading
import os
import time

class DisplayManager:
    def __init__(self, config):
        """
        Initializes and configures the SSD1322 OLED via SPI, then loads fonts and icons.

        :param config: A dictionary (from your YAML) containing:
            - user_home or install_user: The username or full path if needed
            - icon_dir: Where to look for icons
            - fonts: Dict of font definitions, etc.
        """
        # 1) Dynamically figure out the user’s directory or fallback
        #    e.g. from config, or fallback to '/home/matt'.
        self.install_user = config.get('install_user', 'matt')
        self.user_home = config.get('user_home', f"/home/{self.install_user}")
        
        # 2) For icons, either read from config or build a path
        #    e.g. "/home/<user>/Quoode/src/assets/images"
        self.icon_dir = config.get(
            'icon_dir',
            os.path.join(self.user_home, "Quoode/src/assets/images")
        )

        # 3) Set up SPI + SSD1322
        self.serial = spi(device=0, port=0)  # Adjust if needed
        self.oled = ssd1322(self.serial, width=256, height=64, rotate=2)

        self.config = config
        self.lock = threading.Lock()

        # Set up logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.WARNING)

        # (Optional) console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)

        if not self.logger.handlers:
            self.logger.addHandler(ch)

        self.logger.info("DisplayManager initialized.")

        # Prepare fonts & icons
        self.fonts = {}
        self._load_fonts()
        self.icons = {}

        # Load default icon
        self.default_icon = self.load_default_icon()

        # Example: define known services to load icons for:
        services = ["clock", "webradio", "data", "mpd", "nas", "usb", "display", "volume", "screensaver"]

        for service in services:
            icon_path = os.path.join(self.icon_dir, f"{service}.png")
            try:
                icon = Image.open(icon_path)
                # If RGBA, flatten on black
                if icon.mode == "RGBA":
                    background = Image.new("RGB", icon.size, (0, 0, 0))
                    background.paste(icon, mask=icon.split()[3])
                    icon = background
                    self.logger.info(f"Handled transparency for icon '{service}'.")
                # Resize + convert
                icon = icon.resize((35, 35), Image.LANCZOS).convert("RGB")
                self.icons[service] = icon
                self.logger.info(f"Loaded icon for '{service}' from '{icon_path}'.")
            except IOError:
                self.logger.warning(
                    f"Icon for '{service}' not found at '{icon_path}', using default icon."
                )
                self.icons[service] = self.default_icon

    def load_default_icon(self):
        """
        Loads the default icon (falling back if not found).
        Dynamically references self.icon_dir or similar.
        """
        default_icon_path = os.path.join(self.icon_dir, "default.png")
        try:
            icon = Image.open(default_icon_path)
            if icon.mode == "RGBA":
                background = Image.new("RGB", icon.size, (0, 0, 0))
                background.paste(icon, mask=icon.split()[3])
                icon = background
                self.logger.info("Handled transparency for default icon.")
            icon = icon.resize((35, 35), Image.LANCZOS).convert("RGB")
            self.logger.info(f"Loaded default icon from '{default_icon_path}'.")
            return icon
        except IOError:
            self.logger.warning("Default icon not found. Creating grey placeholder.")
            return Image.new("RGB", (35, 35), "grey")

    def _load_fonts(self):
        """
        Loads fonts from config['fonts'].
        Each entry is a dict with 'path' + 'size'.
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

    def clear_screen(self):
        """Clears OLED by showing a blank image."""
        with self.lock:
            blank_image = Image.new("RGB", self.oled.size, "black").convert(self.oled.mode)
            self.oled.display(blank_image)
            self.logger.info("Screen cleared.")

    def display_image(self, image_path, resize=True, timeout=None):
        """
        Displays a single image or a static frame from a GIF.
        If you have an animated GIF, you would need extra handling.
        """
        with self.lock:
            try:
                image = Image.open(image_path)
                # Flatten RGBA
                if image.mode == "RGBA":
                    bg = Image.new("RGB", image.size, (0,0,0))
                    bg.paste(image, mask=image.split()[3])
                    image = bg

                if resize:
                    image = image.resize(self.oled.size, Image.LANCZOS)
                image = image.convert(self.oled.mode)

                self.oled.display(image)
                self.logger.info(f"Displayed image from '{image_path}'.")

                # If a timeout is given, schedule clearing
                if timeout:
                    t = threading.Timer(timeout, self.clear_screen)
                    t.start()
                    self.logger.info(f"Set timeout to clear screen after {timeout}s.")
            except IOError:
                self.logger.error(f"Failed to load image '{image_path}'.")

    def display_text(self, text, position, font_key='default', fill="white"):
        """
        Render text at (x,y) = position, using a font from self.fonts.
        """
        with self.lock:
            image = Image.new("RGB", self.oled.size, "black")
            draw = ImageDraw.Draw(image)
            font = self.fonts.get(font_key, ImageFont.load_default())
            draw.text(position, text, font=font, fill=fill)
            # Convert & show
            image = image.convert(self.oled.mode)
            self.oled.display(image)
            self.logger.info(f"Displayed text '{text}' at {position} using font='{font_key}'.")

    def draw_custom(self, draw_function):
        """
        Provide a function that takes a Pillow.Draw object.
        """
        with self.lock:
            image = Image.new("RGB", self.oled.size, "black")
            draw = ImageDraw.Draw(image)
            draw_function(draw)
            image = image.convert(self.oled.mode)
            self.oled.display(image)
            self.logger.info("Custom drawing executed on OLED.")

    def show_logo(self):
        """
        If config['logo_path'] is set, display for 5s.
        """
        logo_path = self.config.get('logo_path')
        if logo_path:
            self.display_image(logo_path, timeout=5)
            self.logger.info("Displaying startup logo for 5 seconds.")
        else:
            self.logger.warning("No logo path specified in config, skipping.")

    def stop_mode(self):
        """
        Example of a method that stops a 'mode' if you had one.
        For now, just clears screen and sets is_active=False if used.
        """
        self.is_active = False
        self.clear_screen()
        self.logger.info("Stopped current mode and cleared display.")

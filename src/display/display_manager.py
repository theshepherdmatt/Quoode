import logging
from PIL import Image, ImageDraw, ImageFont, ImageSequence
from luma.core.interface.serial import spi
from luma.oled.device import ssd1322
import threading
import os
import time

class DisplayManager:
    def __init__(self, config):
        # Initialize SPI connection for the SSD1322 OLED display
        self.serial = spi(device=0, port=0)  # Default SPI device
        self.oled = ssd1322(self.serial, width=256, height=64, rotate=2)

        self.config = config
        self.lock = threading.Lock()

        # Initialize logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.WARNING)

        # Create console handler with a higher log level
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        # Create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)

        # Add the handlers to the logger
        if not self.logger.handlers:
            self.logger.addHandler(ch)

        self.logger.info("DisplayManager initialized.")

        # Load fonts and icons
        self.fonts = {}
        self._load_fonts()
        self.icons = {}

        # Define the services and load their corresponding icons
        services = ["stream", "library", "playlists", "qobuz", "tidal", "spop", "spotify", "webradio", "mpd", "default", "nas", "usb", "display", "displayfm4", "displaymodern", "volume"]
        icon_dir = self.config.get('icon_dir', "/home/volumio/Quadify/src/assets/images")

        for service in services:
            icon_path = os.path.join(icon_dir, f"{service}.png")
            try:
                # Load the specific icon for each service
                icon = Image.open(icon_path)

                # Handle transparency (if icon has an alpha channel)
                if icon.mode == "RGBA":
                    # Create a new black background image
                    background = Image.new("RGB", icon.size, (0, 0, 0))
                    # Paste the icon onto the background using the alpha channel as mask
                    background.paste(icon, mask=icon.split()[3])
                    icon = background
                    self.logger.info(f"Handled transparency for icon '{service}'.")

                # Resize the icon to fit and convert to RGB mode
                icon = icon.resize((35, 35), Image.LANCZOS).convert("RGB")
                self.icons[service] = icon
                self.logger.info(f"Loaded icon for '{service}' from '{icon_path}'.")

            except IOError:
                self.logger.warning(f"Icon for '{service}' not found at '{icon_path}', using default icon.")
                # Fallback to the default icon in case the specific icon is missing
                self.icons[service] = self.default_icon  # Use the pre-loaded default_icon


        # Load the default icon separately, if needed
        default_icon_path = os.path.join(icon_dir, "default.png")
        try:
            self.default_icon = Image.open(default_icon_path).resize((35, 35), Image.ANTIALIAS).convert("RGB")
            self.logger.info(f"Loaded default icon from '{default_icon_path}'.")
        except IOError:
            self.logger.warning("Default icon not found. Creating grey placeholder.")
            self.default_icon = Image.new("RGB", (35, 35), "grey")

        # Callback list for mode changes
        self.on_mode_change_callbacks = []

    def add_on_mode_change_callback(self, callback):
        """Register a callback to be executed on mode changes."""
        if callable(callback):
            self.on_mode_change_callbacks.append(callback)
            self.logger.debug(f"Added mode change callback: {callback}")
        else:
            self.logger.warning(f"Attempted to add a non-callable callback: {callback}")

    def notify_mode_change(self, current_mode):
        """Invoke all registered callbacks when a mode changes."""
        self.logger.debug(f"Notifying mode change to: {current_mode}")
        for callback in self.on_mode_change_callbacks:
            try:
                callback(current_mode)
                self.logger.debug(f"Successfully executed callback: {callback}")
            except Exception as e:
                self.logger.error(f"Error in callback {callback}: {e}")

    def _load_fonts(self):
        fonts_config = self.config.get('fonts', {})
        default_font = ImageFont.load_default()
        
        for key, font_info in fonts_config.items():
            path = font_info.get('path')
            size = font_info.get('size', 12)
            if path and os.path.isfile(path):
                try:
                    self.fonts[key] = ImageFont.truetype(path, size=size)
                    self.logger.info(f"Loaded font '{key}' from '{path}' with size {size}.")
                except IOError as e:
                    self.logger.error(f"Error loading font '{key}' from '{path}'. Exception: {e}")
                    self.fonts[key] = default_font
            else:
                self.logger.warning(f"Font file not found for '{key}' at '{path}'. Falling back to default font.")
                self.fonts[key] = default_font

        self.logger.info(f"Available fonts after loading: {list(self.fonts.keys())}")

    def clear_screen(self):
        """Clears the OLED screen by displaying a blank image."""
        with self.lock:
            blank_image = Image.new("RGB", self.oled.size, "black").convert(self.oled.mode)
            self.oled.display(blank_image)
            self.logger.info("Screen cleared.")

    def display_image(self, image_path, resize=True, timeout=None):
        """Displays an image or animates a GIF if it's an animated file."""
        with self.lock:
            try:
                # Load the image
                image = Image.open(image_path)

                # Handle transparency (if needed)
                if image.mode == "RGBA":
                    background = Image.new("RGB", image.size, (0, 0, 0))
                    background.paste(image, mask=image.split()[3])
                    image = background

                # Resize and convert as needed
                if resize:
                    image = image.resize(self.oled.size, Image.ANTIALIAS)

                # Convert to match the OLED's mode
                image = image.convert(self.oled.mode)
                self.oled.display(image)
                self.logger.info(f"Displayed image from '{image_path}'.")

                # Set timeout for the image if provided
                if timeout:
                    timer = threading.Timer(timeout, self.clear_screen)
                    timer.start()
                    self.logger.info(f"Set timeout to clear screen after {timeout} seconds.")
            except IOError:
                self.logger.error(f"Failed to load image '{image_path}'.")

    def display_text(self, text, position, font_key='default', fill="white"):
        """Displays text at a specified position using a specified font."""
        with self.lock:
            image = Image.new("RGB", self.oled.size, "black")
            draw = ImageDraw.Draw(image)
            font = self.fonts.get(font_key, ImageFont.load_default())
            draw.text(position, text, font=font, fill=fill)

            # Convert to match the OLED mode before displaying
            image = image.convert(self.oled.mode)
            self.oled.display(image)
            self.logger.info(f"Displayed text '{text}' at {position} with font '{font_key}'.")

    def draw_custom(self, draw_function):
        """Executes a custom drawing function onto the OLED."""
        with self.lock:
            image = Image.new("RGB", self.oled.size, "black")
            draw = ImageDraw.Draw(image)
            draw_function(draw)

            # Convert to match the OLED mode before displaying
            image = image.convert(self.oled.mode)
            self.oled.display(image)
            self.logger.info("Executed custom draw function.")

    def show_logo(self):
        """Displays the startup logo on the OLED screen for a set duration."""
        logo_path = self.config.get('logo_path')
        if logo_path:
            self.display_image(logo_path, timeout=5)
            self.logger.info("Displaying startup logo for 5 seconds.")
        else:
            self.logger.warning("No logo path configured.")

    def stop_mode(self):
        """Stops any active mode and clears the display."""
        self.is_active = False
        self.clear_screen()
        self.logger.info("MenuManager: Stopped menu mode and cleared display.")

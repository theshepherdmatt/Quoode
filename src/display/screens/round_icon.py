# src/display/cava_oled_display_circular.py

from managers.menus.base_manager import BaseManager

import os
import time
import threading
from PIL import Image, ImageDraw
import logging
from logging.handlers import RotatingFileHandler
import math
import colorsys

# Path to the FIFO created for CAVA
FIFO_PATH = "/tmp/display.fifo"

class CavaOLEDDisplayCircular(BaseManager):
    def __init__(self, display_manager, frame_rate=30):
        self.display_manager = display_manager
        self.running = False
        self.thread = None
        self.frame_interval = 1 / frame_rate  # Convert frame rate to interval
        self.last_render_time = 0
        self.previous_bars = None  # For interpolation
        self.current_service = None  # To track the current service

        # Configure logging
        self.logger = logging.getLogger(self.__class__.__name__)

        # Set logging level based on environment variable
        log_level = os.getenv('CAVA_OLED_LOG_LEVEL', 'INFO').upper()
        if log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            log_level = 'INFO'  # Fallback to INFO if invalid level is provided
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))

        # Create console handler with higher log level
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level, logging.INFO))
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)

        # Create rotating file handler for detailed logs
        log_file = os.path.join('/home/volumio/Quadify/logs', 'cava_oled_display_circular.log')  # Adjust path as needed
        file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)  # 5MB per file, 3 backups
        file_handler.setLevel(logging.INFO)  # Capture all logs in the file
        file_handler.setFormatter(formatter)

        # Add handlers to the logger
        if not self.logger.handlers:
            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)

        self.logger.info("CavaOLEDDisplayCircular initialized.")

    def start(self):
        if not os.path.exists(FIFO_PATH):
            self.logger.error(f"FIFO {FIFO_PATH} does not exist. Ensure CAVA is outputting to this file.")
            raise FileNotFoundError(f"FIFO {FIFO_PATH} does not exist.")

        self.logger.info(f"Starting CavaOLEDDisplayCircular. Reading data from {FIFO_PATH}.")
        self.running = True
        self.thread = threading.Thread(target=self._read_fifo)
        self.thread.setDaemon(True)  # Ensure thread does not block exit
        self.logger.debug("Thread created, starting now.")
        self.thread.start()
        self.logger.info("Thread started.")

    def stop(self):
        self.logger.info("Stopping CavaOLEDDisplayCircular.")
        self.running = False
        if self.thread and self.thread.is_alive():
            self.logger.debug("Waiting for the thread to finish.")
            self.thread.join()
        self.logger.info("CavaOLEDDisplayCircular stopped.")

    def _read_fifo(self):
        self.logger.info(f"Opening FIFO for reading: {FIFO_PATH}")
        try:
            with open(FIFO_PATH, "r") as fifo:
                self.logger.info(f"Successfully opened FIFO: {FIFO_PATH}")
                while self.running:
                    try:
                        data = fifo.readline().strip()
                        if not data:
                            self.logger.warning("Received empty line from FIFO.")
                            continue
                        # Safely parse bar values
                        bars = [int(x) for x in data.split(";") if x.isdigit()]
                        if bars:
                            self._draw_circular_spectrum(bars)
                        else:
                            self.logger.warning("No valid bar data parsed.")
                    except ValueError as e:
                        self.logger.error(f"Error parsing FIFO data: {e}")
                    except Exception as e:
                        self.logger.error(f"Unexpected error while reading FIFO: {e}")
        except FileNotFoundError as e:
            self.logger.error(f"FIFO file not found: {e}")
        except Exception as e:
            self.logger.error(f"Error opening FIFO file: {e}")

    def _interpolate_bars(self, current_bars):
        """Smooth transitions between frames."""
        if self.previous_bars is None:
            self.previous_bars = current_bars
            return current_bars
        smoothed_bars = [
            int(self.previous_bars[i] * 0.8 + current_bars[i] * 0.2)
            for i in range(min(len(self.previous_bars), len(current_bars)))
        ]
        self.previous_bars = smoothed_bars
        return smoothed_bars

    def _draw_circular_spectrum(self, bars):
        """Render a circular spectrum on the OLED display with gradient colors and central icon."""
        current_time = time.time()
        if current_time - self.last_render_time < self.frame_interval:
            return  # Skip rendering if within frame interval

        self.last_render_time = current_time
        bars = self._interpolate_bars(bars)
        self.logger.debug(f"Rendering circular spectrum with bars: {bars}")
        try:
            width, height = self.display_manager.oled.width, self.display_manager.oled.height
            center_x, center_y = width // 2, height // 2
            padding = 8  # Reduced padding to make the spectrum slightly larger
            max_radius = min(center_x, center_y) - padding  # Adjusted padding

            self.logger.debug(f"Display dimensions: width={width}, height={height}")
            self.logger.debug(f"Center coordinates: center_x={center_x}, center_y={center_y}")
            self.logger.debug(f"Padding: {padding}, max_radius: {max_radius}")

            # Enforce a minimum radius to prevent excessive shrinking
            min_radius = 10
            if max_radius < min_radius:
                self.logger.warning(f"Max radius {max_radius} is too small. Adjusting to minimum radius {min_radius}.")
                max_radius = min_radius
                padding = min(center_x, center_y) - max_radius
                self.logger.debug(f"Adjusted padding: {padding}, max_radius: {max_radius}")

            num_bars = len(bars)
            angle_step = 360 / num_bars if num_bars else 0

            # Define bar properties
            bar_width = max(1, width // (num_bars * 2))  # Adjust bar width based on number of bars
            self.logger.debug(f"Number of bars: {num_bars}, bar_width: {bar_width}")
            max_bar_height = max_radius // 2  # Maximum height for bars

            # Create an image buffer with RGB mode
            image = Image.new("RGB", (width, height), "black")
            draw = ImageDraw.Draw(image)

            for i, bar in enumerate(bars):
                angle_deg = i * angle_step
                angle_rad = math.radians(angle_deg)

                # Calculate bar height proportional to the bar value
                bar_height = int((bar / 255) * max_bar_height)

                # Ending point at the edge of the max radius
                end_x = center_x + int((max_radius) * math.cos(angle_rad))
                end_y = center_y + int((max_radius) * math.sin(angle_rad))

                # Calculate the bar's extended end point based on bar height
                extended_end_x = end_x + int((bar_height) * math.cos(angle_rad))
                extended_end_y = end_y + int((bar_height) * math.sin(angle_rad))

                # Define bar color using a gradient
                hue = (i / num_bars)  # Hue between 0 and 1
                saturation = 1
                value = bar / 255  # Value based on bar height
                r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
                bar_color = (int(r * 255), int(g * 255), int(b * 255))

                # Draw the bar as a line
                draw.line(
                    [(end_x, end_y), (extended_end_x, extended_end_y)],
                    fill=bar_color,
                    width=bar_width
                )

            # Overlay the central icon based on the current service
            if self.current_service:
                # Fetch the icon from DisplayManager's preloaded icons
                icon_image = self.display_manager.icons.get(self.current_service, self.display_manager.icons.get('default'))
                if icon_image:
                    logo = icon_image.copy()
                    logo_width, logo_height = logo.size

                    self.logger.debug(f"Original logo size: width={logo_width}, height={logo_height}")

                    # Define desired logo size
                    desired_logo_size = 24  # Adjust as needed (e.g., 24x24 pixels)

                    # Scale the logo to desired size while maintaining aspect ratio
                    logo.thumbnail((desired_logo_size, desired_logo_size), Image.ANTIALIAS)

                    logo_width, logo_height = logo.size

                    self.logger.debug(f"Adjusted logo size: width={logo_width}, height={logo_height}")

                    # Calculate position to center the logo
                    logo_position = (
                        center_x - logo_width // 2,
                        center_y - logo_height // 2
                    )
                    self.logger.debug(f"Logo position: {logo_position}")

                    # Paste the logo onto the spectrum image
                    # If the logo has an alpha channel, use it as a mask to preserve transparency
                    if logo.mode in ('RGBA', 'LA') or (logo.mode == 'P' and 'transparency' in logo.info):
                        image.paste(logo, logo_position, logo)
                        self.logger.debug("Pasted central icon onto the spectrum with transparency mask.")
                    else:
                        image.paste(logo, logo_position)
                        self.logger.debug("Pasted central icon onto the spectrum without transparency.")
                else:
                    self.logger.warning(f"No icon found for service '{self.current_service}'. Using default icon.")
            else:
                self.logger.debug("No current service set; skipping central icon.")

            # Convert to match the OLED's mode if necessary
            if image.mode != self.display_manager.oled.mode:
                image = image.convert(self.display_manager.oled.mode)

            # Display on OLED
            self.display_manager.oled.display(image)
            self.logger.info(f"Rendered circular spectrum with central {self.current_service or 'default'} on OLED display.")
        except Exception as e:
            self.logger.error(f"Error rendering circular spectrum on OLED: {e}")

    def set_current_service(self, service):
        """
        Update the current active service.
        
        Args:
            service (str): The name of the active service (e.g., 'spotify', 'tidal').
        """
        if service != self.current_service:
            self.logger.info(f"Updating central icon to service '{service}'.")
            self.current_service = service
            # Optionally, trigger an immediate render by setting a flag or calling a render method
        else:
            self.logger.debug(f"Central icon already set to service '{service}'. No update needed.")

if __name__ == "__main__":
    import yaml

    def load_config(config_path='config.yaml'):
        """Load the YAML configuration file."""
        try:
            with open(config_path, 'r') as file:
                return yaml.safe_load(file)
        except Exception as e:
            print(f"Failed to load configuration: {e}")
            exit(1)

    # Load configuration from config.yaml
    config = load_config('/home/volumio/Quadify/config.yaml')  # Adjust the path as needed

    # Initialize DisplayManager
    display_manager = DisplayManager(config)

    # Initialize CavaOLEDDisplayCircular with desired frame rate
    cava_display = CavaOLEDDisplayCircular(display_manager, frame_rate=30)

    try:
        print("Starting CAVA OLED circular visualization with dynamic central icons...")
        cava_display.start()

        # Keep the script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping CAVA OLED circular visualization...")
    finally:
        cava_display.stop()

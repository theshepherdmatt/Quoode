import os
import time
import threading
from PIL import Image, ImageDraw
from display_manager import DisplayManager
import logging

# Path to the FIFO created for CAVA
FIFO_PATH = "/tmp/display.fifo"

class CavaOLEDDisplay:
    def __init__(self, display_manager):
        self.display_manager = display_manager
        self.running = False
        self.thread = None

        # Configure logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)  # Set to DEBUG for detailed logs
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(handler)

        self.logger.info("CavaOLEDDisplay initialised.")

    def start(self):
        if not os.path.exists(FIFO_PATH):
            self.logger.error(f"FIFO {FIFO_PATH} does not exist. Ensure CAVA is outputting to this file.")
            raise FileNotFoundError(f"FIFO {FIFO_PATH} does not exist.")

        self.logger.info(f"Starting CavaOLEDDisplay. Reading data from {FIFO_PATH}.")
        self.running = True
        self.thread = threading.Thread(target=self._read_fifo)
        self.thread.setDaemon(True)  # Ensure thread does not block exit
        self.logger.debug("Thread created, starting now.")
        self.thread.start()
        self.logger.info("Thread started.")

    def stop(self):
        self.logger.info("Stopping CavaOLEDDisplay.")
        self.running = False
        if self.thread and self.thread.is_alive():
            self.logger.debug("Waiting for the thread to finish.")
            self.thread.join()
        self.logger.info("CavaOLEDDisplay stopped.")

    def _read_fifo(self):
        self.logger.info(f"Opening FIFO for reading: {FIFO_PATH}")
        try:
            with open(FIFO_PATH, "r") as fifo:
                self.logger.info(f"Successfully opened FIFO: {FIFO_PATH}")
                while self.running:
                    try:
                        data = fifo.readline().strip()
                        self.logger.debug(f"Read raw data: '{data}'")
                        if not data:
                            self.logger.warning("Received empty line from FIFO.")
                            continue
                        # Safely parse bar values
                        bars = [int(x) for x in data.split(";") if x.isdigit()]
                        self.logger.debug(f"Parsed bar data: {bars}")
                        if bars:
                            self._draw_bars(bars)
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


    def _draw_bars(self, bars):
        """Render thinner bars with fewer overall bars, horizontally mirrored, and moved down by 10 pixels."""
        self.logger.debug(f"Rendering bars: {bars}")
        try:
            width, height = self.display_manager.oled.size
            downsample_factor = 2  # Reduce the number of bars
            reduced_bars = bars[::downsample_factor]  # Downsample the bars
            total_bars = len(reduced_bars)  # Total bars after downsampling

            bar_width = 1  # Thinner bars
            gap_width = 4  # Spacing between bars
            bar_area_width = (bar_width + gap_width) * total_bars - gap_width  # Total width of bars and gaps
            start_x = (width - bar_area_width) // 2  # Center the bars horizontally
            max_height = height // 2  # Bars span half the height of the screen

            vertical_offset = 20  # Move the bars downward by 10 pixels

            # Create an image buffer
            image = Image.new("RGB", (width, height), "black")
            draw = ImageDraw.Draw(image)

            # Draw left and right mirrored bars
            for i, bar in enumerate(reduced_bars):
                bar_height = int((bar / 255) * max_height)

                # Left side
                x1_left = start_x + i * (bar_width + gap_width)
                x2_left = x1_left + bar_width
                y1 = height // 2 - bar_height + vertical_offset
                y2 = height // 2 + vertical_offset
                draw.rectangle([x1_left, y1, x2_left, y2], fill="#606060")  # Grey colour

                # Right side (mirrored)
                x1_right = width - x2_left
                x2_right = width - x1_left
                draw.rectangle([x1_right, y1, x2_right, y2], fill="#606060")  # Grey colour

            self.logger.debug("Bars drawn successfully.")

            # Display on OLED
            self.display_manager.oled.display(image)
            self.logger.info("Rendered bars on OLED display.")
        except Exception as e:
            self.logger.error(f"Error rendering bars on OLED: {e}")



if __name__ == "__main__":
    # Example configuration for DisplayManager
    config = {
        "icon_dir": "/home/volumio/Quadify/src/assets/images",  # Adjust this path
        "fonts": {
            "default": {"path": "/home/volumio/Quadify/src/assets/fonts/OpenSans-Regular.ttf", "size": 12}
        },
        "logo_path": "/home/volumio/Quadify/src/assets/images/logo.png"  # Adjust this path
    }

    display_manager = DisplayManager(config)
    cava_display = CavaOLEDDisplay(display_manager)

    try:
        print("Starting CAVA OLED visualisation with thinner and shorter bars...")
        cava_display.start()

        # Keep the script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping CAVA OLED visualisation...")
    finally:
        cava_display.stop()

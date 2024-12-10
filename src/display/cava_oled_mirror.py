import os
import time
import threading
from PIL import Image, ImageDraw
from display_manager import DisplayManager
import logging

# Path to the FIFO created for CAVA
FIFO_PATH = "/tmp/display.fifo"

class CavaOLEDDisplay:
    def __init__(self, display_manager, frame_rate=30):
        self.display_manager = display_manager
        self.running = False
        self.thread = None
        self.frame_interval = 1 / frame_rate  # Convert frame rate to interval
        self.last_render_time = 0
        self.previous_bars = None  # For interpolation

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

    def _interpolate_bars(self, current_bars):
        """Smooth transitions between frames."""
        if self.previous_bars is None:
            self.previous_bars = current_bars
        smoothed_bars = [
            int(self.previous_bars[i] * 0.8 + current_bars[i] * 0.2)
            for i in range(len(current_bars))
        ]
        self.previous_bars = smoothed_bars
        return smoothed_bars

    def _draw_bars(self, bars):
        """Render bars on the OLED display."""
        current_time = time.time()
        if current_time - self.last_render_time < self.frame_interval:
            return  # Skip rendering if within frame interval

        self.last_render_time = current_time
        bars = self._interpolate_bars(bars)
        self.logger.debug(f"Rendering bars: {bars}")
        try:
            width, height = self.display_manager.oled.size
            bar_width = (width // len(bars)) - 1  # Adjust bar width for spacing
            max_height = height // 2  # Half-height bars

            # Create an image buffer
            image = Image.new("RGB", (width, height), "black")
            draw = ImageDraw.Draw(image)

            # Draw bars
            for i, bar in enumerate(bars):
                bar_height = int((bar / 255) * max_height)
                x1 = i * (bar_width + 1)  # Add spacing between bars
                x2 = x1 + bar_width
                y1 = (height // 2) - bar_height  # Center vertically
                y2 = (height // 2) + bar_height
                draw.rectangle([x1, y1, x2, y2], fill=(96, 96, 96, 128))  # Grey with slight transparency

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
    cava_display = CavaOLEDDisplay(display_manager, frame_rate=30)

    try:
        print("Starting CAVA OLED visualisation...")
        cava_display.start()

        # Keep the script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping CAVA OLED visualisation...")
    finally:
        cava_display.stop()

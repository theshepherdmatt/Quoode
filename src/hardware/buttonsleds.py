# src/hardware/buttonsleds.py

import smbus2
import time
import threading
import logging
from enum import IntEnum
import yaml
from pathlib import Path

# MCP23017 Register Definitions
MCP23017_IODIRA = 0x00
MCP23017_IODIRB = 0x01
MCP23017_GPIOA = 0x12
MCP23017_GPIOB = 0x13
MCP23017_GPPUA = 0x0C
MCP23017_GPPUB = 0x0D

# Default MCP23017 address if not provided in config.yaml
DEFAULT_MCP23017_ADDRESS = 0x20

# Define LED Constants using IntEnum for clarity
class LED(IntEnum):
    LED1 = 0b10000000  # GPIOA7 - Play LED
    LED2 = 0b01000000  # GPIOA6 - Pause LED
    LED3 = 0b00100000  # GPIOA5 - Previous Button LED
    LED4 = 0b00010000  # GPIOA4 - Next Button LED
    LED5 = 0b00001000  # GPIOA3 - Repeat Button LED
    LED6 = 0b00000100  # GPIOA2 - Random Button LED
    LED7 = 0b00000010  # GPIOA1 - Button 5 LED
    LED8 = 0b00000001  # GPIOA0 - Button 6 LED

class ButtonsLEDController:
    def __init__(self, volumio_listener, config_path='config.yaml', debounce_delay=0.1):
        # Configure the logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.ERROR)  # Set to DEBUG for comprehensive logging

        # Create console handler with a higher log level
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        # Create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)

        # Add the handlers to the logger if not already added
        if not self.logger.handlers:
            self.logger.addHandler(ch)

        self.logger.debug("Initializing ButtonsLEDController.")

        try:
            self.bus = smbus2.SMBus(1)  # Instantiate SMBus directly
            self.logger.debug("I2C bus initialized successfully.")
        except Exception as e:
            self.logger.error(f"Failed to initialize I2C bus: {e}")
            self.bus = None  # Disable bus to prevent further operations

        self.debounce_delay = debounce_delay
        self.prev_button_state = [[1, 1], [1, 1], [1, 1], [1, 1]]
        self.button_map = [[1, 2], [3, 4], [5, 6], [7, 8]]
        self.volumio_listener = volumio_listener
        self.status_led_state = 0
        self.current_button_led_state = 0
        self.current_led_state = 0

        # Load the MCP23017 address from config file or use the default address
        self.mcp23017_address = self._load_mcp_address(config_path)

        # Initialize MCP23017
        self._initialize_mcp23017()

        # Register callbacks with Volumio listener
        self.register_volumio_callbacks()

    def _load_mcp_address(self, config_path):
        self.logger.debug(f"Loading MCP23017 address from config file: {config_path}")
        config_file = Path(config_path)
        if config_file.is_file():
            self.logger.debug("Configuration file found.")
            with open(config_file, 'r') as f:
                try:
                    config = yaml.safe_load(f)
                    address = config.get('mcp23017_address', DEFAULT_MCP23017_ADDRESS)
                    self.logger.debug(f"MCP23017 address loaded: 0x{address:02X}")
                    return address
                except yaml.YAMLError as e:
                    self.logger.error(f"Error reading config file: {e}")
        else:
            self.logger.warning(f"Configuration file {config_path} not found. Using default MCP23017 address.")
        self.logger.debug(f"Using default MCP23017 address: 0x{DEFAULT_MCP23017_ADDRESS:02X}")
        return DEFAULT_MCP23017_ADDRESS

    def _initialize_mcp23017(self):
        if not self.bus:
            self.logger.error("I2C bus not initialized. Cannot initialize MCP23017.")
            return

        try:
            # Configure GPIOA (IODIRA) as outputs for LEDs
            self.bus.write_byte_data(self.mcp23017_address, MCP23017_IODIRA, 0x00)  # All GPIOA pins as outputs
            self.logger.debug("Configured GPIOA as outputs for LEDs.")

            # Configure GPIOB (IODIRB)
            # Set GPIOB0 and GPIOB1 as outputs for button columns
            # Set GPIOB2 to GPIOB7 as inputs for button rows
            self.bus.write_byte_data(self.mcp23017_address, MCP23017_IODIRB, 0xFC)  # 0b11111100
            self.logger.debug("Configured GPIOB0 and GPIOB1 as outputs (button columns), GPIOB2-7 as inputs (button rows).")

            # Enable pull-up resistors on GPIOB2 to GPIOB7 (button rows)
            self.bus.write_byte_data(self.mcp23017_address, MCP23017_GPPUB, 0xFC)  # 0b11111100
            self.logger.debug("Enabled pull-up resistors on GPIOB2-7.")

            # Initialize GPIOA outputs (LEDs) to 0 (all LEDs off)
            self.bus.write_byte_data(self.mcp23017_address, MCP23017_GPIOA, 0x00)
            self.logger.debug("Initialized GPIOA outputs (LEDs) to 0 (all LEDs off).")

            # Initialize GPIOB0 and GPIOB1 (button columns) to high (inactive)
            self.bus.write_byte_data(self.mcp23017_address, MCP23017_GPIOB, 0x03)  # Set B0 and B1 high
            self.logger.debug("Initialized GPIOB0 and GPIOB1 (button columns) to high (inactive).")

            self.logger.info("MCP23017 initialized successfully.")
        except Exception as e:
            self.logger.error(f"Error initializing MCP23017: {e}")
            self.bus = None  # Disable bus to prevent further operations

    def register_volumio_callbacks(self):
        self.logger.debug("Registering Volumio callbacks.")
        try:
            self.volumio_listener.state_changed.connect(self.on_state)
            self.volumio_listener.connected.connect(self.on_connect)
            self.volumio_listener.disconnected.connect(self.on_disconnect)
            self.logger.debug("Volumio callbacks registered successfully.")
        except AttributeError as e:
            self.logger.error(f"Volumio listener does not have the required attributes: {e}")

    def on_connect(self, sender, **kwargs):
        self.logger.info("Connected to Volumio via SocketIO.")

    def on_disconnect(self, sender, **kwargs):
        self.logger.warning("Disconnected from Volumio's SocketIO server.")

    def on_state(self, sender, state):
        new_status = state.get("status")
        if new_status:
            self.logger.debug(f"Volumio status changed to: {new_status.upper()}")
        else:
            self.logger.warning("Received state change with no status.")
        self.update_status_leds(new_status)

    def start(self):
        """Starts the button monitoring loop."""
        self.logger.debug("Starting button monitoring thread.")
        self.running = True
        self.thread = threading.Thread(target=self.check_buttons_and_update_leds, name="ButtonMonitorThread")
        self.thread.start()
        self.logger.info("ButtonsLEDController started.")

    def stop(self):
        """Stops the button monitoring loop."""
        self.logger.debug("Stopping button monitoring thread.")
        self.running = False
        if hasattr(self, 'thread') and self.thread.is_alive():
            self.thread.join()
            self.logger.debug("Button monitoring thread joined successfully.")
        self.logger.info("ButtonsLEDController stopped.")

    def read_button_matrix(self):
        button_matrix_state = [[1, 1], [1, 1], [1, 1], [1, 1]]

        if not self.bus:
            self.logger.error("I2C bus not initialized. Cannot read button matrix.")
            return button_matrix_state

        try:
            for col in range(2):
                # Set one column low at a time on GPIOB0 and GPIOB1
                # Columns are active low
                col_output = ~(1 << col) & 0x03  # Only affecting B0 and B1
                # Preserve B2-B7 as high (input pull-ups)
                self.bus.write_byte_data(self.mcp23017_address, MCP23017_GPIOB, col_output | 0xFC)
                self.logger.debug(f"Set column {col} low: GPIOB = {bin(col_output | 0xFC)}")
                time.sleep(0.005)  # Allow signals to stabilize

                # Read rows from GPIOB2 to GPIOB5
                row_input = self.bus.read_byte_data(self.mcp23017_address, MCP23017_GPIOB)
                self.logger.debug(f"Read GPIOB after setting column {col}: {bin(row_input)}")
                for row in range(4):
                    # Extract the state of each row (active low)
                    button_matrix_state[row][col] = (row_input >> (row + 2)) & 0x01
                    self.logger.debug(f"Button matrix state - Row {row}, Col {col}: {button_matrix_state[row][col]}")
        except Exception as e:
            self.logger.error(f"Error reading button matrix: {e}")

        self.logger.debug(f"Final button matrix state: {button_matrix_state}")
        return button_matrix_state

    def check_buttons_and_update_leds(self):
        self.logger.debug("Button monitoring loop started.")
        while self.running:
            if not self.bus:
                self.logger.error("I2C bus not initialized. Stopping button monitoring.")
                break

            try:
                button_matrix = self.read_button_matrix()
                for row in range(4):
                    for col in range(2):
                        button_id = self.button_map[row][col]
                        current_button_state = button_matrix[row][col]
                        previous_state = self.prev_button_state[row][col]
                        self.logger.debug(f"Checking Button {button_id}: Current State = {current_button_state}, Previous State = {previous_state}")

                        if current_button_state == 0 and previous_state != current_button_state:
                            # Button pressed
                            self.logger.info(f"Button {button_id} pressed")
                            self.handle_button_press(button_id)
                            self.prev_button_state[row][col] = current_button_state
                        else:
                            self.prev_button_state[row][col] = current_button_state
                time.sleep(self.debounce_delay)
            except Exception as e:
                self.logger.error(f"Error in button monitoring loop: {e}")
                time.sleep(1)  # Prevent tight loop on error

        self.logger.debug("Button monitoring loop terminated.")

    def handle_button_press(self, button_id):
        self.logger.debug(f"Handling press for Button {button_id}")
        led_to_light = None

        try:
            # Clear any previous button LEDs
            self.current_button_led_state = 0

            if button_id == 1:
                self.volumio_listener.socketIO.emit('pause')
                self.logger.debug("Emitted 'pause' command to Volumio.")
                # Play/Pause LEDs are handled via Volumio state
            elif button_id == 2:
                self.volumio_listener.socketIO.emit('play')
                self.logger.debug("Emitted 'play' command to Volumio.")
                # Play/Pause LEDs are handled via Volumio state
            elif button_id == 3:
                self.volumio_listener.socketIO.emit('next')
                self.logger.debug("Emitted 'next' command to Volumio.")
                led_to_light = LED.LED4
            elif button_id == 4:
                self.volumio_listener.socketIO.emit('previous')
                self.logger.debug("Emitted 'previous' command to Volumio.")
                led_to_light = LED.LED3
            elif button_id == 5:
                self.volumio_listener.socketIO.emit('repeat')
                self.logger.debug("Emitted 'repeat' command to Volumio.")
                led_to_light = LED.LED5
            elif button_id == 6:
                self.volumio_listener.socketIO.emit('random')
                self.logger.debug("Emitted 'random' command to Volumio.")
                led_to_light = LED.LED6
            elif button_id == 7:
                self.logger.info("Add to favourites functionality not implemented yet.")
                led_to_light = LED.LED7
            elif button_id == 8:
                self.logger.info("Restart OLED service functionality not implemented yet.")
                led_to_light = LED.LED8
            else:
                self.logger.warning(f"Unhandled button ID: {button_id}")

            if led_to_light:
                # Turn off any other button LEDs
                self.current_button_led_state = 0
                # Set the LED for the current button
                self.current_button_led_state = led_to_light.value
                self.logger.debug(f"Button LED state set to: {bin(self.current_button_led_state)}")
                self.control_leds()

                # Start a timer to reset the button LED after 0.5 seconds
                threading.Timer(0.5, self.reset_button_led).start()
            else:
                self.control_leds()
        except Exception as e:
            self.logger.error(f"Error handling button press for Button {button_id}: {e}")

    def reset_button_led(self):
        self.logger.debug("Resetting button LED.")
        self.current_button_led_state = 0
        self.control_leds()

    def control_leds(self):
        # LEDs are controlled via GPIOA; button columns are on GPIOB0 and GPIOB1
        total_state = self.status_led_state | self.current_button_led_state
        self.logger.debug(f"Calculating total LED state: Status = {bin(self.status_led_state)}, Button = {bin(self.current_button_led_state)}, Total = {bin(total_state)}")

        if total_state != self.current_led_state:
            try:
                self.bus.write_byte_data(self.mcp23017_address, MCP23017_GPIOA, total_state)
                self.current_led_state = total_state
                self.logger.info(f"LED state updated: {bin(total_state)}")
            except Exception as e:
                self.logger.error(f"Error setting LED state: {e}")
        else:
            self.logger.debug("LED state unchanged; no update required.")

    def update_status_leds(self, new_status):
        self.logger.debug(f"Updating status LEDs based on new status: {new_status}")
        if new_status == "play":
            self.status_led_state = LED.LED1.value  # Play LED on
            self.logger.debug("Set status_led_state to LED1 (Play).")
        elif new_status in ["pause", "stop"]:
            self.status_led_state = LED.LED2.value  # Pause LED on
            self.logger.debug("Set status_led_state to LED2 (Pause).")
        else:
            self.status_led_state = 0  # Clear status LEDs
            self.logger.debug("Cleared all status LEDs.")
        self.control_leds()

    def clear_all_leds(self):
        """
        Turn off all LEDs.
        """
        try:
            self.bus.write_byte_data(self.mcp23017_address, MCP23017_GPIOA, 0x00)
            self.current_led_state = 0
            self.logger.debug("All LEDs cleared.")
        except Exception as e:
            self.logger.error(f"Error clearing all LEDs: {e}")

    def close(self):
        self.bus.close()
        self.logger.info("Closed SMBus")

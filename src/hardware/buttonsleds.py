# src/hardware/buttonsleds.py

import smbus2
import time
import threading
import logging
import subprocess
from enum import IntEnum
import yaml
from pathlib import Path

# MCP23017 Register Definitions
MCP23017_IODIRA = 0x00
MCP23017_IODIRB = 0x01
MCP23017_GPIOA  = 0x12
MCP23017_GPIOB  = 0x13
MCP23017_GPPUA  = 0x0C
MCP23017_GPPUB  = 0x0D

# Default MCP23017 address if not provided in config.yaml
DEFAULT_MCP23017_ADDRESS = 0x20

# -- NEW: Toggle this if your Play/Pause columns seem reversed
SWAP_COLUMNS = True

# Define LED Constants using IntEnum for clarity
class LED(IntEnum):
    LED1 = 0b10000000  # GPIOA7 - (Play LED)
    LED2 = 0b01000000  # GPIOA6 - (Pause LED)
    LED3 = 0b00100000  # GPIOA5 - (Prev Button LED)
    LED4 = 0b00010000  # GPIOA4 - (Next Button LED)
    LED5 = 0b00001000  # GPIOA3 - (Repeat Button LED)
    LED6 = 0b00000100  # GPIOA2 - (Random Button LED)
    LED7 = 0b00000010  # GPIOA1 - (spare/custom)
    LED8 = 0b00000001  # GPIOA0 - (spare/custom)

class ButtonsLEDController:
    """
    A hardware controller for an MCP23017 expander:
      - Writes to GPIOA for controlling LEDs.
      - Reads a 4x2 button matrix from GPIOB pins.
      - On each button press, calls `mpc` commands to control MPD.
      - Keeps the Play or Pause LED lit based on MPD state.
      - If your play/pause are reversed physically,
        just set SWAP_COLUMNS = True at top.
    """

    def __init__(self, config_path='config.yaml', debounce_delay=0.1):
        # Configure the logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.ERROR)  # Change to DEBUG if needed

        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)

        if not self.logger.handlers:
            self.logger.addHandler(ch)

        self.logger.debug("Initializing ButtonsLEDController.")

        # Attempt to open I2C bus
        try:
            self.bus = smbus2.SMBus(1)
            self.logger.debug("I2C bus initialized successfully.")
        except Exception as e:
            self.logger.error(f"Failed to initialize I2C bus: {e}")
            self.bus = None

        self.debounce_delay = debounce_delay

        # 4x2 matrix => '1' => not pressed, '0' => pressed
        self.prev_button_state = [[1, 1], [1, 1], [1, 1], [1, 1]]

        # Map row/col => button_id
        # Row0 => [1, 2], Row1 => [3,4], Row2 => [5,6], Row3 => [7,8]
        self.button_map = [
            [1, 2],
            [3, 4],
            [5, 6],
            [7, 8],
        ]

        # LED states
        self.status_led_state = 0
        self.current_button_led_state = 0
        self.current_led_state = 0

        # Load MCP address from config
        self.mcp23017_address = self._load_mcp_address(config_path)

        # Initialize the MCP23017
        self._initialize_mcp23017()

        self.running = False

    def _load_mcp_address(self, config_path):
        self.logger.debug(f"Loading MCP23017 address from {config_path}")
        config_file = Path(config_path)
        if config_file.is_file():
            try:
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                    address = config.get('mcp23017_address', DEFAULT_MCP23017_ADDRESS)
                    self.logger.debug(f"MCP23017 address loaded: 0x{address:02X}")
                    return address
            except yaml.YAMLError as e:
                self.logger.error(f"Error reading config file: {e}")
        else:
            self.logger.warning(f"Configuration file {config_path} not found. Using default MCP address.")
        self.logger.debug(f"Using default MCP23017 address: 0x{DEFAULT_MCP23017_ADDRESS:02X}")
        return DEFAULT_MCP23017_ADDRESS

    def _initialize_mcp23017(self):
        """Configure MCP23017 directions and pull-ups."""
        if not self.bus:
            self.logger.error("I2C bus not initialized; cannot init MCP23017.")
            return

        try:
            # GPIOA => outputs for LEDs
            self.bus.write_byte_data(self.mcp23017_address, MCP23017_IODIRA, 0x00)
            self.logger.debug("GPIOA configured as outputs for LEDs.")

            # GPIOB => B0/B1 outputs for columns, B2-B7 as inputs for rows
            self.bus.write_byte_data(self.mcp23017_address, MCP23017_IODIRB, 0xFC)  # 0b11111100
            self.logger.debug("GPIOB => B0/B1 outputs, B2-B7 inputs.")

            # Pull-ups on rows
            self.bus.write_byte_data(self.mcp23017_address, MCP23017_GPPUB, 0xFC)
            self.logger.debug("Pull-ups enabled on GPIOB2-7.")

            # Initialize GPIOA => 0 (all LEDs off)
            self.bus.write_byte_data(self.mcp23017_address, MCP23017_GPIOA, 0x00)
            self.logger.debug("All LEDs off initially.")

            # B0/B1 high => columns inactive
            self.bus.write_byte_data(self.mcp23017_address, MCP23017_GPIOB, 0x03)
            self.logger.debug("GPIOB0/B1 set high (columns inactive).")

            self.logger.info("MCP23017 initialization complete.")
        except Exception as e:
            self.logger.error(f"Error initializing MCP23017: {e}")
            self.bus = None

    def start(self):
        """Start the background thread to monitor buttons & update LEDs."""
        self.logger.debug("Starting button monitoring thread.")
        self.running = True
        self.thread = threading.Thread(target=self.check_buttons_and_update_leds, name="ButtonMonitorThread")
        self.thread.start()
        self.logger.info("ButtonsLEDController started.")

    def stop(self):
        """Stop the background thread."""
        self.logger.debug("Stopping button monitoring thread.")
        self.running = False
        if hasattr(self, 'thread') and self.thread.is_alive():
            self.thread.join()
            self.logger.debug("Button monitoring thread joined.")
        self.logger.info("ButtonsLEDController stopped.")

    def check_buttons_and_update_leds(self):
        """Main loop that polls the button matrix and handles press events."""
        self.logger.debug("Button monitoring loop started.")
        while self.running:
            if not self.bus:
                self.logger.error("I2C bus not initialized; stopping loop.")
                break

            try:
                button_matrix = self.read_button_matrix()
                for row in range(4):
                    for col in range(2):
                        button_id = self.button_map[row][col]
                        current_state = button_matrix[row][col]
                        prev_state = self.prev_button_state[row][col]

                        if current_state == 0 and prev_state != current_state:
                            # A button press
                            self.logger.info(f"Button {button_id} pressed")
                            self.handle_button_press(button_id)

                        self.prev_button_state[row][col] = current_state

                time.sleep(self.debounce_delay)
            except Exception as e:
                self.logger.error(f"Error in button monitoring loop: {e}")
                time.sleep(1)

        self.logger.debug("Button monitoring loop ended.")

    def read_button_matrix(self):
        """Read the 4x2 button matrix from GPIOB pins."""
        button_matrix_state = [[1, 1], [1, 1], [1, 1], [1, 1]]
        if not self.bus:
            self.logger.error("Bus not available; returning default states.")
            return button_matrix_state

        try:
            for col in range(2):
                # Set one column low, the other high (active low)
                col_output = ~(1 << col) & 0x03  # e.g. col=0 => 0b10, col=1 => 0b01
                self.bus.write_byte_data(self.mcp23017_address, MCP23017_GPIOB, col_output | 0xFC)
                time.sleep(0.005)

                row_input = self.bus.read_byte_data(self.mcp23017_address, MCP23017_GPIOB)
                for row in range(4):
                    if SWAP_COLUMNS:
                        # If SWAP_COLUMNS => invert column indexing
                        button_matrix_state[row][1 - col] = (row_input >> (row + 2)) & 0x01
                    else:
                        # Normal
                        button_matrix_state[row][col] = (row_input >> (row + 2)) & 0x01

        except Exception as e:
            self.logger.error(f"Error reading button matrix: {e}")

        return button_matrix_state

    def handle_button_press(self, button_id):
        """
        On button press => call `mpc` & set LED logic.
        - Button1 => play/pause => keep LED1 or LED2 lit based on state
        - Button2 => stop => LED2
        - Next(3), Prev(4), Repeat(5), Random(6) => ephemeral LED
        - Button7 => ephemeral (no specific action)
        - Button8 => restart 'quoode' service
        """
        self.logger.debug(f"Handling press for button {button_id}")

        # Turn off ephemeral button LED for now
        self.current_button_led_state = 0

        try:
            if button_id == 1:
                # Play/Pause => "mpc toggle"
                subprocess.run(["mpc", "toggle"], check=False)
                self.logger.debug("Ran 'mpc toggle'.")
                # Now parse new state => if playing => LED1; else => LED2
                self.update_play_pause_led()

            elif button_id == 2:
                # Stop => "mpc stop"
                subprocess.run(["mpc", "stop"], check=False)
                self.logger.debug("Ran 'mpc stop'.")
                # For stop => pause LED
                self.status_led_state = LED.LED2.value
                self.control_leds()

            elif button_id == 3:
                # Next => ephemeral LED
                subprocess.run(["mpc", "next"], check=False)
                self.logger.debug("Ran 'mpc next'.")
                self.light_button_led_for(LED.LED4, 0.5)

            elif button_id == 4:
                # Previous => ephemeral LED
                subprocess.run(["mpc", "prev"], check=False)
                self.logger.debug("Ran 'mpc prev'.")
                self.light_button_led_for(LED.LED3, 0.5)

            elif button_id == 5:
                # repeat => ephemeral
                subprocess.run(["mpc", "repeat"], check=False)
                self.logger.debug("Ran 'mpc repeat'.")
                self.light_button_led_for(LED.LED5, 0.5)

            elif button_id == 6:
                # random => ephemeral
                subprocess.run(["mpc", "random"], check=False)
                self.logger.debug("Ran 'mpc random'.")
                self.light_button_led_for(LED.LED6, 0.5)

            elif button_id == 7:
                # ephemeral, no action
                self.logger.info("Button 7 pressed, no specific mpc action assigned.")
                self.light_button_led_for(LED.LED7, 0.5)

            elif button_id == 8:
                # restart Quoode
                self.logger.info("Button 8 pressed, restarting 'quoode' systemd service.")
                subprocess.run(["sudo", "systemctl", "restart", "quoode"], check=False)
                self.logger.debug("Ran 'systemctl restart quoode'.")
                self.light_button_led_for(LED.LED8, 0.5)

            else:
                self.logger.warning(f"Unhandled button ID: {button_id}")

        except Exception as e:
            self.logger.error(f"Error handling button {button_id}: {e}")

    def update_play_pause_led(self):
        """Check if MPD is playing => LED1, else => LED2 (for pause/stop)."""
        try:
            result = subprocess.run(["mpc", "status"], capture_output=True, text=True)
            if result.returncode == 0:
                output = result.stdout.lower()
                if "[playing]" in output:
                    self.logger.debug("MPD => playing => LED1 on.")
                    self.status_led_state = LED.LED1.value
                elif "[paused]" in output or "[pause]" in output or "[stopped]" in output:
                    self.logger.debug("MPD => paused/stop => LED2 on.")
                    self.status_led_state = LED.LED2.value
                else:
                    self.logger.debug("MPD => neither playing nor paused => no LED.")
                    self.status_led_state = 0
                self.control_leds()
            else:
                self.logger.warning("mpc status command failed; no LED update.")
        except Exception as e:
            self.logger.error(f"Error checking MPD state for LED: {e}")

    def light_button_led_for(self, led, duration):
        """Light an LED briefly, then revert to status-led-based state."""
        self.current_button_led_state = led.value
        self.control_leds()
        threading.Timer(duration, self.reset_button_led).start()

    def reset_button_led(self):
        self.logger.debug("Resetting ephemeral button LED.")
        self.current_button_led_state = 0
        self.control_leds()

    def control_leds(self):
        """Combine status_led_state & ephemeral LED, write to GPIOA."""
        total_state = self.status_led_state | self.current_button_led_state
        self.logger.debug(
            f"LED states => status: {bin(self.status_led_state)}, "
            f"button: {bin(self.current_button_led_state)}, "
            f"total: {bin(total_state)}"
        )

        if total_state != self.current_led_state:
            if self.bus:
                try:
                    self.bus.write_byte_data(self.mcp23017_address, MCP23017_GPIOA, total_state)
                    self.current_led_state = total_state
                    self.logger.info(f"LED state updated: {bin(total_state)}")
                except Exception as e:
                    self.logger.error(f"Error setting LED state: {e}")
            else:
                self.logger.error("No I2C bus for LED control.")
        else:
            self.logger.debug("LED state unchanged; no update needed.")

    def clear_all_leds(self):
        """Turn off all LEDs."""
        if not self.bus:
            self.logger.warning("No I2C bus to clear LEDs.")
            return
        try:
            self.bus.write_byte_data(self.mcp23017_address, MCP23017_GPIOA, 0x00)
            self.current_led_state = 0
            self.logger.debug("All LEDs cleared.")
        except Exception as e:
            self.logger.error(f"Error clearing all LEDs: {e}")

    def close(self):
        """Close the I2C bus when done."""
        if self.bus:
            self.bus.close()
            self.logger.info("Closed SMBus.")

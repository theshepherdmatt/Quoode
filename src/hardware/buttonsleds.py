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

# Toggle if your play/pause columns are physically reversed
SWAP_COLUMNS = True

# Define LED constants (GPIOA bits). Example bit usage:
class LED(IntEnum):
    LED1 = 0b10000000  # GPIOA7 => Play LED
    LED2 = 0b01000000  # GPIOA6 => Pause LED
    LED3 = 0b00100000  # GPIOA5 => Previous Button LED
    LED4 = 0b00010000  # GPIOA4 => Next Button LED
    LED5 = 0b00001000  # GPIOA3 => Repeat Button LED
    LED6 = 0b00000100  # GPIOA2 => Random Button LED
    LED7 = 0b00000010  # GPIOA1 => spare/custom
    LED8 = 0b00000001  # GPIOA0 => spare/custom

class ButtonsLEDController:
    """
    A hardware controller for an MCP23017 expander:
      - Writes to GPIOA for controlling LEDs.
      - Reads a 4x2 button matrix from GPIOB pins.
      - On each button press, calls `mpc` commands to control MPD.
      - Continuously polls MPD to keep the Play or Pause LED lit even if user
        controls playback externally (like from a phone).
    """

    def __init__(self, config_path='config.yaml', debounce_delay=0.1):
        # Setup logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.ERROR)  # change to DEBUG if needed

        # Add console handler in debug mode
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(ch)

        self.logger.debug("Initializing ButtonsLEDController.")

        # Attempt I2C bus init
        try:
            self.bus = smbus2.SMBus(1)
            self.logger.debug("I2C bus initialized successfully.")
        except Exception as e:
            self.logger.error(f"Failed to initialize I2C bus: {e}")
            self.bus = None

        self.debounce_delay = debounce_delay

        # 4x2 matrix => '1' => not pressed, '0' => pressed
        self.prev_button_state = [[1, 1], [1, 1], [1, 1], [1, 1]]

        # Button map: row/col => button_id
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

        # Read config for MCP address
        self.mcp23017_address = self._load_mcp_address(config_path)

        # Initialize the MCP
        self._initialize_mcp23017()

        # Control threads
        self.running = False
        self.monitor_thread = None

    def _load_mcp_address(self, config_path):
        self.logger.debug(f"Loading MCP23017 address from {config_path}")
        cfg_file = Path(config_path)
        if cfg_file.is_file():
            try:
                with open(cfg_file, 'r') as f:
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
            self.logger.debug("GPIOA => outputs for LEDs.")

            # GPIOB => B0/B1 outputs (columns), B2-B7 inputs (rows)
            self.bus.write_byte_data(self.mcp23017_address, MCP23017_IODIRB, 0xFC)
            self.logger.debug("GPIOB => B0/B1 outputs, B2-B7 inputs.")

            # Pull-ups on rows
            self.bus.write_byte_data(self.mcp23017_address, MCP23017_GPPUB, 0xFC)
            self.logger.debug("Enabled pull-ups on B2-B7.")

            # Initialize GPIOA => 0 => all LEDs off
            self.bus.write_byte_data(self.mcp23017_address, MCP23017_GPIOA, 0x00)
            self.logger.debug("All LEDs off initially.")

            # B0/B1 high => columns inactive
            self.bus.write_byte_data(self.mcp23017_address, MCP23017_GPIOB, 0x03)
            self.logger.debug("GPIOB0/B1 set high (columns inactive).")

            self.logger.info("MCP23017 init complete.")
        except Exception as e:
            self.logger.error(f"Error initializing MCP23017: {e}")
            self.bus = None

    def start(self):
        """
        Start the button-monitor thread and the MPD monitor thread
        so that LED states are continuously updated.
        """
        self.logger.debug("Starting ButtonsLEDController threads.")
        self.running = True

        # 1) Thread for reading button matrix
        self.thread = threading.Thread(target=self._monitor_buttons_loop, name="ButtonMonitorThread")
        self.thread.start()

        # 2) Thread for polling MPD status => keep play/pause LED in sync
        self.monitor_thread = threading.Thread(target=self._monitor_mpd_loop, name="MPDMonitorThread")
        self.monitor_thread.start()

        self.logger.info("ButtonsLEDController started.")

    def stop(self):
        """Stop both threads."""
        self.logger.debug("Stopping ButtonsLEDController threads.")
        self.running = False

        if hasattr(self, 'thread') and self.thread.is_alive():
            self.thread.join()
            self.logger.debug("ButtonMonitorThread joined.")

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join()
            self.logger.debug("MPDMonitorThread joined.")

        self.logger.info("ButtonsLEDController stopped.")

    # -----------------------------------------------------------
    #  Threads
    # -----------------------------------------------------------
    def _monitor_buttons_loop(self):
        """
        Continuously polls the button matrix and triggers handle_button_press
        on transitions from '1' (not pressed) to '0' (pressed).
        """
        self.logger.debug("Button monitoring loop started.")
        while self.running:
            if not self.bus:
                self.logger.error("I2C bus not available; stopping button loop.")
                break

            try:
                matrix = self._read_button_matrix()
                for row in range(4):
                    for col in range(2):
                        btn_id = self.button_map[row][col]
                        curr_state = matrix[row][col]
                        prev_state = self.prev_button_state[row][col]

                        # Check for newly pressed
                        if curr_state == 0 and prev_state != curr_state:
                            self.logger.info(f"Button {btn_id} pressed.")
                            self.handle_button_press(btn_id)

                        self.prev_button_state[row][col] = curr_state
                time.sleep(self.debounce_delay)

            except Exception as e:
                self.logger.error(f"Error in _monitor_buttons_loop: {e}")
                time.sleep(1)
        self.logger.debug("Button monitoring loop ended.")

    def _monitor_mpd_loop(self):
        """
        Periodically checks MPD status to keep LED1 or LED2 lit
        depending on playback state, even if user controls MPD externally.
        """
        self.logger.debug("MPD monitor loop started.")
        while self.running:
            try:
                self.update_play_pause_led()
            except Exception as e:
                self.logger.error(f"Exception in MPD monitor loop: {e}")
            time.sleep(2)  # check every 2 seconds
        self.logger.debug("MPD monitor loop ended.")

    # -----------------------------------------------------------
    #  Reading Buttons
    # -----------------------------------------------------------
    def _read_button_matrix(self):
        """
        Return a 4x2 array of 1/0 states for each button,
        1 => not pressed, 0 => pressed.
        """
        default_state = [[1, 1], [1, 1], [1, 1], [1, 1]]
        if not self.bus:
            return default_state

        matrix_state = [[1, 1], [1, 1], [1, 1], [1, 1]]

        try:
            for col in range(2):
                col_output = ~(1 << col) & 0x03  # col=0 => 0b10; col=1 => 0b01
                self.bus.write_byte_data(self.mcp23017_address, MCP23017_GPIOB, col_output | 0xFC)
                time.sleep(0.005)

                row_in = self.bus.read_byte_data(self.mcp23017_address, MCP23017_GPIOB)
                for row in range(4):
                    bit_val = (row_in >> (row + 2)) & 0x01
                    if SWAP_COLUMNS:
                        matrix_state[row][1 - col] = bit_val
                    else:
                        matrix_state[row][col] = bit_val

        except Exception as e:
            self.logger.error(f"Error reading button matrix: {e}")
        return matrix_state

    # -----------------------------------------------------------
    #  Button Press Handling
    # -----------------------------------------------------------
    def handle_button_press(self, button_id):
        """
        For each button, run an 'mpc' command or ephemeral LED, etc.
        """
        # Clear ephemeral LED
        self.current_button_led_state = 0

        try:
            if button_id == 1:
                # "mpc toggle" => sets either playing or paused
                subprocess.run(["mpc", "toggle"], check=False)
                self.logger.debug("Executed 'mpc toggle'.")
                # We'll let the mpd monitor thread handle LED1 or LED2.

            elif button_id == 2:
                # "mpc stop" => sets paused LED
                subprocess.run(["mpc", "stop"], check=False)
                self.logger.debug("Executed 'mpc stop'.")
                self.status_led_state = LED.LED2.value
                self.control_leds()

            elif button_id == 3:
                subprocess.run(["mpc", "next"], check=False)
                self.logger.debug("Executed 'mpc next'.")
                self.light_button_led_for(LED.LED4, 0.5)

            elif button_id == 4:
                subprocess.run(["mpc", "prev"], check=False)
                self.logger.debug("Executed 'mpc prev'.")
                self.light_button_led_for(LED.LED3, 0.5)

            elif button_id == 5:
                subprocess.run(["mpc", "repeat"], check=False)
                self.logger.debug("Executed 'mpc repeat'.")
                self.light_button_led_for(LED.LED5, 0.5)

            elif button_id == 6:
                subprocess.run(["mpc", "random"], check=False)
                self.logger.debug("Executed 'mpc random'.")
                self.light_button_led_for(LED.LED6, 0.5)

            elif button_id == 7:
                self.logger.info("Button 7 pressed, no special action assigned.")
                self.light_button_led_for(LED.LED7, 0.5)

            elif button_id == 8:
                self.logger.info("Button 8 pressed => restarting 'quoode' service.")
                subprocess.run(["sudo", "systemctl", "restart", "quoode"], check=False)
                self.logger.debug("Executed 'systemctl restart quoode'.")
                self.light_button_led_for(LED.LED8, 0.5)

            else:
                self.logger.warning(f"Unhandled button ID: {button_id}")

        except Exception as e:
            self.logger.error(f"Error handling button {button_id}: {e}")

    # -----------------------------------------------------------
    #  MPD State => LED1 or LED2
    # -----------------------------------------------------------
    def update_play_pause_led(self):
        """
        Reads MPD status. If playing => LED1 on. If paused/stopped => LED2 on.
        """
        try:
            res = subprocess.run(["mpc", "status"], capture_output=True, text=True)
            if res.returncode == 0:
                out = res.stdout.lower()
                if "[playing]" in out:
                    self.logger.debug("MPD => playing => LED1 on.")
                    self.status_led_state = LED.LED1.value
                elif "[paused]" in out or "[pause]" in out or "[stopped]" in out:
                    self.logger.debug("MPD => paused/stopped => LED2 on.")
                    self.status_led_state = LED.LED2.value
                else:
                    # No recognized state => turn both off or pick one
                    self.logger.debug("MPD => unknown => no LED.")
                    self.status_led_state = 0

                self.control_leds()
            else:
                self.logger.warning("mpc status command failed; no LED update.")
        except Exception as e:
            self.logger.error(f"update_play_pause_led: {e}")

    # -----------------------------------------------------------
    #  Ephemeral Button LED
    # -----------------------------------------------------------
    def light_button_led_for(self, led, duration):
        """
        Turn on a button LED for 'duration' seconds; revert to main LED state.
        """
        self.current_button_led_state = led.value
        self.control_leds()
        threading.Timer(duration, self.reset_button_led).start()

    def reset_button_led(self):
        self.logger.debug("Resetting ephemeral button LED.")
        self.current_button_led_state = 0
        self.control_leds()

    # -----------------------------------------------------------
    #  LED Writing
    # -----------------------------------------------------------
    def control_leds(self):
        """
        Combine status_led_state & ephemeral, write to MCP23017 GPIOA.
        """
        total_state = self.status_led_state | self.current_button_led_state
        self.logger.debug(
            f"LED states => status: {bin(self.status_led_state)}, "
            f"button: {bin(self.current_button_led_state)}, total: {bin(total_state)}"
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
        """Close the I2C bus if needed."""
        if self.bus:
            self.bus.close()
            self.logger.info("Closed SMBus.")

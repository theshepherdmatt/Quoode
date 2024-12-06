import logging
import time
import RPi.GPIO as GPIO
from .gpio_setup_module import GPIOSetup  # Import the GPIO setup module

class RotaryControl:
    def __init__(
        self,
        gpio_setup=None,
        rotation_callback=None,
        button_callback=None,
        long_press_callback=None,
        long_press_threshold=2.5  # Long press threshold in seconds
    ):
        """
        Initializes the RotaryControl with GPIO setup already provided.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)  # Set to DEBUG for detailed logs

        if gpio_setup is None:
            self.gpio_setup = GPIOSetup(clk_pin=13, dt_pin=5, sw_pin=6)
        else:
            self.gpio_setup = gpio_setup
        self.rotation_callback = rotation_callback
        self.button_callback = button_callback
        self.long_press_callback = long_press_callback
        self.long_press_threshold = long_press_threshold

        # Use GPIO pins from the provided gpio_setup
        self.CLK_PIN = self.gpio_setup.CLK_PIN
        self.DT_PIN = self.gpio_setup.DT_PIN
        self.SW_PIN = self.gpio_setup.SW_PIN

        # Variables for rotary state
        self.last_encoded = self._read_encoder()  # To track the previous state of CLK and DT
        self.full_cycle = 0  # To track full quadrature cycles
        self.button_last_state = self._read_button_state()  # Save the initial state of the button

        self.logger.debug("RotaryControl initialized using GPIO setup.")

    def _read_encoder(self):
        """Read the current state of the rotary encoder."""
        clk_state = GPIO.input(self.CLK_PIN)
        dt_state = GPIO.input(self.DT_PIN)
        return (clk_state << 1) | dt_state  # Encode as a 2-bit integer

    def _read_button_state(self):
        """Read the current state of the button."""
        return GPIO.input(self.SW_PIN)

    def start(self):
        """Start listening to rotary events."""
        self.logger.debug("RotaryControl started listening to rotary events.")
        try:
            # Read the initial encoder state
            self.last_encoded = self._read_encoder()

            while True:
                # Read the current encoder state
                current_encoded = self._read_encoder()

                # Detect changes in state
                if current_encoded != self.last_encoded:
                    # Determine direction based on state transitions
                    if (self.last_encoded == 0b00 and current_encoded == 0b10) or \
                       (self.last_encoded == 0b10 and current_encoded == 0b11) or \
                       (self.last_encoded == 0b11 and current_encoded == 0b01) or \
                       (self.last_encoded == 0b01 and current_encoded == 0b00):
                        self.full_cycle += 1  # Clockwise step
                    elif (self.last_encoded == 0b00 and current_encoded == 0b01) or \
                         (self.last_encoded == 0b01 and current_encoded == 0b11) or \
                         (self.last_encoded == 0b11 and current_encoded == 0b10) or \
                         (self.last_encoded == 0b10 and current_encoded == 0b00):
                        self.full_cycle -= 1  # Counter-clockwise step

                    # Register a single detent after a full cycle
                    if abs(self.full_cycle) == 4:  # Full quadrature cycle detected
                        direction = 1 if self.full_cycle > 0 else -1
                        self.logger.debug(f"Scrolling in direction: {direction}")
                        if self.rotation_callback:
                            self.rotation_callback(direction)
                        self.full_cycle = 0  # Reset cycle counter

                    self.last_encoded = current_encoded  # Update last state

                # Poll the button state
                button_state = self._read_button_state()
                if button_state == GPIO.LOW and self.button_last_state == GPIO.HIGH:
                    press_start_time = time.time()
                    while GPIO.input(self.SW_PIN) == GPIO.LOW:
                        if time.time() - press_start_time > self.long_press_threshold:
                            if self.long_press_callback:
                                self.long_press_callback()
                            break
                    else:
                        if time.time() - press_start_time < self.long_press_threshold:
                            if self.button_callback:
                                self.button_callback()

                # Update the last state for the button
                self.button_last_state = button_state

                # Add a small delay to avoid CPU overuse
                time.sleep(0.01)

        except KeyboardInterrupt:
            self.logger.info("RotaryControl terminated by user.")
            self.stop()

    def stop(self):
        """Cleans up GPIO resources using the GPIOSetup instance."""
        self.gpio_setup.cleanup()
        self.logger.info("GPIO cleanup complete.")

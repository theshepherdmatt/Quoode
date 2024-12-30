import RPi.GPIO as GPIO
import time

class GPIOSetup:
    def __init__(self, clk_pin, dt_pin, sw_pin):
        """
        Initializes GPIO pins for the rotary encoder, using BCM mode if not already set.
        """
        self.CLK_PIN = clk_pin
        self.DT_PIN = dt_pin
        self.SW_PIN = sw_pin

        # Check current GPIO mode. If None, set to BCM; if something else, clean up and reset.
        current_mode = GPIO.getmode()
        if current_mode is None:
            GPIO.setmode(GPIO.BCM)
        elif current_mode != GPIO.BCM:
            # Optionally do cleanup before forcing BCM:
            GPIO.cleanup()
            GPIO.setmode(GPIO.BCM)

        # Now configure the pins for input with pull-ups.
        GPIO.setup(self.CLK_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.DT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.SW_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def cleanup(self):
        """Cleans up GPIO resources."""
        GPIO.cleanup()

# Usage example
if __name__ == "__main__":
    gpio_setup = GPIOSetup(clk_pin=13, dt_pin=5, sw_pin=6)
    try:
        # Main code would go here
        while True:
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("Program terminated by user.")
    finally:
        gpio_setup.cleanup()

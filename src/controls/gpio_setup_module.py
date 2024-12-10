import RPi.GPIO as GPIO
import time

class GPIOSetup:
    def __init__(self, clk_pin, dt_pin, sw_pin):
        """
        Initializes GPIO pins for the rotary encoder.
        """
        self.CLK_PIN = clk_pin
        self.DT_PIN = dt_pin
        self.SW_PIN = sw_pin

        # Set up GPIO
        GPIO.setmode(GPIO.BCM)
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
            # Add a small delay to avoid CPU overuse
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("Program terminated by user.")
    finally:
        gpio_setup.cleanup()


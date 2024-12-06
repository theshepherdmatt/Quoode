#!/usr/bin/env python3

import RPi.GPIO as GPIO
import time
import sys

# Use Broadcom pin numbering
GPIO.setmode(GPIO.BCM)

# Define the GPIO pin connected to OLED reset
OLED_GPIO_PIN = 25

try:
    # Set GPIO pin as output
    GPIO.setup(OLED_GPIO_PIN, GPIO.OUT)

    # Reset GPIO pin (turn off OLED)
    GPIO.output(OLED_GPIO_PIN, GPIO.LOW)

    # Optional: Wait for a short period
    time.sleep(1)

except Exception as e:
    # Print the error to the console for debugging if needed
    print(f"Error while resetting OLED GPIO: {e}")
    sys.exit(1)  # Exit with error

finally:
    # Clean up GPIO settings
    GPIO.cleanup()


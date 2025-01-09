#!/usr/bin/env python3

import RPi.GPIO as GPIO
import time
import sys

# Use Broadcom pin numbering
GPIO.setmode(GPIO.BCM)

# The GPIO pin tied to your SSD1322/SSD display's Reset line
OLED_GPIO_PIN = 25

try:
    # Configure the pin as an output
    GPIO.setup(OLED_GPIO_PIN, GPIO.OUT)

    # Drive it LOW to force the display into hardware reset (screen goes off)
    GPIO.output(OLED_GPIO_PIN, GPIO.LOW)

    # Optionally wait a moment if you like
    time.sleep(0.5)

except Exception as e:
    print(f"Error while attempting to drive OLED RESET pin low: {e}", file=sys.stderr)
    sys.exit(1)

# Notice we do NOT call GPIO.cleanup() here.
# This preserves the pin state as LOW even after the script exits,
# keeping the display off until the system restarts your main Quoode app.

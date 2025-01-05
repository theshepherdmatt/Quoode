#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time

BTN_PIN = 6
GPIO.setwarnings(False)     # Suppress "channel already in use" warning
GPIO.setmode(GPIO.BCM)      # Ensure we use BCM numbering
GPIO.setup(BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

last_state = GPIO.HIGH

try:
    while True:
        current_state = GPIO.input(BTN_PIN)
        if current_state != last_state:
            print(f"Button changed from {last_state} to {current_state}")
            last_state = current_state
        time.sleep(0.01)
except KeyboardInterrupt:
    GPIO.cleanup()

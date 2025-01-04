# src/main.py

#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time
import threading
import logging
import yaml
import os
import sys
from PIL import Image, ImageSequence

# Importing components from the src directory
from display.display_manager import DisplayManager
from correct_time import wait_for_correct_time
from display.screens.clock import Clock
from display.screens.original_screen import OriginalScreen
from display.screens.modern_screen import ModernScreen
from managers.mode_manager import ModeManager
from managers.menu_manager import MenuManager
from managers.menus.playlist_manager import PlaylistManager
from managers.menus.radio_manager import RadioManager
from managers.menus.library_manager import LibraryManager
from managers.menus.usb_library_manager import USBLibraryManager
from controls.rotary_control import RotaryControl

# Moode-based MPD listener
from network.moode_listener import MoodeListener

from hardware.buttonsleds import ButtonsLEDController
from handlers.state_handler import StateHandler
from managers.manager_factory import ManagerFactory


def load_config(config_path='/config.yaml'):
    abs_path = os.path.abspath(config_path)
    print(f"Attempting to load config from: {abs_path}")
    print(f"Does the file exist? {os.path.isfile(config_path)}")  # Debug line
    config = {}
    if os.path.isfile(config_path):
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
            logging.debug(f"Configuration loaded from {config_path}.")
        except yaml.YAMLError as e:
            logging.error(f"Error loading config file {config_path}: {e}")
    else:
        logging.warning(f"Config file {config_path} not found. Using default configuration.")
    return config

def main():
    # 1. Set up logging
    logging.basicConfig(
        level=logging.INFO,  # Set to DEBUG for detailed logs
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger("Main")

    # 2. Load configuration
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, '..', 'config.yaml')
    config = load_config(config_path)

    # 3. Initialize DisplayManager
    display_config = config.get('display', {})
    display_manager = DisplayManager(display_config)

    # 4. Display logo for 5 seconds
    logger.info("Displaying startup logo...")
    display_manager.show_logo()
    logger.info("Startup logo displayed for 5 seconds.")
    time.sleep(5)  # Wait for 5 seconds to ensure the logo is visible

    # A. Clear the Screen After Logo Display
    display_manager.clear_screen()
    logger.info("Screen cleared after logo display.")

    # 5. Define events to signal when Moode is ready and minimum loading duration has elapsed
    moode_ready_event = threading.Event()
    min_loading_event = threading.Event()
    time_correct_event = threading.Event()
    min_loading_duration = 5  # seconds

    # 6. Define a function to set the minimum loading duration
    def set_min_loading_event():
        time.sleep(min_loading_duration)
        min_loading_event.set()
        logger.info(f"Minimum loading duration of {min_loading_duration}s has elapsed.")

    # Start the timer thread
    timer_thread = threading.Thread(target=set_min_loading_event, daemon=True)
    timer_thread.start()

    # 7. Define a function to show loading GIF until all events are set
    def show_loading():
        loading_gif_path = config['display'].get('loading_gif_path', 'loading.gif')
        try:
            image = Image.open(loading_gif_path)
            if not getattr(image, "is_animated", False):
                logger.warning(f"The loading GIF at '{loading_gif_path}' is not animated.")
                return
        except IOError:
            logger.error(f"Failed to load loading GIF '{loading_gif_path}'.")
            return

        logger.info("Displaying loading GIF (until MPD is ready + time correct + min load).")
        display_manager.clear_screen()
        time.sleep(0.1)

        while True:
            # If all are set, exit the loop
            if (moode_ready_event.is_set() and
                time_correct_event.is_set() and
                min_loading_event.is_set()):
                logger.info("All events set, exiting loading GIF.")
                return

            # Cycle frames
            for frame in ImageSequence.Iterator(image):
                # Double-check inside each frame
                if (moode_ready_event.is_set() and
                    time_correct_event.is_set() and
                    min_loading_event.is_set()):
                    logger.info("All events set mid-frame, exiting loading GIF.")
                    return

                display_manager.oled.display(frame.convert(display_manager.oled.mode))
                frame_duration = frame.info.get('duration', 100) / 1000.0
                time.sleep(frame_duration)

    # 8. Start the loading GIF in a separate daemon thread
    loading_thread = threading.Thread(target=show_loading, daemon=True)
    loading_thread.start()

    # 9. Initialize MoodeListener with moode_ready_event
    moode_config = config.get('moode', {})
    moode_host = moode_config.get('host', 'localhost')
    moode_port = moode_config.get('port', 6600)

    # Pass the moode_ready_event to MoodeListener
    moode_listener = MoodeListener(
        host=moode_host,
        port=moode_port,
        reconnect_delay=5,
        mode_manager=None,        # We'll assign this after creating ModeManager
        auto_connect=False,       # Avoid immediate connect
        moode_ready_event=moode_ready_event  # Pass the event
    )

    # 10. Initialize Clock
    clock_config = config.get('clock', {})
    clock = Clock(display_manager, clock_config)
    clock.logger = logging.getLogger("Clock")
    clock.logger.setLevel(logging.INFO)

    # 11. Initialize ModeManager
    mode_manager = ModeManager(
        display_manager=display_manager,
        clock=clock,
        moode_listener=moode_listener
    )

    # 12. Link them both ways
    moode_listener.mode_manager = mode_manager

    # 13. Now actually connect to MPD (init_listener)
    moode_listener.init_listener()

    # 14. Start the time synchronization thread
    def check_time_sync():
        if wait_for_correct_time(threshold_year=2023, timeout=60):
            time_correct_event.set()
            logger.info("System time is confirmed correct (year >= 2023).")
        else:
            logger.warning("System time did not sync within 60s; continuing anyway.")
            time_correct_event.set()

    time_sync_thread = threading.Thread(target=check_time_sync, daemon=True)
    time_sync_thread.start()

    # 15. Wait until all events are set
    logger.info("Waiting for MPD (moode_ready_event), correct time, and min loading to pass...")
    while not (moode_ready_event.is_set() and
               time_correct_event.is_set() and
               min_loading_event.is_set()):
        time.sleep(0.2)

    logger.info("All readiness events satisfied. Proceeding with initialization...")

    mode_manager.to_clock()
    logger.info("ModeManager: switched to clock after loading.")


    # 16. Build other managers via ManagerFactory
    manager_factory = ManagerFactory(
        display_manager=display_manager,
        moode_listener=moode_listener,
        mode_manager=mode_manager,
        config=config
    )
    manager_factory.setup_mode_manager()

    # Extract references if needed
    original_screen = manager_factory.original_screen
    modern_screen = manager_factory.modern_screen
    menu_manager = manager_factory.menu_manager
    playlist_manager = manager_factory.playlist_manager
    radio_manager = manager_factory.radio_manager
    library_manager = manager_factory.library_manager
    usb_library_manager = manager_factory.usb_library_manager

    # 17. Initialize ButtonsLEDController
    buttons_leds = ButtonsLEDController(moode_listener=moode_listener, config_path=config_path)
    buttons_leds.start()

    # 18. Rotary callbacks (Unchanged from your code)
    def on_rotate(direction):
        current_mode = mode_manager.get_mode()
        if current_mode == 'original':
            volume_change = 10 if direction == 1 else -10
            original_screen.adjust_volume(volume_change)
        elif current_mode == 'playback':
            volume_change = 10 if direction == 1 else -10
            original_screen.adjust_volume(volume_change)
        elif current_mode == 'modern':
            volume_change = 10 if direction == 1 else -10
            modern_screen.adjust_volume(volume_change)
        elif current_mode == 'menu':
            menu_manager.scroll_selection(direction)
        else:
            logger.warning(f"Unhandled mode: {current_mode}. No rotary action performed.")

    def on_button_press_inner():
        current_mode = mode_manager.get_mode()
        if current_mode == 'clock':
            mode_manager.to_menu()
        elif current_mode == 'menu':
            menu_manager.select_item()
        elif current_mode == 'original':
            original_screen.toggle_play_pause()
        elif current_mode == 'modern':
            modern_screen.toggle_play_pause()
        elif current_mode == 'playback':
            original_screen.toggle_play_pause()
        else:
            logger.warning(f"Unhandled mode: {current_mode}. No button action performed.")

    def on_long_press():
        logger.info("Long button press detected.")
        current_mode = mode_manager.get_mode()
        if current_mode != 'clock':
            mode_manager.to_clock()
            logger.info("ModeManager: Switched to 'clock' mode via long press.")

    # 19. Initialize RotaryControl
    rotary_control = RotaryControl(
        rotation_callback=on_rotate,
        button_callback=on_button_press_inner,
        long_press_callback=on_long_press,
        long_press_threshold=2.5
    )
    rotary_control.start()

    # 20. Run the Main Application Loop
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down Quoode...")
    finally:
        buttons_leds.stop()
        rotary_control.stop()
        moode_listener.stop()
        clock.stop()
        display_manager.clear_screen()
        logger.info("Quoode has been shut down gracefully.")

if __name__ == "__main__":
    main()

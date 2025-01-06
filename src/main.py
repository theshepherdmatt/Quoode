#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time
import threading
import logging
import yaml
import json             
import os
import sys
import subprocess
from PIL import Image, ImageSequence

# Importing components from the src directory
from display.display_manager import DisplayManager
from correct_time import wait_for_correct_time
from display.screens.clock import Clock
from display.screens.original_screen import OriginalScreen
from display.screens.modern_screen import ModernScreen
from display.screensavers.snakescreensaver import SnakeScreensaver
from managers.mode_manager import ModeManager
from managers.menu_manager import MenuManager
from managers.menus.clock_menu import ClockMenu
from controls.rotary_control import RotaryControl

# Moode-based MPD listener
from network.moode_listener import MoodeListener

# Optional additional hardware / managers
# from hardware.buttonsleds import ButtonsLEDController
from handlers.state_handler import StateHandler
from managers.manager_factory import ManagerFactory

# For volume-debounce
last_volume_update = 0
volume_update_cooldown = 0.2  # 200 ms

IDLE_TIMEOUT = 10  # or 10 * 60 for 10 minutes

def load_config(config_path='/config.yaml'):
    """
    Load a YAML-based configuration file.
    """
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

def load_preferences(path="Quoode/src/preference.json"):
    """
    Load user preferences (e.g., clock_font_key, show_seconds) from a JSON file, if present.
    Returns {} if the file is not found or if there's an error parsing JSON.
    """
    if not os.path.exists(path):
        print(f"No preference file at {path}, returning defaults.")
        return {}
    try:
        with open(path, "r") as f:
            data = json.load(f)
        print(f"Loaded preferences from {path}: {data}")
        return data
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading JSON from {path}, using defaults. Error={e}")
        return {}

def main():
    # 1. Set up logging
    logging.basicConfig(
        level=logging.INFO,  # Change to DEBUG for more detailed logs
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger("Main")

    # 2. Load YAML-based config
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, '..', 'config.yaml')
    config = load_config(config_path)

    # 2a. Load JSON-based user preferences
    preferences = load_preferences("Quoode/src/preference.json")

    # 2b. Merge preferences into config, so user overrides appear in config
    config.update(preferences)

    # 3. Initialize DisplayManager
    display_config = config.get('display', {})
    display_manager = DisplayManager(display_config)

    # 4. Display startup logo for 5 seconds
    logger.info("Displaying startup logo...")
    display_manager.show_logo()
    logger.info("Startup logo displayed for 5 seconds.")
    time.sleep(5)  # Wait 5s for the logo

    # Clear screen after logo
    display_manager.clear_screen()
    logger.info("Screen cleared after logo display.")

    # 5. Define readiness events
    moode_ready_event = threading.Event()
    min_loading_event = threading.Event()
    time_correct_event = threading.Event()
    min_loading_duration = 5  # seconds

    # 6. Start a timer thread for min loading
    def set_min_loading_event():
        time.sleep(min_loading_duration)
        min_loading_event.set()
        logger.info(f"Minimum loading duration of {min_loading_duration}s has elapsed.")

    timer_thread = threading.Thread(target=set_min_loading_event, daemon=True)
    timer_thread.start()

    # 7. Loading GIF until readiness
    def show_loading():
        loading_gif_path = display_config.get('loading_gif_path', 'loading.gif')
        try:
            image = Image.open(loading_gif_path)
            if not getattr(image, "is_animated", False):
                logger.warning(f"The loading GIF at '{loading_gif_path}' is not animated.")
                return
        except IOError:
            logger.error(f"Failed to load loading GIF '{loading_gif_path}'.")
            return

        logger.info("Displaying loading GIF (until MPD ready + time correct + min load).")
        display_manager.clear_screen()
        time.sleep(0.1)

        while True:
            if moode_ready_event.is_set() and time_correct_event.is_set() and min_loading_event.is_set():
                logger.info("All events set, exiting loading GIF.")
                return

            for frame in ImageSequence.Iterator(image):
                if moode_ready_event.is_set() and time_correct_event.is_set() and min_loading_event.is_set():
                    logger.info("All events set mid-frame, exiting loading GIF.")
                    return

                # Display each frame
                display_manager.oled.display(frame.convert(display_manager.oled.mode))
                frame_duration = frame.info.get('duration', 100) / 1000.0
                time.sleep(frame_duration)

    loading_thread = threading.Thread(target=show_loading, daemon=True)
    loading_thread.start()

    # 9. Initialize MoodeListener
    moode_config = config.get('moode', {})
    moode_host = moode_config.get('host', 'localhost')
    moode_port = moode_config.get('port', 6600)

    moode_listener = MoodeListener(
        host=moode_host,
        port=moode_port,
        reconnect_delay=5,
        mode_manager=None,   # We'll assign after creating ModeManager
        auto_connect=False,  # Avoid immediate connect
        moode_ready_event=moode_ready_event
    )

    # 10. Initialize Clock
    clock_config = config.get('clock', {})
    clock = Clock(display_manager, clock_config)
    clock.logger = logging.getLogger("Clock")
    clock.logger.setLevel(logging.INFO)

    # 11. Initialize ModeManager, pass merged config
    mode_manager = ModeManager(
        display_manager=display_manager,
        clock=clock,
        moode_listener=moode_listener,
        preference_file_path="../preference.json",
        config=config
    )

    # Link them
    moode_listener.mode_manager = mode_manager

    # 13. Connect to MPD
    moode_listener.init_listener()

    # 14. Time sync thread
    def check_time_sync():
        if wait_for_correct_time(threshold_year=2023, timeout=60):
            time_correct_event.set()
            logger.info("System time is confirmed correct (year >= 2023).")
        else:
            logger.warning("System time did not sync within 60s; continuing anyway.")
            time_correct_event.set()

    time_sync_thread = threading.Thread(target=check_time_sync, daemon=True)
    time_sync_thread.start()

    # 15. Wait until moOde ready, time correct, min loading
    logger.info("Waiting for MPD (moode_ready_event), correct time, and min loading to pass...")
    while not (moode_ready_event.is_set() and time_correct_event.is_set() and min_loading_event.is_set()):
        time.sleep(0.2)

    logger.info("All readiness events satisfied. Proceeding with initialization...")

    # Switch to clock
    mode_manager.to_clock()
    logger.info("ModeManager: switched to clock after loading.")

    # 16. ManagerFactory
    manager_factory = ManagerFactory(
        display_manager=display_manager,
        moode_listener=moode_listener,
        mode_manager=mode_manager,
        config=config
    )
    manager_factory.setup_mode_manager()

    # If you need references:
    original_screen = manager_factory.original_screen
    modern_screen   = manager_factory.modern_screen
    snakescreensaver   = manager_factory.snakescreensaver
    menu_manager    = manager_factory.menu_manager
    clock_menu      = manager_factory.clock_menu

    # 17. Optional ButtonsLEDController
    # buttons_leds = ButtonsLEDController(moode_listener=moode_listener, config_path=config_path)
    # buttons_leds.start()

    last_interaction_time = time.time()

    # 18. Rotary callbacks
    def on_rotate(direction):
        global last_interaction_time
        last_interaction_time = time.time() 
        global last_volume_update, volume_update_cooldown
        current_mode = mode_manager.get_mode()
        now = time.time()

        if mode_manager.get_mode() == 'screensaver':
            mode_manager.exit_screensaver()
            return

        if current_mode in ['original', 'modern', 'playback']:
            # Debounced volume adjustments
            if now - last_volume_update > volume_update_cooldown:
                if direction == 1:
                    subprocess.run(["mpc", "volume", "+5"], check=False)
                else:
                    subprocess.run(["mpc", "volume", "-5"], check=False)
                logger.info(f"Sent MPC volume command direction={direction}")
                last_volume_update = now
            else:
                logger.debug("Skipping volume update (debounce).")

        elif current_mode == 'menu':
            menu_manager.scroll_selection(direction)

        elif current_mode == 'clockmenu':
            clock_menu.scroll_selection(direction)

        else:
            logger.warning(f"Unhandled mode: {current_mode}. No rotary action performed.")

    def on_button_press_inner():
        """
        Handle short-press of the rotary button depending on current mode.
        """
        global last_interaction_time
        last_interaction_time = time.time()
        current_mode = mode_manager.get_mode()

        if current_mode == 'clock':
            # from clock -> menu
            mode_manager.to_menu()

        elif current_mode == 'menu':
            menu_manager.select_item()

        elif current_mode == 'clockmenu':
            # short-press in clock menu
            clock_menu.select_item()

        elif current_mode in ['original', 'modern', 'playback']:
            # Toggle play/pause
            subprocess.run(["mpc", "toggle"], check=False)
            logger.info("Toggled play/pause via `mpc toggle`.")

        else:
            logger.warning(f"Unhandled mode: {current_mode}. No button action performed.")

    def on_long_press():
        logger.info("Long button press detected.")
        current_mode = mode_manager.get_mode()
        if current_mode != 'clock':
            mode_manager.to_clock()
            logger.info("ModeManager: Switched to clock mode via long press.")

    # 19. RotaryControl
    rotary_control = RotaryControl(
        rotation_callback=on_rotate,
        button_callback=on_button_press_inner,
        long_press_callback=on_long_press,
        long_press_threshold=2.5
    )
    rotary_control.start()

    try:
        while True:
            # 1) Check for idle:
            elapsed = time.time() - last_interaction_time

            # 2) If we exceed IDLE_TIMEOUT, go to screensaver
            #    but only if we’re not already in it (or in a menu).
            if elapsed >= IDLE_TIMEOUT:
                current_mode = mode_manager.get_mode()

                # Possibly skip entering screensaver if user is in 'menu' or 'clockmenu'
                # But typically you'd skip if already 'screensaver' or other logic.
                if current_mode not in ["screensaver", "menu", "clockmenu"]:
                    mode_manager.to_screensaver()

            # Sleep for 1 second between checks
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutting down Quoode...")
    finally:
        # Clean up stuff
        rotary_control.stop()
        moode_listener.stop()
        clock.stop()
        display_manager.clear_screen()
        logger.info("Quoode has been shut down gracefully.")


if __name__ == "__main__":
    main()

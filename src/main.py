# src/main.py
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
from display.screens.clock import Clock
from display.screens.playback_manager import PlaybackManager
from display.screens.radioplayback_manager import RadioPlaybackManager
from display.screens.detailed_playback_manager import DetailedPlaybackManager
from managers.mode_manager import ModeManager
from managers.menu_manager import MenuManager
from managers.menus.playlist_manager import PlaylistManager
from managers.menus.radio_manager import RadioManager
from managers.menus.tidal_manager import TidalManager
from managers.menus.qobuz_manager import QobuzManager
from managers.menus.spotify_manager import SpotifyManager
from managers.menus.library_manager import LibraryManager
from managers.menus.usb_library_manager import USBLibraryManager
from controls.rotary_control import RotaryControl
from network.volumio_listener import VolumioListener
from hardware.buttonsleds import ButtonsLEDController
from handlers.state_handler import StateHandler
from display.screen_manager import ScreenManager
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

    # **A. Clear the Screen After Logo Display**
    display_manager.clear_screen()
    logger.info("Screen cleared after logo display.")

    # 5. Define events to signal when Volumio is ready and minimum loading duration has elapsed
    volumio_ready_event = threading.Event()
    min_loading_event = threading.Event()
    min_loading_duration = 5  # seconds

    # 6. Define a function to set the minimum loading duration
    def set_min_loading_event():
        time.sleep(min_loading_duration)
        min_loading_event.set()
        logger.info("Minimum loading duration has elapsed.")

    # Start the timer thread
    timer_thread = threading.Thread(target=set_min_loading_event, daemon=True)
    timer_thread.start()

    # 7. Define a function to show loading GIF until both events are set
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

        logger.info("Displaying loading GIF...")

        # Ensure the screen is cleared before starting the GIF
        display_manager.clear_screen()
        time.sleep(0.1)  # Allow the screen to refresh
        logger.info("Screen cleared before displaying GIF.")

        # Loop through GIF frames until Volumio is ready and minimum duration has elapsed
        while not (volumio_ready_event.is_set() and min_loading_event.is_set()):
            for frame in ImageSequence.Iterator(image):
                if volumio_ready_event.is_set() and min_loading_event.is_set():
                    logger.info("Volumio is ready and minimum loading duration has elapsed.")
                    return  # Exit the loop

                # Display the current frame
                display_manager.oled.display(frame.convert(display_manager.oled.mode))
                logger.debug("Displayed a frame of the loading GIF.")

                # Pause for the frame duration
                frame_duration = frame.info.get('duration', 100) / 1000.0  # Convert ms to seconds
                time.sleep(frame_duration)

        logger.info("Loading GIF display thread exiting.")

    # 8. Start the loading GIF in a separate daemon thread
    loading_thread = threading.Thread(target=show_loading, daemon=True)
    loading_thread.start()

    # 9. Initialize VolumioListener
    volumio_config = config.get('volumio', {})
    volumio_host = volumio_config.get('host', 'localhost')
    volumio_port = volumio_config.get('port', 3000)
    volumio_listener = VolumioListener(host=volumio_host, port=volumio_port)

    # 10. Define a callback for state_changed signal
    def on_state_changed(sender, state):
        logger.info(f"Volumio state changed: {state}")
        # Define readiness criteria based on your requirements
        if state.get('status') in ['play', 'stop', 'pause']:
            logger.info("Volumio is ready.")
            volumio_ready_event.set()
            # Optionally, disconnect the callback to prevent further triggers
            volumio_listener.state_changed.disconnect(on_state_changed)
            logger.info("ModeManager: Disconnected from state_changed signal.")

    # 11. Connect the callback to the state_changed signal
    volumio_listener.state_changed.connect(on_state_changed)

    # 12. Wait until both events are set
    logger.info("Waiting for Volumio to be ready and minimum loading duration to pass...")
    volumio_ready_event.wait()
    min_loading_event.wait()
    logger.info("Both Volumio is ready and minimum loading duration has passed. Proceeding with initialization.")

    # 13. Initialize Clock
    clock_config = config.get('clock', {})
    clock = Clock(display_manager, clock_config)
    clock.logger = logging.getLogger("Clock")
    clock.logger.setLevel(logging.INFO)

    # 14. Initialize ModeManager
    mode_manager = ModeManager(
        display_manager=display_manager,
        clock=clock,
        volumio_listener=volumio_listener,
    )

    # Initialize ManagerFactory with the required dependencies
    manager_factory = ManagerFactory(
        display_manager=display_manager,
        volumio_listener=volumio_listener,
        mode_manager=mode_manager,  # Use the initialized ModeManager
        config=config 
    )

    # Set up ModeManager with all components
    manager_factory.setup_mode_manager()

    # Access the managers via factory's attributes
    playback_manager = manager_factory.playback_manager
    radioplayback_manager = manager_factory.radioplayback_manager
    menu_manager = manager_factory.menu_manager
    playlist_manager = manager_factory.playlist_manager
    radio_manager = manager_factory.radio_manager
    tidal_manager = manager_factory.tidal_manager
    qobuz_manager = manager_factory.qobuz_manager
    spotify_manager = manager_factory.spotify_manager
    library_manager = manager_factory.library_manager
    usb_library_manager = manager_factory.usb_library_manager
    screen_manager = manager_factory.screen_manager

    # Log the initialization of the ScreenManager
    logging.info(f"Main: ScreenManager initialized with current screen: {screen_manager.get_current_screen()}")


    # 20. Assign mode_manager to volumio_listener
    volumio_listener.mode_manager = mode_manager

    # 21. Initialize ButtonsLEDController
    buttons_leds = ButtonsLEDController(volumio_listener=volumio_listener, config_path=config_path)
    buttons_leds.start()

    # 22. Define RotaryControl callbacks
    def on_rotate(direction):
        current_mode = mode_manager.get_mode()

        if current_mode == 'playback':
            # Adjust volume in PlaybackManager based on direction
            volume_change = 10 if direction == 1 else -10
            playback_manager.adjust_volume(volume_change)
            
        if current_mode == 'detailed_playback':
            # Adjust volume in PlaybackManager based on direction
            volume_change = 10 if direction == 1 else -10
            detailed_playback_manager.adjust_volume(volume_change)
            logger.debug(f"PlaybackManager: Adjusted volume in playback mode by direction: {volume_change}")
        
        elif current_mode == 'radioplayback':
            # Adjust volume in RadioPlaybackManager based on direction
            volume_change = 10 if direction == 1 else -10
            radioplayback_manager.adjust_volume(volume_change)  # Assuming `radioplayback_manager` is an instance of `RadioPlaybackManager`
            logger.debug(f"RadioPlaybackManager: Adjusted volume in radioplayback mode by direction: {volume_change}")

        elif current_mode == 'menu':
            # Only allow scrolling when explicitly in menu mode, prevent unintended menu activation
            menu_manager.scroll_selection(direction)
            logger.debug(f"Scrolled menu in mode: {current_mode} with direction: {direction}")

        elif current_mode == 'tidal':
            tidal_manager.scroll_selection(direction)
            logger.debug(f"Scrolled Tidal menu in mode: {current_mode} with direction: {direction}")

        elif current_mode == 'qobuz':
            qobuz_manager.scroll_selection(direction)
            logger.debug(f"Scrolled Qobuz menu in mode: {current_mode} with direction: {direction}")

        elif current_mode == 'spotify':
            spotify_manager.scroll_selection(direction)
            logger.debug(f"Scrolled Spotify menu in mode: {current_mode} with direction: {direction}")

        elif current_mode == 'playlists':
            playlist_manager.scroll_selection(direction)
            logger.debug(f"Scrolled Playlist menu in mode: {current_mode} with direction: {direction}")

        elif current_mode == 'webradio':
            radio_manager.scroll_selection(direction)
            logger.debug(f"Scrolled Radio menu in mode: {current_mode} with direction: {direction}")

        elif current_mode == 'library':
            library_manager.scroll_selection(direction)
            logger.debug(f"Scrolled Library menu in mode: {current_mode} with direction: {direction}")

        elif current_mode == 'usblibrary':
            usb_library_manager.scroll_selection(direction)
            logger.debug(f"Scrolled USB Library menu in mode: {current_mode} with direction: {direction}")

        else:
            logger.warning(f"Unhandled mode: {current_mode}. No rotary action performed.")


    def on_button_press_inner():
        current_mode = mode_manager.get_mode()

        if current_mode == 'clock':
            # Switch from clock mode to menu mode
            mode_manager.to_menu()
        elif current_mode == 'menu':
            # Select the currently highlighted menu item
            menu_manager.select_item()
        elif current_mode in ['fm4', 'modern']:
            # Toggle screens if button pressed in FM4 or Modern mode
            screen_manager.switch_screen()
            logger.info(f"Toggled to {screen_manager.get_current_screen()} screen in {current_mode} mode.")
        elif current_mode == 'playback':
            # Toggle play/pause in playback mode
            playback_manager.toggle_play_pause()
        elif current_mode == 'radioplayback':
            # Toggle play/pause in radioplayback mode
            radioplayback_manager.toggle_play_pause()  # Assuming `radioplayback_manager` is an instance of `RadioPlaybackManager`
            logger.debug("RadioPlaybackManager: Toggled play/pause in radioplayback mode.")
        elif current_mode == 'tidal':
            # Select the currently highlighted item in the Tidal menu
            tidal_manager.select_item()
            logger.debug(f"Button pressed in tidal mode: selected item {tidal_manager.current_selection_index}")
        elif current_mode == 'qobuz':
            # Select the currently highlighted item in the Qobuz menu
            qobuz_manager.select_item()
            logger.debug(f"Button pressed in qobuz mode: selected item {qobuz_manager.current_selection_index}")
        elif current_mode == 'spotify':
            # Select the currently highlighted item in the Spotify menu
            spotify_manager.select_item()
            logger.debug(f"Button pressed in spotify mode: selected item {spotify_manager.current_selection_index}")
        elif current_mode == 'webradio':
            # Handle item selection in Webradio mode
            radio_manager.select_item()
            logger.debug(f"Button pressed in webradio mode: selected item {radio_manager.current_selection_index}")
        elif current_mode == 'library':
            # Handle item selection in Library mode
            library_manager.select_item()
            logger.debug(f"Button pressed in library mode: selected item {library_manager.current_selection_index}")
        elif current_mode == 'usblibrary':
            # Handle item selection in Library mode
            usb_library_manager.select_item()
            logger.debug(f"Button pressed in usblibrary mode: selected item {usb_library_manager.current_selection_index}")
        elif current_mode == 'playlists':
            # Handle item selection in Playlists mode
            playlist_manager.select_item()
            logger.debug(f"Button pressed in playlists mode: selected item {playlist_manager.current_selection_index}")
        else:
            logger.warning(f"Unhandled mode: {current_mode}. No button action performed.")

    def on_long_press():
        logger.info("Long button press detected")
        # Example action for long press: return to clock mode
        current_mode = mode_manager.get_mode()
        if current_mode != 'clock':
            mode_manager.to_clock()

    # 23. Initialize RotaryControl
    rotary_control = RotaryControl(
        rotation_callback=on_rotate,
        button_callback=on_button_press_inner,
        long_press_callback=on_long_press,
        long_press_threshold=2.5
    )

    rotary_control.start()  # Start listening to rotary events

    # 24. Run the Main Application Loop
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down Quadify...")
    finally:
        buttons_leds.stop()
        rotary_control.stop()
        volumio_listener.stop_listener()
        clock.stop()
        display_manager.clear_screen()
        logger.info("Quadify has been shut down gracefully.")

if __name__ == "__main__":
    main()

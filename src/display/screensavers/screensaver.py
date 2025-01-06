import threading
import time

class Screensaver:
    """
    A generic Screensaver class.
    - Starts a background thread to run any screensaver animation.
    - Calls to stop will stop the thread and clear the screen.
    """

    def __init__(self, display_manager, mode_manager=None, update_interval=0.1):
        """
        :param display_manager: Your DisplayManager for drawing/clearing.
        :param mode_manager:    (Optional) If you need references to transition
                                out of the screensaver, or check user config, etc.
        :param update_interval: Frequency (in seconds) at which to update the screensaver.
        """
        self.display_manager = display_manager
        self.mode_manager = mode_manager
        self.update_interval = update_interval

        self._stop_event = threading.Event()
        self._thread = None

    def start_screensaver(self):
        """
        Start the screensaver in a background thread.
        """
        if self._thread and self._thread.is_alive():
            # If already running, do nothing
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop_screensaver(self):
        """
        Stop the screensaver gracefully.
        """
        self._stop_event.set()
        if self._thread:
            self._thread.join()
            self._thread = None

        # Optionally clear the screen or revert to some "off" state.
        self.display_manager.clear_screen()

    def _run(self):
        """
        Main loop for screensaver animation.
        Replace this with your actual animation logic.
        """
        while not self._stop_event.is_set():
            # 1. Draw or animate something:
            #    e.g., self.display_manager.draw_text("Screensaver", x=10, y=10)
            # 2. Wait briefly, allowing some animation cycle
            time.sleep(self.update_interval)
            # 3. Possibly change positions/frames in each loop iteration.
            #    For example, a bouncing shape, random lines, etc.

            # Example: This is a placeholder. In a real screensaver,
            # you’d do something more interesting with display_manager.
            pass

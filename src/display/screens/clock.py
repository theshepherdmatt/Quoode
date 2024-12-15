# src/display/clock.py
import time
import threading

class Clock:
    def __init__(self, display_manager, config):

        self.mode_name = "clock"

        self.display_manager = display_manager
        self.config = config
        self.running = False
        self.thread = None

    def draw_clock(self):
        current_time = time.strftime("%H:%M")
        font_key = 'clock_large'

        # Check if the font is loaded in DisplayManager
        if font_key not in self.display_manager.fonts:
            print(f"Error: Font '{font_key}' not loaded in DisplayManager.")
            return  # Exit the function if the font is not available

        self.display_manager.display_text(
            text=current_time,
            position=(self.display_manager.oled.width // 5, self.display_manager.oled.height // 5),
            font_key='clock_large'  # Ensure this matches the key in config.yaml
        )


    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.update_clock, daemon=True)
            self.thread.start()
            print("Clock: Started.")

    def stop(self):
        if self.running:
            self.running = False
            self.thread.join()
            self.display_manager.clear_screen()
            print("Clock: Stopped.")

    def update_clock(self):
        while self.running:
            self.draw_clock()
            time.sleep(1)

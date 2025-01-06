# src/managers/menus/screensaver_menu.py

from managers.menus.base_manager import BaseManager
import logging
from PIL import ImageFont
import time

class ScreensaverMenu(BaseManager):
    """
    A text-list menu for picking which screensaver to use at idle.

    Items: [None, Snake, Stars, Quoode]

    On selection, store in mode_manager.config["screensaver_type"], e.g.:
      - "none"   => no screensaver
      - "snake"  => run SnakeScreensaver
      - "stars"  => run StarfieldScreensaver
      - "quoode" => run BouncingTextScreensaver
    """

    def __init__(
        self,
        display_manager,
        mode_manager,
        window_size=4,    
        y_offset=2,
        line_spacing=15
    ):
        """
        :param display_manager: The DisplayManager controlling the OLED.
        :param mode_manager:    The ModeManager where we store user preferences.
        :param window_size:     Number of text lines visible at once.
        :param y_offset:        Vertical offset for the first line.
        :param line_spacing:    Pixels between lines of text.
        """
        super().__init__(display_manager, None, mode_manager)

        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)

        self.mode_manager = mode_manager
        self.display_manager = display_manager
        self.is_active = False

        # Font for text drawing
        self.font_key = "menu_font"
        self.font = self.display_manager.fonts.get(self.font_key) or ImageFont.load_default()

        # A simple text-based menu for screensavers
        self.screensaver_items = ["None", "Snake", "Stars", "Quoode"]
        self.current_index = 0

        # Layout
        self.window_size = window_size
        self.y_offset = y_offset
        self.line_spacing = line_spacing

        # Debounce
        self.last_action_time = 0
        self.debounce_interval = 0.3

    # -------------------------------------------------------
    # Activation / Deactivation
    # -------------------------------------------------------
    def start_mode(self):
        if self.is_active:
            self.logger.debug("ScreensaverMenu: Already active.")
            return
        self.is_active = True
        self.logger.info("ScreensaverMenu: Starting screensaver selection menu.")
        self.display_items()

    def stop_mode(self):
        if self.is_active:
            self.is_active = False
            self.display_manager.clear_screen()
            self.logger.info("ScreensaverMenu: Stopped and cleared display.")

    # -------------------------------------------------------
    # Display
    # -------------------------------------------------------
    def display_items(self):
        """
        Renders the list of screensaver options, highlighting the current selection.
        """
        def draw(draw_obj):
            # For simplicity, we just display all items if window_size >= len(screensaver_items).
            # If you want scrolling, implement logic similar to your ClockMenu’s get_visible_window().
            for i, name in enumerate(self.screensaver_items):
                arrow = "-> " if i == self.current_index else "   "
                fill_color = "white" if i == self.current_index else "gray"
                y_pos = self.y_offset + i * self.line_spacing
                draw_obj.text(
                    (5, y_pos),
                    f"{arrow}{name}",
                    font=self.font,
                    fill=fill_color
                )

        self.display_manager.draw_custom(draw)
        self.logger.debug(f"ScreensaverMenu: Displayed items: {self.screensaver_items}")

    # -------------------------------------------------------
    # Scrolling & Selection
    # -------------------------------------------------------
    def scroll_selection(self, direction):
        if not self.is_active:
            self.logger.warning("ScreensaverMenu: Attempted scroll while inactive.")
            return
        now = time.time()
        if now - self.last_action_time < self.debounce_interval:
            self.logger.debug("ScreensaverMenu: Scroll debounced.")
            return
        self.last_action_time = now

        old_index = self.current_index
        self.current_index += direction

        # Clamp within [0, len-1]
        self.current_index = max(0, min(self.current_index, len(self.screensaver_items) - 1))

        if old_index != self.current_index:
            self.logger.debug(f"ScreensaverMenu: scrolled from {old_index} to {self.current_index}")
            self.display_items()

    def select_item(self):
        if not self.is_active:
            self.logger.warning("ScreensaverMenu: Attempted select while inactive.")
            return

        now = time.time()
        if now - self.last_action_time < self.debounce_interval:
            self.logger.debug("ScreensaverMenu: Select debounced.")
            return
        self.last_action_time = now

        selected_name = self.screensaver_items[self.current_index]
        self.logger.info(f"ScreensaverMenu: Selected => {selected_name}")

        # Store user selection in mode_manager.config so idle logic can read it
        if selected_name == "None":
            self.mode_manager.config["screensaver_type"] = "none"
        elif selected_name == "Snake":
            self.mode_manager.config["screensaver_type"] = "snake"
        elif selected_name == "Stars":
            self.mode_manager.config["screensaver_type"] = "stars"
        elif selected_name == "Quoode":
            self.mode_manager.config["screensaver_type"] = "quoode"
        else:
            self.logger.warning(f"ScreensaverMenu: Unrecognized option: {selected_name}")
            self.mode_manager.config["screensaver_type"] = "none"

        # Persist user preference
        self.mode_manager.save_preferences()
        self.logger.debug(f"ScreensaverMenu: config['screensaver_type'] is now {self.mode_manager.config['screensaver_type']}")

        # Return to your normal clock or menu
        self.logger.debug("ScreensaverMenu: Returning to clock after selection.")
        self.stop_mode()
        self.mode_manager.to_clock()

# src/managers/menus/display_menu.py

import logging
import time
from PIL import ImageFont
from managers.menus.base_manager import BaseManager

class DisplayMenu(BaseManager):
    """
    A text-list menu for picking which display style to use:
      - Modern
      - Classic
      - Contrast (placeholder)
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
        :param mode_manager:    The ModeManager where we store user preferences or do transitions.
        :param window_size:     Number of text lines visible at once.
        :param y_offset:        Vertical offset for the first line.
        :param line_spacing:    Pixels between lines of text.
        """
        super().__init__(display_manager, None, mode_manager)

        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)

        self.mode_manager     = mode_manager
        self.display_manager = display_manager
        self.is_active       = False

        # Font for text drawing
        self.font_key = "menu_font"
        self.font = self.display_manager.fonts.get(self.font_key) or ImageFont.load_default()

        # Our display menu items
        self.display_items = ["Modern", "Original", "Contrast"]
        self.current_index = 0

        # Layout
        self.window_size   = window_size
        self.y_offset      = y_offset
        self.line_spacing  = line_spacing

        # Debounce
        self.last_action_time   = 0
        self.debounce_interval = 0.3

    # -------------------------------------------------------
    # Activation / Deactivation
    # -------------------------------------------------------
    def start_mode(self):
        if self.is_active:
            self.logger.debug("DisplayMenu: Already active.")
            return
        self.is_active = True
        self.logger.info("DisplayMenu: Starting display selection menu.")
        self.display_items_list()

    def stop_mode(self):
        if self.is_active:
            self.is_active = False
            self.display_manager.clear_screen()
            self.logger.info("DisplayMenu: Stopped and cleared display.")

    # -------------------------------------------------------
    # Display
    # -------------------------------------------------------
    def display_items_list(self):
        """
        Renders the list of display options, highlighting the current selection.
        """
        def draw(draw_obj):
            # For simplicity, we just display all items if window_size >= len(display_items).
            # If you want scrolling, implement logic similar to your other menus.
            for i, name in enumerate(self.display_items):
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
        self.logger.debug(f"DisplayMenu: Displayed items: {self.display_items}")

    # -------------------------------------------------------
    # Scrolling & Selection
    # -------------------------------------------------------
    def scroll_selection(self, direction):
        if not self.is_active:
            self.logger.warning("DisplayMenu: Attempted scroll while inactive.")
            return
        now = time.time()
        if now - self.last_action_time < self.debounce_interval:
            self.logger.debug("DisplayMenu: Scroll debounced.")
            return
        self.last_action_time = now

        old_index = self.current_index
        self.current_index += direction

        # Clamp within [0, len-1]
        self.current_index = max(0, min(self.current_index, len(self.display_items) - 1))

        if old_index != self.current_index:
            self.logger.debug(f"DisplayMenu: scrolled from {old_index} to {self.current_index}")
            self.display_items_list()

    def select_item(self):
        """
        A short press => select the item under highlight.
        """
        if not self.is_active:
            self.logger.warning("DisplayMenu: Attempted select while inactive.")
            return

        now = time.time()
        if now - self.last_action_time < self.debounce_interval:
            self.logger.debug("DisplayMenu: Select debounced.")
            return
        self.last_action_time = now

        selected_name = self.display_items[self.current_index]
        self.logger.info(f"DisplayMenu: Selected => {selected_name}")

        # Decide what to do based on selection
        if selected_name == "Original":
            # 1) Update the config
            self.mode_manager.config["display_mode"] = "original"
            # 2) Actually switch to 'original' playback mode if you want immediate effect
            self.logger.debug("DisplayMenu: Transition to classic screen.")
            self.mode_manager.set_display_mode("original")
            # 3) Save preferences so it’s persisted
            self.mode_manager.save_preferences()
            self.mode_manager.to_clock()

        elif selected_name == "Modern":
            self.mode_manager.config["display_mode"] = "modern"
            self.logger.debug("DisplayMenu: Transition to modern screen.")
            self.mode_manager.set_display_mode("modern")
            self.mode_manager.save_preferences()
            self.mode_manager.to_clock()

        elif selected_name == "Contrast":
            # 3) Placeholder for adjusting display contrast or other logic
            self.logger.info("TODO: Implement 'Contrast' setting.")
            # You can handle it here or just log
            # E.g. open a sub-menu for Contrast or run some method
            self.logger.info("DisplayMenu: Returning to clock after 'Contrast' placeholder.")
            self.stop_mode()
            self.mode_manager.to_clock()
        else:
            self.logger.warning(f"DisplayMenu: Unrecognized option: {selected_name}")

        # If you want to persist user selection in config, you can do that:
        # self.mode_manager.config["playback_style"] = selected_name.lower()
        # self.mode_manager.save_preferences()

        # Or automatically switch back to clock or main menu. 
        # (We've done that above for each item.)

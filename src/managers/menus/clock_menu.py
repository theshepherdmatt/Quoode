# src/managers/menus/clock_menu.py

import logging
import time
from PIL import ImageFont

from managers.menus.base_manager import BaseManager

class ClockMenu(BaseManager):
    """
    A text-based sub-menu manager for 'Clock' settings,
    similar to how RadioManager or any text-list approach works.

    Items might include:
      - Show Seconds (toggle)
      - Show Date (toggle)
      - Select Font => [Sans, Dots, Digital]
    """

    def __init__(
        self,
        display_manager,
        mode_manager,
        window_size=4,    # Must be an integer for the visible lines
        y_offset=2,
        line_spacing=15
    ):
        """
        :param display_manager: The DisplayManager (controls the OLED).
        :param mode_manager:    The ModeManager (for global transitions, config storage, etc.).
        :param window_size:     Number of text lines to display at once in the text-list.
        :param y_offset:        Vertical offset for first line.
        :param line_spacing:    Spacing in pixels between lines of text.
        """
        super().__init__(display_manager, None, mode_manager)

        self.mode_name = "clock_menu"
        self.display_manager = display_manager
        self.mode_manager = mode_manager

        # Logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)

        # Font details
        self.font_key = "menu_font"
        self.font = self.display_manager.fonts.get(self.font_key, ImageFont.load_default())

        # Layout config
        self.window_size = window_size
        self.y_offset = y_offset
        self.line_spacing = line_spacing

        # Define the main items (top-level) & the font sub-menu
        self.main_items = [
            "Show Seconds",
            "Show Date",
            "Select Font"
        ]
        self.font_items = ["Sans", "Dots", "Digital"]

        self.current_menu = "clock_main"   # or 'fonts'
        self.current_items = list(self.main_items)
        self.current_selection_index = 0
        self.window_start_index = 0

        self.is_active = False

        # Simple debouncing
        self.last_action_time = 0
        self.debounce_interval = 0.3

        # Menu stack for optional back navigation
        self.menu_stack = []

    def start_mode(self):
        """Activate this ClockMenu."""
        if self.is_active:
            self.logger.debug("ClockMenu: Already active.")
            return
        self.logger.info("ClockMenu: Starting Clock Menu mode.")

        self.is_active = True
        self.current_menu = "clock_main"
        self.current_items = list(self.main_items)
        self.current_selection_index = 0
        self.window_start_index = 0
        self.menu_stack.clear()

        # Immediately display
        self.display_current_menu()

    def stop_mode(self):
        """Deactivate the ClockMenu and clear the screen."""
        self.logger.info("ClockMenu: Stopping Clock Menu mode.")
        if not self.is_active:
            self.logger.warning("ClockMenu: Already inactive.")
            return

        self.is_active = False
        self.display_manager.clear_screen()

    def display_current_menu(self):
        """
        Display items based on self.current_menu (either 'clock_main' or 'fonts').
        """
        if self.current_menu == "clock_main":
            self.display_text_list(self.current_items)
        elif self.current_menu == "fonts":
            self.display_text_list(self.current_items)
        else:
            self.logger.warning(f"ClockMenu: Unknown current_menu '{self.current_menu}'")
            self.display_text_list(["[Unknown Menu]"])

    def display_text_list(self, items):
        """
        Draw a simple text-based menu list, highlighting the current selection.
        """
        if not items:
            self.display_empty_message("No Items")
            return

        def draw(draw_obj):
            visible = self.get_visible_window(items)
            x_offset = 5
            for i, item_name in enumerate(visible):
                actual_index = self.window_start_index + i
                arrow = "-> " if actual_index == self.current_selection_index else "   "
                fill_color = "white" if actual_index == self.current_selection_index else "gray"
                y_pos = self.y_offset + i * self.line_spacing
                draw_obj.text(
                    (x_offset, y_pos),
                    f"{arrow}{item_name}",
                    font=self.font,
                    fill=fill_color
                )

        self.display_manager.draw_custom(draw)
        self.logger.debug(f"ClockMenu: Displayed menu items: {items}")

    def get_visible_window(self, all_items):
        """
        Return the subset of items in the window_size range,
        centering on self.current_selection_index if possible.
        """
        total = len(all_items)
        half_window = self.window_size // 2

        # Attempt to center the selection
        tentative_start = self.current_selection_index - half_window

        # Clamp to valid range
        if tentative_start < 0:
            self.window_start_index = 0
        elif tentative_start + self.window_size > total:
            self.window_start_index = max(total - self.window_size, 0)
        else:
            self.window_start_index = tentative_start

        visible = all_items[self.window_start_index : self.window_start_index + self.window_size]
        self.logger.debug(
            f"ClockMenu: Visible window from {self.window_start_index} "
            f"to {self.window_start_index + len(visible) - 1}, selection={self.current_selection_index}"
        )
        return visible

    def display_empty_message(self, text):
        """
        If no items are available, show a message on-screen.
        """
        def draw(draw_obj):
            font = self.font
            w, h = draw_obj.im.size
            tw, th = draw_obj.textsize(text, font=font)
            x = (w - tw) // 2
            y = (h - th) // 2
            draw_obj.text((x, y), text, font=font, fill="white")

        self.display_manager.draw_custom(draw)

    def scroll_selection(self, direction):
        """
        Scroll up or down the menu (direction>0 => down, <0 => up).
        """
        if not self.is_active:
            self.logger.warning("ClockMenu: Attempted scroll while inactive.")
            return

        now = time.time()
        if now - self.last_action_time < self.debounce_interval:
            self.logger.debug("ClockMenu: Scroll debounced.")
            return
        self.last_action_time = now

        items = self.current_items
        if not items:
            self.logger.warning("ClockMenu: No items to scroll.")
            return

        old_index = self.current_selection_index
        # Move selection up or down
        if direction > 0 and self.current_selection_index < len(items) - 1:
            self.current_selection_index += 1
        elif direction < 0 and self.current_selection_index > 0:
            self.current_selection_index -= 1

        if old_index != self.current_selection_index:
            self.logger.debug(f"ClockMenu: Scrolled from {old_index} to {self.current_selection_index}")
            self.display_current_menu()

    def select_item(self):
        """
        Handle short-press to select the current item.
        """
        if not self.is_active:
            self.logger.warning("ClockMenu: Attempted select while inactive.")
            return

        now = time.time()
        if now - self.last_action_time < self.debounce_interval:
            self.logger.debug("ClockMenu: Select debounced.")
            return
        self.last_action_time = now

        if not self.current_items:
            self.logger.warning("ClockMenu: No items to select.")
            return

        selected = self.current_items[self.current_selection_index]
        self.logger.info(f"ClockMenu: Selected item => {selected}")

        if self.current_menu == "clock_main":
            self.handle_clock_main_selection(selected)
        elif self.current_menu == "fonts":
            self.handle_font_selection(selected)
        else:
            self.logger.warning(f"ClockMenu: Unknown menu '{self.current_menu}'")

    def handle_clock_main_selection(self, item):
        """
        Process an item from the main clock menu:
         - Show Seconds
         - Show Date
         - Select Font
        """
        if item == "Show Seconds":
            current_val = self.mode_manager.config.get("show_seconds", False)
            new_val = not current_val
            self.mode_manager.config["show_seconds"] = new_val
            self.logger.info(f"ClockMenu: show_seconds toggled to {new_val}")

            self.mode_manager.save_preferences()
            self.mode_manager.to_clock()

        elif item == "Show Date":
            current_val = self.mode_manager.config.get("show_date", False)
            new_val = not current_val
            self.mode_manager.config["show_date"] = new_val
            self.logger.info(f"ClockMenu: show_date toggled to {new_val}")

            self.mode_manager.save_preferences()
            self.mode_manager.to_clock()

        elif item == "Select Font":
            # Switch to the fonts sub-menu
            self.menu_stack.append(
                (self.current_menu, list(self.current_items), self.current_selection_index)
            )
            self.current_menu = "fonts"
            self.current_items = self.font_items
            self.current_selection_index = 0
            self.window_start_index = 0
            self.display_current_menu()

        else:
            self.logger.warning(f"ClockMenu: Unknown clock_main item '{item}'")

    def handle_font_selection(self, item):
        """
        e.g. 'Sans', 'Dots', 'Digital'
        """
        if item == "Sans":
            self.mode_manager.config["clock_font_key"] = "clock_sans"
            self.logger.info("ClockMenu: Font changed to clock_sans")
        elif item == "Dots":
            self.mode_manager.config["clock_font_key"] = "clock_dots"
            self.logger.info("ClockMenu: Font changed to clock_dots")
        elif item == "Digital":
            self.mode_manager.config["clock_font_key"] = "clock_digital"
            self.logger.info("ClockMenu: Font changed to clock_digital")
        else:
            self.logger.warning(f"ClockMenu: Unknown font item '{item}'")

        # Save the updated config to JSON so it's persisted
        self.mode_manager.save_preferences()

        # Return to normal clock
        self.mode_manager.to_clock()

    def navigate_back(self):
        """
        If you add a 'Back' item in sub-menus, or want to revert to main menu,
        you can pop from self.menu_stack here.
        """
        if not self.is_active:
            self.logger.warning("ClockMenu: Attempted back while inactive.")
            return

        now = time.time()
        if now - self.last_action_time < self.debounce_interval:
            self.logger.debug("ClockMenu: Back debounced.")
            return
        self.last_action_time = now

        if not self.menu_stack:
            # At top-level => stop or revert to main
            self.logger.info("ClockMenu: No previous menu in stack, stopping mode.")
            self.stop_mode()
            return

        # Pop from stack
        prev_menu, prev_items, prev_index = self.menu_stack.pop()
        self.current_menu = prev_menu
        self.current_items = prev_items
        self.current_selection_index = prev_index
        self.window_start_index = 0
        self.display_current_menu()

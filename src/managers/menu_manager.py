# src/managers/menu_manager.py

import logging
from PIL import Image, ImageDraw, ImageFont
import threading
import time

class MenuManager:
    def __init__(self, display_manager, moode_listener, mode_manager,
                 window_size=5, menu_type="icon_row"):
        """
        :param display_manager: DisplayManager instance (controls OLED)
        :param moode_listener:  MoodeListener instance (if needed for integration)
        :param mode_manager:    ModeManager (for state transitions like to_clockmenu, etc.)
        :param window_size:     How many icons to show at once before scrolling
        :param menu_type:       'icon_row' or other style (not fully implemented here)
        """
        self.display_manager = display_manager
        self.moode_listener = moode_listener
        self.mode_manager = mode_manager

        # Initialize logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.info("MenuManager initialized.")

        # Menu initialization
        # For your top-level menu items:
        self.menu_stack = []
        self.current_menu_items = ["Clock", "Screensaver", "Display", "System Data"]

        # Sub-menu for Display
        self.display_menu_items = ["Modern", "Classic"]

        # Sub-menu for System Data
        self.system_data_items = ["CPU Temp", "IP Address"]

        # Icons dictionary — fill in keys for every item you have icons for
        self.icons = {
            "Clock":       self.display_manager.icons.get("clock"),
            "Screensaver": self.display_manager.icons.get("screensaver"),
            "Display":     self.display_manager.icons.get("display"),
            "System Data": self.display_manager.icons.get("data"),

            "Contrast":    self.display_manager.icons.get("contrast"),
            "Fonts":       self.display_manager.icons.get("fonts"),

            "CPU Temp":    self.display_manager.icons.get("cpu"),
            "IP Address":  self.display_manager.icons.get("ip"),
        }

        # Selection and layout
        self.current_selection_index = 0
        self.is_active = False
        self.window_size = window_size
        self.window_start_index = 0
        self.menu_type = menu_type

        # Font keys in display_manager
        self.font_key = 'menu_font'
        self.bold_font_key = 'menu_font_bold'

        # Thread-safe rendering
        self.lock = threading.Lock()

        # If ModeManager supports a callback for mode changes
        if hasattr(self.mode_manager, "add_on_mode_change_callback"):
            self.mode_manager.add_on_mode_change_callback(self.handle_mode_change)

    def handle_mode_change(self, current_mode):
        """
        Called if mode_manager triggers a mode change callback.
        If we enter 'menu' mode, we start. Otherwise, we stop.
        """
        self.logger.info(f"MenuManager handling mode change to: {current_mode}")
        if current_mode == "menu":
            self.start_mode()
        elif self.is_active:
            self.stop_mode()

    def start_mode(self):
        """
        Called when user (short press from clock, etc.) triggers menu mode.
        Resets to top-level menu and displays it in a background thread.
        """
        self.is_active = True
        # Reset top-level items
        self.current_menu_items = ["Clock", "Screensaver", "Display", "System Data"]
        self.current_selection_index = 0
        self.window_start_index = 0

        # Start background thread to render menu
        threading.Thread(target=self.display_menu, daemon=True).start()

    def stop_mode(self):
        """
        Deactivate the menu and clear the screen.
        """
        if not self.is_active:
            return
        self.is_active = False
        with self.lock:
            self.display_manager.clear_screen()
        self.logger.info("MenuManager: Stopped menu mode and cleared display.")

    def display_menu(self):
        """
        Renders the menu UI based on self.menu_type (e.g. 'icon_row').
        """
        if self.menu_type == "icon_row":
            self.display_icon_row_menu()

    def display_icon_row_menu(self):
        """
        Icon-based row menu, with a highlight for the selected item.
        """
        with self.lock:
            # Determine which items are visible based on window_size
            visible_items = self.get_visible_window(self.current_menu_items, self.window_size)

            icon_size = 30
            spacing = 15
            total_width = self.display_manager.oled.width
            total_height = self.display_manager.oled.height

            total_icons_width = len(visible_items) * icon_size \
                                + (len(visible_items) - 1) * spacing

            # Center them horizontally
            x_offset = (total_width - total_icons_width) // 2
            # A slight upward shift if you want
            y_position = (total_height - icon_size) // 2 - 10

            # Make a fresh image to draw on
            base_image = Image.new("RGB", self.display_manager.oled.size, "black")
            draw_obj = ImageDraw.Draw(base_image)

            # Iterate over the visible items
            for i, item in enumerate(visible_items):
                actual_index = self.window_start_index + i

                # Get icon or fallback
                icon = self.icons.get(item, self.display_manager.default_icon)
                if icon is None:
                    self.logger.warning(f"No icon found for '{item}'. Using placeholder.")
                    # Create a grey placeholder
                    icon = Image.new("RGB", (30, 30), "grey")

                # Flatten alpha if needed
                if icon.mode == "RGBA":
                    background = Image.new("RGB", icon.size, (0, 0, 0))
                    background.paste(icon, mask=icon.split()[3])
                    icon = background

                # Resize icon
                icon = icon.resize((icon_size, icon_size), Image.LANCZOS)

                # X coordinate for this icon
                x = x_offset + i * (icon_size + spacing)

                # If selected, "pop" it up by 5 pixels
                if actual_index == self.current_selection_index:
                    y_adjustment = -5
                else:
                    y_adjustment = 0

                # Paste icon
                base_image.paste(icon, (x, y_position + y_adjustment))

                # If it's the selected item, draw a label below
                if actual_index == self.current_selection_index:
                    label = item
                    font = self.display_manager.fonts.get(
                        self.bold_font_key,
                        self.display_manager.fonts.get(self.font_key, ImageFont.load_default())
                    )
                    text_color = "white"

                    text_width = draw_obj.textlength(label, font=font)
                    text_x = x + (icon_size - text_width) // 2
                    text_y = y_position + icon_size + 5

                    draw_obj.text((text_x, text_y), label, font=font, fill=text_color)

            # Now display it
            base_image = base_image.convert(self.display_manager.oled.mode)
            self.display_manager.oled.display(base_image)
            self.logger.info("MenuManager: Icon row menu displayed with selected text only.")

    def get_visible_window(self, items, window_size):
        """
        Return a subset of items to center the selected index in the window.
        """
        half_window = window_size // 2
        self.window_start_index = self.current_selection_index - half_window

        if self.window_start_index < 0:
            self.window_start_index = 0
        elif self.window_start_index + window_size > len(items):
            self.window_start_index = max(len(items) - window_size, 0)

        return items[self.window_start_index : self.window_start_index + window_size]

    def scroll_selection(self, direction):
        """
        Rotary rotation => move selection up or down.
        direction > 0 => next item, direction < 0 => previous item.
        """
        if not self.is_active:
            return

        old_index = self.current_selection_index
        self.current_selection_index += direction
        # Clamp
        self.current_selection_index = max(
            0, min(self.current_selection_index, len(self.current_menu_items) - 1)
        )

        self.logger.info(
            f"MenuManager: Scrolled from {old_index} to {self.current_selection_index}. "
            f"Current menu items: {self.current_menu_items}"
        )

        # Re-center
        self.window_start_index = self.current_selection_index - (self.window_size // 2)
        self.window_start_index = max(
            0, min(self.window_start_index, len(self.current_menu_items) - self.window_size)
        )

        # Re-draw the menu
        self.display_menu()

    def select_item(self):
        """
        A short press => select the item under highlight.
        """
        if not self.is_active or not self.current_menu_items:
            return

        selected_item = self.current_menu_items[self.current_selection_index]
        self.logger.info(f"MenuManager: Selected menu item: {selected_item}")

        # Avoid blocking UI by using a thread
        threading.Thread(target=self._handle_selection, args=(selected_item,), daemon=True).start()

    def _handle_selection(self, selected_item):
        """
        Perform the action associated with the chosen menu item.
        E.g. sub-menu logic or transitions into ModeManager states.
        """
        # Add a small delay to avoid accidental double-press
        time.sleep(0.2)

        if selected_item == "Clock":
            self.mode_manager.to_clockmenu()

        elif selected_item == "Screensaver":
            self.mode_manager.to_screensavermenu()

        elif selected_item == "Display":
            # Sub-menu for things like Contrast, Fonts
            self.menu_stack.append(list(self.current_menu_items))
            self.current_menu_items = self.display_menu_items
            self.current_selection_index = 0
            self.window_start_index = 0
            self.display_menu()

        elif selected_item == "System Data":
            # Sub-menu for CPU Temp, IP
            self.menu_stack.append(list(self.current_menu_items))
            self.current_menu_items = self.system_data_items
            self.current_selection_index = 0
            self.window_start_index = 0
            self.display_menu()

        # Sub-menu items
        elif selected_item == "Contrast":
            self.logger.info("TODO: Adjust display contrast here, e.g. self.display_manager.set_contrast(...).")

        elif selected_item == "Fonts":
            self.logger.info("TODO: Manage global font styles from here if desired.")

        elif selected_item == "CPU Temp":
            self.logger.info("TODO: Show CPU temperature, or run a command to read CPU info.")

        elif selected_item == "IP Address":
            self.logger.info("TODO: Display IP info, e.g. run `hostname -I` or similar.")

        # Potentially, you could auto-return to main menu or clock
        # self.mode_manager.to_clock()

    # Optional method to navigate back if you want a "Back" item in sub-menus
    def navigate_back(self):
        """
        Example if you add a 'Back' item in sub-menu:
        """
        if not self.menu_stack:
            # Already at top-level
            self.logger.info("MenuManager: Already at top-level, nothing to go back to.")
            return

        # Pop from stack
        previous_items = self.menu_stack.pop()
        self.current_menu_items = previous_items
        self.current_selection_index = 0
        self.window_start_index = 0
        self.display_menu()

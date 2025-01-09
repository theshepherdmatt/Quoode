# src/managers/menus/display_menu.py

import logging
import time
from PIL import ImageFont
from managers.menus.base_manager import BaseManager

class DisplayMenu(BaseManager):
    """
    A text-list menu for picking which display style to use:
      - Modern
      - Original
      - Contrast
      - Brightness (added)
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
        :param mode_manager:    The ModeManager (for transitions, config, etc.).
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

        # Font for text
        self.font_key = "menu_font"
        self.font = self.display_manager.fonts.get(self.font_key) or ImageFont.load_default()

        # Main display menu items (now includes "Brightness")
        self.display_items = ["Modern", "Original", "Brightness"]
        self.current_index = 0

        # Layout
        self.window_size   = window_size
        self.y_offset      = y_offset
        self.line_spacing  = line_spacing

        # Debounce
        self.last_action_time   = 0
        self.debounce_interval = 0.3

        # If you want sub-menu "stack" logic:
        self.menu_stack = []
        self.submenu_active = False

    # -------------------------------------------------------
    # Activation / Deactivation
    # -------------------------------------------------------
    def start_mode(self):
        if self.is_active:
            self.logger.debug("DisplayMenu: Already active.")
            return
        self.is_active = True
        self.logger.info("DisplayMenu: Starting display selection menu.")
        self.show_items_list()

    def stop_mode(self):
        if self.is_active:
            self.is_active = False
            self.display_manager.clear_screen()
            self.logger.info("DisplayMenu: Stopped and cleared display.")

    # -------------------------------------------------------
    # Display
    # -------------------------------------------------------
    def show_items_list(self):
        """
        Renders the list of current menu items, highlighting the selection.
        """
        def draw(draw_obj):
            for i, name in enumerate(self.display_items):
                arrow = "-> " if i == self.current_index else "   "
                fill_color = "white" if i == self.current_index else "gray"
                y_pos = self.y_offset + i * self.line_spacing
                draw_obj.text((5, y_pos), f"{arrow}{name}", font=self.font, fill=fill_color)

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
        # Clamp
        self.current_index = max(0, min(self.current_index, len(self.display_items) - 1))

        if old_index != self.current_index:
            self.logger.debug(f"DisplayMenu: scrolled from {old_index} to {self.current_index}")
            self.show_items_list()

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

        # Main logic
        if not self.submenu_active:
            # ----- Normal top-level selection -----
            if selected_name == "Original":
                # Switch to 'original' playback mode
                self.logger.debug("DisplayMenu: Transition to classic screen.")
                self.mode_manager.config["display_mode"] = "original"
                self.mode_manager.set_display_mode("original")
                self.mode_manager.save_preferences()
                self.stop_mode()
                self.mode_manager.to_clock()

            elif selected_name == "Modern":
                self.logger.debug("DisplayMenu: Transition to modern screen.")
                self.mode_manager.config["display_mode"] = "modern"
                self.mode_manager.set_display_mode("modern")
                self.mode_manager.save_preferences()
                self.stop_mode()
                self.mode_manager.to_clock()


            elif selected_name == "Brightness":
                self.logger.info("DisplayMenu: Opening Brightness sub-menu.")
                self._open_brightness_submenu()
                self.mode_manager.save_preferences()

            else:
                self.logger.warning(f"DisplayMenu: Unrecognized option: {selected_name}")

        else:
            # ----- If currently in brightness sub-menu -----
            # 1) Apply brightness
            self._handle_brightness_selection(selected_name)
            # 2) Immediately return user to the clock
            self.stop_mode()        # Stop this sub-menu
            self.mode_manager.to_clock()  # Switch to clock

    # -------------------------------------------------------
    #  Brightness Sub-Menu
    # -------------------------------------------------------
    def _open_brightness_submenu(self):
        """
        Replace current list items with brightness levels,
        remembering old items for a 'back' or direct return.
        """
        # Save current state
        self.menu_stack.append((list(self.display_items), self.current_index))
        self.submenu_active = True

        # Now show 3 levels
        self.display_items = ["Low", "Medium", "High"]
        self.current_index = 0
        self.show_items_list()

    def _handle_brightness_selection(self, selected_level):
        """
        User picked "Low", "Medium", or "High". Apply contrast, then return.
        """
        self.logger.debug(f"DisplayMenu: Brightness sub-menu => {selected_level}")
        # Simple mapping
        brightness_map = {
            "Low":    50,
            "Medium": 150,
            "High":   255
        }
        val = brightness_map.get(selected_level, 150)

        # Apply immediately if your display_manager.oled supports .contrast()
        try:
            if hasattr(self.display_manager.oled, "contrast"):
                self.display_manager.oled.contrast(val)
                self.logger.info(f"DisplayMenu: Set brightness to {selected_level} => contrast({val}).")
            else:
                self.logger.warning("DisplayMenu: .contrast() not found on this display device.")
        except Exception as e:
            self.logger.error(f"DisplayMenu: Failed to set brightness => {e}")

        # (Optional) Save to config so it’s remembered
        self.mode_manager.config["oled_brightness"] = val
        self.mode_manager.save_preferences()

        # Return to main list or auto-exit
        self._close_submenu_and_return()

    def _close_submenu_and_return(self):
        """
        Restore the old list items from the stack, if you want to remain in DisplayMenu,
        or just exit to clock.
        """
        if self.menu_stack:
            old_items, old_index = self.menu_stack.pop()
            self.display_items  = old_items
            self.current_index  = old_index
            self.submenu_active = False
            self.show_items_list()
        else:
            # no previous => just exit
            self.stop_mode()
            self.mode_manager.to_clock()


# src/managers/menu_manager.py

import logging
from PIL import Image, ImageDraw, ImageFont
import threading
import time

class MenuManager:
    def __init__(self, display_manager, volumio_listener, mode_manager, window_size=5, menu_type="icon_row"):
        self.display_manager = display_manager
        self.volumio_listener = volumio_listener
        self.mode_manager = mode_manager

        # Initialize logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.info("MenuManager initialized.")

        # Menu initialization
        self.menu_stack = []
        self.current_menu_items = ["Stream", "Library", "Radio", "Playlists", "Display"]  # Added Display menu
        self.stream_menu_items = ["Tidal", "Qobuz", "Spotify"]
        self.library_menu_items = ["NAS", "USB"]
        self.display_menu_items = ["FM4", "Modern"]  # New Display sub-menu
        self.icons = {
            "Stream": self.display_manager.icons.get("stream"),
            "Library": self.display_manager.icons.get("library"),
            "Radio": self.display_manager.icons.get("webradio"),
            "Playlists": self.display_manager.icons.get("playlists"),
            "Tidal": self.display_manager.icons.get("tidal"),
            "Qobuz": self.display_manager.icons.get("qobuz"),
            "Spotify": self.display_manager.icons.get("spop"),
            "NAS": self.display_manager.icons.get("nas"), 
            "USB": self.display_manager.icons.get("usb"),
            "Display": self.display_manager.icons.get("display"),  # Icon for Display menu
            "FM4": self.display_manager.icons.get("displayfm4"),  # Icon for FM4
            "Modern": self.display_manager.icons.get("displaymodern")  # Icon for Modern
        }
        self.current_selection_index = 0
        self.is_active = False
        self.window_size = window_size
        self.window_start_index = 0
        self.menu_type = menu_type
        self.font_key = 'menu_font'
        self.bold_font_key = 'menu_font_bold'
        self.lock = threading.Lock()

        # Register mode change callback if available
        if hasattr(self.mode_manager, "add_on_mode_change_callback"):
            self.mode_manager.add_on_mode_change_callback(self.handle_mode_change)


    def handle_mode_change(self, current_mode):
        self.logger.info(f"MenuManager handling mode change to: {current_mode}")
        if current_mode == "menu":
            self.start_mode()
        elif self.is_active:
            self.stop_mode()

    def start_mode(self):
        self.is_active = True
        # Reset to top-level menu items
        self.current_menu_items = ["Stream", "Library", "Radio", "Playlists", "Display"]
        self.current_selection_index = 0
        self.window_start_index = 0
        # Schedule display_menu without blocking
        threading.Thread(target=self.display_menu, daemon=True).start()

    def stop_mode(self):
        if not self.is_active:
            return
        self.is_active = False
        with self.lock:
            self.display_manager.clear_screen()
        self.logger.info("MenuManager: Stopped menu mode and cleared display.")

    def display_menu(self):
        if self.menu_type == "icon_row":
            self.display_icon_row_menu()

    def display_icon_row_menu(self):
        with self.lock:
            # Calculate the visible window based on current selection
            visible_items = self.get_visible_window(self.current_menu_items, self.window_size)

            # Constants for layout
            icon_size = 40  # Fixed size for icons
            spacing = 10    # Fixed spacing between icons
            total_width = self.display_manager.oled.width
            total_height = self.display_manager.oled.height

            # Calculate the total width for the visible items (icon + spacing)
            total_icons_width = len(visible_items) * icon_size + (len(visible_items) - 1) * spacing

            # X offset to center the visible items on the screen
            x_offset = (total_width - total_icons_width) // 2

            # Y position for the icons
            y_position = (total_height - icon_size) // 2 - 10  # Centered vertically with slight offset

            # Create an image to draw on
            base_image = Image.new("RGB", self.display_manager.oled.size, "black")
            draw_obj = ImageDraw.Draw(base_image)

            # Iterate over visible items to draw icons
            for i, item in enumerate(visible_items):
                actual_index = self.window_start_index + i
                icon = self.icons.get(item, self.display_manager.default_icon)

                # Handle transparency for icons with an alpha channel
                if icon.mode == "RGBA":
                    background = Image.new("RGB", icon.size, (0, 0, 0))
                    background.paste(icon, mask=icon.split()[3])
                    icon = background

                # Resize the icon with anti-aliasing
                icon = icon.resize((icon_size, icon_size), Image.ANTIALIAS)

                # Calculate x-coordinate for the current icon
                x = x_offset + i * (icon_size + spacing)

                # Adjust position of the selected item to "pop out" slightly
                if actual_index == self.current_selection_index:
                    y_adjustment = -5  # Move the selected icon up slightly
                else:
                    y_adjustment = 0  # Keep other icons at the normal position

                # Paste the icon onto the base image
                base_image.paste(icon, (x, y_position + y_adjustment))

                # Draw labels below icons
                label = item
                font = self.display_manager.fonts.get(self.font_key, ImageFont.load_default())
                text_color = "white" if actual_index == self.current_selection_index else "gray"

                # Calculate text size
                text_width, text_height = draw_obj.textsize(label, font=font)
                text_x = x + (icon_size - text_width) // 2
                text_y = y_position + icon_size + 3  # Position text slightly below the icon

                # Draw the label
                draw_obj.text((text_x, text_y), label, font=font, fill=text_color)

            # Convert the image to the OLED display mode and render it
            base_image = base_image.convert(self.display_manager.oled.mode)
            self.display_manager.oled.display(base_image)
            self.logger.info("MenuManager: Icon row menu displayed with scrolling effect.")




    def get_visible_window(self, items, window_size):
        # Calculate half window size
        half_window = window_size // 2

        # Set window_start_index so that the selected item is centered
        self.window_start_index = self.current_selection_index - half_window

        # Ensure window_start_index is within bounds
        if self.window_start_index < 0:
            self.window_start_index = 0
        elif self.window_start_index + window_size > len(items):
            self.window_start_index = max(len(items) - window_size, 0)

        return items[self.window_start_index:self.window_start_index + window_size]

    def scroll_selection(self, direction):
        if not self.is_active:
            return

        previous_index = self.current_selection_index
        self.current_selection_index += direction

        # Clamp the selection index within valid range
        self.current_selection_index = max(0, min(self.current_selection_index, len(self.current_menu_items) - 1))

        self.logger.info(
            f"MenuManager: Scrolled from {previous_index} to {self.current_selection_index}. "
            f"Current menu items: {self.current_menu_items}"
        )

        # Recalculate window_start_index to center the selection
        self.window_start_index = self.current_selection_index - self.window_size // 2
        self.window_start_index = max(0, min(self.window_start_index, len(self.current_menu_items) - self.window_size))

        self.display_menu()
       
    def select_item(self):
        if not self.is_active or not self.current_menu_items:
            return
        selected_item = self.current_menu_items[self.current_selection_index]
        self.logger.info(f"MenuManager: Selected menu item: {selected_item}")

        # Schedule mode change without blocking
        threading.Thread(target=self._handle_selection, args=(selected_item,), daemon=True).start()

    def _handle_selection(self, selected_item):
        # Adding a short delay to prevent accidental fast actions
        time.sleep(0.2)

        if selected_item == "Radio":
            self.mode_manager.to_webradio()
        elif selected_item == "Playlists":
            self.mode_manager.to_playlists()
        elif selected_item == "Stream":
            # Navigate into Stream menu
            self.menu_stack.append(self.current_menu_items)
            self.current_menu_items = self.stream_menu_items
            self.current_selection_index = 0
            self.window_start_index = 0
            self.display_menu()
        elif selected_item == "Library":
            # Navigate into Library menu (with NAS and USB options)
            self.menu_stack.append(self.current_menu_items)
            self.current_menu_items = self.library_menu_items
            self.current_selection_index = 0
            self.window_start_index = 0
            self.display_menu()
        elif selected_item == "Display":
            # Navigate into Display menu (with FM4 and Modern options)
            self.menu_stack.append(self.current_menu_items)
            self.current_menu_items = self.display_menu_items
            self.current_selection_index = 0
            self.window_start_index = 0
            self.display_menu()
        if selected_item == "FM4":
            self.mode_manager.to_fm4()
            self.logger.info("MenuManager: Switching to FM4 screen.")
            self.mode_manager.to_menu()  # Return to menu after selection
        elif selected_item == "Modern":
            self.mode_manager.to_modern()
            self.logger.info("MenuManager: Switching to Modern screen.")
            self.mode_manager.to_menu()  # Return to menu after selection
        elif selected_item == "NAS":
            self.mode_manager.to_library(start_uri="music-library/NAS")
            self.logger.info("Library Manager for NAS activated.")
        elif selected_item == "USB":
            self.mode_manager.to_library(start_uri="music-library/USB")
            self.logger.info("USB Library Manager activated.")
        elif selected_item == "Tidal":
            self.mode_manager.to_tidal()
        elif selected_item == "Qobuz":
            self.mode_manager.to_qobuz()
        elif selected_item == "Spotify":
            self.mode_manager.to_spotify()

# src/managers/manager_factory.py

import logging
from .menus.clock_menu import ClockMenu
from display.screens.modern_screen import ModernScreen
from display.screens.original_screen import OriginalScreen
from display.screensavers.snakescreensaver import SnakeScreensaver


class ManagerFactory:
    def __init__(self, display_manager, moode_listener, mode_manager, config):
        self.display_manager = display_manager
        self.moode_listener = moode_listener
        self.mode_manager = mode_manager
        self.config = config

        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.info("ManagerFactory initialized.")

        # Initialize manager instances as None
        self.original_screen = None
        self.menu_manager = None
        self.clock_menu = None
        self.modern_screen = None
        self.snakescreensaver = None

    def setup_mode_manager(self):
        """Set up all parts of the ModeManager."""
        # Create managers
        self.original_screen = self.create_original_screen()
        self.menu_manager = self.create_menu_manager()
        self.clock_menu = self.create_clock_menu()
        self.snakescreensaver = self.create_snakescreensaver() 
        self.modern_screen = self.create_modern_screen()

        # Assign the managers to mode_manager
        self.mode_manager.set_original_screen(self.original_screen)
        self.mode_manager.set_menu_manager(self.menu_manager)
        self.mode_manager.set_clock_menu(self.clock_menu)
        self.mode_manager.set_snakescreensaver(self.snakescreensaver)
        self.mode_manager.set_modern_screen(self.modern_screen)

        self.logger.info("ModeManager fully configured.")

    def create_menu_manager(self):
        from managers.menu_manager import MenuManager
        # MenuManager *does* want moode_listener for actual MPD stuff:
        return MenuManager(self.display_manager, self.moode_listener, self.mode_manager)

    def create_clock_menu(self):
        """
        Correctly instantiate ClockMenu so that it gets:
          - display_manager
          - mode_manager
          - (optionally) window_size=..., y_offset=..., line_spacing=...
        moode_listener is *NOT* needed by ClockMenu (it's None in the constructor).
        """
        self.logger.debug("Creating ClockMenu instance.")

        # By naming the arguments, we ensure the right ones go to the right place.
        # e.g. window_size=4, y_offset=2, line_spacing=15 as defaults.
        return ClockMenu(
            display_manager=self.display_manager,
            mode_manager=self.mode_manager,
            window_size=4,    # Must be an integer
            y_offset=2,
            line_spacing=15
        )

    def create_modern_screen(self):
        return ModernScreen(
            self.display_manager,
            self.moode_listener,
            self.mode_manager
        )

    def create_original_screen(self):
        return OriginalScreen(
            self.display_manager,
            self.moode_listener,
            self.mode_manager
        )

    def create_snakescreensaver(self):
        return SnakeScreensaver(
            self.display_manager,
            self.mode_manager
        )

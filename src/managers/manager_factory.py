# src/managers/manager_factory.py

import logging
from .menus.clock_menu import ClockMenu
from .menus.screensaver_menu import ScreensaverMenu
from .menus.display_menu import DisplayMenu
from display.screens.analog_clock import AnalogClock
from display.screens.modern_screen import ModernScreen
from display.screens.original_screen import OriginalScreen
from display.screens.system_info_screen import SystemInfoScreen

class ManagerFactory:
    def __init__(self, display_manager, moode_listener, mode_manager, config):
        self.display_manager = display_manager
        self.moode_listener = moode_listener
        self.mode_manager = mode_manager
        self.config = config

        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.info("ManagerFactory initialised.")

        # Initialise manager references
        self.original_screen = None
        self.modern_screen = None
        self.menu_manager = None
        self.clock_menu = None
        self.screensaver_menu = None
        self.display_menu = None
        self.screensaver = None
        self.system_info_screen = None

    def setup_mode_manager(self):
        """
        Instantiates and configures all screens/managers, then registers
        them with ModeManager so it can transition between them.
        """
        self.original_screen   = self.create_original_screen()
        self.modern_screen     = self.create_modern_screen()
        self.system_info_screen  = self.create_system_info_screen()
        self.menu_manager      = self.create_menu_manager()
        self.clock_menu        = self.create_clock_menu()
        self.display_menu        = self.create_display_menu()
        self.screensaver_menu  = self.create_screensaver_menu()
        self.screensaver       = self.create_screensaver()

        # Assign them to the ModeManager
        self.mode_manager.set_original_screen(self.original_screen)
        self.mode_manager.set_modern_screen(self.modern_screen)
        self.mode_manager.set_system_info_screen(self.system_info_screen)
        self.mode_manager.set_menu_manager(self.menu_manager)
        self.mode_manager.set_clock_menu(self.clock_menu)
        self.mode_manager.set_display_menu(self.display_menu)
        self.mode_manager.set_screensaver_menu(self.screensaver_menu)
        self.mode_manager.set_screensaver(self.screensaver)

        self.logger.info("ManagerFactory: ModeManager fully configured.")

    def create_menu_manager(self):
        """
        Create and return a MenuManager instance.
        """
        from managers.menu_manager import MenuManager
        return MenuManager(
            display_manager=self.display_manager,
            moode_listener=self.moode_listener,
            mode_manager=self.mode_manager
        )

    def create_clock_menu(self):
        """
        Create and return a ClockMenu instance (for clock settings).
        """
        self.logger.debug("Creating ClockMenu instance.")
        from .menus.clock_menu import ClockMenu
        return ClockMenu(
            display_manager=self.display_manager,
            mode_manager=self.mode_manager,
            window_size=4,
            y_offset=2,
            line_spacing=15
        )
    
    def create_display_menu(self):
        """
        Create and return a DisplayMenu instance (for display settings).
        """
        self.logger.debug("Creating DisplayMenu instance.")
        from .menus.display_menu import DisplayMenu
        return DisplayMenu(
            display_manager=self.display_manager,
            mode_manager=self.mode_manager,
            window_size=4,
            y_offset=2,
            line_spacing=15
        )

    def create_screensaver_menu(self):
        """
        Create and return a ScreenSaverMenu instance (for display settings).
        """
        self.logger.debug("Creating ScreenSaverMenu instance.")
        from .menus.screensaver_menu import ScreensaverMenu
        return ScreensaverMenu(
            display_manager=self.display_manager,
            mode_manager=self.mode_manager,
            window_size=4,
            y_offset=2,
            line_spacing=15
        )

    def create_modern_screen(self):
        """
        Create and return a ModernScreen instance.
        """
        self.logger.debug("Creating ModernScreen instance.")
        return ModernScreen(
            self.display_manager,
            self.moode_listener,
            self.mode_manager
        )

    def create_original_screen(self):
        """
        Create and return an OriginalScreen instance.
        """
        self.logger.debug("Creating OriginalScreen instance.")
        return OriginalScreen(
            self.display_manager,
            self.moode_listener,
            self.mode_manager
        )
    
    def create_system_info_screen(self):
        """
        Create and return an SystemInfoScreen instance.
        """
        self.logger.debug("Creating SystemInfoScreen instance.")
        return SystemInfoScreen(
            self.display_manager,
            self.moode_listener,
            self.mode_manager
        )

    def create_screensaver(self):
        """
        Dynamically load a screensaver class based on `screensaver_type`
        from preferences.json, then instantiate it.
        """
        self.logger.debug("Creating Screensaver instance based on user preference.")
        screensaver_type = self.config.get("screensaver_type", "generic").lower()

        if screensaver_type == "snake":
            from display.screensavers.snake_screensaver import SnakeScreensaver
            self.logger.info("ManagerFactory: Using SnakeScreensaver.")
            return SnakeScreensaver(
                display_manager=self.display_manager,
                update_interval=0.04
            )
        elif screensaver_type in ("stars", "starfield"):
            from display.screensavers.starfield_screensaver import StarfieldScreensaver
            self.logger.info("ManagerFactory: Using StarfieldScreensaver.")
            return StarfieldScreensaver(
                display_manager=self.display_manager,
                num_stars=40,
                update_interval=0.05
            )
        elif screensaver_type in ("quoode", "bouncing_text"):
            from display.screensavers.bouncing_text_screensaver import BouncingTextScreensaver
            self.logger.info("ManagerFactory: Using BouncingTextScreensaver.")
            return BouncingTextScreensaver(
                display_manager=self.display_manager,
                text="Quoode",
                update_interval=0.06
            )
        else:
            from display.screensavers.screensaver import Screensaver
            self.logger.info(f"ManagerFactory: Using generic Screensaver (type={screensaver_type}).")
            return Screensaver(
                display_manager=self.display_manager,
                update_interval=0.04
            )

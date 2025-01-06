# src/managers/base_manager.py
from abc import ABC, abstractmethod
import logging
import threading

class SingletonMeta(type):
    """
    A thread-safe implementation of Singleton.
    """
    _instances = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]


class BaseManager(ABC):
    def __init__(self, display_manager, moode_listener, mode_manager):
        self.display_manager = display_manager
        self.moode_listener = moode_listener
        self.mode_manager = mode_manager
        self.is_active = False
        self.on_mode_change_callbacks = []

        # Initialize logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)  # Set to INFO or adjust as needed

    @abstractmethod
    def start_mode(self):
        pass

    @abstractmethod
    def stop_mode(self):
        pass

    def add_on_mode_change_callback(self, callback):
        if callable(callback):
            self.on_mode_change_callbacks.append(callback)
            self.logger.debug(f"Added mode change callback: {callback}")
        else:
            self.logger.warning(f"Attempted to add a non-callable callback: {callback}")

    def notify_mode_change(self, mode):
        self.logger.debug(f"Notifying mode change to: {mode}")
        for callback in self.on_mode_change_callbacks:
            try:
                callback(mode)
                self.logger.debug(f"Successfully executed callback: {callback}")
            except Exception as e:
                self.logger.error(f"Error in callback {callback}: {e}")

    def clear_display(self):
        self.display_manager.clear_screen()
        self.logger.info("Cleared the display screen.")

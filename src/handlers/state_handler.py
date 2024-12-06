# src/handlers/state_handler.py

import logging

class StateHandler:
    def __init__(self, volumio_listener, mode_manager):
        self.volumio_listener = volumio_listener
        self.mode_manager = mode_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)  # Set to desired level (DEBUG/INFO/etc.)
        
        self.register_listeners()

    def register_listeners(self):
        # Connect the receiver method to the 'state_changed' signal
        self.volumio_listener.state_changed.connect(self.on_volumio_state_change)
        # Register as a mode change callback
        self.mode_manager.add_on_mode_change_callback(self.on_mode_change)

    def on_volumio_state_change(self, *args, **kwargs):
        """Handle the state change emitted by VolumioListener."""
        self.logger.debug(f"Received state change with args: {args}, kwargs: {kwargs}")
        
        # Extract sender and state
        sender = None
        state = None

        if len(args) == 1:
            sender = args[0]
            state = kwargs.get('state')
        elif len(args) == 2:
            sender, state = args
        else:
            sender = kwargs.get('sender')
            state = kwargs.get('state')

        if state is None:
            self.logger.error("StateHandler: No 'state' argument received in state change.")
            return

        self.logger.info(f"State changed by {sender}: {state}")
        # Implement your state handling logic here

    def on_mode_change(self, current_mode):
        self.logger.info(f"StateHandler: Mode changed to {current_mode}")
        # Implement any additional logic needed when mode changes
        # For example, updating the display or triggering other actions

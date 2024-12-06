# event_bus.py
from collections import defaultdict

class EventBus:
    def __init__(self):
        self.listeners = defaultdict(list)

    def subscribe(self, event_type, callback):
        self.listeners[event_type].append(callback)

    def publish(self, event_type, data=None):
        for callback in self.listeners[event_type]:
            callback(data)

# Instantiate a global event bus
bus = EventBus()


# test_detailed_playback_manager.py
from PIL import ImageFont
from detailed_playback_manager import DetailedPlaybackManager
from mock_dependencies import MockDisplayManager, MockVolumioListener, MockModeManager

# Mock dependencies for testing (replace with actual dependencies if needed)
class MockDisplayManager:
    def __init__(self):
        self.oled = MockOLED()
        self.fonts = {
            'playback_medium': ImageFont.load_default(),
            'progress_bar': ImageFont.load_default(),
        }
        self.icons = {
            'spotify': ImageFont.load_default(),
            'tidal': ImageFont.load_default(),
            'qobuz': ImageFont.load_default(),
            # Add more mock icons if needed
        }

    def clear_screen(self):
        print("Screen cleared!")

class MockOLED:
    def __init__(self):
        self.size = (128, 64)  # Replace with your screen size
        self.mode = "RGB"

    def display(self, image):
        print("Image displayed on screen!")

class MockVolumioListener:
    def get_current_state(self):
        return {
            "title": "Mock Song Title",
            "artist": "Mock Artist Name",
            "progress": 0.5,
            "service": "spotify",
        }

class MockModeManager:
    pass

# Initialize mock dependencies
display_manager = MockDisplayManager()
volumio_listener = MockVolumioListener()
mode_manager = MockModeManager()

# Initialize the DetailedPlaybackManager
detailed_playback_manager = DetailedPlaybackManager(display_manager, volumio_listener, mode_manager)

# Test data
test_data = {
    "title": "Test Song Title That Might Be Too Long for the Screen",
    "artist": "Test Artist With A Very Long Name",
    "progress": 0.65,
    "service": "spotify",
}

# Draw the test display
detailed_playback_manager.draw_display(test_data)
print("Test display updated!")

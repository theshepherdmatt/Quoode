import os
import time

fifo_path = "/tmp/cava_fifo"

# Ensure the FIFO exists
if not os.path.exists(fifo_path):
    raise FileNotFoundError(f"FIFO file not found: {fifo_path}")

# Simulated DisplayManager class (replace with your actual implementation)
class MockDisplayManager:
    def draw_custom(self, draw_function):
        # Simulate drawing to the OLED by printing to terminal
        draw_function()

display_manager = MockDisplayManager()  # Replace with your actual DisplayManager instance

def render_bars(bars):
    """Render bars on the OLED display."""
    bar_height = ["█" * int(bar) for bar in bars]  # Create text-based bars for testing
    for i, bar in enumerate(bar_height):
        print(f"Bar {i}: {bar}")  # Replace this with OLED rendering logic

# Read from the FIFO file in a loop
try:
    with open(fifo_path, "r") as fifo:
        while True:
            # Read a line of ASCII numbers from CAVA's output
            line = fifo.readline().strip()
            if line:
                # Parse numbers into a list of integers
                bars = [int(value) for value in line.split()]
                # Send parsed data to the OLED display
                display_manager.draw_custom(lambda: render_bars(bars))
            time.sleep(0.05)  # Small delay to avoid excessive CPU usage
except KeyboardInterrupt:
    print("Stopped visualisation.")


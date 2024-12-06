# src/managers/volume_overlay_manager.py

from PIL import Image, ImageDraw, ImageFont
import threading
import time
import logging

class VolumeOverlayManager:
    def __init__(self, display_manager, volumio_listener, detailed_playback_manager, overlay_duration=3):
        """
        Initializes the VolumeOverlayManager.

        :param display_manager: Instance managing display operations.
        :param volumio_listener: Instance listening to Volumio events.
        :param detailed_playback_manager: Instance of DetailedPlaybackManager.
        :param overlay_duration: Duration (in seconds) the overlay remains visible.
        """
        self.display_manager = display_manager
        self.volumio_listener = volumio_listener
        self.detailed_playback_manager = detailed_playback_manager
        self.overlay_duration = overlay_duration  # Duration in seconds

        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)

        # Thread control
        self.overlay_thread = None
        self.stop_event = threading.Event()

        # Volume tracking
        self.last_volume = None
        self.volume_lock = threading.Lock()

        # Overlay active flag
        self.overlay_active = False
        self.overlay_lock = threading.Lock()

        # Register the state_changed callback
        self.volumio_listener.state_changed.connect(self.on_state_changed)
        self.logger.info("VolumeOverlayManager initialized.")

    def on_state_changed(self, sender, state):
        """
        Callback triggered when the playback state changes.

        :param sender: The sender of the signal.
        :param state: Dictionary containing the current state.
        """
        try:
            new_volume = int(state.get("volume", 0))
            with self.volume_lock:
                if self.last_volume is None:
                    self.last_volume = new_volume  # Initialize on first state
                    self.logger.debug(f"VolumeOverlayManager: Initial volume set to {self.last_volume}")
                    return

                if new_volume != self.last_volume:
                    self.logger.debug(f"VolumeOverlayManager: Volume changed from {self.last_volume} to {new_volume}")
                    self.last_volume = new_volume
                    self.trigger_overlay(new_volume)
                else:
                    self.logger.debug("VolumeOverlayManager: Volume unchanged.")
        except Exception as e:
            self.logger.error(f"VolumeOverlayManager: Error processing state_changed signal - {e}")

    def trigger_overlay(self, volume_level):
        """
        Triggers the display of the volume overlay.

        :param volume_level: Integer (0-100) representing the current volume.
        """
        self.logger.debug("VolumeOverlayManager: Triggering volume overlay.")

        with self.overlay_lock:
            # If an overlay is already active, stop it
            if self.overlay_thread and self.overlay_thread.is_alive():
                self.logger.debug("VolumeOverlayManager: Overlay already active, resetting timer.")
                self.stop_event.set()
                self.overlay_thread.join()

            # Start a new overlay thread
            self.stop_event.clear()
            self.overlay_thread = threading.Thread(target=self.display_overlay, args=(volume_level,), daemon=True)
            self.overlay_thread.start()

    def display_overlay(self, volume_level):
        """
        Displays the volume overlay and removes it after the specified duration.

        :param volume_level: Integer (0-100) representing the volume percentage.
        """
        self.logger.debug("VolumeOverlayManager: Displaying volume overlay.")

        try:
            with self.overlay_lock:
                self.overlay_active = True  # Set the flag before drawing
                self.logger.debug(f"VolumeOverlayManager: overlay_active set to {self.overlay_active}")

            # Calculate center position based on 254x64 display
            display_width, display_height = self.display_manager.oled.width, self.display_manager.oled.height
            center_x, center_y = display_width // 2, display_height // 2

            # Calculate radius as 30% of the smaller dimension to ensure proportional sizing
            radius = int(min(display_width, display_height) * 0.3)  # For 254x64, radius = 19

            # High-resolution scaling factor for smoother drawing
            scale_factor = 2  # Drawing at double resolution
            high_res_size = (display_width * scale_factor, display_height * scale_factor)
            high_res_overlay = Image.new("RGB", high_res_size, "black")
            draw = ImageDraw.Draw(high_res_overlay)

            # Scale position and radius for high-resolution drawing
            high_res_position = (center_x * scale_factor, center_y * scale_factor)
            high_res_radius = radius * scale_factor
            high_res_thickness = 6 * scale_factor  # Adjust thickness proportionally

            # Draw the circular volume wheel at high resolution
            self.draw_volume_wheel(
                draw,
                volume_level=volume_level,
                position=high_res_position,
                radius=high_res_radius,
                thickness=high_res_thickness
            )

            # Downscale the image to original size with anti-aliasing
            overlay_image = high_res_overlay.resize((display_width, display_height), Image.LANCZOS)

            # Display the overlay
            self.display_manager.oled.display(overlay_image)
            self.logger.debug("VolumeOverlayManager: Volume overlay displayed.")

            # Log start of waiting
            self.logger.debug(f"VolumeOverlayManager: Waiting for {self.overlay_duration} seconds.")

            # Wait for the duration or until interrupted
            start_time = time.time()
            while time.time() - start_time < self.overlay_duration:
                if self.stop_event.is_set():
                    self.logger.debug("VolumeOverlayManager: Overlay display interrupted.")
                    break
                time.sleep(0.1)  # Check every 100ms

            # Log end of waiting
            elapsed = time.time() - start_time
            self.logger.debug(f"VolumeOverlayManager: Waited for {elapsed:.2f} seconds.")

            # Clear the overlay by refreshing the original playback screen
            self.refresh_playback_screen()

        except Exception as e:
            self.logger.error(f"VolumeOverlayManager: Exception during overlay display - {e}")

        finally:
            with self.overlay_lock:
                self.overlay_active = False  # Reset the flag after clearing
                self.logger.debug(f"VolumeOverlayManager: overlay_active set to {self.overlay_active}")

    def draw_volume_wheel(self, draw, volume_level, position, radius, thickness):
        """
        Draws a circular volume wheel on the provided ImageDraw object.

        :param draw: PIL ImageDraw object.
        :param volume_level: Integer (0-100) representing the volume percentage.
        :param position: Tuple (x, y) for the center of the wheel.
        :param radius: Radius of the wheel in pixels.
        :param thickness: Thickness of the wheel arc.
        """
        start_angle = 135  # Starting angle for the arc
        end_angle = start_angle + (volume_level / 100) * 270  # 270 degrees span

        # Determine fill color based on mute state
        fill_color = "red" if volume_level == 0 else "white"

        # Draw the background arc (full volume range)
        draw.arc(
            [
                position[0] - radius,
                position[1] - radius,
                position[0] + radius,
                position[1] + radius
            ],
            start=start_angle,
            end=start_angle + 270,
            fill="grey",
            width=thickness
        )

        # Draw the filled arc representing current volume
        draw.arc(
            [
                position[0] - radius,
                position[1] - radius,
                position[0] + radius,
                position[1] + radius
            ],
            start=start_angle,
            end=end_angle,
            fill=fill_color,
            width=thickness
        )

        # Draw the volume percentage at the center
        volume_text = "Muted" if volume_level == 0 else f"{volume_level}%"
        try:
            # Attempt to retrieve 'volume_font' from DisplayManager's fonts
            font = self.display_manager.fonts.get('volume_font', ImageFont.truetype("arial.ttf", 24))  # Increased font size
        except IOError:
            font = ImageFont.load_default()
            self.logger.warning("VolumeOverlayManager: 'arial.ttf' not found. Using default font.")
        text_width, text_height = draw.textsize(volume_text, font=font)
        text_position = (position[0] - text_width // 2, position[1] - text_height // 2)
        draw.text(text_position, volume_text, font=font, fill="white")

        # Optional: Draw mute icon (e.g., two diagonal lines)
        if volume_level == 0:
            offset = radius + 4  # Slightly larger offset for visibility
            line_width = thickness // 2 if thickness > 2 else 2
            draw.line(
                [position[0] - offset, position[1] - offset, position[0] + offset, position[1] + offset],
                fill="red",
                width=line_width
            )
            draw.line(
                [position[0] + offset, position[1] - offset, position[0] - offset, position[1] + offset],
                fill="red",
                width=line_width
            )

    def refresh_playback_screen(self):
        """
        Refreshes the original playback screen after the overlay is removed.
        """
        self.logger.debug("VolumeOverlayManager: Refreshing the playback screen.")
        try:
            playback_state = self.volumio_listener.get_current_state()
            if playback_state:
                self.detailed_playback_manager.draw_display(playback_state)
                self.logger.debug("VolumeOverlayManager: Playback screen refreshed.")
            else:
                self.logger.warning("VolumeOverlayManager: No playback state available to refresh the screen.")
        except Exception as e:
            self.logger.error(f"VolumeOverlayManager: Exception during playback screen refresh - {e}")

    def is_overlay_active(self):
        """
        Thread-safe method to check if the overlay is active.
        """
        with self.overlay_lock:
            return self.overlay_active

    def stop(self):
        """
        Stops the VolumeOverlayManager, ensuring any active overlays are removed.
        """
        self.logger.info("VolumeOverlayManager: Stopping manager.")
        with self.overlay_lock:
            if self.overlay_thread and self.overlay_thread.is_alive():
                self.logger.debug("VolumeOverlayManager: Stopping active overlay thread.")
                self.stop_event.set()
                self.overlay_thread.join()
                self.logger.debug("VolumeOverlayManager: Active overlay thread stopped.")

            self.overlay_active = False

        # Clear the overlay display if necessary
        self.display_manager.clear_screen()
        self.logger.info("VolumeOverlayManager: Manager stopped and display cleared.")

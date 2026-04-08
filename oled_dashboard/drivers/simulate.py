"""
Simulated OLED driver for development and web preview.
Renders to an in-memory PIL Image instead of real hardware.
"""

import io
import base64
from PIL import Image
from oled_dashboard.drivers.base import OLEDDriver


class SimulatedDriver(OLEDDriver):
    """Simulated OLED driver that renders to memory.
    Used for the web preview and development without hardware.
    """

    CHIP = "SIMULATED"
    SUPPORTED_DISPLAYS = {
        "any": {"width": 0, "height": 0, "description": "Simulated display"},
    }

    def __init__(self, width: int = 128, height: int = 64, **kwargs):
        super().__init__(width=width, height=height, **kwargs)
        self._framebuffer = None

    def initialize(self) -> bool:
        """Initialize the simulated display."""
        self._framebuffer = Image.new("1", (self.width, self.height), 0)
        self._initialized = True
        return True

    def display_image(self, image: Image.Image) -> None:
        """Store the image in the framebuffer."""
        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height))
        if image.mode != "1":
            image = image.convert("1")
        self._framebuffer = image.copy()

    def clear(self) -> None:
        """Clear the framebuffer."""
        if self._framebuffer is not None:
            self._framebuffer = Image.new("1", (self.width, self.height), 0)

    def set_brightness(self, level: int) -> None:
        """No-op for simulated display."""
        pass

    def get_framebuffer(self) -> Image.Image:
        """Get the current framebuffer image."""
        if self._framebuffer is None:
            return Image.new("1", (self.width, self.height), 0)
        return self._framebuffer.copy()

    def get_framebuffer_base64(self, scale: int = 4) -> str:
        """Get the framebuffer as a base64-encoded PNG for web preview."""
        img = self.get_framebuffer()
        # Scale up for visibility in the web UI
        if scale > 1:
            img = img.resize(
                (self.width * scale, self.height * scale),
                Image.NEAREST,
            )
        # Convert to RGB with OLED-like colors (cyan/blue on black)
        rgb = Image.new("RGB", img.size, (0, 0, 0))
        pixels = img.load()
        rgb_pixels = rgb.load()
        for y in range(img.height):
            for x in range(img.width):
                if pixels[x, y]:
                    rgb_pixels[x, y] = (0, 220, 255)  # Cyan OLED look

        buffer = io.BytesIO()
        rgb.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

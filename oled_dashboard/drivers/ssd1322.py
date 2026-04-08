"""
SSD1322 OLED driver.
Supports 256x64 (3.12") grayscale displays.
"""

from PIL import Image
from oled_dashboard.drivers.base import OLEDDriver


class SSD1322Driver(OLEDDriver):
    """Driver for SSD1322-based OLED displays (grayscale)."""

    CHIP = "SSD1322"
    SUPPORTED_DISPLAYS = {
        "256x64": {"width": 256, "height": 64, "description": '3.12" 256x64'},
    }

    def initialize(self) -> bool:
        """Initialize the SSD1322 display."""
        try:
            if self.interface == "spi":
                self._display = self._init_spi()
            elif self.interface == "i2c":
                self._display = self._init_i2c()
            else:
                raise ValueError(f"Unsupported interface: {self.interface}")

            self.clear()
            self._initialized = True
            return True
        except Exception as e:
            print(f"[SSD1322] Initialization failed: {e}")
            self._initialized = False
            return False

    def _init_spi(self):
        """Initialize via SPI (most common for SSD1322)."""
        from luma.core.interface.serial import spi as luma_spi
        from luma.oled.device import ssd1322

        serial = luma_spi(
            device=self.spi_device,
            port=0,
            gpio_DC=self.spi_dc_pin,
            gpio_RST=self.spi_reset_pin,
        )
        return ssd1322(serial, width=self.width, height=self.height,
                       rotate=self._luma_rotation())

    def _init_i2c(self):
        """Initialize via I2C."""
        from luma.core.interface.serial import i2c as luma_i2c
        from luma.oled.device import ssd1322

        serial = luma_i2c(port=self.i2c_bus, address=self.address)
        return ssd1322(serial, width=self.width, height=self.height,
                       rotate=self._luma_rotation())

    def _luma_rotation(self) -> int:
        """Convert rotation degrees to luma rotation value (0-3)."""
        return {0: 0, 90: 1, 180: 2, 270: 3}.get(self.rotation, 0)

    def display_image(self, image: Image.Image) -> None:
        """Display a PIL Image on the OLED."""
        if not self._initialized or self._display is None:
            return

        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height))
        # SSD1322 supports grayscale
        if image.mode != "L":
            image = image.convert("L")

        self._display.display(image)

    def clear(self) -> None:
        """Clear the display."""
        if self._display is not None:
            self._display.clear()

    def set_brightness(self, level: int) -> None:
        """Set display contrast (0-255)."""
        if self._display is not None:
            level = max(0, min(255, level))
            self._display.contrast(level)

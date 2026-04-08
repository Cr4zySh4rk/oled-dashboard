"""
SH1106 OLED driver.
Supports 128x64 (1.3") displays.
"""

from PIL import Image
from typing import Optional
from oled_dashboard.drivers.base import OLEDDriver


class SH1106Driver(OLEDDriver):
    """Driver for SH1106-based OLED displays."""

    CHIP = "SH1106"
    SUPPORTED_DISPLAYS = {
        "128x64": {"width": 128, "height": 64, "description": '1.3" 128x64'},
    }

    def initialize(self) -> bool:
        """Initialize the SH1106 display."""
        try:
            if self.interface == "i2c":
                self._display = self._init_i2c()
            elif self.interface == "spi":
                self._display = self._init_spi()
            else:
                raise ValueError(f"Unsupported interface: {self.interface}")

            self.clear()
            self._initialized = True
            return True
        except Exception as e:
            print(f"[SH1106] Initialization failed: {e}")
            self._initialized = False
            return False

    def _init_i2c(self):
        """Initialize via I2C."""
        import board
        import busio
        from adafruit_bus_device.i2c_device import I2CDevice

        # SH1106 uses luma.oled or adafruit_displayio_sh1106
        # We use luma.oled for broader compatibility
        from luma.core.interface.serial import i2c as luma_i2c
        from luma.oled.device import sh1106

        serial = luma_i2c(port=self.i2c_bus, address=self.address)
        device = sh1106(serial, width=self.width, height=self.height,
                        rotate=self._luma_rotation())
        return device

    def _init_spi(self):
        """Initialize via SPI."""
        from luma.core.interface.serial import spi as luma_spi
        from luma.oled.device import sh1106

        serial = luma_spi(
            device=self.spi_device,
            port=0,
            gpio_DC=self.spi_dc_pin,
            gpio_RST=self.spi_reset_pin,
        )
        device = sh1106(serial, width=self.width, height=self.height,
                        rotate=self._luma_rotation())
        return device

    def _luma_rotation(self) -> int:
        """Convert rotation degrees to luma rotation value (0-3)."""
        return {0: 0, 90: 1, 180: 2, 270: 3}.get(self.rotation, 0)

    def display_image(self, image: Image.Image) -> None:
        """Display a PIL Image on the OLED."""
        if not self._initialized or self._display is None:
            return

        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height))
        if image.mode != "1":
            image = image.convert("1")

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

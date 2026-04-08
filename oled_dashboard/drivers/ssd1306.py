"""
SSD1306 OLED driver.
Supports 128x64 (0.96"), 128x32 (0.91"), 64x48 (0.66"), 64x32 displays.
"""

from PIL import Image
from typing import Optional
from oled_dashboard.drivers.base import OLEDDriver


class SSD1306Driver(OLEDDriver):
    """Driver for SSD1306-based OLED displays."""

    CHIP = "SSD1306"
    SUPPORTED_DISPLAYS = {
        "128x64": {"width": 128, "height": 64, "description": '0.96" 128x64'},
        "128x32": {"width": 128, "height": 32, "description": '0.91" 128x32'},
        "64x48": {"width": 64, "height": 48, "description": '0.66" 64x48'},
        "64x32": {"width": 64, "height": 32, "description": '0.49" 64x32'},
    }

    def initialize(self) -> bool:
        """Initialize the SSD1306 display."""
        try:
            if self.interface == "i2c":
                self._display = self._init_i2c()
            elif self.interface == "spi":
                self._display = self._init_spi()
            else:
                raise ValueError(f"Unsupported interface: {self.interface}")

            if self.rotation == 180:
                try:
                    self._display.rotate(2)
                except AttributeError:
                    self._display.rotation = 2

            self.clear()
            self._initialized = True
            return True
        except Exception as e:
            print(f"[SSD1306] Initialization failed: {e}")
            self._initialized = False
            return False

    def _init_i2c(self):
        """Initialize via I2C."""
        import board
        import busio
        import adafruit_ssd1306

        i2c = busio.I2C(board.SCL, board.SDA)
        return adafruit_ssd1306.SSD1306_I2C(
            self.width, self.height, i2c, addr=self.address
        )

    def _init_spi(self):
        """Initialize via SPI."""
        import board
        import busio
        import digitalio
        import adafruit_ssd1306

        spi = busio.SPI(board.SCK, MOSI=board.MOSI)
        dc = digitalio.DigitalInOut(getattr(board, f"D{self.spi_dc_pin}"))
        cs = digitalio.DigitalInOut(getattr(board, f"D{self.spi_cs_pin}"))
        reset = None
        if self.spi_reset_pin is not None:
            reset = digitalio.DigitalInOut(
                getattr(board, f"D{self.spi_reset_pin}")
            )
        return adafruit_ssd1306.SSD1306_SPI(
            self.width, self.height, spi, dc, reset, cs
        )

    def display_image(self, image: Image.Image) -> None:
        """Display a PIL Image on the OLED."""
        if not self._initialized or self._display is None:
            return

        # Handle rotation in software for 90/270
        if self.rotation in (90, 270):
            image = image.rotate(-self.rotation, expand=True)

        # Convert to 1-bit and resize if needed
        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height))
        if image.mode != "1":
            image = image.convert("1")

        self._display.image(image)
        self._display.show()

    def clear(self) -> None:
        """Clear the display."""
        if self._display is not None:
            self._display.fill(0)
            self._display.show()

    def set_brightness(self, level: int) -> None:
        """Set display contrast (0-255)."""
        if self._display is not None:
            level = max(0, min(255, level))
            self._display.contrast(level)

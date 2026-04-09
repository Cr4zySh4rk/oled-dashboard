"""
SSD1306 OLED driver.
Supports 128x64 (0.96"), 128x32 (0.91"), 64x48 (0.66"), 64x32 displays.

Uses smbus2 + direct I2C as primary path (works reliably on DietPi/Raspberry Pi OS),
with adafruit-circuitpython-ssd1306 as a secondary path if available.
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
        "64x48":  {"width": 64,  "height": 48, "description": '0.66" 64x48'},
        "64x32":  {"width": 64,  "height": 32, "description": '0.49" 64x32'},
    }

    def initialize(self) -> bool:
        """Initialize the SSD1306 display."""
        error_messages = []

        if self.interface == "i2c":
            # Try luma.oled first (works best on DietPi / bare Pi without Blinka)
            try:
                self._display = self._init_luma_i2c()
                self._backend = "luma"
                self._apply_rotation_luma()
                self.clear()
                self._initialized = True
                print(f"[SSD1306] Initialized via luma.oled I2C (bus={self.i2c_bus}, addr=0x{self.address:02X})")
                return True
            except Exception as e:
                error_messages.append(f"luma.oled: {e}")

            # Fall back to adafruit-circuitpython-ssd1306 (needs Blinka)
            try:
                self._display = self._init_adafruit_i2c()
                self._backend = "adafruit"
                self._apply_rotation_adafruit()
                self.clear()
                self._initialized = True
                print(f"[SSD1306] Initialized via adafruit I2C (bus={self.i2c_bus}, addr=0x{self.address:02X})")
                return True
            except Exception as e:
                error_messages.append(f"adafruit: {e}")

        elif self.interface == "spi":
            try:
                self._display = self._init_luma_spi()
                self._backend = "luma"
                self._apply_rotation_luma()
                self.clear()
                self._initialized = True
                print(f"[SSD1306] Initialized via luma.oled SPI")
                return True
            except Exception as e:
                error_messages.append(f"luma SPI: {e}")

            try:
                self._display = self._init_adafruit_spi()
                self._backend = "adafruit"
                self._apply_rotation_adafruit()
                self.clear()
                self._initialized = True
                print(f"[SSD1306] Initialized via adafruit SPI")
                return True
            except Exception as e:
                error_messages.append(f"adafruit SPI: {e}")

        # All methods failed — print clear diagnostics
        print(f"[SSD1306] *** HARDWARE INIT FAILED — display will NOT render ***")
        print(f"[SSD1306] Tried:")
        for msg in error_messages:
            print(f"  • {msg}")
        print(f"[SSD1306] Check:")
        print(f"  1. Is I2C enabled? Run: sudo raspi-config → Interface Options → I2C")
        print(f"  2. Is the display detected? Run: sudo i2cdetect -y {self.i2c_bus}")
        print(f"  3. Is the I2C address correct? Config says 0x{self.address:02X}")
        print(f"  4. Install dependencies: pip install luma.oled smbus2")
        self._initialized = False
        return False

    # ── luma.oled backend (preferred) ─────────────────────────────

    def _init_luma_i2c(self):
        from luma.core.interface.serial import i2c as luma_i2c
        from luma.oled.device import ssd1306

        serial = luma_i2c(port=self.i2c_bus, address=self.address)
        return ssd1306(serial, width=self.width, height=self.height)

    def _init_luma_spi(self):
        from luma.core.interface.serial import spi as luma_spi
        from luma.oled.device import ssd1306

        serial = luma_spi(
            device=self.spi_device,
            port=0,
            gpio_DC=self.spi_dc_pin,
            gpio_RST=self.spi_reset_pin,
        )
        return ssd1306(serial, width=self.width, height=self.height)

    def _apply_rotation_luma(self):
        rot = {0: 0, 90: 1, 180: 2, 270: 3}.get(self.rotation, 0)
        if rot and hasattr(self._display, 'rotate'):
            self._display.rotate(rot)

    # ── adafruit-circuitpython-ssd1306 backend ─────────────────────

    def _init_adafruit_i2c(self):
        import board
        import busio
        import adafruit_ssd1306

        i2c = busio.I2C(board.SCL, board.SDA)
        return adafruit_ssd1306.SSD1306_I2C(
            self.width, self.height, i2c, addr=self.address
        )

    def _init_adafruit_spi(self):
        import board
        import busio
        import digitalio
        import adafruit_ssd1306

        spi = busio.SPI(board.SCK, MOSI=board.MOSI)
        dc = digitalio.DigitalInOut(getattr(board, f"D{self.spi_dc_pin}"))
        cs = digitalio.DigitalInOut(getattr(board, f"D{self.spi_cs_pin}"))
        reset = None
        if self.spi_reset_pin is not None:
            reset = digitalio.DigitalInOut(getattr(board, f"D{self.spi_reset_pin}"))
        return adafruit_ssd1306.SSD1306_SPI(
            self.width, self.height, spi, dc, reset, cs
        )

    def _apply_rotation_adafruit(self):
        if self.rotation == 180:
            try:
                self._display.rotate(2)
            except AttributeError:
                self._display.rotation = 2

    # ── Unified display methods ────────────────────────────────────

    def display_image(self, image: Image.Image) -> None:
        if not self._initialized or self._display is None:
            return

        # Software rotation for 90/270
        if self.rotation in (90, 270):
            image = image.rotate(-self.rotation, expand=True)

        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height))
        if image.mode != "1":
            image = image.convert("1")

        if getattr(self, '_backend', None) == "luma":
            self._display.display(image)
        else:
            self._display.image(image)
            self._display.show()

    def clear(self) -> None:
        if self._display is None:
            return
        if getattr(self, '_backend', None) == "luma":
            self._display.clear()
        else:
            self._display.fill(0)
            self._display.show()

    def set_brightness(self, level: int) -> None:
        if self._display is not None:
            level = max(0, min(255, level))
            self._display.contrast(level)

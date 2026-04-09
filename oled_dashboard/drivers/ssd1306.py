"""
SSD1306 / SH1106 OLED driver.
Supports 128x64 (0.96"), 128x32 (0.91"), 64x48 (0.66"), 64x32 displays.

Key insight from the original OLED_Stats project:
  Many OLED modules have their RST pin wired to a GPIO (default GPIO 4).
  Without a hardware reset pulse (HIGH → LOW → HIGH) before initialisation,
  the controller stays in an undefined state — it ACKs I2C writes silently
  but never updates the display pixels. This is the most common cause of a
  blank screen even when i2cdetect finds the device.

Driver tries in order:
  1. GPIO reset (GPIO 4 by default, skipped gracefully if not wired)
  2. luma.oled ssd1306
  3. luma.oled sh1106  ← same address, commonly mislabeled modules
  4. adafruit-circuitpython-ssd1306 (needs Blinka)
"""

import time
from PIL import Image
from typing import Optional
from oled_dashboard.drivers.base import OLEDDriver


def _gpio_reset(gpio_pin: int = 4) -> None:
    """
    Pulse the OLED reset pin LOW then HIGH.
    Matches the reset sequence used by the original OLED_Stats project.
    Silently skipped if gpiozero / RPi.GPIO is unavailable or pin not wired.
    """
    # Try gpiozero first (cleanest API)
    try:
        import gpiozero
        rst = gpiozero.OutputDevice(gpio_pin, active_high=False)
        rst.on()           # active_high=False → pin goes HIGH (not reset)
        time.sleep(0.1)
        rst.off()          # pin goes LOW  → assert reset
        time.sleep(0.1)
        rst.on()           # pin goes HIGH → release reset
        time.sleep(0.05)   # give controller time to boot
        rst.close()
        print(f"[OLED] GPIO {gpio_pin} reset pulse sent (via gpiozero)")
        return
    except Exception as e:
        pass  # gpiozero not available or pin not wired

    # Fall back to RPi.GPIO
    try:
        import RPi.GPIO as GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(gpio_pin, GPIO.OUT)
        GPIO.output(gpio_pin, GPIO.HIGH)
        time.sleep(0.1)
        GPIO.output(gpio_pin, GPIO.LOW)
        time.sleep(0.1)
        GPIO.output(gpio_pin, GPIO.HIGH)
        time.sleep(0.05)
        print(f"[OLED] GPIO {gpio_pin} reset pulse sent (via RPi.GPIO)")
        return
    except Exception:
        pass  # RPi.GPIO not available or running as non-root

    print(f"[OLED] GPIO reset skipped (GPIO {gpio_pin} — no GPIO library or pin not wired)")


class SSD1306Driver(OLEDDriver):
    """
    Driver for SSD1306 and SH1106-based OLED displays.

    Tries multiple backends in order:
      1. GPIO reset pulse (GPIO 4, matching original OLED_Stats wiring)
      2. luma.oled ssd1306
      3. luma.oled sh1106  (many cheap modules are mislabeled)
      4. adafruit-circuitpython-ssd1306 (needs Blinka)
    """

    CHIP = "SSD1306"
    SUPPORTED_DISPLAYS = {
        "128x64": {"width": 128, "height": 64, "description": '0.96" 128x64'},
        "128x32": {"width": 128, "height": 32, "description": '0.91" 128x32'},
        "64x48":  {"width": 64,  "height": 48, "description": '0.66" 64x48'},
        "64x32":  {"width": 64,  "height": 32, "description": '0.49" 64x32'},
    }

    def initialize(self) -> bool:
        """Initialize display with GPIO reset → luma ssd1306 → luma sh1106 → adafruit."""
        error_messages = []

        # ── GPIO hardware reset (critical for modules with RST on GPIO 4) ──
        reset_pin = self.reset_pin if self.reset_pin is not None else 4
        _gpio_reset(reset_pin)

        if self.interface == "i2c":
            # ── luma.oled SSD1306 ─────────────────────────────────────────
            try:
                self._display = self._init_luma_i2c("ssd1306")
                self._backend = "luma"
                self._chip_used = "ssd1306"
                self._apply_rotation_luma()
                self.clear()
                self._initialized = True
                print(f"[OLED] Initialized SSD1306 via luma.oled I2C "
                      f"(bus={self.i2c_bus}, addr=0x{self.address:02X})")
                return True
            except Exception as e:
                error_messages.append(f"luma ssd1306: {e}")

            # ── luma.oled SH1106 (same address, common mislabeling) ───────
            try:
                self._display = self._init_luma_i2c("sh1106")
                self._backend = "luma"
                self._chip_used = "sh1106"
                self._apply_rotation_luma()
                self.clear()
                self._initialized = True
                print(f"[OLED] Initialized SH1106 via luma.oled I2C "
                      f"(bus={self.i2c_bus}, addr=0x{self.address:02X})")
                print(f"[OLED] NOTE: Your display is SH1106, not SSD1306. "
                      f"Consider updating 'chip' in config to 'SH1106'.")
                return True
            except Exception as e:
                error_messages.append(f"luma sh1106: {e}")

            # ── adafruit-circuitpython-ssd1306 (needs Blinka) ─────────────
            try:
                self._display = self._init_adafruit_i2c()
                self._backend = "adafruit"
                self._chip_used = "ssd1306"
                self._apply_rotation_adafruit()
                self.clear()
                self._initialized = True
                print(f"[OLED] Initialized SSD1306 via adafruit I2C "
                      f"(bus={self.i2c_bus}, addr=0x{self.address:02X})")
                return True
            except Exception as e:
                error_messages.append(f"adafruit: {e}")

        elif self.interface == "spi":
            for chip_name in ("ssd1306", "sh1106"):
                try:
                    self._display = self._init_luma_spi(chip_name)
                    self._backend = "luma"
                    self._chip_used = chip_name
                    self._apply_rotation_luma()
                    self.clear()
                    self._initialized = True
                    print(f"[OLED] Initialized {chip_name.upper()} via luma.oled SPI")
                    return True
                except Exception as e:
                    error_messages.append(f"luma SPI {chip_name}: {e}")

            try:
                self._display = self._init_adafruit_spi()
                self._backend = "adafruit"
                self._chip_used = "ssd1306"
                self._apply_rotation_adafruit()
                self.clear()
                self._initialized = True
                print(f"[OLED] Initialized via adafruit SPI")
                return True
            except Exception as e:
                error_messages.append(f"adafruit SPI: {e}")

        # ── All methods failed ─────────────────────────────────────────────
        print(f"[OLED] *** HARDWARE INIT FAILED — display will NOT render ***")
        print(f"[OLED] Tried:")
        for msg in error_messages:
            print(f"  • {msg}")
        print(f"[OLED] Diagnostics:")
        print(f"  1. Is I2C enabled?  sudo raspi-config → Interface Options → I2C")
        print(f"  2. Is device found? sudo i2cdetect -y {self.i2c_bus}")
        print(f"  3. Config address:  0x{self.address:02X} — try 0x3D if nothing at 0x3C")
        print(f"  4. Install deps:    pip install luma.oled smbus2")
        print(f"  5. Run diagnostic:  python /opt/oled-dashboard/test_display.py")
        self._initialized = False
        return False

    # ── luma.oled backends ────────────────────────────────────────────────

    def _init_luma_i2c(self, chip: str = "ssd1306"):
        from luma.core.interface.serial import i2c as luma_i2c
        serial = luma_i2c(port=self.i2c_bus, address=self.address)
        if chip == "sh1106":
            from luma.oled.device import sh1106
            return sh1106(serial, width=self.width, height=self.height)
        else:
            from luma.oled.device import ssd1306
            return ssd1306(serial, width=self.width, height=self.height)

    def _init_luma_spi(self, chip: str = "ssd1306"):
        from luma.core.interface.serial import spi as luma_spi
        serial = luma_spi(
            device=self.spi_device,
            port=0,
            gpio_DC=self.spi_dc_pin,
            gpio_RST=self.spi_reset_pin,
        )
        if chip == "sh1106":
            from luma.oled.device import sh1106
            return sh1106(serial, width=self.width, height=self.height)
        else:
            from luma.oled.device import ssd1306
            return ssd1306(serial, width=self.width, height=self.height)

    def _apply_rotation_luma(self):
        rot = {0: 0, 90: 1, 180: 2, 270: 3}.get(self.rotation, 0)
        if rot and hasattr(self._display, 'rotate'):
            self._display.rotate(rot)

    # ── adafruit backend ──────────────────────────────────────────────────

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

    # ── Unified display methods ───────────────────────────────────────────

    def display_image(self, image: Image.Image) -> None:
        if not self._initialized or self._display is None:
            return

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

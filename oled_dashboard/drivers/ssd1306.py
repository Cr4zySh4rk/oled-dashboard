"""
SSD1306 / SH1106 OLED driver.
Supports 128x64 (0.96"), 128x32 (0.91"), 64x48 (0.66"), 64x32 displays.

For 4-pin I2C modules (VCC GND SDA SCL) — no RST pin, no GPIO needed.

Rendering pipeline (tried in order):
  1. luma.oled ssd1306.display(image)   — primary path
  2. luma.oled sh1106.display(image)    — same address, mislabeled modules
  3. Direct smbus2 framebuffer write    — guaranteed fallback, bypasses both
     libraries, sends pixels in 32-byte I2C chunks that work on all platforms
     including Pi 5 RP1 I2C controller
  4. adafruit-circuitpython-ssd1306     — last resort (needs Blinka)
"""

import time
from PIL import Image
from typing import Optional
from oled_dashboard.drivers.base import OLEDDriver


# ── Direct smbus2 rendering (no external OLED library needed) ─────────────────

def _pil_to_ssd1306_bytes(image: Image.Image) -> bytes:
    """
    Convert a PIL mode-'1' image to the SSD1306 native page format.
    SSD1306 stores pixels as pages of 8 rows; within each page, each byte
    is one column, with bit-0 being the top row of that page.
    PIL stores pixels row-major with bit-7 first.
    """
    if image.mode != "1":
        image = image.convert("1")
    w, h = image.size
    pages = (h + 7) // 8
    pixels = image.load()
    buf = []
    for page in range(pages):
        for x in range(w):
            byte = 0
            for bit in range(8):
                y = page * 8 + bit
                if y < h and pixels[x, y]:
                    byte |= (1 << bit)
            buf.append(byte)
    return bytes(buf)


def _smbus2_display(image: Image.Image, bus_num: int, addr: int, width: int, height: int) -> None:
    """
    Write a PIL image directly to an SSD1306/SH1106 via smbus2.
    Sends data in 32-byte chunks — safe for all I2C controller buffer sizes
    including the Pi 5 RP1 chip.
    """
    import smbus2

    buf = _pil_to_ssd1306_bytes(image)
    pages = (height + 7) // 8

    with smbus2.SMBus(bus_num) as bus:
        def cmd(b):
            bus.write_byte_data(addr, 0x00, b)

        # Set horizontal addressing mode and full-screen window
        cmd(0x20); cmd(0x00)          # Horizontal addressing mode
        cmd(0x21); cmd(0x00); cmd(width - 1)   # Column start / end
        cmd(0x22); cmd(0x00); cmd(pages - 1)   # Page start / end

        # Send framebuffer in 32-byte chunks
        CHUNK = 32
        for i in range(0, len(buf), CHUNK):
            chunk = list(buf[i:i + CHUNK])
            bus.write_i2c_block_data(addr, 0x40, chunk)


# ── Driver class ──────────────────────────────────────────────────────────────

class SSD1306Driver(OLEDDriver):
    """
    Driver for 4-pin I2C SSD1306 and SH1106 OLED displays.
    No GPIO/RST pin required.
    """

    CHIP = "SSD1306"
    SUPPORTED_DISPLAYS = {
        "128x64": {"width": 128, "height": 64, "description": '0.96" 128x64'},
        "128x32": {"width": 128, "height": 32, "description": '0.91" 128x32'},
        "64x48":  {"width": 64,  "height": 48, "description": '0.66" 64x48'},
        "64x32":  {"width": 64,  "height": 32, "description": '0.49" 64x32'},
    }

    def initialize(self) -> bool:
        error_messages = []

        if self.interface == "i2c":
            # ── 1. luma.oled SSD1306 ─────────────────────────────────────
            try:
                self._display = self._init_luma_i2c("ssd1306")
                self._backend = "luma"
                self._chip_used = "ssd1306"
                self._apply_rotation_luma()
                self._initialized = True
                self._luma_verify_or_fallback_to_smbus2()
                print(f"[OLED] Ready: SSD1306 luma.oled I2C "
                      f"(bus={self.i2c_bus}, addr=0x{self.address:02X}, "
                      f"render={'direct-smbus2' if self._use_smbus2 else 'luma'})")
                return True
            except Exception as e:
                error_messages.append(f"luma ssd1306: {e}")

            # ── 2. luma.oled SH1106 ──────────────────────────────────────
            try:
                self._display = self._init_luma_i2c("sh1106")
                self._backend = "luma"
                self._chip_used = "sh1106"
                self._apply_rotation_luma()
                self._initialized = True
                self._luma_verify_or_fallback_to_smbus2()
                print(f"[OLED] Ready: SH1106 luma.oled I2C "
                      f"(bus={self.i2c_bus}, addr=0x{self.address:02X}, "
                      f"render={'direct-smbus2' if self._use_smbus2 else 'luma'})")
                print(f"[OLED] NOTE: Your module is SH1106, not SSD1306. "
                      f"You can set 'chip': 'SH1106' in config.")
                return True
            except Exception as e:
                error_messages.append(f"luma sh1106: {e}")

            # ── 3. Direct smbus2 (no luma needed) ────────────────────────
            try:
                self._smbus2_init()
                self._backend = "smbus2"
                self._chip_used = "ssd1306"
                self._use_smbus2 = True
                self._initialized = True
                print(f"[OLED] Ready: SSD1306 direct smbus2 "
                      f"(bus={self.i2c_bus}, addr=0x{self.address:02X})")
                return True
            except Exception as e:
                error_messages.append(f"direct smbus2: {e}")

            # ── 4. adafruit-circuitpython-ssd1306 ────────────────────────
            try:
                self._display = self._init_adafruit_i2c()
                self._backend = "adafruit"
                self._chip_used = "ssd1306"
                self._use_smbus2 = False
                self._initialized = True
                self.clear()
                print(f"[OLED] Ready: SSD1306 adafruit I2C "
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
                    self._use_smbus2 = False
                    self._apply_rotation_luma()
                    self.clear()
                    self._initialized = True
                    print(f"[OLED] Ready: {chip_name.upper()} luma.oled SPI")
                    return True
                except Exception as e:
                    error_messages.append(f"luma SPI {chip_name}: {e}")

        # ── All failed ────────────────────────────────────────────────────
        print(f"[OLED] *** HARDWARE INIT FAILED ***")
        for msg in error_messages:
            print(f"  • {msg}")
        print(f"[OLED] Check: i2cdetect -y {self.i2c_bus}  |  addr=0x{self.address:02X}")
        print(f"[OLED] Diagnostic: python /opt/oled-dashboard/test_display.py")
        self._initialized = False
        return False

    # ── luma.oled verification ────────────────────────────────────────────────

    def _luma_verify_or_fallback_to_smbus2(self):
        """
        After luma.oled init, try a test render via device.display().
        If that raises an exception, fall back to direct smbus2 rendering.
        Some platforms (e.g. Pi 5 RP1 I2C) reject large luma I2C writes.
        """
        self._use_smbus2 = False
        try:
            test_img = Image.new("1", (self.width, self.height), 0)
            self._display.display(test_img)
        except Exception as e:
            print(f"[OLED] luma display() failed ({e}), switching to direct smbus2 render")
            self._use_smbus2 = True

    # ── smbus2 direct init ────────────────────────────────────────────────────

    def _smbus2_init(self):
        """
        Initialise an SSD1306 via raw smbus2 commands.
        Sends the standard initialization sequence used by most SSD1306 libraries.
        """
        import smbus2

        w, h = self.width, self.height
        pages = (h + 7) // 8

        init_cmds = [
            0xAE,           # Display off
            0xD5, 0x80,     # Set display clock divide ratio / oscillator frequency
            0xA8, h - 1,    # Set multiplex ratio
            0xD3, 0x00,     # Set display offset
            0x40,           # Set start line = 0
            0x8D, 0x14,     # Charge pump: enable
            0x20, 0x00,     # Memory addressing: horizontal
            0xA1,           # Segment re-map: col 127 = SEG0
            0xC8,           # COM scan direction: remapped
            0xDA, 0x12 if h == 64 else 0x02,  # COM pins hardware config
            0x81, 0xCF,     # Contrast
            0xD9, 0xF1,     # Pre-charge period
            0xDB, 0x40,     # VCOMH deselect level
            0xA4,           # Entire display ON (use RAM content)
            0xA6,           # Normal display (not inverted)
            0xAF,           # Display ON
        ]

        with smbus2.SMBus(self.i2c_bus) as bus:
            for c in init_cmds:
                bus.write_byte_data(self.address, 0x00, c)

        # Send a blank frame to clear any garbage
        blank = Image.new("1", (w, h), 0)
        _smbus2_display(blank, self.i2c_bus, self.address, w, h)

    # ── luma.oled backends ────────────────────────────────────────────────────

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
            device=self.spi_device, port=0,
            gpio_DC=self.spi_dc_pin, gpio_RST=self.spi_reset_pin,
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

    # ── adafruit backend ──────────────────────────────────────────────────────

    def _init_adafruit_i2c(self):
        import board, busio, adafruit_ssd1306
        i2c = busio.I2C(board.SCL, board.SDA)
        return adafruit_ssd1306.SSD1306_I2C(self.width, self.height, i2c, addr=self.address)

    def _init_adafruit_spi(self):
        import board, busio, digitalio, adafruit_ssd1306
        spi = busio.SPI(board.SCK, MOSI=board.MOSI)
        dc = digitalio.DigitalInOut(getattr(board, f"D{self.spi_dc_pin}"))
        cs = digitalio.DigitalInOut(getattr(board, f"D{self.spi_cs_pin}"))
        reset = (digitalio.DigitalInOut(getattr(board, f"D{self.spi_reset_pin}"))
                 if self.spi_reset_pin is not None else None)
        return adafruit_ssd1306.SSD1306_SPI(self.width, self.height, spi, dc, reset, cs)

    # ── Unified display methods ───────────────────────────────────────────────

    def display_image(self, image: Image.Image) -> None:
        if not self._initialized or self._display is None and not getattr(self, '_use_smbus2', False):
            return

        if self.rotation in (90, 270):
            image = image.rotate(-self.rotation, expand=True)
        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height))
        if image.mode != "1":
            image = image.convert("1")

        backend = getattr(self, '_backend', None)

        if backend == "smbus2" or getattr(self, '_use_smbus2', False):
            _smbus2_display(image, self.i2c_bus, self.address, self.width, self.height)
        elif backend == "luma":
            self._display.display(image)
        elif backend == "adafruit":
            self._display.image(image)
            self._display.show()

    def clear(self) -> None:
        blank = Image.new("1", (self.width, self.height), 0)
        self.display_image(blank)

    def set_brightness(self, level: int) -> None:
        level = max(0, min(255, level))
        backend = getattr(self, '_backend', None)
        if backend == "smbus2" or getattr(self, '_use_smbus2', False):
            try:
                import smbus2
                with smbus2.SMBus(self.i2c_bus) as bus:
                    bus.write_byte_data(self.address, 0x00, 0x81)
                    bus.write_byte_data(self.address, 0x00, level)
            except Exception:
                pass
        elif self._display is not None:
            try:
                self._display.contrast(level)
            except Exception:
                pass

"""
SSD1306 / SH1106 OLED driver.
Supports 128x64 (0.96"), 128x32 (0.91"), 64x48 (0.66"), 64x32 displays.

Uses the same library stack as the original OLED_Stats project (mklements/OLED_Stats):
  adafruit-blinka + adafruit-circuitpython-ssd1306

Rendering order:
  1. adafruit-circuitpython-ssd1306 via board.I2C()   ← same as OLED_Stats, proven working
  2. luma.oled ssd1306 via smbus2                     ← DietPi fallback (no Blinka needed)
  3. luma.oled sh1106                                 ← mislabeled module fallback
  4. Direct smbus2 framebuffer write                  ← last resort, bypasses all libs

For 4-pin I2C modules (VCC GND SDA SCL) — no RST / GPIO needed.
"""

import time
from PIL import Image
from typing import Optional
from oled_dashboard.drivers.base import OLEDDriver


# ── Direct smbus2 rendering (guaranteed fallback) ─────────────────────────────

def _pil_to_ssd1306_bytes(image: Image.Image) -> bytes:
    """Convert PIL mode-'1' image to SSD1306 native page format."""
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


def _smbus2_display(image: Image.Image, bus_num: int, addr: int,
                    width: int, height: int) -> None:
    """Write framebuffer directly via smbus2 in 32-byte chunks."""
    import smbus2
    buf = _pil_to_ssd1306_bytes(image)
    pages = (height + 7) // 8
    with smbus2.SMBus(bus_num) as bus:
        def cmd(b):
            bus.write_byte_data(addr, 0x00, b)
        cmd(0x20); cmd(0x00)                   # Horizontal addressing
        cmd(0x21); cmd(0x00); cmd(width - 1)   # Column window
        cmd(0x22); cmd(0x00); cmd(pages - 1)   # Page window
        for i in range(0, len(buf), 32):
            bus.write_i2c_block_data(addr, 0x40, list(buf[i:i + 32]))


# ── Driver ────────────────────────────────────────────────────────────────────

class SSD1306Driver(OLEDDriver):
    """
    Driver for 4-pin I2C SSD1306/SH1106 OLED displays.
    Tries adafruit stack first (same as OLED_Stats), then luma, then direct smbus2.
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
        self._backend = None
        self._display = None

        if self.interface == "i2c":

            # ── 1. adafruit-circuitpython-ssd1306 (OLED_Stats proven method) ──
            try:
                import board
                import busio
                import adafruit_ssd1306

                i2c = board.I2C()
                self._display = adafruit_ssd1306.SSD1306_I2C(
                    self.width, self.height, i2c, addr=self.address
                )
                # NOTE: We do NOT set hardware rotation here.
                # All rotation is handled in display_image() via PIL for reliability.
                # Clear like OLED_Stats does
                self._display.fill(0)
                self._display.show()
                self._backend = "adafruit"
                self._initialized = True
                print(f"[OLED] Ready: SSD1306 adafruit I2C "
                      f"(addr=0x{self.address:02X}) — same stack as OLED_Stats")
                return True
            except Exception as e:
                error_messages.append(f"adafruit board.I2C: {e}")

            # ── 2. luma.oled ssd1306 (DietPi / no-Blinka fallback) ────────────
            try:
                from luma.core.interface.serial import i2c as luma_i2c
                from luma.oled.device import ssd1306
                serial = luma_i2c(port=self.i2c_bus, address=self.address)
                self._display = ssd1306(serial, width=self.width, height=self.height)
                self._backend = "luma"
                # NOTE: No hardware rotation set — PIL rotation in display_image() handles it
                self._display.clear()
                self._initialized = True
                print(f"[OLED] Ready: SSD1306 luma.oled I2C "
                      f"(bus={self.i2c_bus}, addr=0x{self.address:02X})")
                return True
            except Exception as e:
                error_messages.append(f"luma ssd1306: {e}")

            # ── 3. luma.oled sh1106 (mislabeled module) ───────────────────────
            try:
                from luma.core.interface.serial import i2c as luma_i2c
                from luma.oled.device import sh1106
                serial = luma_i2c(port=self.i2c_bus, address=self.address)
                self._display = sh1106(serial, width=self.width, height=self.height)
                self._backend = "luma"
                # NOTE: No hardware rotation set — PIL rotation in display_image() handles it
                self._display.clear()
                self._initialized = True
                print(f"[OLED] Ready: SH1106 luma.oled I2C "
                      f"(bus={self.i2c_bus}, addr=0x{self.address:02X})")
                print(f"[OLED] NOTE: Module appears to be SH1106, not SSD1306.")
                return True
            except Exception as e:
                error_messages.append(f"luma sh1106: {e}")

            # ── 4. Direct smbus2 (no library needed beyond smbus2) ────────────
            try:
                self._smbus2_init()
                self._backend = "smbus2"
                self._initialized = True
                print(f"[OLED] Ready: SSD1306 direct smbus2 "
                      f"(bus={self.i2c_bus}, addr=0x{self.address:02X})")
                return True
            except Exception as e:
                error_messages.append(f"direct smbus2: {e}")

        elif self.interface == "spi":
            for chip_name in ("ssd1306", "sh1106"):
                try:
                    from luma.core.interface.serial import spi as luma_spi
                    serial = luma_spi(
                        device=self.spi_device, port=0,
                        gpio_DC=self.spi_dc_pin, gpio_RST=self.spi_reset_pin,
                    )
                    if chip_name == "sh1106":
                        from luma.oled.device import sh1106
                        self._display = sh1106(serial, width=self.width, height=self.height)
                    else:
                        from luma.oled.device import ssd1306
                        self._display = ssd1306(serial, width=self.width, height=self.height)
                    self._backend = "luma"
                    # NOTE: No hardware rotation — PIL rotation in display_image() handles all angles
                    self._display.clear()
                    self._initialized = True
                    print(f"[OLED] Ready: {chip_name.upper()} luma.oled SPI")
                    return True
                except Exception as e:
                    error_messages.append(f"luma SPI {chip_name}: {e}")

        # ── All failed ────────────────────────────────────────────────────────
        print(f"[OLED] *** HARDWARE INIT FAILED ***")
        for msg in error_messages:
            print(f"  • {msg}")
        print(f"[OLED] Tip: run  sudo /opt/oled-dashboard/venv/bin/python "
              f"/opt/oled-dashboard/test_display.py")
        self._initialized = False
        return False

    def _smbus2_init(self):
        import smbus2
        h = self.height
        init_cmds = [
            0xAE, 0xD5, 0x80, 0xA8, h - 1, 0xD3, 0x00, 0x40,
            0x8D, 0x14, 0x20, 0x00, 0xA1, 0xC8,
            0xDA, 0x12 if h == 64 else 0x02,
            0x81, 0xCF, 0xD9, 0xF1, 0xDB, 0x40, 0xA4, 0xA6, 0xAF,
        ]
        with smbus2.SMBus(self.i2c_bus) as bus:
            for c in init_cmds:
                bus.write_byte_data(self.address, 0x00, c)
        blank = Image.new("1", (self.width, self.height), 0)
        _smbus2_display(blank, self.i2c_bus, self.address, self.width, self.height)

    def display_image(self, image: Image.Image) -> None:
        if not self._initialized:
            return

        # PIL-level rotation for ALL angles — reliable across all backends.
        # 90/270 expand dimensions then resize back; 180 keeps same size.
        if self.rotation in (90, 180, 270):
            image = image.rotate(-self.rotation, expand=self.rotation in (90, 270))
        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height))
        if image.mode != "1":
            image = image.convert("1")

        try:
            if self._backend == "adafruit":
                self._display.image(image)
                self._display.show()
            elif self._backend == "luma":
                self._display.display(image)
            elif self._backend == "smbus2":
                _smbus2_display(image, self.i2c_bus, self.address,
                                self.width, self.height)
        except Exception as e:
            print(f"[OLED] display_image error ({self._backend}): {e}")

    def clear(self) -> None:
        blank = Image.new("1", (self.width, self.height), 0)
        self.display_image(blank)

    def set_brightness(self, level: int) -> None:
        level = max(0, min(255, level))
        try:
            if self._backend in ("adafruit", "luma") and self._display:
                self._display.contrast(level)
            elif self._backend == "smbus2":
                import smbus2
                with smbus2.SMBus(self.i2c_bus) as bus:
                    bus.write_byte_data(self.address, 0x00, 0x81)
                    bus.write_byte_data(self.address, 0x00, level)
        except Exception:
            pass

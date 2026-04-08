"""
SSD1309 OLED driver.
Supports 128x64 (2.42") displays.
The SSD1309 is register-compatible with SSD1306 for most operations.
"""

from PIL import Image
from oled_dashboard.drivers.ssd1306 import SSD1306Driver


class SSD1309Driver(SSD1306Driver):
    """Driver for SSD1309-based OLED displays.

    The SSD1309 is largely compatible with SSD1306 but supports
    larger display panels (up to 2.42").
    """

    CHIP = "SSD1309"
    SUPPORTED_DISPLAYS = {
        "128x64": {"width": 128, "height": 64, "description": '2.42" 128x64'},
    }

    # SSD1309 is register-compatible with SSD1306, so we inherit
    # all methods. The main difference is physical panel size.

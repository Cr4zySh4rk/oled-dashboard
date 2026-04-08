"""
OLED display driver abstraction layer.
Supports SSD1306, SH1106, SSD1309, SSD1322 over I2C and SPI.
"""

from oled_dashboard.drivers.base import OLEDDriver
from oled_dashboard.drivers.registry import DriverRegistry, get_driver

__all__ = ["OLEDDriver", "DriverRegistry", "get_driver"]

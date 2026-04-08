"""
Driver registry - maps chip names to driver classes and enumerates
all supported display configurations.
"""

from typing import Dict, List, Optional, Type
from oled_dashboard.drivers.base import OLEDDriver
from oled_dashboard.drivers.ssd1306 import SSD1306Driver
from oled_dashboard.drivers.sh1106 import SH1106Driver
from oled_dashboard.drivers.ssd1309 import SSD1309Driver
from oled_dashboard.drivers.ssd1322 import SSD1322Driver
from oled_dashboard.drivers.simulate import SimulatedDriver


class DriverRegistry:
    """Registry of all available OLED drivers and display configurations."""

    _drivers: Dict[str, Type[OLEDDriver]] = {
        "SSD1306": SSD1306Driver,
        "SH1106": SH1106Driver,
        "SSD1309": SSD1309Driver,
        "SSD1322": SSD1322Driver,
        "SIMULATED": SimulatedDriver,
    }

    @classmethod
    def get_driver_class(cls, chip: str) -> Optional[Type[OLEDDriver]]:
        """Get the driver class for a given chip."""
        return cls._drivers.get(chip.upper())

    @classmethod
    def list_drivers(cls) -> List[str]:
        """List all available driver chip names."""
        return [k for k in cls._drivers.keys() if k != "SIMULATED"]

    @classmethod
    def list_all_displays(cls) -> List[Dict]:
        """List all supported display configurations."""
        displays = []
        for chip, driver_cls in cls._drivers.items():
            if chip == "SIMULATED":
                continue
            for res_key, info in driver_cls.SUPPORTED_DISPLAYS.items():
                displays.append({
                    "chip": chip,
                    "resolution": res_key,
                    "width": info["width"],
                    "height": info["height"],
                    "description": info["description"],
                    "interfaces": cls._get_supported_interfaces(chip),
                })
        return displays

    @classmethod
    def _get_supported_interfaces(cls, chip: str) -> List[str]:
        """Get supported interfaces for a chip."""
        if chip == "SSD1322":
            return ["spi", "i2c"]
        return ["i2c", "spi"]

    @classmethod
    def register_driver(cls, chip: str, driver_class: Type[OLEDDriver]) -> None:
        """Register a custom driver."""
        cls._drivers[chip.upper()] = driver_class


def get_driver(
    chip: str,
    width: int,
    height: int,
    interface: str = "i2c",
    **kwargs,
) -> OLEDDriver:
    """Factory function to create a configured driver instance."""
    driver_cls = DriverRegistry.get_driver_class(chip)
    if driver_cls is None:
        raise ValueError(
            f"Unknown chip: {chip}. Available: {DriverRegistry.list_drivers()}"
        )
    return driver_cls(width=width, height=height, interface=interface, **kwargs)

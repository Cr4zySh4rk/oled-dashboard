"""
Base OLED driver abstraction.
All display drivers implement this interface.
"""

from abc import ABC, abstractmethod
from PIL import Image
from typing import Optional, Tuple


class OLEDDriver(ABC):
    """Abstract base class for OLED display drivers."""

    SUPPORTED_DISPLAYS = {}  # Subclasses populate this

    def __init__(
        self,
        width: int,
        height: int,
        interface: str = "i2c",
        address: int = 0x3C,
        rotation: int = 0,
        i2c_bus: int = 1,
        spi_device: int = 0,
        spi_dc_pin: int = 24,
        spi_reset_pin: Optional[int] = 25,
        spi_cs_pin: int = 8,
        reset_pin: Optional[int] = None,
    ):
        self.width = width
        self.height = height
        self.interface = interface
        self.address = address
        self.rotation = rotation
        self.i2c_bus = i2c_bus
        self.spi_device = spi_device
        self.spi_dc_pin = spi_dc_pin
        self.spi_reset_pin = spi_reset_pin
        self.spi_cs_pin = spi_cs_pin
        self.reset_pin = reset_pin
        self._display = None
        self._initialized = False

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the display hardware. Returns True on success."""
        pass

    @abstractmethod
    def display_image(self, image: Image.Image) -> None:
        """Display a PIL Image on the OLED."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear the display."""
        pass

    @abstractmethod
    def set_brightness(self, level: int) -> None:
        """Set display brightness/contrast (0-255)."""
        pass

    def set_rotation(self, rotation: int) -> None:
        """Set display rotation (0, 90, 180, 270)."""
        self.rotation = rotation % 360

    def get_effective_size(self) -> Tuple[int, int]:
        """Get effective display size accounting for rotation."""
        if self.rotation in (90, 270):
            return (self.height, self.width)
        return (self.width, self.height)

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def shutdown(self) -> None:
        """Cleanup and shutdown the display."""
        if self._initialized:
            try:
                self.clear()
            except Exception:
                pass
            self._initialized = False

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"width={self.width}, height={self.height}, "
            f"interface={self.interface}, rotation={self.rotation})"
        )

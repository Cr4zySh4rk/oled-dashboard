"""
Base widget class. All display widgets inherit from this.
"""

from abc import ABC, abstractmethod
from PIL import Image, ImageDraw, ImageFont
from typing import Any, Dict, Optional, Tuple


class Widget(ABC):
    """Base class for all OLED dashboard widgets."""

    # Subclasses must define these
    WIDGET_ID: str = ""
    WIDGET_NAME: str = ""
    WIDGET_CATEGORY: str = "general"  # general, system, network, storage, custom
    DEFAULT_SIZE: Tuple[int, int] = (64, 16)  # (width, height) in pixels
    MIN_SIZE: Tuple[int, int] = (32, 8)
    DESCRIPTION: str = ""
    REFRESH_INTERVAL: float = 1.0  # seconds

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: Optional[int] = None,
        height: Optional[int] = None,
        font_size: int = 12,
        font_path: Optional[str] = None,
        label: str = "",
        config: Optional[Dict[str, Any]] = None,
    ):
        self.x = x
        self.y = y
        self.width = width or self.DEFAULT_SIZE[0]
        self.height = height or self.DEFAULT_SIZE[1]
        self.font_size = font_size
        self.font_path = font_path
        self.label = label or self.WIDGET_NAME
        self.config = config or {}
        self._last_value: Any = None
        self._font: Optional[ImageFont.FreeTypeFont] = None

    def get_font(self) -> ImageFont.FreeTypeFont:
        """Get the configured font, with fallback."""
        if self._font is None:
            try:
                path = self.font_path or "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
                self._font = ImageFont.truetype(path, self.font_size)
            except (IOError, OSError):
                try:
                    self._font = ImageFont.truetype("PixelOperator.ttf", self.font_size)
                except (IOError, OSError):
                    self._font = ImageFont.load_default()
        return self._font

    @abstractmethod
    def fetch_data(self) -> Any:
        """Fetch the current data for this widget. Must be implemented."""
        pass

    @abstractmethod
    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        """Render the widget onto the given ImageDraw context."""
        pass

    def update(self) -> Any:
        """Fetch data and store it."""
        self._last_value = self.fetch_data()
        return self._last_value

    def draw(self, draw: ImageDraw.ImageDraw) -> None:
        """Full update cycle: fetch data and render."""
        data = self.update()
        self.render(draw, data)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize widget configuration to dict."""
        return {
            "widget_id": self.WIDGET_ID,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "font_size": self.font_size,
            "font_path": self.font_path,
            "label": self.label,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Widget":
        """Deserialize widget from dict."""
        return cls(
            x=data.get("x", 0),
            y=data.get("y", 0),
            width=data.get("width"),
            height=data.get("height"),
            font_size=data.get("font_size", 12),
            font_path=data.get("font_path"),
            label=data.get("label", ""),
            config=data.get("config", {}),
        )

    def get_metadata(self) -> Dict[str, Any]:
        """Get widget metadata for the web UI."""
        return {
            "widget_id": self.WIDGET_ID,
            "name": self.WIDGET_NAME,
            "category": self.WIDGET_CATEGORY,
            "description": self.DESCRIPTION,
            "default_size": list(self.DEFAULT_SIZE),
            "min_size": list(self.MIN_SIZE),
            "refresh_interval": self.REFRESH_INTERVAL,
        }

"""
Static content widgets: Static Text, Horizontal Line, Box/Frame, Custom Icon.
"""

from typing import Any, Dict
from PIL import ImageDraw
from oled_dashboard.widgets.base import Widget


class StaticTextWidget(Widget):
    """Displays static custom text."""

    WIDGET_ID = "static_text"
    WIDGET_NAME = "Static Text"
    WIDGET_CATEGORY = "general"
    DEFAULT_SIZE = (80, 12)
    MIN_SIZE = (16, 8)
    DESCRIPTION = "Custom static text label"
    REFRESH_INTERVAL = 999999  # Basically never refresh

    def fetch_data(self) -> Dict[str, Any]:
        return {"text": self.config.get("text", self.label)}

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font = self.get_font()
        draw.text((self.x, self.y), data["text"], font=font, fill=255)


class HLineWidget(Widget):
    """Draws a horizontal line."""

    WIDGET_ID = "hline"
    WIDGET_NAME = "Horizontal Line"
    WIDGET_CATEGORY = "general"
    DEFAULT_SIZE = (128, 1)
    MIN_SIZE = (8, 1)
    DESCRIPTION = "Horizontal separator line"
    REFRESH_INTERVAL = 999999

    def fetch_data(self) -> Dict[str, Any]:
        return {}

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        y = self.y + self.height // 2
        draw.line([(self.x, y), (self.x + self.width, y)], fill=255, width=1)


class VLineWidget(Widget):
    """Draws a vertical line."""

    WIDGET_ID = "vline"
    WIDGET_NAME = "Vertical Line"
    WIDGET_CATEGORY = "general"
    DEFAULT_SIZE = (1, 64)
    MIN_SIZE = (1, 8)
    DESCRIPTION = "Vertical separator line"
    REFRESH_INTERVAL = 999999

    def fetch_data(self) -> Dict[str, Any]:
        return {}

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        x = self.x + self.width // 2
        draw.line([(x, self.y), (x, self.y + self.height)], fill=255, width=1)


class BoxWidget(Widget):
    """Draws a rectangular box/frame."""

    WIDGET_ID = "box"
    WIDGET_NAME = "Box Frame"
    WIDGET_CATEGORY = "general"
    DEFAULT_SIZE = (64, 32)
    MIN_SIZE = (8, 8)
    DESCRIPTION = "Rectangular frame/border"
    REFRESH_INTERVAL = 999999

    def fetch_data(self) -> Dict[str, Any]:
        return {}

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        filled = self.config.get("filled", False)
        if filled:
            draw.rectangle(
                [self.x, self.y, self.x + self.width, self.y + self.height],
                outline=255, fill=255,
            )
        else:
            draw.rectangle(
                [self.x, self.y, self.x + self.width, self.y + self.height],
                outline=255, fill=0,
            )


class ProgressBarWidget(Widget):
    """A generic progress bar that can be bound to any data source."""

    WIDGET_ID = "progress_bar"
    WIDGET_NAME = "Progress Bar"
    WIDGET_CATEGORY = "general"
    DEFAULT_SIZE = (100, 8)
    MIN_SIZE = (20, 4)
    DESCRIPTION = "Customizable progress bar (0-100%)"
    REFRESH_INTERVAL = 2.0

    def fetch_data(self) -> Dict[str, Any]:
        return {"value": self.config.get("value", 50)}

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        val = max(0, min(100, data.get("value", 0)))
        # Outer rectangle
        draw.rectangle(
            [self.x, self.y, self.x + self.width, self.y + self.height],
            outline=255,
        )
        # Fill
        fill_w = int((self.width - 2) * val / 100)
        if fill_w > 0:
            draw.rectangle(
                [self.x + 1, self.y + 1, self.x + 1 + fill_w, self.y + self.height - 1],
                fill=255,
            )


class DateTimeWidget(Widget):
    """Displays the current date and/or time."""

    WIDGET_ID = "datetime"
    WIDGET_NAME = "Date/Time"
    WIDGET_CATEGORY = "general"
    DEFAULT_SIZE = (80, 12)
    MIN_SIZE = (40, 10)
    DESCRIPTION = "Current date and/or time"
    REFRESH_INTERVAL = 1.0

    def fetch_data(self) -> Dict[str, Any]:
        from datetime import datetime
        now = datetime.now()
        return {
            "time": now.strftime("%H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "short_time": now.strftime("%H:%M"),
            "short_date": now.strftime("%m/%d"),
        }

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font = self.get_font()
        fmt = self.config.get("format", "time")
        if fmt == "date":
            text = data["date"]
        elif fmt == "datetime":
            text = f"{data['short_date']} {data['short_time']}"
        elif fmt == "short_time":
            text = data["short_time"]
        else:
            text = data["time"]
        draw.text((self.x, self.y), text, font=font, fill=255)

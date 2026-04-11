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
    """Displays the current date and/or time.

    Supported formats:
      time          → 13:45:30   (24h with seconds, default)
      short_time    → 13:45      (24h, no seconds)
      time_12h      → 1:45 PM    (12h, no seconds)
      time_12h_full → 1:45:30 PM (12h with seconds)
      date          → 2024-01-25
      date_short    → 01/25
      date_long     → Thu Jan 25
      datetime      → 01/25 13:45
      datetime_12h  → 01/25 1:45 PM
    """

    WIDGET_ID = "datetime"
    WIDGET_NAME = "Date/Time"
    WIDGET_CATEGORY = "general"
    DEFAULT_SIZE = (80, 12)
    MIN_SIZE = (40, 10)
    DESCRIPTION = "Current date and/or time (12h/24h, with or without seconds)"
    REFRESH_INTERVAL = 1.0

    def fetch_data(self) -> Dict[str, Any]:
        from datetime import datetime
        now = datetime.now()
        hour12 = now.strftime("%-I") if hasattr(now, 'strftime') else str(int(now.strftime("%I")))
        # Remove leading zero from 12-hour format on Windows-friendly way
        try:
            hour12 = str(int(now.strftime("%I")))
        except Exception:
            hour12 = now.strftime("%I").lstrip("0") or "12"
        ampm = now.strftime("%p")   # AM or PM
        return {
            "time":          now.strftime("%H:%M:%S"),
            "short_time":    now.strftime("%H:%M"),
            "time_12h":      f"{hour12}:{now.strftime('%M')} {ampm}",
            "time_12h_full": f"{hour12}:{now.strftime('%M:%S')} {ampm}",
            "date":          now.strftime("%Y-%m-%d"),
            "date_short":    now.strftime("%m/%d"),
            "date_long":     now.strftime("%a %b %d"),
            "datetime":      f"{now.strftime('%m/%d')} {now.strftime('%H:%M')}",
            "datetime_12h":  f"{now.strftime('%m/%d')} {hour12}:{now.strftime('%M')} {ampm}",
        }

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font = self.get_font()
        fmt = self.config.get("format", "time")
        text = data.get(fmt, data["time"])
        draw.text((self.x, self.y), text, font=font, fill=255)

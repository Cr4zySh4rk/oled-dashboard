"""
Storage monitoring widgets: Disk Space, Disk I/O.
"""

import subprocess
from typing import Any, Dict
from PIL import ImageDraw
from oled_dashboard.widgets.base import Widget


def _measure_text(font, text: str) -> int:
    """Return pixel width of *text* rendered with *font* (PIL ≥9.2 + older)."""
    try:
        return int(font.getlength(text))
    except AttributeError:
        try:
            return font.getsize(text)[0]
        except Exception:
            return len(text) * 6


def _draw_widget_icon(draw: ImageDraw.ImageDraw, widget, icon_size: int,
                      line_y: int = None, line_h: int = None) -> int:
    """Draw the widget's icon if enabled. Returns text_x offset.

    *line_y* / *line_h*: vertically centre icon within a specific line rather
    than the full widget (useful for top line of multi-line layouts).
    """
    show_icon = widget.config.get("show_icon", True)
    if show_icon and widget.width > icon_size + 20:
        from oled_dashboard.icons import draw_icon, icon_width as _iw
        ref_y = line_y if line_y is not None else widget.y
        ref_h = line_h if line_h is not None else widget.height
        icon_y = ref_y + max(0, (ref_h - icon_size) // 2)
        draw_icon(draw, widget.WIDGET_ID, widget.x, icon_y, size=icon_size)
        return widget.x + _iw(icon_size)
    return widget.x


class DiskSpaceWidget(Widget):
    """Displays disk space usage for a mount point."""

    WIDGET_ID = "disk_space"
    WIDGET_NAME = "Disk Space"
    WIDGET_CATEGORY = "storage"
    DEFAULT_SIZE = (128, 16)
    MIN_SIZE = (48, 10)
    DESCRIPTION = "Disk space usage for a mount point"
    REFRESH_INTERVAL = 10.0

    # Supported unit strings → (divisor, label suffix)
    _UNITS = {
        "MB": (1048576,    "M"),
        "GB": (1073741824, "G"),
        "TB": (1099511627776, "T"),
    }

    def fetch_data(self) -> Dict[str, Any]:
        mount = self.config.get("mount_point", "/")
        try:
            import shutil
            usage = shutil.disk_usage(mount)
            total_bytes = usage.total
            used_bytes  = usage.used
            free_bytes  = usage.free
            percent = (used_bytes / total_bytes * 100) if total_bytes > 0 else 0
            return {
                "total_bytes": total_bytes,
                "used_bytes":  used_bytes,
                "free_bytes":  free_bytes,
                "percent":     round(percent, 1),
                "mount":       mount,
            }
        except Exception:
            return {
                "total_bytes": 0, "used_bytes": 0, "free_bytes": 0,
                "percent": 0, "mount": mount,
            }

    def _format_size(self, bytes_val: float) -> str:
        """Format a byte count according to the configured unit."""
        unit = self.config.get("units", "GB").upper()
        divisor, suffix = self._UNITS.get(unit, self._UNITS["GB"])
        value = bytes_val / divisor
        # Pick precision: 2 decimals for < 1, 1 decimal for 1–99, 0 for ≥ 100
        if value >= 100:
            fmt = f"{value:.0f}"
        elif value >= 1:
            fmt = f"{value:.1f}"
        else:
            fmt = f"{value:.2f}"
        return f"{fmt}{suffix}"

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font = self.get_font()
        pct = data["percent"]
        pct_text = f"{pct:.0f}%"
        used_str  = self._format_size(data["used_bytes"])
        total_str = self._format_size(data["total_bytes"])
        disk_text = f"Disk:{used_str}/{total_str}"

        if self.height >= 18:
            # Two-line combined view: text line + bar+% line
            first_h   = self.font_size + 2
            icon_size = min(first_h - 2, 12)
            tx = _draw_widget_icon(draw, self, icon_size,
                                   line_y=self.y, line_h=first_h)
            draw.text((tx, self.y), disk_text, font=font, fill=255)
            # Bar + % on second line
            bar_y = self.y + first_h
            bar_h = max(3, self.height - first_h - 1)
            pct_w = _measure_text(font, pct_text) + 2
            bar_w = self.width - pct_w - 1
            draw.rectangle([self.x, bar_y, self.x + bar_w, bar_y + bar_h], outline=255)
            fill_w = int((bar_w - 2) * pct / 100)
            if fill_w > 0:
                draw.rectangle(
                    [self.x + 1, bar_y + 1, self.x + 1 + fill_w, bar_y + bar_h - 1],
                    fill=255,
                )
            draw.text((self.x + bar_w + 2, bar_y), pct_text, font=font, fill=255)
        else:
            # Single line
            icon_size = min(self.height - 2, 14)
            tx = _draw_widget_icon(draw, self, icon_size)
            draw.text((tx, self.y), disk_text, font=font, fill=255)


class DiskIOWidget(Widget):
    """Displays disk I/O statistics."""

    WIDGET_ID = "disk_io"
    WIDGET_NAME = "Disk I/O"
    WIDGET_CATEGORY = "storage"
    DEFAULT_SIZE = (128, 12)
    MIN_SIZE = (64, 10)
    DESCRIPTION = "Disk read/write activity"
    REFRESH_INTERVAL = 2.0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._prev_stats = None

    def fetch_data(self) -> Dict[str, Any]:
        try:
            with open("/proc/diskstats", "r") as f:
                lines = f.readlines()

            device = self.config.get("device", "")
            if not device:
                # Find the root device
                for line in lines:
                    parts = line.split()
                    name = parts[2]
                    if name in ("sda", "mmcblk0", "nvme0n1", "vda"):
                        device = name
                        break
                if not device:
                    device = "sda"

            for line in lines:
                parts = line.split()
                if parts[2] == device:
                    reads = int(parts[5])   # sectors read
                    writes = int(parts[9])  # sectors written

                    prev = self._prev_stats
                    self._prev_stats = {"reads": reads, "writes": writes}

                    if prev is None:
                        return {"read_kb": 0, "write_kb": 0}

                    # Sectors are 512 bytes
                    read_kb = (reads - prev["reads"]) * 512 / 1024
                    write_kb = (writes - prev["writes"]) * 512 / 1024
                    return {
                        "read_kb": max(0, round(read_kb, 1)),
                        "write_kb": max(0, round(write_kb, 1)),
                    }

            return {"read_kb": 0, "write_kb": 0}
        except Exception:
            return {"read_kb": 0, "write_kb": 0}

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font = self.get_font()
        icon_size = min(self.height - 2, 10)
        tx = _draw_widget_icon(draw, self, icon_size)
        text = f"R:{data['read_kb']}K W:{data['write_kb']}K"
        draw.text((tx, self.y), text, font=font, fill=255)

"""
Storage monitoring widgets: Disk Space, Disk I/O.
"""

import subprocess
from typing import Any, Dict
from PIL import ImageDraw
from oled_dashboard.widgets.base import Widget


def _draw_widget_icon(draw: ImageDraw.ImageDraw, widget, icon_size: int) -> int:
    """Draw the widget's icon if enabled. Returns text_x offset."""
    show_icon = widget.config.get("show_icon", True)
    if show_icon and widget.width > icon_size + 20:
        from oled_dashboard.icons import draw_icon, icon_width as _iw
        icon_y = widget.y + max(0, (widget.height - icon_size) // 2)
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

    def fetch_data(self) -> Dict[str, Any]:
        mount = self.config.get("mount_point", "/")
        try:
            import shutil
            usage = shutil.disk_usage(mount)
            total_gb = usage.total / 1073741824
            used_gb = usage.used / 1073741824
            free_gb = usage.free / 1073741824
            percent = (usage.used / usage.total * 100) if usage.total > 0 else 0
            return {
                "total_gb": round(total_gb, 1),
                "used_gb": round(used_gb, 1),
                "free_gb": round(free_gb, 1),
                "percent": round(percent, 1),
                "mount": mount,
            }
        except Exception:
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0, "mount": mount}

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font = self.get_font()
        pct = data["percent"]
        show_bar = self.config.get("show_bar", False)
        icon_size = min(self.height - 2, 10)
        tx = _draw_widget_icon(draw, self, icon_size)
        avail_w = self.width - (tx - self.x)

        if show_bar and self.height >= 14:
            draw.text((tx, self.y), "Disk", font=font, fill=255)
            pct_text = f"{pct:.0f}%"
            draw.text((tx + avail_w - len(pct_text) * 6, self.y), pct_text, font=font, fill=255)
            bar_y = self.y + self.font_size + 1
            bar_h = max(4, self.height - self.font_size - 2)
            draw.rectangle([tx, bar_y, tx + avail_w, bar_y + bar_h], outline=255)
            fill_w = int((avail_w - 2) * pct / 100)
            if fill_w > 0:
                draw.rectangle(
                    [tx + 1, bar_y + 1, tx + 1 + fill_w, bar_y + bar_h - 1],
                    fill=255,
                )
        else:
            text = f"Disk: {data['used_gb']}/{data['total_gb']}GB {pct:.0f}%"
            draw.text((tx, self.y), text, font=font, fill=255)


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

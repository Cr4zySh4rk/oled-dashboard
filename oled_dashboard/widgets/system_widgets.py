"""
System monitoring widgets: CPU, RAM, Swap, Temperature, Uptime, Load Average.
"""

import os
import time
import subprocess
from typing import Any, Dict, Optional, Tuple
from PIL import ImageDraw
from oled_dashboard.widgets.base import Widget


def _icon_offset(widget, icon_size: int) -> Tuple[int, int]:
    """Return (text_x, icon_y) for a widget with icon support."""
    show_icon = widget.config.get("show_icon", True)
    if show_icon and widget.width > icon_size + 20:
        from oled_dashboard.icons import draw_icon, icon_width as _iw
        icon_y = widget.y + max(0, (widget.height - icon_size) // 2)
        draw_icon(None, widget.WIDGET_ID, widget.x, icon_y, size=icon_size)
        return widget.x + _iw(icon_size), icon_y
    return widget.x, widget.y


def _draw_widget_icon(draw: ImageDraw.ImageDraw, widget, icon_size: int):
    """Draw the widget's icon if enabled. Returns text_x offset."""
    show_icon = widget.config.get("show_icon", True)
    if show_icon and widget.width > icon_size + 20:
        from oled_dashboard.icons import draw_icon, icon_width as _iw
        icon_y = widget.y + max(0, (widget.height - icon_size) // 2)
        draw_icon(draw, widget.WIDGET_ID, widget.x, icon_y, size=icon_size)
        return widget.x + _iw(icon_size)
    return widget.x


class CPUUsageWidget(Widget):
    """Displays current CPU usage percentage."""

    WIDGET_ID = "cpu_usage"
    WIDGET_NAME = "CPU Usage"
    WIDGET_CATEGORY = "system"
    DEFAULT_SIZE = (64, 16)
    MIN_SIZE = (40, 10)
    DESCRIPTION = "Real-time CPU usage percentage"
    REFRESH_INTERVAL = 1.0

    def fetch_data(self) -> Dict[str, Any]:
        try:
            with open("/proc/stat", "r") as f:
                line = f.readline()
            parts = line.split()
            idle = int(parts[4])
            total = sum(int(p) for p in parts[1:])

            prev = getattr(self, "_prev_cpu", None)
            self._prev_cpu = (idle, total)

            if prev is None:
                return {"percent": 0.0}

            prev_idle, prev_total = prev
            diff_idle = idle - prev_idle
            diff_total = total - prev_total
            if diff_total == 0:
                return {"percent": 0.0}
            usage = (1.0 - diff_idle / diff_total) * 100.0
            return {"percent": round(usage, 1)}
        except Exception:
            try:
                out = subprocess.check_output(
                    "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'",
                    shell=True, timeout=2
                ).decode().strip()
                return {"percent": float(out)}
            except Exception:
                return {"percent": 0.0}

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font = self.get_font()
        show_bar = self.config.get("show_bar", True)
        pct = data.get("percent", 0)
        icon_size = min(self.height - 2, 10)
        tx = _draw_widget_icon(draw, self, icon_size)
        avail_w = self.width - (tx - self.x)

        if show_bar and self.height >= 14:
            draw.text((tx, self.y), "CPU", font=font, fill=255)
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
            draw.text((tx, self.y), f"CPU: {pct:.1f}%", font=font, fill=255)


class RAMUsageWidget(Widget):
    """Displays RAM usage."""

    WIDGET_ID = "ram_usage"
    WIDGET_NAME = "RAM Usage"
    WIDGET_CATEGORY = "system"
    DEFAULT_SIZE = (128, 16)
    MIN_SIZE = (48, 10)
    DESCRIPTION = "Memory usage with used/total and percentage"
    REFRESH_INTERVAL = 2.0

    def fetch_data(self) -> Dict[str, Any]:
        try:
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()
            info = {}
            for line in lines:
                parts = line.split()
                key = parts[0].rstrip(":")
                info[key] = int(parts[1])  # in kB

            total = info.get("MemTotal", 0)
            available = info.get("MemAvailable", 0)
            used = total - available
            percent = (used / total * 100) if total > 0 else 0

            return {
                "used_mb": round(used / 1024),
                "total_mb": round(total / 1024),
                "used_gb": round(used / 1048576, 1),
                "total_gb": round(total / 1048576, 1),
                "percent": round(percent, 1),
            }
        except Exception:
            return {"used_mb": 0, "total_mb": 0, "used_gb": 0, "total_gb": 0, "percent": 0}

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font = self.get_font()
        fmt = self.config.get("format", "compact")
        pct = data.get("percent", 0)
        icon_size = min(self.height - 2, 10)
        tx = _draw_widget_icon(draw, self, icon_size)
        avail_w = self.width - (tx - self.x)

        if fmt == "bar" and self.height >= 14:
            draw.text((tx, self.y), "RAM", font=font, fill=255)
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
            text = f"Mem: {data['used_gb']}/{data['total_gb']}GB {pct:.0f}%"
            draw.text((tx, self.y), text, font=font, fill=255)


class SwapUsageWidget(Widget):
    """Displays swap usage."""

    WIDGET_ID = "swap_usage"
    WIDGET_NAME = "Swap Usage"
    WIDGET_CATEGORY = "system"
    DEFAULT_SIZE = (128, 12)
    MIN_SIZE = (48, 10)
    DESCRIPTION = "Swap memory usage"
    REFRESH_INTERVAL = 5.0

    def fetch_data(self) -> Dict[str, Any]:
        try:
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()
            info = {}
            for line in lines:
                parts = line.split()
                info[parts[0].rstrip(":")] = int(parts[1])

            total = info.get("SwapTotal", 0)
            free = info.get("SwapFree", 0)
            used = total - free
            percent = (used / total * 100) if total > 0 else 0

            return {
                "used_mb": round(used / 1024),
                "total_mb": round(total / 1024),
                "percent": round(percent, 1),
            }
        except Exception:
            return {"used_mb": 0, "total_mb": 0, "percent": 0}

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font = self.get_font()
        icon_size = min(self.height - 2, 10)
        tx = _draw_widget_icon(draw, self, icon_size)
        text = f"Swap: {data['used_mb']}/{data['total_mb']}MB {data['percent']:.0f}%"
        draw.text((tx, self.y), text, font=font, fill=255)


class TemperatureWidget(Widget):
    """Displays CPU temperature."""

    WIDGET_ID = "temperature"
    WIDGET_NAME = "CPU Temp"
    WIDGET_CATEGORY = "system"
    DEFAULT_SIZE = (48, 12)
    MIN_SIZE = (32, 10)
    DESCRIPTION = "CPU temperature reading"
    REFRESH_INTERVAL = 2.0

    def fetch_data(self) -> Dict[str, Any]:
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = int(f.read().strip()) / 1000.0
            return {"temp_c": round(temp, 1), "temp_f": round(temp * 9 / 5 + 32, 1)}
        except Exception:
            return {"temp_c": 0, "temp_f": 0}

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font = self.get_font()
        unit = self.config.get("unit", "C")
        icon_size = min(self.height - 2, 10)
        tx = _draw_widget_icon(draw, self, icon_size)
        if unit == "F":
            text = f"{data['temp_f']:.1f}°F"
        else:
            text = f"{data['temp_c']:.1f}°C"
        draw.text((tx, self.y), text, font=font, fill=255)


class UptimeWidget(Widget):
    """Displays system uptime."""

    WIDGET_ID = "uptime"
    WIDGET_NAME = "Uptime"
    WIDGET_CATEGORY = "system"
    DEFAULT_SIZE = (80, 12)
    MIN_SIZE = (48, 10)
    DESCRIPTION = "System uptime since last boot"
    REFRESH_INTERVAL = 10.0

    def fetch_data(self) -> Dict[str, Any]:
        try:
            with open("/proc/uptime", "r") as f:
                uptime_secs = float(f.read().split()[0])
            days = int(uptime_secs // 86400)
            hours = int((uptime_secs % 86400) // 3600)
            minutes = int((uptime_secs % 3600) // 60)
            return {"days": days, "hours": hours, "minutes": minutes, "total_seconds": uptime_secs}
        except Exception:
            return {"days": 0, "hours": 0, "minutes": 0, "total_seconds": 0}

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font = self.get_font()
        d, h, m = data["days"], data["hours"], data["minutes"]
        icon_size = min(self.height - 2, 10)
        tx = _draw_widget_icon(draw, self, icon_size)
        if d > 0:
            text = f"Up: {d}d {h}h {m}m"
        elif h > 0:
            text = f"Up: {h}h {m}m"
        else:
            text = f"Up: {m}m"
        draw.text((tx, self.y), text, font=font, fill=255)


class LoadAverageWidget(Widget):
    """Displays system load average."""

    WIDGET_ID = "load_avg"
    WIDGET_NAME = "Load Average"
    WIDGET_CATEGORY = "system"
    DEFAULT_SIZE = (100, 12)
    MIN_SIZE = (48, 10)
    DESCRIPTION = "1/5/15 minute load averages"
    REFRESH_INTERVAL = 5.0

    def fetch_data(self) -> Dict[str, Any]:
        try:
            load1, load5, load15 = os.getloadavg()
            return {
                "load1": round(load1, 2),
                "load5": round(load5, 2),
                "load15": round(load15, 2),
            }
        except Exception:
            return {"load1": 0, "load5": 0, "load15": 0}

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font = self.get_font()
        fmt = self.config.get("format", "all")
        icon_size = min(self.height - 2, 10)
        tx = _draw_widget_icon(draw, self, icon_size)
        if fmt == "1min":
            text = f"Load: {data['load1']:.2f}"
        else:
            text = f"Load: {data['load1']:.1f} {data['load5']:.1f} {data['load15']:.1f}"
        draw.text((tx, self.y), text, font=font, fill=255)


class HostnameWidget(Widget):
    """Displays the system hostname."""

    WIDGET_ID = "hostname"
    WIDGET_NAME = "Hostname"
    WIDGET_CATEGORY = "system"
    DEFAULT_SIZE = (100, 12)
    MIN_SIZE = (40, 10)
    DESCRIPTION = "System hostname"
    REFRESH_INTERVAL = 60.0

    def fetch_data(self) -> Dict[str, Any]:
        try:
            import socket
            return {"hostname": socket.gethostname()}
        except Exception:
            return {"hostname": "unknown"}

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font = self.get_font()
        icon_size = min(self.height - 2, 10)
        tx = _draw_widget_icon(draw, self, icon_size)
        draw.text((tx, self.y), data["hostname"], font=font, fill=255)

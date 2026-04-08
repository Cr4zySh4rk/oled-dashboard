"""
Network monitoring widgets: IP Address, Network Speed, Network Usage.
"""

import os
import time
import subprocess
import socket
from typing import Any, Dict, Optional
from PIL import ImageDraw
from oled_dashboard.widgets.base import Widget


class IPAddressWidget(Widget):
    """Displays the system's IP address."""

    WIDGET_ID = "ip_address"
    WIDGET_NAME = "IP Address"
    WIDGET_CATEGORY = "network"
    DEFAULT_SIZE = (128, 12)
    MIN_SIZE = (64, 10)
    DESCRIPTION = "Current IP address of the system"
    REFRESH_INTERVAL = 10.0

    def fetch_data(self) -> Dict[str, Any]:
        try:
            iface = self.config.get("interface", "")
            if iface:
                out = subprocess.check_output(
                    f"ip -4 addr show {iface} | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){{3}}'",
                    shell=True, timeout=2
                ).decode().strip().split("\n")[0]
                return {"ip": out, "interface": iface}

            # Auto-detect
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            finally:
                s.close()
            return {"ip": ip, "interface": "auto"}
        except Exception:
            try:
                out = subprocess.check_output(
                    "hostname -I | cut -d' ' -f1", shell=True, timeout=2
                ).decode().strip()
                return {"ip": out or "No IP", "interface": "auto"}
            except Exception:
                return {"ip": "No IP", "interface": "unknown"}

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font = self.get_font()
        show_label = self.config.get("show_label", True)
        if show_label:
            draw.text((self.x, self.y), f"IP: {data['ip']}", font=font, fill=255)
        else:
            draw.text((self.x, self.y), data["ip"], font=font, fill=255)


class NetworkSpeedWidget(Widget):
    """Displays current network upload/download speeds."""

    WIDGET_ID = "net_speed"
    WIDGET_NAME = "Net Speed"
    WIDGET_CATEGORY = "network"
    DEFAULT_SIZE = (128, 24)
    MIN_SIZE = (64, 12)
    DESCRIPTION = "Real-time network upload/download speeds"
    REFRESH_INTERVAL = 1.0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._prev_stats = None
        self._prev_time = None

    def _read_net_stats(self, iface: str) -> Optional[Dict[str, int]]:
        """Read bytes received/transmitted for an interface."""
        try:
            rx_path = f"/sys/class/net/{iface}/statistics/rx_bytes"
            tx_path = f"/sys/class/net/{iface}/statistics/tx_bytes"
            with open(rx_path) as f:
                rx = int(f.read().strip())
            with open(tx_path) as f:
                tx = int(f.read().strip())
            return {"rx": rx, "tx": tx}
        except Exception:
            return None

    def _detect_interface(self) -> str:
        """Auto-detect the primary network interface."""
        for iface in ["eth0", "wlan0", "enp0s3", "ens3"]:
            if os.path.exists(f"/sys/class/net/{iface}"):
                return iface
        try:
            ifaces = os.listdir("/sys/class/net/")
            for iface in ifaces:
                if iface != "lo":
                    return iface
        except Exception:
            pass
        return "eth0"

    def fetch_data(self) -> Dict[str, Any]:
        iface = self.config.get("interface", "") or self._detect_interface()
        stats = self._read_net_stats(iface)
        now = time.time()

        if stats is None or self._prev_stats is None or self._prev_time is None:
            self._prev_stats = stats
            self._prev_time = now
            return {"rx_speed": 0, "tx_speed": 0, "interface": iface}

        dt = now - self._prev_time
        if dt <= 0:
            dt = 1

        rx_speed = (stats["rx"] - self._prev_stats["rx"]) / dt
        tx_speed = (stats["tx"] - self._prev_stats["tx"]) / dt

        self._prev_stats = stats
        self._prev_time = now

        return {
            "rx_speed": rx_speed,
            "tx_speed": tx_speed,
            "interface": iface,
        }

    @staticmethod
    def _format_speed(bps: float) -> str:
        """Format bytes/sec to human readable."""
        if bps >= 1048576:
            return f"{bps / 1048576:.1f} MB/s"
        elif bps >= 1024:
            return f"{bps / 1024:.1f} KB/s"
        else:
            return f"{bps:.0f} B/s"

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font = self.get_font()
        rx = self._format_speed(data["rx_speed"])
        tx = self._format_speed(data["tx_speed"])
        iface = data["interface"]

        if self.height >= 24:
            draw.text((self.x, self.y), f"{iface}:", font=font, fill=255)
            draw.text((self.x, self.y + self.font_size + 1), f"↓{rx} ↑{tx}", font=font, fill=255)
        else:
            draw.text((self.x, self.y), f"↓{rx} ↑{tx}", font=font, fill=255)


class NetworkUsageWidget(Widget):
    """Displays total network data usage since boot."""

    WIDGET_ID = "net_usage"
    WIDGET_NAME = "Net Usage"
    WIDGET_CATEGORY = "network"
    DEFAULT_SIZE = (128, 12)
    MIN_SIZE = (64, 10)
    DESCRIPTION = "Total network data transferred since boot"
    REFRESH_INTERVAL = 5.0

    def fetch_data(self) -> Dict[str, Any]:
        iface = self.config.get("interface", "")
        try:
            if not iface:
                for candidate in ["eth0", "wlan0", "enp0s3"]:
                    if os.path.exists(f"/sys/class/net/{candidate}"):
                        iface = candidate
                        break

            rx_path = f"/sys/class/net/{iface}/statistics/rx_bytes"
            tx_path = f"/sys/class/net/{iface}/statistics/tx_bytes"
            with open(rx_path) as f:
                rx = int(f.read().strip())
            with open(tx_path) as f:
                tx = int(f.read().strip())

            return {
                "rx_gb": round(rx / 1073741824, 2),
                "tx_gb": round(tx / 1073741824, 2),
                "interface": iface,
            }
        except Exception:
            return {"rx_gb": 0, "tx_gb": 0, "interface": iface or "unknown"}

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font = self.get_font()
        text = f"↓{data['rx_gb']}G ↑{data['tx_gb']}G"
        draw.text((self.x, self.y), text, font=font, fill=255)

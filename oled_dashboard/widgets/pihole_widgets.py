"""
Pi-hole monitoring widgets.

These widgets are only registered when Pi-hole is detected on the system
(via /etc/pihole directory, the pihole binary, or a reachable local API).

Supports both Pi-hole v6 API  (/api/stats/summary)
         and Pi-hole v5 API  (/admin/api.php?summaryRaw).
"""

import os
import time
import subprocess
from typing import Any, Dict, Optional
from PIL import ImageDraw
from oled_dashboard.widgets.base import Widget


# ── Detection ──────────────────────────────────────────────────────────────

def is_pihole_available() -> bool:
    """Return True if Pi-hole appears to be installed on this system."""
    # Fastest check: config directory
    if os.path.isdir("/etc/pihole"):
        return True
    # Fallback: binary in PATH
    try:
        subprocess.run(
            ["pihole", "version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return True
    except Exception:
        pass
    return False


# ── Shared API helper ───────────────────────────────────────────────────────

# Simple module-level cache: (timestamp, data_dict)
_pihole_cache: Dict[str, Any] = {}
_CACHE_TTL = 10.0  # seconds


def _fetch_pihole_data(api_key: str = "") -> Dict[str, Any]:
    """
    Fetch summary stats from the Pi-hole API.

    Tries v6 first (/api/stats/summary), then falls back to v5
    (/admin/api.php?summaryRaw).  Results are cached for _CACHE_TTL seconds
    so multiple widgets on the same page share one network request.
    """
    now = time.time()
    if _pihole_cache.get("ts", 0) + _CACHE_TTL > now:
        return _pihole_cache.get("data", _empty_data())

    data = _empty_data()
    try:
        import requests

        # ── Pi-hole v6 API ─────────────────────────────────────────────
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        r = requests.get(
            "http://localhost/api/stats/summary",
            headers=headers,
            timeout=2,
        )
        if r.status_code == 200:
            j = r.json()
            queries    = j.get("queries",  {})
            clients_d  = j.get("clients",  {})
            data = {
                "queries_total":   int(queries.get("total",   0)),
                "queries_blocked": int(queries.get("blocked", 0)),
                "percent_blocked": float(queries.get("percent_blocked", 0)),
                "clients":         int(clients_d.get("total", 0)),
                "status":          j.get("status", {}).get("dns", {}).get("status", "unknown"),
                "api_version":     6,
            }
        else:
            raise ValueError(f"v6 status {r.status_code}")

    except Exception:
        # ── Pi-hole v5 API fallback ───────────────────────────────────
        try:
            import requests
            params = {"summaryRaw": "", "auth": api_key} if api_key else {"summaryRaw": ""}
            r = requests.get(
                "http://localhost/admin/api.php",
                params=params,
                timeout=2,
            )
            j = r.json()
            total   = int(j.get("dns_queries_today",     0))
            blocked = int(j.get("ads_blocked_today",     0))
            pct     = float(j.get("ads_percentage_today", 0))
            data = {
                "queries_total":   total,
                "queries_blocked": blocked,
                "percent_blocked": pct,
                "clients":         int(j.get("unique_clients", 0)),
                "status":          j.get("status", "unknown"),
                "api_version":     5,
            }
        except Exception:
            data = _empty_data()

    _pihole_cache["ts"]   = now
    _pihole_cache["data"] = data
    return data


def _empty_data() -> Dict[str, Any]:
    return {
        "queries_total":   0,
        "queries_blocked": 0,
        "percent_blocked": 0.0,
        "clients":         0,
        "status":          "error",
        "api_version":     0,
    }


def _fmt_count(n: int) -> str:
    """Compact number formatter: 1234 → '1234', 12345 → '12.3K', 1234567 → '1.2M'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


# ── Shared drawing helpers (duplicated from other modules to stay self-contained)

def _measure_text(font, text: str) -> int:
    try:
        return int(font.getlength(text))
    except AttributeError:
        try:
            return font.getsize(text)[0]
        except Exception:
            return len(text) * 6


def _draw_pihole_icon(draw: ImageDraw.ImageDraw, widget, icon_size: int,
                      line_y: int = None, line_h: int = None) -> int:
    """Draw Pi-hole shield icon if show_icon is enabled. Returns text x-offset."""
    show_icon = widget.config.get("show_icon", True)
    if show_icon and widget.width > icon_size + 20:
        from oled_dashboard.icons import draw_icon, icon_width as _iw
        ref_y = line_y if line_y is not None else widget.y
        ref_h = line_h if line_h is not None else widget.height
        icon_y = ref_y + max(0, (ref_h - icon_size) // 2)
        draw_icon(draw, widget.WIDGET_ID, widget.x, icon_y, size=icon_size)
        return widget.x + _iw(icon_size)
    return widget.x


# ── Widgets ────────────────────────────────────────────────────────────────

class PiholeSummaryWidget(Widget):
    """
    Pi-hole summary: queries blocked + block rate.

    Tall (≥ 18 px):  line 1 = "Pi: <queries> blk"
                     line 2 = [bar] <pct>% · <N> clients
    Short:           "Pi:<blk>/<tot> <pct>%"
    """

    WIDGET_ID        = "pihole_summary"
    WIDGET_NAME      = "Pi-hole Summary"
    WIDGET_CATEGORY  = "pihole"
    DEFAULT_SIZE     = (128, 24)
    MIN_SIZE         = (64, 12)
    DESCRIPTION      = "Pi-hole: total queries, blocked count, and block rate"
    REFRESH_INTERVAL = 10.0

    def fetch_data(self) -> Dict[str, Any]:
        api_key = self.config.get("api_key", "")
        return _fetch_pihole_data(api_key)

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font     = self.get_font()
        tot      = data["queries_total"]
        blk      = data["queries_blocked"]
        pct      = data["percent_blocked"]
        clients  = data["clients"]
        pct_text = f"{pct:.0f}%"

        if self.height >= 18:
            first_h   = self.font_size + 2
            icon_size = min(first_h - 2, 12)
            tx = _draw_pihole_icon(draw, self, icon_size,
                                   line_y=self.y, line_h=first_h)
            # Line 1: "Pi: 12.3K blk"
            draw.text((tx, self.y),
                      f"Pi: {_fmt_count(blk)} blk / {_fmt_count(tot)}",
                      font=font, fill=255)
            # Line 2: bar + % + clients
            bar_y  = self.y + first_h
            bar_h  = max(3, self.height - first_h - 1)
            suffix = f" {pct_text} {clients}cl"
            suf_w  = _measure_text(font, suffix) + 1
            bar_w  = self.width - suf_w - 1
            draw.rectangle([self.x, bar_y, self.x + bar_w, bar_y + bar_h], outline=255)
            fill_w = int((bar_w - 2) * pct / 100)
            if fill_w > 0:
                draw.rectangle(
                    [self.x + 1, bar_y + 1, self.x + 1 + fill_w, bar_y + bar_h - 1],
                    fill=255,
                )
            draw.text((self.x + bar_w + 2, bar_y), suffix.strip(), font=font, fill=255)
        else:
            icon_size = min(self.height - 2, 14)
            tx = _draw_pihole_icon(draw, self, icon_size)
            draw.text((tx, self.y),
                      f"Pi:{_fmt_count(blk)}/{_fmt_count(tot)} {pct_text}",
                      font=font, fill=255)


class PiholeBlockRateWidget(Widget):
    """
    Pi-hole block rate as a fill bar, like the RAM/Disk bar widgets.

    Tall (≥ 18 px):  line 1 = "Blocked: <N>"
                     line 2 = [bar] <pct>%
    Short:           "Blk: <N> (<pct>%)"
    """

    WIDGET_ID        = "pihole_block_rate"
    WIDGET_NAME      = "Pi-hole Block Rate"
    WIDGET_CATEGORY  = "pihole"
    DEFAULT_SIZE     = (128, 18)
    MIN_SIZE         = (64, 12)
    DESCRIPTION      = "Pi-hole ad block rate as a percentage bar"
    REFRESH_INTERVAL = 10.0

    def fetch_data(self) -> Dict[str, Any]:
        return _fetch_pihole_data(self.config.get("api_key", ""))

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font     = self.get_font()
        blk      = data["queries_blocked"]
        pct      = data["percent_blocked"]
        pct_text = f"{pct:.0f}%"

        if self.height >= 18:
            first_h   = self.font_size + 2
            icon_size = min(first_h - 2, 12)
            tx = _draw_pihole_icon(draw, self, icon_size,
                                   line_y=self.y, line_h=first_h)
            draw.text((tx, self.y), f"Blocked: {_fmt_count(blk)}", font=font, fill=255)
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
            icon_size = min(self.height - 2, 14)
            tx = _draw_pihole_icon(draw, self, icon_size)
            draw.text((tx, self.y),
                      f"Blk: {_fmt_count(blk)} ({pct_text})",
                      font=font, fill=255)


class PiholeQueriesWidget(Widget):
    """
    Pi-hole query counter: total and blocked on one compact line.
    """

    WIDGET_ID        = "pihole_queries"
    WIDGET_NAME      = "Pi-hole Queries"
    WIDGET_CATEGORY  = "pihole"
    DEFAULT_SIZE     = (128, 12)
    MIN_SIZE         = (64, 10)
    DESCRIPTION      = "Pi-hole total DNS queries today"
    REFRESH_INTERVAL = 10.0

    def fetch_data(self) -> Dict[str, Any]:
        return _fetch_pihole_data(self.config.get("api_key", ""))

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font      = self.get_font()
        icon_size = min(self.height - 2, 14)
        tx        = _draw_pihole_icon(draw, self, icon_size)
        tot       = _fmt_count(data["queries_total"])
        blk       = _fmt_count(data["queries_blocked"])
        draw.text((tx, self.y), f"Q:{tot} B:{blk}", font=font, fill=255)


class PiholeClientsWidget(Widget):
    """
    Pi-hole client counter: unique clients seen today.
    """

    WIDGET_ID        = "pihole_clients"
    WIDGET_NAME      = "Pi-hole Clients"
    WIDGET_CATEGORY  = "pihole"
    DEFAULT_SIZE     = (80, 12)
    MIN_SIZE         = (48, 10)
    DESCRIPTION      = "Number of unique DNS clients seen by Pi-hole"
    REFRESH_INTERVAL = 30.0

    def fetch_data(self) -> Dict[str, Any]:
        return _fetch_pihole_data(self.config.get("api_key", ""))

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font      = self.get_font()
        icon_size = min(self.height - 2, 14)
        tx        = _draw_pihole_icon(draw, self, icon_size)
        draw.text((tx, self.y), f"Clients: {data['clients']}", font=font, fill=255)


# ── All Pi-hole widget classes for external import ─────────────────────────

PIHOLE_WIDGETS = [
    PiholeSummaryWidget,
    PiholeBlockRateWidget,
    PiholeQueriesWidget,
    PiholeClientsWidget,
]

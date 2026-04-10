"""
Pi-hole monitoring widgets — Pi-hole v6 API.

Authentication flow (matches https://github.com/RPiSpy/pi-hole-screen):
  1. POST  /api/auth   {"password": "<password>"}
       → {"session": {"sid": "...", "csrf": "..."}}
  2. GET   /api/stats/summary   json={"sid": "...", "csrf": "..."}
  3. GET   /api/dns/blocking    json={"sid": "...", "csrf": "..."}
  Sessions last ~5 minutes; we refresh after 4 minutes automatically.

Pi-hole with no password set: requests succeed without a session body.

These widgets are only registered by the widget registry when Pi-hole is
detected on the host (see is_pihole_available()).
"""

import os
import time
import subprocess
import logging
from typing import Any, Dict, Optional
from PIL import ImageDraw
from oled_dashboard.widgets.base import Widget

log = logging.getLogger(__name__)


# ── Detection ───────────────────────────────────────────────────────────────

def is_pihole_available() -> bool:
    """Return True if Pi-hole appears to be installed on this system."""
    if os.path.isdir("/etc/pihole"):
        return True
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


# ── Session cache (shared across all widget instances) ──────────────────────

# Keyed by "base_url:password" so different Pi-hole hosts/passwords don't
# collide.
_sessions: Dict[str, Dict[str, Any]] = {}
_SESSION_TTL = 240.0   # refresh 1 minute before Pi-hole's 5-minute default

# Data cache: keyed by "base_url:password"
_data_cache: Dict[str, Dict[str, Any]] = {}
_DATA_TTL = 10.0       # fetch fresh stats every 10 seconds


def _auth_pihole(password: str, base_url: str) -> Optional[Dict[str, str]]:
    """
    POST to /api/auth to create a new Pi-hole session.
    Returns {"sid": ..., "csrf": ...} or None on failure.
    """
    try:
        import requests
        r = requests.post(
            f"{base_url}/api/auth",
            json={"password": password},
            timeout=3,
        )
        if r.status_code == 200:
            sess = r.json().get("session", {})
            sid  = sess.get("sid")
            csrf = sess.get("csrf")
            if sid and csrf:
                log.debug("Pi-hole: new session created")
                return {"sid": sid, "csrf": csrf}
        log.warning("Pi-hole auth failed: HTTP %s", r.status_code)
    except Exception as exc:
        log.warning("Pi-hole auth error: %s", exc)
    return None


def _get_session(password: str, base_url: str) -> Optional[Dict[str, str]]:
    """
    Return a valid session dict, (re-)authenticating as needed.
    Returns None when no password is configured (unauthenticated mode).
    """
    if not password:
        return None   # Pi-hole has no password → skip auth entirely

    cache_key = f"{base_url}:{password}"
    now = time.time()
    cached = _sessions.get(cache_key, {})

    if cached.get("sid") and now < cached.get("expires", 0):
        return {"sid": cached["sid"], "csrf": cached["csrf"]}

    # Need a fresh session
    sess = _auth_pihole(password, base_url)
    if sess:
        _sessions[cache_key] = {
            "sid":     sess["sid"],
            "csrf":    sess["csrf"],
            "expires": now + _SESSION_TTL,
        }
        return {"sid": sess["sid"], "csrf": sess["csrf"]}

    return None


def _fetch_pihole_data(password: str = "",
                       base_url: str = "http://localhost") -> Dict[str, Any]:
    """
    Fetch Pi-hole summary stats, using the correct v6 session-auth flow.

    Results are cached for _DATA_TTL seconds so every widget on the page
    shares a single network request.
    """
    cache_key = f"{base_url}:{password}"
    now = time.time()

    cached = _data_cache.get(cache_key, {})
    if cached.get("ts", 0) + _DATA_TTL > now:
        return cached.get("data", _empty_data())

    data = _empty_data()
    try:
        import requests

        session = _get_session(password, base_url)

        # Session is passed as a JSON body on every GET request.
        # For unauthenticated Pi-hole, session is None → send no body.
        def _get(url: str, **kw) -> "requests.Response":
            if session:
                kw.setdefault("json", session)
            return requests.get(url, timeout=3, **kw)

        r = _get(f"{base_url}/api/stats/summary")

        # If the session expired mid-flight, re-auth once and retry
        if r.status_code in (401, 403) and password:
            log.debug("Pi-hole session expired — re-authenticating")
            cache_key_sess = f"{base_url}:{password}"
            _sessions.pop(cache_key_sess, None)   # invalidate cached session
            session = _get_session(password, base_url)
            r = _get(f"{base_url}/api/stats/summary")

        if r.status_code == 200:
            j = r.json()
            queries  = j.get("queries",  {})
            clients_ = j.get("clients",  {})

            data = {
                "queries_total":   int(queries.get("total",           0)),
                "queries_blocked": int(queries.get("blocked",         0)),
                "percent_blocked": float(queries.get("percent_blocked", 0.0)),
                "unique_domains":  int(queries.get("unique_domains",  0)),
                "cached":          int(queries.get("cached",          0)),
                "forwarded":       int(queries.get("forwarded",       0)),
                "frequency":       round(float(queries.get("frequency", 0.0)), 2),
                # clients may be dict {"total": N, "active": M} or absent
                "clients": (
                    int(clients_.get("total", 0))
                    if isinstance(clients_, dict) else 0
                ),
                "status":      "enabled",
                "api_version": 6,
            }

            # Blocking status (optional — don't let this failure kill data)
            try:
                rb = _get(f"{base_url}/api/dns/blocking")
                if rb.status_code == 200:
                    data["status"] = rb.json().get("blocking", "enabled")
            except Exception:
                pass
        else:
            log.warning("Pi-hole summary returned HTTP %s", r.status_code)

    except Exception as exc:
        log.warning("Pi-hole fetch error: %s", exc)

    _data_cache[cache_key] = {"ts": now, "data": data}
    return data


def _empty_data() -> Dict[str, Any]:
    return {
        "queries_total":   0,
        "queries_blocked": 0,
        "percent_blocked": 0.0,
        "unique_domains":  0,
        "cached":          0,
        "forwarded":       0,
        "frequency":       0.0,
        "clients":         0,
        "status":          "error",
        "api_version":     6,
    }


# ── Shared drawing helpers ───────────────────────────────────────────────────

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
        ref_y  = line_y if line_y is not None else widget.y
        ref_h  = line_h if line_h is not None else widget.height
        icon_y = ref_y + max(0, (ref_h - icon_size) // 2)
        draw_icon(draw, widget.WIDGET_ID, widget.x, icon_y, size=icon_size)
        return widget.x + _iw(icon_size)
    return widget.x


def _fmt_count(n: int) -> str:
    """Compact number: 999→'999', 12345→'12.3K', 1234567→'1.2M'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _widget_data(widget) -> Dict[str, Any]:
    """Convenience: read password + base_url from widget config and fetch."""
    password = widget.config.get("password", "")
    base_url = widget.config.get("base_url", "http://localhost").rstrip("/")
    return _fetch_pihole_data(password, base_url)


# ── Widgets ─────────────────────────────────────────────────────────────────

class PiholeSummaryWidget(Widget):
    """
    Pi-hole summary: blocked count, total queries, block rate bar.

    Tall (≥ 18 px):  line 1 = [icon] "Pi: <blk> blk / <tot>"
                     line 2 = [bar] <pct>%  <N>cl
    Short:           [icon] "Pi:<blk>/<tot> <pct>%"
    """

    WIDGET_ID        = "pihole_summary"
    WIDGET_NAME      = "Pi-hole Summary"
    WIDGET_CATEGORY  = "pihole"
    DEFAULT_SIZE     = (128, 24)
    MIN_SIZE         = (64, 12)
    DESCRIPTION      = "Pi-hole: blocked count, total queries, and block rate bar"
    REFRESH_INTERVAL = 10.0

    def fetch_data(self) -> Dict[str, Any]:
        return _widget_data(self)

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
            draw.text((tx, self.y),
                      f"Pi: {_fmt_count(blk)} blk / {_fmt_count(tot)}",
                      font=font, fill=255)
            # Line 2: bar + % + clients
            bar_y  = self.y + first_h
            bar_h  = max(3, self.height - first_h - 1)
            suffix = f"{pct_text} {clients}cl" if clients else pct_text
            suf_w  = _measure_text(font, suffix) + 2
            bar_w  = self.width - suf_w - 1
            draw.rectangle([self.x, bar_y, self.x + bar_w, bar_y + bar_h], outline=255)
            fill_w = int((bar_w - 2) * pct / 100)
            if fill_w > 0:
                draw.rectangle(
                    [self.x + 1, bar_y + 1, self.x + 1 + fill_w, bar_y + bar_h - 1],
                    fill=255,
                )
            draw.text((self.x + bar_w + 2, bar_y), suffix, font=font, fill=255)
        else:
            icon_size = min(self.height - 2, 14)
            tx = _draw_pihole_icon(draw, self, icon_size)
            draw.text((tx, self.y),
                      f"Pi:{_fmt_count(blk)}/{_fmt_count(tot)} {pct_text}",
                      font=font, fill=255)


class PiholeBlockRateWidget(Widget):
    """
    Pi-hole block rate as a fill bar.

    Tall (≥ 18 px):  line 1 = [icon] "Blocked: <N>"
                     line 2 = [bar] <pct>%
    Short:           [icon] "Blk: <N> (<pct>%)"
    """

    WIDGET_ID        = "pihole_block_rate"
    WIDGET_NAME      = "Pi-hole Block Rate"
    WIDGET_CATEGORY  = "pihole"
    DEFAULT_SIZE     = (128, 18)
    MIN_SIZE         = (64, 12)
    DESCRIPTION      = "Pi-hole ad block rate as a percentage bar"
    REFRESH_INTERVAL = 10.0

    def fetch_data(self) -> Dict[str, Any]:
        return _widget_data(self)

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
                      f"Blk:{_fmt_count(blk)} ({pct_text})",
                      font=font, fill=255)


class PiholeQueriesWidget(Widget):
    """Pi-hole query counter: total and blocked on one compact line."""

    WIDGET_ID        = "pihole_queries"
    WIDGET_NAME      = "Pi-hole Queries"
    WIDGET_CATEGORY  = "pihole"
    DEFAULT_SIZE     = (128, 12)
    MIN_SIZE         = (64, 10)
    DESCRIPTION      = "Pi-hole total DNS queries and blocked count"
    REFRESH_INTERVAL = 10.0

    def fetch_data(self) -> Dict[str, Any]:
        return _widget_data(self)

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font      = self.get_font()
        icon_size = min(self.height - 2, 14)
        tx        = _draw_pihole_icon(draw, self, icon_size)
        tot       = _fmt_count(data["queries_total"])
        blk       = _fmt_count(data["queries_blocked"])
        draw.text((tx, self.y), f"Q:{tot} B:{blk}", font=font, fill=255)


class PiholeClientsWidget(Widget):
    """Pi-hole client counter: unique clients seen today."""

    WIDGET_ID        = "pihole_clients"
    WIDGET_NAME      = "Pi-hole Clients"
    WIDGET_CATEGORY  = "pihole"
    DEFAULT_SIZE     = (80, 12)
    MIN_SIZE         = (48, 10)
    DESCRIPTION      = "Number of unique DNS clients seen by Pi-hole"
    REFRESH_INTERVAL = 30.0

    def fetch_data(self) -> Dict[str, Any]:
        return _widget_data(self)

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font      = self.get_font()
        icon_size = min(self.height - 2, 14)
        tx        = _draw_pihole_icon(draw, self, icon_size)
        draw.text((tx, self.y), f"Clients: {data['clients']}", font=font, fill=255)


# ── Export ───────────────────────────────────────────────────────────────────

PIHOLE_WIDGETS = [
    PiholeSummaryWidget,
    PiholeBlockRateWidget,
    PiholeQueriesWidget,
    PiholeClientsWidget,
]

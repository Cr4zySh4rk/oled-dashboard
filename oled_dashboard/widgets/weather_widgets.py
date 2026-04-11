"""
Weather widget using the Open-Meteo free API (no API key required).

Fetches current conditions: temperature, weather code (condition), wind
speed, and humidity. Data is cached for the configured refresh interval
(default 10 minutes) to avoid hammering the API.

Configuration keys (all optional):
  latitude      float   Default 0.0  (your location)
  longitude     float   Default 0.0
  temp_unit     str     "C" or "F"   (default "C")
  wind_unit     str     "kmh" or "mph" (default "kmh")
  format        str     One of the FORMAT_* keys below (default "temp_cond")
  show_icon     bool    True

Formats:
  temp_cond    → "23°C Cloudy"
  temp_only    → "23°C"
  full         → "23°C ↑12km/h 65%"   (temp + wind + humidity)
  compact      → "23° ⛅"
"""

import time
import logging
from typing import Any, Dict, Optional

from PIL import ImageDraw
from oled_dashboard.widgets.base import Widget

log = logging.getLogger(__name__)

# ── WMO weather interpretation codes → short description ───────────────────
_WMO_DESCRIPTIONS = {
    0: "Clear",
    1: "Mostly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy Fog",
    51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle",
    61: "Light Rain", 63: "Rain", 65: "Heavy Rain",
    71: "Light Snow", 73: "Snow", 75: "Heavy Snow",
    77: "Snow Grains",
    80: "Showers", 81: "Showers", 82: "Heavy Showers",
    85: "Snow Showers", 86: "Heavy Snow Showers",
    95: "Thunderstorm",
    96: "T-Storm + Hail", 99: "T-Storm + Hail",
}

# Short 4-char abbreviations for tight displays
_WMO_SHORT = {
    0: "Clr", 1: "MCl", 2: "PCl", 3: "Ovr",
    45: "Fog", 48: "Fog",
    51: "Drz", 53: "Drz", 55: "Drz",
    61: "Ran", 63: "Ran", 65: "HRn",
    71: "Snw", 73: "Snw", 75: "HSn",
    77: "Snw",
    80: "Shr", 81: "Shr", 82: "HSh",
    85: "SSh", 86: "SSh",
    95: "Tst",
    96: "Tst", 99: "Tst",
}

# ── Shared data cache (keyed by "lat:lon:unit") ─────────────────────────────
_weather_cache: Dict[str, Dict[str, Any]] = {}


def _fetch_weather(latitude: float, longitude: float,
                   temp_unit: str = "celsius",
                   wind_unit: str = "kmh") -> Dict[str, Any]:
    """
    Call Open-Meteo /v1/forecast for current conditions.
    Returns a dict with keys: temp, wind_speed, humidity, weather_code, condition.
    On error, returns a dict with status="error".
    """
    try:
        import urllib.request
        import json as _json

        params = (
            f"latitude={latitude}&longitude={longitude}"
            f"&current=temperature_2m,relative_humidity_2m,"
            f"weather_code,wind_speed_10m"
            f"&temperature_unit={'celsius' if temp_unit.upper() == 'C' else 'fahrenheit'}"
            f"&wind_speed_unit={wind_unit.lower()}"
            f"&forecast_days=1"
        )
        url = f"https://api.open-meteo.com/v1/forecast?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "oled-dashboard/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())

        cur = data.get("current", {})
        code = int(cur.get("weather_code", 0))
        return {
            "temp":         round(float(cur.get("temperature_2m", 0)), 1),
            "wind_speed":   round(float(cur.get("wind_speed_10m", 0)), 1),
            "humidity":     int(cur.get("relative_humidity_2m", 0)),
            "weather_code": code,
            "condition":    _WMO_DESCRIPTIONS.get(code, "Unknown"),
            "cond_short":   _WMO_SHORT.get(code, "?"),
            "temp_unit":    "°C" if temp_unit.upper() == "C" else "°F",
            "wind_unit":    wind_unit.lower(),
            "status":       "ok",
        }
    except Exception as exc:
        log.warning("Weather fetch error: %s", exc)
        return {
            "temp": 0, "wind_speed": 0, "humidity": 0,
            "weather_code": 0, "condition": "No Data", "cond_short": "N/A",
            "temp_unit": "°C", "wind_unit": "kmh", "status": "error",
        }


def _get_weather_data(latitude: float, longitude: float,
                      temp_unit: str, wind_unit: str,
                      ttl: float) -> Dict[str, Any]:
    """Return cached (or freshly fetched) weather data."""
    key = f"{latitude:.4f}:{longitude:.4f}:{temp_unit}:{wind_unit}"
    now = time.time()
    cached = _weather_cache.get(key, {})
    if cached.get("ts", 0) + ttl > now:
        return cached.get("data", {})
    data = _fetch_weather(latitude, longitude, temp_unit, wind_unit)
    _weather_cache[key] = {"ts": now, "data": data}
    return data


def _measure_text(font, text: str) -> int:
    try:
        return int(font.getlength(text))
    except AttributeError:
        try:
            return font.getsize(text)[0]
        except Exception:
            return len(text) * 6


# ── Widget ──────────────────────────────────────────────────────────────────

class WeatherWidget(Widget):
    """
    Current weather from Open-Meteo (free, no API key needed).

    Uses lat/lon from the widget config. If both are 0 and no location
    has been set, shows "Set lat/lon".
    """

    WIDGET_ID        = "weather"
    WIDGET_NAME      = "Weather"
    WIDGET_CATEGORY  = "general"
    DEFAULT_SIZE     = (128, 16)
    MIN_SIZE         = (48, 10)
    DESCRIPTION      = "Current weather (temperature, condition, wind, humidity)"
    REFRESH_INTERVAL = 600.0   # 10 minutes — Open-Meteo updates every 15 min

    def fetch_data(self) -> Dict[str, Any]:
        lat  = float(self.config.get("latitude",  0.0))
        lon  = float(self.config.get("longitude", 0.0))
        tunit = self.config.get("temp_unit",  "C").upper()
        wunit = self.config.get("wind_unit",  "kmh").lower()
        if lat == 0.0 and lon == 0.0:
            return {
                "temp": "--", "wind_speed": "--", "humidity": "--",
                "condition": "Set lat/lon", "cond_short": "---",
                "temp_unit": "°C", "wind_unit": wunit, "status": "unconfigured",
            }
        return _get_weather_data(lat, lon, tunit, wunit, self.REFRESH_INTERVAL)

    def render(self, draw: ImageDraw.ImageDraw, data: Any) -> None:
        font     = self.get_font()
        fmt      = self.config.get("format", "temp_cond")
        tunit    = data.get("temp_unit", "°C")
        wunit    = data.get("wind_unit", "kmh")
        temp     = data.get("temp", "--")
        cond     = data.get("condition", "")
        cond_s   = data.get("cond_short", "")
        wind     = data.get("wind_speed", "--")
        hum      = data.get("humidity", "--")

        # Draw icon if room
        show_icon = self.config.get("show_icon", True)
        tx = self.x
        if show_icon and self.width > 24:
            from oled_dashboard.icons import draw_icon, icon_width as _iw
            icon_size = min(self.height - 2, 12)
            icon_y = self.y + max(0, (self.height - icon_size) // 2)
            draw_icon(draw, self.WIDGET_ID, self.x, icon_y, size=icon_size)
            tx = self.x + _iw(icon_size)

        # Choose text based on format
        if fmt == "temp_only":
            text = f"{temp}{tunit}"
        elif fmt == "full":
            wu = "m" if wunit == "mph" else "k"
            text = f"{temp}{tunit} {wind}{wu} {hum}%"
        elif fmt == "compact":
            text = f"{temp}° {cond_s}"
        else:  # "temp_cond" (default)
            text = f"{temp}{tunit} {cond}"

        draw.text((tx, self.y), text, font=font, fill=255)


# ── Export ────────────────────────────────────────────────────────────────────

WEATHER_WIDGETS = [
    WeatherWidget,
]

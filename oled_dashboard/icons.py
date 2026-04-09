"""
Pixel-art icon library for OLED Dashboard.

All icons are drawn procedurally with PIL so they scale cleanly to any
small size (default 10x10 px). They use only binary (0/255) colors to
match the 1-bit OLED display.

Usage:
    from oled_dashboard.icons import draw_icon
    draw_icon(draw, "cpu", x=0, y=2, size=10)
"""

from PIL import ImageDraw
from typing import Tuple

# ── Helpers ────────────────────────────────────────────────────────────

def _rect(draw, x, y, w, h, fill=255):
    draw.rectangle([x, y, x + w - 1, y + h - 1], fill=fill)

def _px(draw, x, y, fill=255):
    draw.point([x, y], fill=fill)

def _line(draw, x0, y0, x1, y1, fill=255):
    draw.line([x0, y0, x1, y1], fill=fill)

def _ellipse(draw, x, y, w, h, outline=255, fill=None):
    draw.ellipse([x, y, x + w - 1, y + h - 1], outline=outline, fill=fill)


# ── Icon Drawers ───────────────────────────────────────────────────────

def _icon_cpu(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Microchip: square body with pins on all sides."""
    m = max(1, s // 6)         # margin for pins
    body = s - m * 2
    # Body
    draw.rectangle([x + m, y + m, x + m + body - 1, y + m + body - 1], outline=255)
    # Corner dots (die area)
    inner = body // 3
    ox, oy = x + m + (body - inner) // 2, y + m + (body - inner) // 2
    draw.rectangle([ox, oy, ox + inner - 1, oy + inner - 1], fill=255)
    # Pins — top and bottom (2 each)
    pin_gap = body // 3
    for i in range(2):
        px_ = x + m + pin_gap // 2 + i * pin_gap
        _line(draw, px_, y, px_, y + m - 1)             # top
        _line(draw, px_, y + m + body, px_, y + s - 1)  # bottom
    # Pins — left and right
    for i in range(2):
        py_ = y + m + pin_gap // 2 + i * pin_gap
        _line(draw, x, py_, x + m - 1, py_)             # left
        _line(draw, x + m + body, py_, x + s - 1, py_)  # right


def _icon_ram(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """RAM stick: rectangle with notch and chip bumps on top."""
    bar_h = max(2, s * 3 // 8)
    bar_y = y + s - bar_h
    # Main bar
    draw.rectangle([x, bar_y, x + s - 1, y + s - 1], outline=255)
    # Notch (bottom center)
    notch_w = max(2, s // 5)
    notch_x = x + (s - notch_w) // 2
    draw.rectangle([notch_x, y + s - max(2, s // 5), notch_x + notch_w - 1, y + s - 1], fill=0, outline=0)
    # Chip bumps on top
    n_chips = max(2, s // 4)
    chip_w = max(1, (s - n_chips) // n_chips)
    for i in range(n_chips):
        cx = x + i * (chip_w + 1)
        if cx + chip_w <= x + s:
            chip_h = max(2, s // 4)
            draw.rectangle([cx, bar_y - chip_h, cx + chip_w - 1, bar_y - 1], fill=255)


def _icon_temperature(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Thermometer: tube with bulb at bottom."""
    cx = x + s // 2
    tube_w = max(2, s // 5)
    bulb_r = max(2, s // 4)
    tube_top = y + 1
    tube_bot = y + s - bulb_r - 1
    # Tube outline
    draw.rectangle([cx - tube_w // 2, tube_top, cx + tube_w // 2, tube_bot], outline=255)
    # Fill tube partway (mercury level ~60%)
    fill_top = tube_top + (tube_bot - tube_top) * 4 // 10
    if fill_top < tube_bot:
        draw.rectangle([cx - tube_w // 2 + 1, fill_top, cx + tube_w // 2 - 1, tube_bot], fill=255)
    # Bulb
    _ellipse(draw, cx - bulb_r, tube_bot - 1, bulb_r * 2 + 1, bulb_r * 2 + 1, outline=255, fill=255)
    # Tick marks on right side
    for i in range(3):
        ty = tube_top + (tube_bot - tube_top) * (i + 1) // 4
        _line(draw, cx + tube_w // 2 + 1, ty, cx + tube_w // 2 + max(2, s // 5), ty)


def _icon_uptime(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Clock: circle with hands."""
    r = s // 2 - 1
    cx, cy = x + s // 2, y + s // 2
    _ellipse(draw, cx - r, cy - r, r * 2, r * 2, outline=255)
    # Hour hand (pointing ~10 o'clock)
    import math
    h_angle = math.radians(-60)
    hx = int(cx + (r * 0.5) * math.sin(h_angle))
    hy = int(cy - (r * 0.5) * math.cos(h_angle))
    _line(draw, cx, cy, hx, hy)
    # Minute hand (pointing ~12 o'clock)
    _line(draw, cx, cy, cx, cy - r + 1)
    # Center dot
    _px(draw, cx, cy)


def _icon_load(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Bar chart: 3 vertical bars of increasing height."""
    n = 3
    bar_w = max(1, (s - n - 1) // n)
    heights = [s * 4 // 10, s * 6 // 10, s * 9 // 10]
    for i in range(n):
        bx = x + 1 + i * (bar_w + 1)
        bh = heights[i]
        by = y + s - bh
        draw.rectangle([bx, by, bx + bar_w - 1, y + s - 1], fill=255)


def _icon_hostname(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """House silhouette."""
    # Roof (triangle via lines)
    mid = x + s // 2
    _line(draw, x, y + s * 4 // 10, mid, y)                # left roof
    _line(draw, mid, y, x + s - 1, y + s * 4 // 10)        # right roof
    _line(draw, x, y + s * 4 // 10, x + s - 1, y + s * 4 // 10)  # eave
    # Walls
    wall_y = y + s * 4 // 10
    draw.rectangle([x + 1, wall_y, x + s - 2, y + s - 1], outline=255)
    # Door
    door_w = max(2, s // 4)
    door_h = max(2, s // 3)
    door_x = x + (s - door_w) // 2
    draw.rectangle([door_x, y + s - door_h - 1, door_x + door_w - 1, y + s - 1], fill=255)


def _icon_ip(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Globe with latitude/longitude lines."""
    r = s // 2 - 1
    cx, cy = x + s // 2, y + s // 2
    # Outer circle
    _ellipse(draw, cx - r, cy - r, r * 2, r * 2, outline=255)
    # Vertical center line (meridian)
    _line(draw, cx, cy - r + 1, cx, cy + r - 1)
    # Horizontal center line (equator)
    _line(draw, cx - r + 1, cy, cx + r - 1, cy)
    # Top and bottom latitude arcs (simplified as horizontal lines)
    lat_off = r * 5 // 8
    lat_half = max(1, int((r**2 - lat_off**2) ** 0.5))
    _line(draw, cx - lat_half, cy - lat_off, cx + lat_half, cy - lat_off)
    _line(draw, cx - lat_half, cy + lat_off, cx + lat_half, cy + lat_off)


def _icon_network_speed(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Wi-Fi / radio waves (3 arcs + dot)."""
    cx = x + s // 2
    dot_y = y + s - 2
    # Dot
    _ellipse(draw, cx - 1, dot_y - 1, 3, 3, outline=255, fill=255)
    # Arcs — draw as portions of ellipses
    offsets = [3, 5, 7] if s >= 10 else [2, 4]
    for off in offsets:
        if off < s // 2:
            ay = dot_y - off
            _ellipse(draw, cx - off, ay - off, off * 2, off * 2, outline=255)
            # Mask bottom half of arc (keep only top arc)
            draw.rectangle([x, dot_y - off, x + s - 1, dot_y], fill=0)
    # Redraw dot
    _ellipse(draw, cx - 1, dot_y - 1, 3, 3, outline=255, fill=255)


def _icon_ethernet(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Ethernet plug: RJ45 shape."""
    plug_w = s * 5 // 8
    plug_h = s * 6 // 8
    ox = x + (s - plug_w) // 2
    oy = y + (s - plug_h) // 2
    # Main body
    draw.rectangle([ox, oy, ox + plug_w - 1, oy + plug_h - 1], outline=255)
    # Contacts (3 lines at bottom)
    pin_y = oy + plug_h - max(2, plug_h // 3)
    pin_gap = plug_w // 4
    for i in range(3):
        px_ = ox + pin_gap // 2 + i * pin_gap
        if px_ < ox + plug_w:
            _line(draw, px_, pin_y, px_, oy + plug_h - 1)
    # Tab (clip at top)
    tab_w = plug_w * 3 // 5
    tab_x = ox + (plug_w - tab_w) // 2
    draw.rectangle([tab_x, oy - max(1, s // 8), tab_x + tab_w - 1, oy], fill=255)


def _icon_net_usage(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Up/down arrows for transfer totals."""
    mid = s // 2
    arr_h = max(3, s * 4 // 10)
    arr_w = max(2, s * 3 // 10)
    # Down arrow (left half)
    ax = x + mid // 2
    _line(draw, ax, y + 1, ax, y + arr_h)
    draw.polygon([ax - arr_w // 2, y + arr_h - 1,
                  ax + arr_w // 2, y + arr_h - 1,
                  ax, y + arr_h + arr_w // 2], fill=255)
    # Up arrow (right half)
    ax2 = x + mid + mid // 2
    _line(draw, ax2, y + s - 2, ax2, y + s - arr_h - 1)
    draw.polygon([ax2 - arr_w // 2, y + s - arr_h + 1,
                  ax2 + arr_w // 2, y + s - arr_h + 1,
                  ax2, y + s - arr_h - arr_w // 2 - 1], fill=255)


def _icon_disk(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Hard disk / CD: outer ring + inner hole + small sector."""
    r = s // 2 - 1
    cx, cy = x + s // 2, y + s // 2
    _ellipse(draw, cx - r, cy - r, r * 2, r * 2, outline=255)
    # Inner hole
    hole_r = max(1, r // 3)
    _ellipse(draw, cx - hole_r, cy - hole_r, hole_r * 2, hole_r * 2, outline=255, fill=0)
    # One filled sector (read head arm)
    _line(draw, cx, cy, cx + r - 1, cy)
    _line(draw, cx, cy, cx, cy - r + 1)


def _icon_disk_io(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Disk platter with read arm."""
    r = s // 2 - 1
    cx, cy = x + s // 2, y + s // 2
    _ellipse(draw, cx - r, cy - r, r * 2, r * 2, outline=255)
    hole_r = max(1, r // 4)
    _ellipse(draw, cx - hole_r, cy - hole_r, hole_r * 2, hole_r * 2, fill=255)
    # Arm line from edge to hole
    _line(draw, cx - r + 1, cy - r + 1, cx - hole_r, cy - hole_r)


def _icon_lightning(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Lightning bolt: zig-zag."""
    pts = [
        x + s * 6 // 10, y,
        x + s * 3 // 10, y + s // 2,
        x + s * 5 // 10, y + s // 2,
        x + s * 2 // 10, y + s - 1,
        x + s * 7 // 10, y + s * 4 // 10,
        x + s * 5 // 10, y + s * 4 // 10,
        x + s * 6 // 10, y,
    ]
    for i in range(0, len(pts) - 2, 2):
        _line(draw, pts[i], pts[i + 1], pts[i + 2], pts[i + 3])
    # Fill interior for bolder look
    draw.polygon(pts, fill=255)


def _icon_text(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """'Aa' text label icon."""
    # Big A
    mid = x + s // 2
    _line(draw, x + 1, y + s - 1, mid - 1, y + 1)
    _line(draw, mid - 1, y + 1, mid + s // 4, y + s - 1)
    cross_y = y + s * 5 // 8
    _line(draw, x + s // 4, cross_y, mid + s // 8, cross_y)
    # Small a (right side)
    ax = x + s * 5 // 8
    aw = max(2, s // 4)
    small_top = y + s // 3
    _ellipse(draw, ax, small_top, aw, aw, outline=255)
    _line(draw, ax + aw, small_top, ax + aw, y + s - 1)


def _icon_hline(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Horizontal rule."""
    mid = y + s // 2
    _line(draw, x, mid - 1, x + s - 1, mid - 1)
    _line(draw, x, mid + 1, x + s - 1, mid + 1)
    _line(draw, x, mid, x + s - 1, mid)


def _icon_vline(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Vertical rule."""
    mid = x + s // 2
    _line(draw, mid - 1, y, mid - 1, y + s - 1)
    _line(draw, mid + 1, y, mid + 1, y + s - 1)
    _line(draw, mid, y, mid, y + s - 1)


def _icon_box(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Box / frame."""
    draw.rectangle([x, y, x + s - 1, y + s - 1], outline=255)
    draw.rectangle([x + 2, y + 2, x + s - 3, y + s - 3], outline=255)


def _icon_progress(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Progress bar."""
    bar_h = max(2, s // 3)
    by = y + (s - bar_h) // 2
    draw.rectangle([x, by, x + s - 1, by + bar_h - 1], outline=255)
    # Fill ~60%
    fill_w = (s - 2) * 6 // 10
    draw.rectangle([x + 1, by + 1, x + 1 + fill_w, by + bar_h - 2], fill=255)


def _icon_datetime(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Calendar with clock."""
    cal_h = s * 7 // 10
    # Calendar body
    draw.rectangle([x, y + s - cal_h, x + s - 1, y + s - 1], outline=255)
    # Header bar
    draw.rectangle([x, y + s - cal_h, x + s - 1, y + s - cal_h + max(1, s // 6)], fill=255)
    # Two hanging tabs at top
    tab_w = max(1, s // 6)
    for tx in [x + s // 4, x + s * 3 // 4]:
        draw.rectangle([tx - tab_w // 2, y + s - cal_h - max(1, s // 6),
                        tx + tab_w // 2, y + s - cal_h], fill=255)
    # 4 dots for days
    for dy_ in range(2):
        for dx_ in range(2):
            dot_x = x + s // 4 + dx_ * s // 2
            dot_y = y + s - cal_h // 2 + dy_ * (s // 5)
            _px(draw, dot_x, dot_y)


def _icon_swap(draw: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Two overlapping rectangles (swap / virtual memory)."""
    off = max(1, s // 5)
    draw.rectangle([x, y, x + s - 1 - off, y + s - 1 - off], outline=255)
    draw.rectangle([x + off, y + off, x + s - 1, y + s - 1], outline=255, fill=0)
    draw.rectangle([x + off, y + off, x + s - 1, y + s - 1], outline=255)


# ── Registry ───────────────────────────────────────────────────────────

_ICON_MAP = {
    "cpu_usage":    _icon_lightning,
    "ram_usage":    _icon_ram,
    "swap_usage":   _icon_swap,
    "temperature":  _icon_temperature,
    "uptime":       _icon_uptime,
    "load_avg":     _icon_load,
    "hostname":     _icon_hostname,
    "ip_address":   _icon_ip,
    "net_speed":    _icon_network_speed,
    "net_usage":    _icon_net_usage,
    "disk_space":   _icon_disk,
    "disk_io":      _icon_disk_io,
    "static_text":  _icon_text,
    "hline":        _icon_hline,
    "vline":        _icon_vline,
    "box":          _icon_box,
    "progress_bar": _icon_progress,
    "datetime":     _icon_datetime,
    # aliases
    "cpu":          _icon_lightning,
    "ram":          _icon_ram,
    "temp":         _icon_temperature,
    "network":      _icon_ethernet,
    "ethernet":     _icon_ethernet,
    "disk":         _icon_disk,
}


def draw_icon(
    draw: ImageDraw.ImageDraw,
    widget_id: str,
    x: int,
    y: int,
    size: int = 10,
) -> None:
    """
    Draw a pixel-art icon for the given widget_id.

    Args:
        draw:      PIL ImageDraw object
        widget_id: Widget identifier string (e.g. "cpu_usage")
        x, y:      Top-left corner of the icon bounding box
        size:      Width and height of the icon in pixels
    """
    fn = _ICON_MAP.get(widget_id)
    if fn is not None:
        try:
            fn(draw, x, y, size)
        except Exception:
            # Never crash the render loop over an icon
            draw.rectangle([x, y, x + size - 1, y + size - 1], outline=255)


def icon_width(size: int = 10) -> int:
    """Return the pixel width an icon occupies (icon + 1px gap)."""
    return size + 2


def available_icons() -> list:
    """List all widget IDs that have icons."""
    return sorted(set(_ICON_MAP.keys()))

"""
Display renderer - reads the layout configuration and renders widgets
to the OLED display in a loop.

Supports page-transition animations:
  none, diffuse, swipe_right, swipe_left, swipe_up, swipe_down,
  scroll_left, scroll_right, scroll_up, scroll_down
"""

import time
import threading
from typing import List, Optional
from PIL import Image, ImageDraw

from oled_dashboard.config_manager import ConfigManager
from oled_dashboard.drivers import get_driver
from oled_dashboard.drivers.base import OLEDDriver
from oled_dashboard.drivers.simulate import SimulatedDriver
from oled_dashboard.widgets.base import Widget
from oled_dashboard.widgets.registry import WidgetRegistry


class DisplayRenderer:
    """Renders widgets onto the OLED display based on layout config."""

    # Transition duration in seconds and steps
    _TRANSITION_DURATION = 0.4
    _TRANSITION_STEPS    = 8   # number of intermediate frames

    def __init__(self, config_manager: ConfigManager, simulate: bool = False):
        self.config_manager = config_manager
        self.simulate = simulate
        self.driver: Optional[OLEDDriver] = None
        # Multi-page state
        self._pages_widgets: List[List[Widget]] = [[]]
        self._current_page: int = 0
        self._last_page_switch: float = 0.0
        self._page_interval: float = 5.0
        self._page_transition: str = "none"
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._simulated_driver: Optional[SimulatedDriver] = None
        # Track whether hardware init actually succeeded
        self._hardware_ok = False

    @property
    def widgets(self) -> List[Widget]:
        """Widgets on the currently displayed page."""
        if self._pages_widgets and self._current_page < len(self._pages_widgets):
            return self._pages_widgets[self._current_page]
        return []

    def initialize(self) -> bool:
        """Initialize the display driver and load widgets."""
        config = self.config_manager.load()
        display_cfg = config.get("display", {})

        chip = display_cfg.get("chip", "SSD1306")
        width = display_cfg.get("width", 128)
        height = display_cfg.get("height", 64)
        interface = display_cfg.get("interface", "i2c")
        rotation = display_cfg.get("rotation", 0)
        address = int(display_cfg.get("i2c_address", "0x3C"), 16)
        brightness = display_cfg.get("brightness", 255)

        # Always create a simulated driver for web preview
        self._simulated_driver = SimulatedDriver(width=width, height=height)
        self._simulated_driver.initialize()

        if self.simulate:
            self.driver = self._simulated_driver
            self._hardware_ok = False
            print("[Renderer] Running in simulation mode (no hardware output)")
        else:
            try:
                hw_driver = get_driver(
                    chip=chip,
                    width=width,
                    height=height,
                    interface=interface,
                    address=address,
                    rotation=rotation,
                    i2c_bus=display_cfg.get("i2c_bus", 1),
                    spi_device=display_cfg.get("spi_device", 0),
                    spi_dc_pin=display_cfg.get("spi_dc_pin", 24),
                    spi_reset_pin=display_cfg.get("spi_reset_pin", None),
                    spi_cs_pin=display_cfg.get("spi_cs_pin", 8),
                )
                if hw_driver.initialize():
                    hw_driver.set_brightness(brightness)
                    self.driver = hw_driver
                    self._hardware_ok = True
                    print(f"[Renderer] Hardware display ready: {chip} {width}x{height} via {interface}")
                else:
                    # initialize() already printed detailed diagnostics
                    print("[Renderer] *** Hardware display NOT active — web preview only ***")
                    self.driver = self._simulated_driver
                    self._hardware_ok = False
            except Exception as e:
                print(f"[Renderer] Hardware driver exception: {e}")
                print("[Renderer] *** Hardware display NOT active — web preview only ***")
                self.driver = self._simulated_driver
                self._hardware_ok = False

        self._page_interval  = self.config_manager.get_page_interval()
        self._page_transition = self.config_manager.get_page_transition()
        self._load_pages()
        return True

    def _load_pages(self) -> None:
        """Load all pages' widgets from config."""
        pages_cfg = self.config_manager.get_pages()
        new_pages: List[List[Widget]] = []
        for page_cfg in pages_cfg:
            page_widgets: List[Widget] = []
            for wc in page_cfg.get("widgets", []):
                widget = WidgetRegistry.create_from_dict(wc)
                if widget is not None:
                    page_widgets.append(widget)
                else:
                    print(f"[Renderer] Unknown widget: {wc.get('widget_id')}")
            new_pages.append(page_widgets)
        self._pages_widgets = new_pages if new_pages else [[]]
        self._current_page = 0
        self._last_page_switch = time.time()

    # Keep _load_widgets as an alias for backward compat with any external callers
    def _load_widgets(self) -> None:
        self._load_pages()

    def reload_layout(self) -> None:
        """Reload all pages from config (hot reload)."""
        with self._lock:
            self.config_manager._config = None
            self._page_interval  = self.config_manager.get_page_interval()
            self._page_transition = self.config_manager.get_page_transition()
            self._load_pages()

    def _maybe_advance_page(self) -> None:
        """Advance to the next page if the page interval has elapsed."""
        if len(self._pages_widgets) <= 1 or self._page_interval <= 0:
            return
        if time.time() - self._last_page_switch >= self._page_interval:
            old_page = self._current_page
            self._current_page = (self._current_page + 1) % len(self._pages_widgets)
            self._last_page_switch = time.time()
            # Play transition animation if configured
            if self._page_transition != "none":
                self._play_transition(old_page, self._current_page)

    def _render_page_image(self, page_idx: int) -> Image.Image:
        """Render a single page to an image without touching the display."""
        w = self.driver.width if self.driver else 128
        h = self.driver.height if self.driver else 64
        image = Image.new("1", (w, h), 0)
        draw = ImageDraw.Draw(image)
        widgets = self._pages_widgets[page_idx] if page_idx < len(self._pages_widgets) else []
        for widget in widgets:
            try:
                widget.draw(draw)
            except Exception:
                pass
        return image

    def _push_frame(self, image: Image.Image) -> None:
        """Push an image to both the sim buffer and hardware."""
        self._simulated_driver.display_image(image)
        if self._hardware_ok and self.driver and not isinstance(self.driver, SimulatedDriver):
            try:
                self.driver.display_image(image)
            except Exception:
                pass

    def _play_transition(self, from_page: int, to_page: int) -> None:
        """Render a transition animation between two pages."""
        w = self.driver.width if self.driver else 128
        h = self.driver.height if self.driver else 64
        steps = self._TRANSITION_STEPS
        delay = self._TRANSITION_DURATION / steps

        img_from = self._render_page_image(from_page)
        img_to   = self._render_page_image(to_page)

        t = self._page_transition

        for step in range(1, steps + 1):
            frac = step / steps          # 0 < frac ≤ 1
            frame = Image.new("1", (w, h), 0)

            if t == "diffuse":
                # Pixel-level probabilistic blend: at each step, each pixel
                # from 'to' image has a `frac` chance of showing through.
                import random
                px_from = list(img_from.getdata())
                px_to   = list(img_to.getdata())
                out = [
                    px_to[i] if random.random() < frac else px_from[i]
                    for i in range(w * h)
                ]
                frame.putdata(out)

            elif t in ("swipe_right", "swipe_left", "swipe_up", "swipe_down",
                       "scroll_left", "scroll_right", "scroll_up", "scroll_down"):
                # All slide variants: compute offset for this step
                # "swipe_*"  → incoming page slides over the outgoing (which is static)
                # "scroll_*" → both pages scroll together (continuous belt feel)
                if t in ("swipe_right", "scroll_right"):
                    offset = int(w * (1 - frac))   # incoming from right → left
                    if t == "swipe_right":
                        frame.paste(img_from, (0, 0))
                        frame.paste(img_to, (-(w - offset), 0))
                    else:
                        # Continuous scroll: old slides out left, new slides in right
                        frame.paste(img_from, (-offset, 0))
                        frame.paste(img_to,   (w - offset, 0))

                elif t in ("swipe_left", "scroll_left"):
                    offset = int(w * frac)
                    if t == "swipe_left":
                        frame.paste(img_from, (0, 0))
                        frame.paste(img_to, (w - offset, 0))
                    else:
                        frame.paste(img_from, (-offset, 0))
                        frame.paste(img_to,   (w - offset, 0))

                elif t in ("swipe_up", "scroll_up"):
                    offset = int(h * frac)
                    if t == "swipe_up":
                        frame.paste(img_from, (0, 0))
                        frame.paste(img_to, (0, h - offset))
                    else:
                        frame.paste(img_from, (0, -offset))
                        frame.paste(img_to,   (0, h - offset))

                elif t in ("swipe_down", "scroll_down"):
                    offset = int(h * (1 - frac))
                    if t == "swipe_down":
                        frame.paste(img_from, (0, 0))
                        frame.paste(img_to, (0, -(h - offset)))
                    else:
                        frame.paste(img_from, (0, offset))
                        frame.paste(img_to,   (0, -(h - offset)))

            self._push_frame(frame)
            time.sleep(delay)

    def render_frame(self) -> Image.Image:
        """Render a single frame and return the image."""
        w = self.driver.width if self.driver else 128
        h = self.driver.height if self.driver else 64
        image = Image.new("1", (w, h), 0)
        draw = ImageDraw.Draw(image)

        with self._lock:
            for widget in self.widgets:
                try:
                    widget.draw(draw)
                except Exception as e:
                    print(f"[Renderer] Widget {widget.WIDGET_ID} error: {e}")

        return image

    def render_and_display(self) -> None:
        """Render a frame, push to hardware AND update preview buffer."""
        image = self.render_frame()

        # Always update the web preview buffer
        self._simulated_driver.display_image(image)

        # Also push to real hardware if available
        if self._hardware_ok and self.driver is not None and not isinstance(self.driver, SimulatedDriver):
            try:
                self.driver.display_image(image)
            except Exception as e:
                print(f"[Renderer] Hardware display error: {e}")

    def get_preview_base64(self, scale: int = 4) -> str:
        """Render and return a base64-encoded preview image."""
        # Render fresh and push to preview buffer
        image = self.render_frame()
        self._simulated_driver.display_image(image)
        return self._simulated_driver.get_framebuffer_base64(scale=scale)

    def start(self) -> None:
        """Start the render loop in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._render_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the render loop."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        if self._hardware_ok and self.driver and not isinstance(self.driver, SimulatedDriver):
            self.driver.shutdown()

    def _render_loop(self) -> None:
        """Main render loop."""
        refresh_rate = self.config_manager.get("refresh_rate", 1.0)
        while self._running:
            try:
                self._maybe_advance_page()
                self.render_and_display()
            except Exception as e:
                print(f"[Renderer] Frame error: {e}")
            time.sleep(refresh_rate)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_simulated(self) -> bool:
        return not self._hardware_ok

    @property
    def hardware_ok(self) -> bool:
        return self._hardware_ok

"""
Display renderer - reads the layout configuration and renders widgets
to the OLED display in a loop.
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

    def __init__(self, config_manager: ConfigManager, simulate: bool = False):
        self.config_manager = config_manager
        self.simulate = simulate
        self.driver: Optional[OLEDDriver] = None
        self.widgets: List[Widget] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._simulated_driver: Optional[SimulatedDriver] = None
        # Track whether hardware init actually succeeded
        self._hardware_ok = False

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

        self._load_widgets()
        return True

    def _load_widgets(self) -> None:
        """Load widgets from the current layout config."""
        layout = self.config_manager.get_layout()
        widget_configs = layout.get("widgets", [])

        self.widgets = []
        for wc in widget_configs:
            widget = WidgetRegistry.create_from_dict(wc)
            if widget is not None:
                self.widgets.append(widget)
            else:
                print(f"[Renderer] Unknown widget: {wc.get('widget_id')}")

    def reload_layout(self) -> None:
        """Reload the layout from config (hot reload)."""
        with self._lock:
            self.config_manager._config = None
            self._load_widgets()

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

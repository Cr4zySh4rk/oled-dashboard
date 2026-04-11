"""
Widget registry - maps widget IDs to classes and provides discovery.
"""

from typing import Dict, List, Optional, Type
from oled_dashboard.widgets.base import Widget
from oled_dashboard.widgets.system_widgets import (
    CPUUsageWidget,
    RAMUsageWidget,
    SwapUsageWidget,
    TemperatureWidget,
    UptimeWidget,
    LoadAverageWidget,
    HostnameWidget,
)
from oled_dashboard.widgets.network_widgets import (
    IPAddressWidget,
    NetworkSpeedWidget,
    NetworkUsageWidget,
)
from oled_dashboard.widgets.storage_widgets import (
    DiskSpaceWidget,
    DiskIOWidget,
)
from oled_dashboard.widgets.static_widgets import (
    StaticTextWidget,
    HLineWidget,
    VLineWidget,
    BoxWidget,
    ProgressBarWidget,
    DateTimeWidget,
)


class WidgetRegistry:
    """Registry of all available widgets."""

    _widgets: Dict[str, Type[Widget]] = {}

    @classmethod
    def _ensure_registered(cls):
        """Register all built-in widgets, plus optional service widgets."""
        if cls._widgets:
            return

        builtin = [
            # System
            CPUUsageWidget,
            RAMUsageWidget,
            SwapUsageWidget,
            TemperatureWidget,
            UptimeWidget,
            LoadAverageWidget,
            HostnameWidget,
            # Network
            IPAddressWidget,
            NetworkSpeedWidget,
            NetworkUsageWidget,
            # Storage
            DiskSpaceWidget,
            DiskIOWidget,
            # General / Static
            StaticTextWidget,
            HLineWidget,
            VLineWidget,
            BoxWidget,
            ProgressBarWidget,
            DateTimeWidget,
        ]
        for w in builtin:
            cls._widgets[w.WIDGET_ID] = w

        # ── Always register Pi-hole widgets ──────────────────────────
        # Widgets are always registered so they appear in the palette.
        # They handle connection errors gracefully at runtime (show 0s /
        # "error" status when Pi-hole is unreachable).
        try:
            from oled_dashboard.widgets.pihole_widgets import PIHOLE_WIDGETS
            for w in PIHOLE_WIDGETS:
                cls._widgets[w.WIDGET_ID] = w
        except ImportError:
            pass  # pihole_widgets module not present — skip silently

        # ── Always register weather widget ────────────────────────────
        try:
            from oled_dashboard.widgets.weather_widgets import WEATHER_WIDGETS
            for w in WEATHER_WIDGETS:
                cls._widgets[w.WIDGET_ID] = w
        except ImportError:
            pass

    @classmethod
    def get_widget_class(cls, widget_id: str) -> Optional[Type[Widget]]:
        """Get a widget class by ID."""
        cls._ensure_registered()
        return cls._widgets.get(widget_id)

    @classmethod
    def create_widget(cls, widget_id: str, **kwargs) -> Optional[Widget]:
        """Create a widget instance by ID."""
        widget_cls = cls.get_widget_class(widget_id)
        if widget_cls is None:
            return None
        return widget_cls(**kwargs)

    @classmethod
    def create_from_dict(cls, data: Dict) -> Optional[Widget]:
        """Create a widget from a serialized dict."""
        widget_id = data.get("widget_id")
        widget_cls = cls.get_widget_class(widget_id)
        if widget_cls is None:
            return None
        return widget_cls.from_dict(data)

    @classmethod
    def list_widgets(cls) -> List[Dict]:
        """List all available widgets with metadata."""
        cls._ensure_registered()
        result = []
        for widget_id, widget_cls in cls._widgets.items():
            instance = widget_cls()
            result.append(instance.get_metadata())
        return result

    @classmethod
    def list_by_category(cls) -> Dict[str, List[Dict]]:
        """List widgets grouped by category."""
        cls._ensure_registered()
        categories = {}
        for widget_id, widget_cls in cls._widgets.items():
            instance = widget_cls()
            meta = instance.get_metadata()
            cat = meta["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(meta)
        return categories

    @classmethod
    def register_widget(cls, widget_class: Type[Widget]) -> None:
        """Register a custom widget."""
        cls._ensure_registered()
        cls._widgets[widget_class.WIDGET_ID] = widget_class

"""
Widget system for dynamic and static OLED content modules.
Each widget is a self-contained unit that can be placed on the display grid.
"""

from oled_dashboard.widgets.base import Widget
from oled_dashboard.widgets.registry import WidgetRegistry

__all__ = ["Widget", "WidgetRegistry"]

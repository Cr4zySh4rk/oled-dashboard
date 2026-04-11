"""
Configuration manager for OLED Dashboard.
Handles loading/saving display settings and layout configurations.
"""

import json
import os
import copy
from typing import Any, Dict, List, Optional

DEFAULT_CONFIG_DIR = os.path.expanduser("~/.config/oled-dashboard")
DEFAULT_CONFIG_FILE = "config.json"

_DEFAULT_WIDGETS = [
    {
        "widget_id": "ip_address",
        "x": 0, "y": 0,
        "width": 128, "height": 14,
        "font_size": 12,
        "config": {"show_label": True},
    },
    {
        "widget_id": "cpu_usage",
        "x": 0, "y": 16,
        "width": 60, "height": 14,
        "font_size": 11,
        "config": {"show_bar": False},
    },
    {
        "widget_id": "temperature",
        "x": 68, "y": 16,
        "width": 60, "height": 14,
        "font_size": 11,
        "config": {"unit": "C"},
    },
    {
        "widget_id": "ram_usage",
        "x": 0, "y": 32,
        "width": 128, "height": 14,
        "font_size": 11,
        "config": {"format": "compact"},
    },
    {
        "widget_id": "disk_space",
        "x": 0, "y": 48,
        "width": 128, "height": 14,
        "font_size": 11,
        "config": {"mount_point": "/", "show_bar": False},
    },
]

DEFAULT_CONFIG = {
    "display": {
        "chip": "SSD1306",
        "width": 128,
        "height": 64,
        "interface": "i2c",
        "i2c_address": "0x3C",
        "i2c_bus": 1,
        "spi_device": 0,
        "spi_dc_pin": 24,
        "spi_reset_pin": 25,
        "spi_cs_pin": 8,
        "rotation": 0,
        "brightness": 255,
        "reset_pin": None,
    },
    # Multi-page layout: up to 3 pages, each with a name and widget list.
    "pages": [
        {"name": "Page 1", "widgets": _DEFAULT_WIDGETS},
    ],
    "page_interval": 5.0,   # seconds between page transitions (0 = no auto-switch)
    "page_transition": "none",  # transition animation: none|diffuse|swipe_right|swipe_left|swipe_up|swipe_down|scroll_left|scroll_right|scroll_up|scroll_down
    # Legacy single-layout key (kept for backward compatibility)
    "layout": {
        "name": "Default",
        "widgets": _DEFAULT_WIDGETS,
    },
    "server": {
        "host": "0.0.0.0",
        "port": 8686,
        "debug": False,
    },
    "refresh_rate": 1.0,
    "saved_layouts": [],
}


class ConfigManager:
    """Manages OLED Dashboard configuration."""

    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = config_dir or DEFAULT_CONFIG_DIR
        self.config_file = os.path.join(self.config_dir, DEFAULT_CONFIG_FILE)
        self._config = None

    def load(self) -> Dict[str, Any]:
        """Load configuration from disk, or create default."""
        if self._config is not None:
            return self._config

        os.makedirs(self.config_dir, exist_ok=True)

        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    self._config = json.load(f)
                # Merge with defaults for any missing keys
                self._config = self._merge_defaults(self._config, DEFAULT_CONFIG)
            except (json.JSONDecodeError, IOError):
                self._config = copy.deepcopy(DEFAULT_CONFIG)
                self.save()
        else:
            self._config = copy.deepcopy(DEFAULT_CONFIG)
            self.save()

        return self._config

    def save(self) -> None:
        """Save current configuration to disk."""
        if self._config is None:
            self._config = copy.deepcopy(DEFAULT_CONFIG)

        os.makedirs(self.config_dir, exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(self._config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by dot-notated key."""
        config = self.load()
        keys = key.split(".")
        for k in keys:
            if isinstance(config, dict):
                config = config.get(k, default)
            else:
                return default
        return config

    def set(self, key: str, value: Any) -> None:
        """Set a config value by dot-notated key."""
        config = self.load()
        keys = key.split(".")
        target = config
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value
        self.save()

    def get_display_config(self) -> Dict[str, Any]:
        return self.load().get("display", {})

    def set_display_config(self, display_config: Dict[str, Any]) -> None:
        config = self.load()
        config["display"] = display_config
        self.save()

    def get_layout(self) -> Dict[str, Any]:
        return self.load().get("layout", {})

    def set_layout(self, layout: Dict[str, Any]) -> None:
        config = self.load()
        config["layout"] = layout
        self.save()

    # ── Multi-page API ────────────────────────────────────────────────────────

    def get_pages(self) -> List[Dict[str, Any]]:
        """Return the list of pages. Migrates from old single-layout format if needed."""
        config = self.load()
        pages = config.get("pages")
        if pages and isinstance(pages, list) and len(pages) > 0:
            return pages
        # Migrate: build pages from the legacy 'layout' key
        layout = config.get("layout", {})
        return [{"name": "Page 1", "widgets": layout.get("widgets", [])}]

    def set_pages(self, pages: List[Dict[str, Any]]) -> None:
        """Save up to 3 pages. Also updates legacy 'layout' key for backward compat."""
        pages = pages[:3]  # enforce max 3 pages
        config = self.load()
        config["pages"] = pages
        # Keep legacy layout in sync with page 1
        if pages:
            config["layout"] = {
                "name": pages[0].get("name", "Page 1"),
                "widgets": pages[0].get("widgets", []),
            }
        self.save()

    def get_page_interval(self) -> float:
        """Return seconds between automatic page transitions (0 = no auto-switch)."""
        return float(self.load().get("page_interval", 5.0))

    def set_page_interval(self, interval: float) -> None:
        config = self.load()
        config["page_interval"] = max(0.0, float(interval))
        self.save()

    def get_page_transition(self) -> str:
        """Return the transition animation name."""
        return self.load().get("page_transition", "none")

    def set_page_transition(self, transition: str) -> None:
        valid = {
            "none", "diffuse", "swipe_right", "swipe_left", "swipe_up", "swipe_down",
            "scroll_left", "scroll_right", "scroll_up", "scroll_down",
        }
        config = self.load()
        config["page_transition"] = transition if transition in valid else "none"
        self.save()

    def import_config(self, data: Dict[str, Any]) -> None:
        """Replace the entire config with imported data. Validates minimally."""
        if not isinstance(data, dict):
            raise ValueError("Config must be a JSON object")
        if "display" not in data:
            raise ValueError("Config missing 'display' key")
        self._config = data
        self.save()

    def save_layout_preset(self, name: str, layout: Dict[str, Any]) -> None:
        """Save a named layout preset."""
        config = self.load()
        presets = config.get("saved_layouts", [])
        # Replace if exists
        presets = [p for p in presets if p.get("name") != name]
        layout_copy = copy.deepcopy(layout)
        layout_copy["name"] = name
        presets.append(layout_copy)
        config["saved_layouts"] = presets
        self.save()

    def list_layout_presets(self) -> List[Dict[str, Any]]:
        """List all saved layout presets."""
        return self.load().get("saved_layouts", [])

    def load_layout_preset(self, name: str) -> Optional[Dict[str, Any]]:
        """Load a named layout preset."""
        for preset in self.list_layout_presets():
            if preset.get("name") == name:
                return preset
        return None

    def delete_layout_preset(self, name: str) -> bool:
        """Delete a named layout preset."""
        config = self.load()
        presets = config.get("saved_layouts", [])
        new_presets = [p for p in presets if p.get("name") != name]
        if len(new_presets) < len(presets):
            config["saved_layouts"] = new_presets
            self.save()
            return True
        return False

    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        self._config = copy.deepcopy(DEFAULT_CONFIG)
        self.save()

    @staticmethod
    def _merge_defaults(config: Dict, defaults: Dict) -> Dict:
        """Recursively merge defaults into config for missing keys."""
        result = copy.deepcopy(defaults)
        for key, value in config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigManager._merge_defaults(value, result[key])
            else:
                result[key] = value
        return result

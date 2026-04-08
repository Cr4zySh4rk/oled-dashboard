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
    "layout": {
        "name": "Default",
        "widgets": [
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
        ],
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

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULT_CONFIG = {
    "movement_keys": {
        "forward": "W",
        "backward": "S",
        "left": "A",
        "right": "D",
    },
    "thresholds": {
        "max_shot_delay": 150.0,
        "min_shot_delay": 0.0,
        "max_cs_time": 100.0,
    },
    "hotkeys": {
        "toggle_visibility": "F6",
        "exit": "F8",
        "increase_size": "=",
        "decrease_size": "-",
    },
    "overlay": {
        "position_x": None,
        "position_y": None,
        "font_size": 10,
    },
}


class Config:
    """Configuration manager for cStrafe UI."""

    def __init__(self, config_path: str = CONFIG_FILE) -> None:
        self._config_path = config_path
        self._config: dict[str, Any] = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from file or create default."""
        if Path(self._config_path).exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                return self._merge_with_defaults(config)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Could not load config file: %s. Using defaults.", e)
                return DEFAULT_CONFIG.copy()
        else:
            self._save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()

    def _merge_with_defaults(self, config: dict[str, Any]) -> dict[str, Any]:
        """Merge loaded config with defaults to ensure all keys exist."""
        merged = DEFAULT_CONFIG.copy()
        for key, value in config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
        return merged

    def _save_config(self, config: dict[str, Any]) -> None:
        """Save configuration to file."""
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    def save(self) -> None:
        """Save current configuration to file."""
        self._save_config(self._config)

    def get(self, *keys: str, default: Any = None) -> Any:
        """Get a nested config value using multiple keys."""
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def set(self, *keys: str, value: Any) -> None:
        """Set a nested config value using multiple keys."""
        config = self._config
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value

    @property
    def movement_keys(self) -> dict[str, str]:
        """Get movement key bindings."""
        return self._config["movement_keys"]

    @property
    def thresholds(self) -> dict[str, float]:
        """Get timing thresholds."""
        return self._config["thresholds"]

    @property
    def hotkeys(self) -> dict[str, str]:
        """Get hotkey bindings."""
        return self._config["hotkeys"]

    @property
    def overlay(self) -> dict[str, Any]:
        """Get overlay settings."""
        return self._config["overlay"]

    def update_overlay_position(self, x: Optional[int], y: Optional[int]) -> None:
        """Update overlay position in config."""
        self.set("overlay", "position_x", value=x)
        self.set("overlay", "position_y", value=y)
        self.save()

    def update_font_size(self, size: int) -> None:
        """Update font size in config."""
        self.set("overlay", "font_size", value=size)
        self.save()

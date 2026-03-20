import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass

CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULT_CONFIG = {
    "movement_keys": {
        "forward": "W",
        "backward": "S",
        "left": "A",
        "right": "D",
    },
    "thresholds": {
        "max_shot_delay": 230.0,
        "min_shot_delay": 0.0,
        "max_cs_time": 215.0,
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
    """Configuration manager for Counter Strafe Practise."""

    def __init__(self, config_path: str | Path = CONFIG_FILE) -> None:
        self._config_path = config_path
        self._config: dict[str, Any] = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from file or create default."""
        if Path(self._config_path).exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                self._validate_config_structure(config)
                return self._merge_with_defaults(config)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Could not load config file: %s. Using defaults.", e)
                return DEFAULT_CONFIG.copy()
            except ConfigValidationError as e:
                logger.warning("Invalid config structure: %s. Using defaults.", e)
                return DEFAULT_CONFIG.copy()
        else:
            self._save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()

    def _get_default_for_path(self, path: str, key: str) -> Any:
        """Get the default value for a nested config key.
        
        Args:
            path: Current path in config hierarchy (e.g., "root" or "root.movement_keys")
            key: The key to look up
            
        Returns:
            The default value for the key, or None if not found
        """
        if path == "root":
            return DEFAULT_CONFIG.get(key)
        
        # Extract nested path from "root.xxx.yyy" -> ["xxx", "yyy"]
        path_parts = path.split(".")[1:]  # Skip "root"
        current = DEFAULT_CONFIG
        for part in path_parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        if isinstance(current, dict):
            return current.get(key)
        return None

    def _validate_config_structure(self, config: dict[str, Any], path: str = "root") -> None:
        """Validate configuration structure and types.
        
        Args:
            config: Configuration dictionary to validate
            path: Current path in config hierarchy (for error messages)
            
        Raises:
            ConfigValidationError: If validation fails
        """
        if not isinstance(config, dict):
            raise ConfigValidationError(f"Expected dict at {path}, got {type(config).__name__}")
        
        for key, value in config.items():
            current_path = f"{path}.{key}"
            
            default_value = self._get_default_for_path(path, key)
            if default_value is None:
                logger.debug("Unknown config key: %s", current_path)
                continue
            
            # Validate type compatibility
            if isinstance(default_value, dict):
                if not isinstance(value, dict):
                    raise ConfigValidationError(
                        f"Expected dict at {current_path}, got {type(value).__name__}"
                    )
                # Recursively validate nested dicts
                self._validate_config_structure(value, current_path)
            elif isinstance(default_value, str):
                if not isinstance(value, str):
                    raise ConfigValidationError(
                        f"Expected str at {current_path}, got {type(value).__name__}"
                    )
            elif isinstance(default_value, (int, float)):
                if not isinstance(value, (int, float)):
                    raise ConfigValidationError(
                        f"Expected number at {current_path}, got {type(value).__name__}"
                    )
            elif default_value is None:
                # Allow any type for None defaults (e.g., position_x, position_y)
                pass
            else:
                # For other types, check exact type match
                if not isinstance(value, type(default_value)):
                    raise ConfigValidationError(
                        f"Expected {type(default_value).__name__} at {current_path}, got {type(value).__name__}"
                    )

    def _merge_with_defaults(self, config: dict[str, Any], default: dict[str, Any] = DEFAULT_CONFIG) -> dict[str, Any]:
        """Merge loaded config with defaults to ensure all keys exist."""
        merged = default.copy()
        for key, value in config.items():
            if key in merged:
                if isinstance(merged[key], dict) and isinstance(value, dict):
                    merged[key] = self._merge_with_defaults(value, merged[key])
                elif isinstance(value, type(merged[key])) or (isinstance(merged[key], float) and isinstance(value, (int, float))):
                    merged[key] = value
                elif merged[key] is None:
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
        
        # Validate the value type against default config
        default_config = DEFAULT_CONFIG
        for key in keys[:-1]:
            if key in default_config and isinstance(default_config[key], dict):
                default_config = default_config[key]
            else:
                break
        
        if keys[-1] in default_config:
            expected_type = type(default_config[keys[-1]])
            if expected_type is not type(None) and not isinstance(value, expected_type):
                # Allow int to be set as float
                if not (expected_type is float and isinstance(value, int)):
                    logger.warning(
                        "Type mismatch for %s: expected %s, got %s",
                        ".".join(keys),
                        expected_type.__name__,
                        type(value).__name__
                    )
        
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

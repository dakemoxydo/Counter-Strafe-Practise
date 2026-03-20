"""Shared constants and utility functions for Counter Strafe Practise."""

from typing import Dict, List

# Project name
PROJECT_NAME: str = "Counter Strafe Practise"
PROJECT_NAME_SHORT: str = "CSP"

# Label formatting constants
DOT_LABELS: Dict[str, str] = {
    "Counter\u2011strafe": "[CS]",
    "Overlap": "[OL]",
    "Bad": "[BD]",
}
"""Mapping of classification labels to short dot indicators."""

DEFAULT_DOT_LABEL: str = "[??]"
"""Default indicator for unknown labels."""

# Overlay animation constants
FADE_STEPS: int = 40
"""Number of steps for fade animation."""

FADE_DELAY_MS: int = 25
"""Delay in milliseconds between fade animation steps."""

FADE_START_DELAY_MS: int = 800
"""Delay in milliseconds before fade animation starts."""

# Statistics constants
MAX_RECENT_HISTORY: int = 20
"""Maximum number of recent classification labels to store in history."""


# ============================================================
# DESIGN CONSTANTS - Color Palette (Dark Theme with Accents)
# ============================================================

class Colors:
    """Color palette for the application."""

    # Background colors
    BG_DARK: str = "#0d1117"
    BG_MEDIUM: str = "#161b22"
    BG_LIGHT: str = "#21262d"
    BG_CARD: str = "#1c2128"

    # Text colors
    TEXT_PRIMARY: str = "#e6edf3"
    TEXT_SECONDARY: str = "#8b949e"
    TEXT_MUTED: str = "#484f58"

    # Accent colors
    ACCENT_PRIMARY: str = "#58a6ff"
    ACCENT_SUCCESS: str = "#238636"
    ACCENT_WARNING: str = "#d29922"
    ACCENT_DANGER: str = "#f85149"

    # Classification colors (brighter, more vibrant)
    CLASS_COUNTER_STRAFE: str = "#3fb950"
    CLASS_OVERLAP: str = "#f0883e"
    CLASS_BAD: str = "#f85149"

    # Border colors
    BORDER_COLOR: str = "#30363d"
    BORDER_HIGHLIGHT: str = "#484f58"

    # Gradient colors for headers
    HEADER_GRADIENT_START: str = "#1f6feb"
    HEADER_GRADIENT_END: str = "#388bfd"


class Fonts:
    """Font settings for the application."""

    # Font families
    FONT_MONO: str = "Consolas"
    FONT_SANS: str = "Segoe UI"

    # Font sizes
    FONT_SIZE_TINY: int = 10
    FONT_SIZE_SMALL: int = 12
    FONT_SIZE_NORMAL: int = 14
    FONT_SIZE_LARGE: int = 16
    FONT_SIZE_XLARGE: int = 20
    FONT_SIZE_TITLE: int = 24
    FONT_SIZE_HEADER: int = 28


class Spacing:
    """Spacing constants for layout."""

    PADDING_TINY: int = 4
    PADDING_SMALL: int = 8
    PADDING_MEDIUM: int = 16
    PADDING_LARGE: int = 24
    PADDING_XLARGE: int = 32

    MARGIN_TINY: int = 4
    MARGIN_SMALL: int = 8
    MARGIN_MEDIUM: int = 16
    MARGIN_LARGE: int = 24

    BORDER_RADIUS_SMALL: int = 4
    BORDER_RADIUS_MEDIUM: int = 8
    BORDER_RADIUS_LARGE: int = 12


class OverlayConfig:
    """Overlay-specific design constants."""

    # Transparency
    OVERLAY_ALPHA: float = 0.95

    # Default sizes
    DEFAULT_FONT_SIZE: int = 12
    HEADER_FONT_SIZE: int = 14
    BODY_FONT_SIZE: int = 12
    HISTORY_FONT_SIZE: int = 10

    # Fixed window dimensions (width x height)
    WINDOW_WIDTH: int = 200
    WINDOW_HEIGHT: int = 120

    # Min/Max font sizes
    MIN_FONT_SIZE: int = 8
    MAX_FONT_SIZE: int = 24
    FONT_SIZE_STEP: int = 2

    # Padding
    OVERLAY_PADDING_X: int = 12
    OVERLAY_PADDING_Y: int = 8

    # Animation
    FADE_ANIMATION_DURATION: int = 1000  # ms
    FADE_ANIMATION_STEPS: int = 30


class DashboardConfig:
    """Dashboard-specific design constants."""

    # Window
    WINDOW_WIDTH: int = 650
    WINDOW_HEIGHT: int = 500
    WINDOW_MIN_WIDTH: int = 550
    WINDOW_MIN_HEIGHT: int = 450

    # Header
    HEADER_HEIGHT: int = 60

    # Tab padding
    TAB_PADDING: int = 20

    # Button sizes
    BUTTON_HEIGHT: int = 45
    BUTTON_WIDTH: int = 200

    # Progress bar
    PROGRESS_BAR_HEIGHT: int = 8
    PROGRESS_BAR_WIDTH: int = 200


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def format_history_dots(history: List[str], max_items: int = 10) -> str:
    """Format classification history as a string of dot indicators.

    Args:
        history: List of classification labels
        max_items: Maximum number of recent items to include (default: 10)

    Returns:
        Formatted string of dot indicators (e.g., "[CS][OL][BD]")
    """
    return "".join(DOT_LABELS.get(lbl, DEFAULT_DOT_LABEL) for lbl in history[-max_items:])


def get_classification_color(label: str) -> str:
    """Get the color associated with a classification label.

    Args:
        label: Classification label string

    Returns:
        Hex color string for the label
    """
    colors = {
        "Counter\u2011strafe": Colors.CLASS_COUNTER_STRAFE,
        "Overlap": Colors.CLASS_OVERLAP,
        "Bad": Colors.CLASS_BAD,
    }
    return colors.get(label, Colors.TEXT_MUTED)

import logging
import threading
from typing import Dict, Optional, Tuple

import customtkinter as ctk

from config import Config
from constants import (
    Colors,
    DashboardConfig,
    Fonts,
    PROJECT_NAME,
    Spacing,
    get_classification_color,
)
from constants import DOT_LABELS, format_history_dots
from input_events import InputListener
from overlay import Overlay
from statistics import StatisticsManager

logger = logging.getLogger(__name__)


class Dashboard(ctk.CTk):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.stats = StatisticsManager()
        self.overlay: Optional[Overlay] = None
        self.listener: Optional[InputListener] = None

        # Configure appearance
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("dark-blue")

        self.title(f"{PROJECT_NAME} - Dashboard")
        self.geometry(f"{DashboardConfig.WINDOW_WIDTH}x{DashboardConfig.WINDOW_HEIGHT}")
        self.minsize(DashboardConfig.WINDOW_MIN_WIDTH, DashboardConfig.WINDOW_MIN_HEIGHT)

        # Configure grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Build UI
        self._build_header()
        self._build_tabs()

        # Update stats UI periodically
        self._update_stats_ui()

    def _build_header(self):
        """Build the header with project title."""
        # Header frame
        header_frame = ctk.CTkFrame(self, fg_color=Colors.BG_LIGHT, corner_radius=0)
        header_frame.grid(row=0, column=0, sticky="ew")

        # Configure header grid
        header_frame.grid_columnconfigure(1, weight=1)
        header_frame.grid_rowconfigure(0, weight=1)

        # Icon/Label
        icon_label = ctk.CTkLabel(
            header_frame,
            text="🎯",
            font=ctk.CTkFont(size=24),
        )
        icon_label.grid(row=0, column=0, padx=(20, 10), pady=15)

        # Title
        title_label = ctk.CTkLabel(
            header_frame,
            text=PROJECT_NAME,
            font=ctk.CTkFont(size=Fonts.FONT_SIZE_TITLE, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        )
        title_label.grid(row=0, column=1, padx=10, pady=15, sticky="w")

        # Subtitle
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Counter-Strafing Practice Tool",
            font=ctk.CTkFont(size=Fonts.FONT_SIZE_SMALL),
            text_color=Colors.TEXT_SECONDARY,
        )
        subtitle_label.grid(row=0, column=2, padx=(0, 20), pady=15, sticky="e")

    def _build_tabs(self):
        """Build the tab view with all tabs."""
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=Colors.BG_MEDIUM,
            border_color=Colors.BORDER_COLOR,
            border_width=1,
        )
        self.tabview.grid(row=1, column=0, padx=Spacing.MARGIN_MEDIUM, pady=Spacing.MARGIN_MEDIUM, sticky="nsew")

        self.tabview.add("Control")
        self.tabview.add("Statistics")
        self.tabview.add("Settings")

        self.tabview.set("Control")

        self._build_control_tab()
        self._build_stats_tab()
        self._build_settings_tab()

    def _build_control_tab(self):
        """Build the control/overlay tab."""
        tab = self.tabview.tab("Control")
        tab.grid_columnconfigure(0, weight=1)

        # Status card
        status_card = ctk.CTkFrame(tab, fg_color=Colors.BG_CARD, corner_radius=12)
        status_card.grid(row=0, column=0, pady=(30, 20), padx=20, sticky="ew")
        status_card.grid_columnconfigure(0, weight=1)

        # Status icon
        self.status_icon = ctk.CTkLabel(
            status_card,
            text="⏹",
            font=ctk.CTkFont(size=40),
            text_color=Colors.ACCENT_DANGER,
        )
        self.status_icon.grid(row=0, column=0, pady=(20, 10))

        # Status label
        self.status_label = ctk.CTkLabel(
            status_card,
            text="Overlay Status: STOPPED",
            font=ctk.CTkFont(size=Fonts.FONT_SIZE_LARGE, weight="bold"),
            text_color=Colors.ACCENT_DANGER,
        )
        self.status_label.grid(row=1, column=0, pady=5)

        # Status description
        status_desc = ctk.CTkLabel(
            status_card,
            text="Click below to start monitoring your strafing",
            font=ctk.CTkFont(size=Fonts.FONT_SIZE_SMALL),
            text_color=Colors.TEXT_SECONDARY,
        )
        status_desc.grid(row=2, column=0, pady=(0, 15))

        # Start/Stop button
        self.start_btn = ctk.CTkButton(
            tab,
            text="▶  Start Overlay",
            font=ctk.CTkFont(size=Fonts.FONT_SIZE_NORMAL, weight="bold"),
            height=DashboardConfig.BUTTON_HEIGHT,
            fg_color=Colors.ACCENT_SUCCESS,
            hover_color="#1a6328",
            command=self.toggle_overlay,
        )
        self.start_btn.grid(row=1, column=0, pady=20)

        # Hotkey info card
        hotkey_card = ctk.CTkFrame(tab, fg_color=Colors.BG_CARD, corner_radius=12)
        hotkey_card.grid(row=2, column=0, pady=20, padx=20, sticky="ew")
        hotkey_card.grid_columnconfigure((0, 1), weight=1)

        hotkey_title = ctk.CTkLabel(
            hotkey_card,
            text="Keyboard Shortcuts",
            font=ctk.CTkFont(size=Fonts.FONT_SIZE_NORMAL, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        )
        hotkey_title.grid(row=0, column=0, columnspan=2, pady=(15, 10))

        hotkeys = [
            ("F6", "Toggle Overlay"),
            ("F8", "Exit Program"),
            ("=", "Increase Size"),
            ("-", "Decrease Size"),
        ]

        for i, (key, action) in enumerate(hotkeys):
            row = (i // 2) + 1
            col = (i % 2)

            key_label = ctk.CTkLabel(
                hotkey_card,
                text=key,
                font=ctk.CTkFont(size=Fonts.FONT_SIZE_NORMAL, weight="bold"),
                text_color=Colors.ACCENT_PRIMARY,
                fg_color=Colors.BG_LIGHT,
                corner_radius=4,
            )
            key_label.grid(row=row, column=col, padx=15, pady=8)

            action_label = ctk.CTkLabel(
                hotkey_card,
                text=action,
                font=ctk.CTkFont(size=Fonts.FONT_SIZE_SMALL),
                text_color=Colors.TEXT_SECONDARY,
            )
            action_label.grid(row=row, column=col, padx=(40 if col == 0 else 10), pady=5, sticky="w" if col == 0 else "")

    def _build_stats_tab(self):
        """Build the statistics tab with improved design."""
        tab = self.tabview.tab("Statistics")
        tab.grid_columnconfigure(0, weight=1)

        self.stats_labels = {}

        # Stats card
        stats_card = ctk.CTkFrame(tab, fg_color=Colors.BG_CARD, corner_radius=12)
        stats_card.grid(row=0, column=0, pady=20, padx=20, sticky="ew")
        stats_card.grid_columnconfigure(0, weight=1)
        stats_card.grid_columnconfigure(1, weight=1)

        # Title
        stats_title = ctk.CTkLabel(
            stats_card,
            text="Session Statistics",
            font=ctk.CTkFont(size=Fonts.FONT_SIZE_LARGE, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        )
        stats_title.grid(row=0, column=0, columnspan=2, pady=(15, 20))

        # Stats headers with values
        headers = [
            ("Accuracy", "accuracy", "%"),
            ("Total Shots", "total_shots", ""),
            ("Avg CS Time", "avg_cs_time", " ms"),
            ("Avg Shot Delay", "avg_shot_delay", " ms"),
        ]

        for i, (text, key, unit) in enumerate(headers):
            row = (i // 2) + 1

            # Label
            label = ctk.CTkLabel(
                stats_card,
                text=text,
                font=ctk.CTkFont(size=Fonts.FONT_SIZE_SMALL),
                text_color=Colors.TEXT_SECONDARY,
            )
            label.grid(row=row, column=0 if i % 2 == 0 else 1, pady=5, padx=(20, 10), sticky="e" if i % 2 == 0 else "w")

            # Value
            value = ctk.CTkLabel(
                stats_card,
                text=f"0{unit}",
                font=ctk.CTkFont(size=Fonts.FONT_SIZE_LARGE, weight="bold"),
                text_color=Colors.TEXT_PRIMARY,
            )
            value.grid(row=row, column=0 if i % 2 == 0 else 1, pady=5, padx=(10, 20), sticky="w" if i % 2 == 0 else "e")
            self.stats_labels[key] = (value, unit)

        # Accuracy progress bar
        self.accuracy_progress = ctk.CTkProgressBar(
            stats_card,
            progress_color=Colors.ACCENT_SUCCESS,
            fg_color=Colors.BG_LIGHT,
            height=DashboardConfig.PROGRESS_BAR_HEIGHT,
        )
        self.accuracy_progress.grid(row=5, column=0, columnspan=2, padx=20, pady=(15, 5))
        self.accuracy_progress.set(0)

        self.accuracy_label = ctk.CTkLabel(
            stats_card,
            text="0% Accuracy",
            font=ctk.CTkFont(size=Fonts.FONT_SIZE_SMALL),
            text_color=Colors.TEXT_SECONDARY,
        )
        self.accuracy_label.grid(row=6, column=0, columnspan=2, pady=(0, 15))

        # History section
        history_card = ctk.CTkFrame(tab, fg_color=Colors.BG_CARD, corner_radius=12)
        history_card.grid(row=1, column=0, pady=(0, 20), padx=20, sticky="ew")
        history_card.grid_columnconfigure(0, weight=1)

        history_title = ctk.CTkLabel(
            history_card,
            text="Recent History",
            font=ctk.CTkFont(size=Fonts.FONT_SIZE_NORMAL, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        )
        history_title.grid(row=0, column=0, pady=(15, 10))

        self.history_dots = ctk.CTkLabel(
            history_card,
            text="[--][--][--][--][--][--][--][--][--][--]",
            font=ctk.CTkFont(size=Fonts.FONT_SIZE_LARGE, weight="bold"),
            text_color=Colors.TEXT_MUTED,
        )
        self.history_dots.grid(row=1, column=0, pady=(0, 15))

        # Reset button
        self.reset_btn = ctk.CTkButton(
            tab,
            text="↻  Reset Statistics",
            command=self.reset_stats,
            fg_color=Colors.ACCENT_DANGER,
            hover_color="#b82a2a",
            height=40,
        )
        self.reset_btn.grid(row=2, column=0, pady=(0, 20))

    def reset_stats(self):
        """Reset session statistics."""
        self.stats.reset_session()
        self._refresh_stats_display()

    def _update_stats_ui(self):
        """Periodically update statistics display."""
        self._refresh_stats_display()
        self.after(1000, self._update_stats_ui)

    def _refresh_stats_display(self) -> None:
        """Refresh the statistics display."""
        # Update numeric values
        self.stats_labels["accuracy"][0].configure(
            text=f"{self.stats.accuracy:.1f}{self.stats_labels['accuracy'][1]}"
        )
        self.stats_labels["total_shots"][0].configure(
            text=f"{self.stats.data.total_shots}{self.stats_labels['total_shots'][1]}"
        )
        self.stats_labels["avg_cs_time"][0].configure(
            text=f"{self.stats.avg_cs_time:.1f}{self.stats_labels['avg_cs_time'][1]}"
        )
        self.stats_labels["avg_shot_delay"][0].configure(
            text=f"{self.stats.avg_shot_delay:.1f}{self.stats_labels['avg_shot_delay'][1]}"
        )

        # Update progress bar
        accuracy = self.stats.accuracy / 100.0
        self.accuracy_progress.set(accuracy)

        # Update progress bar color based on accuracy
        if self.stats.accuracy >= 70:
            progress_color = Colors.ACCENT_SUCCESS
        elif self.stats.accuracy >= 40:
            progress_color = Colors.ACCENT_WARNING
        else:
            progress_color = Colors.ACCENT_DANGER
        self.accuracy_progress.configure(progress_color=progress_color)
        self.accuracy_label.configure(
            text=f"{self.stats.accuracy:.1f}% Accuracy",
            text_color=progress_color,
        )

        # Update history dots
        dots = format_history_dots(self.stats.data.recent_history)
        last_label: Optional[str] = (
            self.stats.data.recent_history[-1] if self.stats.data.recent_history else None
        )
        dot_color = get_classification_color(last_label) if last_label else Colors.TEXT_MUTED
        self.history_dots.configure(text=dots, text_color=dot_color)

    def _build_settings_tab(self):
        """Build the settings tab."""
        tab = self.tabview.tab("Settings")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(
            tab,
            fg_color="transparent",
            scrollbar_button_color=Colors.BG_LIGHT,
            scrollbar_button_hover_color=Colors.BORDER_HIGHLIGHT,
        )
        scroll.grid(row=0, column=0, sticky="nsew", padx=Spacing.MARGIN_SMALL, pady=Spacing.MARGIN_SMALL)

        # Variables
        self.var_fwd = ctk.StringVar(value=self.config.movement_keys.get("forward", "W"))
        self.var_bwd = ctk.StringVar(value=self.config.movement_keys.get("backward", "S"))
        self.var_left = ctk.StringVar(value=self.config.movement_keys.get("left", "A"))
        self.var_right = ctk.StringVar(value=self.config.movement_keys.get("right", "D"))

        self.var_min_shot = ctk.IntVar(value=int(self.config.thresholds.get("min_shot_delay", 0.0)))
        self.var_max_shot = ctk.IntVar(value=int(self.config.thresholds.get("max_shot_delay", 150.0)))
        self.var_max_cs = ctk.IntVar(value=int(self.config.thresholds.get("max_cs_time", 100.0)))

        # Category: Keys
        keys_lbl = ctk.CTkLabel(
            scroll,
            text="🎮 Movement Keys",
            font=ctk.CTkFont(size=Fonts.FONT_SIZE_LARGE, weight="bold"),
        )
        keys_lbl.grid(row=0, column=0, sticky="w", pady=(Spacing.MARGIN_MEDIUM, Spacing.MARGIN_SMALL))

        keys_frame = ctk.CTkFrame(scroll, fg_color=Colors.BG_CARD, corner_radius=8)
        keys_frame.grid(row=1, column=0, sticky="ew", pady=(0, Spacing.MARGIN_MEDIUM))

        for i, (label, var) in enumerate(
            [
                ("Forward", self.var_fwd),
                ("Backward", self.var_bwd),
                ("Left", self.var_left),
                ("Right", self.var_right),
            ]
        ):
            ctk.CTkLabel(
                keys_frame,
                text=label,
                text_color=Colors.TEXT_SECONDARY,
            ).grid(row=i, column=0, padx=15, pady=8, sticky="e")
            ctk.CTkEntry(
                keys_frame,
                textvariable=var,
                width=60,
                fg_color=Colors.BG_LIGHT,
                border_color=Colors.BORDER_COLOR,
            ).grid(row=i, column=1, padx=15, pady=8, sticky="w")

        # Category: Thresholds
        thresh_lbl = ctk.CTkLabel(
            scroll,
            text="⚙️ Classification Thresholds (ms)",
            font=ctk.CTkFont(size=Fonts.FONT_SIZE_LARGE, weight="bold"),
        )
        thresh_lbl.grid(row=2, column=0, sticky="w", pady=(Spacing.MARGIN_MEDIUM, Spacing.MARGIN_SMALL))

        thresh_frame = ctk.CTkFrame(scroll, fg_color=Colors.BG_CARD, corner_radius=8)
        thresh_frame.grid(row=3, column=0, sticky="ew", pady=(0, Spacing.MARGIN_MEDIUM))

        def add_slider(row, text, var, from_, to_):
            ctk.CTkLabel(
                thresh_frame,
                text=text,
                text_color=Colors.TEXT_SECONDARY,
            ).grid(row=row, column=0, padx=15, sticky="e")
            val_lbl = ctk.CTkLabel(
                thresh_frame,
                text=f"{var.get()} ms",
                width=60,
                text_color=Colors.TEXT_PRIMARY,
            )
            val_lbl.grid(row=row, column=2, padx=15)

            def on_change(v, l=val_lbl, vr=var):
                l.configure(text=f"{int(float(v))} ms")
                vr.set(int(float(v)))

            slider = ctk.CTkSlider(
                thresh_frame,
                from_=from_,
                to=to_,
                variable=var,
                command=on_change,
                fg_color=Colors.BG_LIGHT,
                progress_color=Colors.ACCENT_PRIMARY,
            )
            slider.grid(row=row, column=1, padx=10, pady=10)

        add_slider(0, "Min Shot Delay", self.var_min_shot, 0, 100)
        add_slider(1, "Max Shot Delay", self.var_max_shot, 50, 300)
        add_slider(2, "Max CS Time", self.var_max_cs, 0, 300)

        # Save Button
        save_btn = ctk.CTkButton(
            scroll,
            text="💾 Save & Apply",
            command=self.save_settings,
            fg_color=Colors.ACCENT_PRIMARY,
            hover_color="#4090e0",
            height=45,
            font=ctk.CTkFont(size=Fonts.FONT_SIZE_NORMAL, weight="bold"),
        )
        save_btn.grid(row=4, column=0, pady=Spacing.MARGIN_LARGE)

    def _validate_key(self, raw: str, default: str) -> str:
        """Validate movement key input."""
        s = raw.strip()
        if len(s) == 1 and s.isalnum():
            return s.upper()
        logger.warning("Invalid key '%s', falling back to '%s'.", raw, default)
        return default

    def save_settings(self):
        """Save and apply settings."""
        fwd = self.var_fwd.get().strip().upper()
        bwd = self.var_bwd.get().strip().upper()
        left = self.var_left.get().strip().upper()
        right = self.var_right.get().strip().upper()

        val_fwd = self._validate_key(fwd, "W")
        val_bwd = self._validate_key(bwd, "S")
        val_left = self._validate_key(left, "A")
        val_right = self._validate_key(right, "D")

        self.config.set("movement_keys", "forward", value=val_fwd)
        self.config.set("movement_keys", "backward", value=val_bwd)
        self.config.set("movement_keys", "left", value=val_left)
        self.config.set("movement_keys", "right", value=val_right)

        self.var_fwd.set(val_fwd)
        self.var_bwd.set(val_bwd)
        self.var_left.set(val_left)
        self.var_right.set(val_right)

        self.config.set("thresholds", "min_shot_delay", value=float(self.var_min_shot.get()))
        self.config.set("thresholds", "max_shot_delay", value=float(self.var_max_shot.get()))
        self.config.set("thresholds", "max_cs_time", value=float(self.var_max_cs.get()))

        self.config.save()

        # Restart overlay if running to apply changes
        if self.listener is not None:
            self.toggle_overlay()  # stops
            self.toggle_overlay()  # starts with new config

    def toggle_overlay(self):
        """Toggle the overlay on/off."""
        if self.listener is None:
            # Start
            self.overlay = Overlay(self.config, master=self)
            self.listener = InputListener(self.overlay, self.config, self.stats)
            self.listener.start()

            self.status_label.configure(text="Overlay Status: RUNNING", text_color=Colors.ACCENT_SUCCESS)
            self.status_icon.configure(text="▶", text_color=Colors.ACCENT_SUCCESS)
            self.start_btn.configure(text="⏹  Stop Overlay", fg_color=Colors.ACCENT_DANGER, hover_color="#b82a2a")
        else:
            # Stop
            self.listener.stop()
            self.listener = None
            if self.overlay:
                self.overlay.terminate()
            self.overlay = None

            self.status_label.configure(text="Overlay Status: STOPPED", text_color=Colors.ACCENT_DANGER)
            self.status_icon.configure(text="⏹", text_color=Colors.ACCENT_DANGER)
            self.start_btn.configure(text="▶  Start Overlay", fg_color=Colors.ACCENT_SUCCESS, hover_color="#1a6328")

    def on_closing(self):
        """Clean up and close the application."""
        if self.listener:
            self.listener.stop()
            self.listener = None
        if self.overlay:
            self.overlay.terminate()
            self.overlay = None
        self.destroy()

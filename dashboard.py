import logging
import threading
from typing import Optional

import customtkinter as ctk

from config import Config
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

        self.title("CS2 Strafe UI - Dashboard")
        self.geometry("600x450")
        self.minsize(500, 400)

        # Main layout
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        self.tabview.add("Control")
        self.tabview.add("Statistics")
        self.tabview.add("Settings")

        self.tabview.set("Control")

        self._build_control_tab()
        self._build_stats_tab()
        self._build_settings_tab()

        # Update stats UI periodically
        self._update_stats_ui()

    def _build_control_tab(self):
        tab = self.tabview.tab("Control")
        tab.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            tab, text="Overlay Status: STOPPED", font=ctk.CTkFont(size=20, weight="bold"), text_color="red"
        )
        self.status_label.grid(row=0, column=0, pady=(40, 20))

        self.start_btn = ctk.CTkButton(
            tab, text="Start Overlay", font=ctk.CTkFont(size=16), height=50, command=self.toggle_overlay
        )
        self.start_btn.grid(row=1, column=0, pady=20)

    def _build_stats_tab(self):
        tab = self.tabview.tab("Statistics")
        tab.grid_columnconfigure(0, weight=1)

        self.stats_labels = {}
        
        # Headers
        headers = [
            ("Accuracy:", "accuracy", "%"),
            ("Total Shots:", "total_shots", ""),
            ("Avg CS Time:", "avg_cs_time", " ms"),
            ("Avg Shot Delay:", "avg_shot_delay", " ms"),
        ]
        
        for i, (text, key, unit) in enumerate(headers):
            title = ctk.CTkLabel(tab, text=text, font=ctk.CTkFont(size=16, weight="bold"))
            title.grid(row=i, column=0, pady=5, padx=10, sticky="e")
            
            value = ctk.CTkLabel(tab, text=f"0{unit}", font=ctk.CTkFont(size=16))
            value.grid(row=i, column=1, pady=5, padx=10, sticky="w")
            self.stats_labels[key] = (value, unit)

        self.history_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self.history_frame.grid(row=len(headers), column=0, columnspan=2, pady=20)
        
        self.history_title = ctk.CTkLabel(self.history_frame, text="Recent History:")
        self.history_title.pack(side="left", padx=5)
        
        self.history_dots = ctk.CTkLabel(self.history_frame, text="", font=ctk.CTkFont(size=20))
        self.history_dots.pack(side="left", padx=5)

        self.reset_btn = ctk.CTkButton(tab, text="Reset Stats", command=self.reset_stats, fg_color="darkred", hover_color="red")
        self.reset_btn.grid(row=len(headers)+1, column=0, columnspan=2, pady=20)

    def reset_stats(self):
        self.stats.reset_session()
        self._refresh_stats_display()

    def _update_stats_ui(self):
        self._refresh_stats_display()
        self.after(1000, self._update_stats_ui)

    def _refresh_stats_display(self):
        self.stats_labels["accuracy"][0].configure(text=f"{self.stats.accuracy:.1f}{self.stats_labels['accuracy'][1]}")
        self.stats_labels["total_shots"][0].configure(text=f"{self.stats.data.total_shots}{self.stats_labels['total_shots'][1]}")
        self.stats_labels["avg_cs_time"][0].configure(text=f"{self.stats.avg_cs_time:.1f}{self.stats_labels['avg_cs_time'][1]}")
        self.stats_labels["avg_shot_delay"][0].configure(text=f"{self.stats.avg_shot_delay:.1f}{self.stats_labels['avg_shot_delay'][1]}")
        
        colors = {"Counter\u2011strafe": "🟢", "Overlap": "🟡", "Bad": "🔴"}
        dots = "".join(colors.get(lbl, "⚪") for lbl in self.stats.data.recent_history)
        self.history_dots.configure(text=dots)

    def _build_settings_tab(self):
        tab = self.tabview.tab("Settings")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab)
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Variables
        self.var_fwd = ctk.StringVar(value=self.config.movement_keys.get("forward", "W"))
        self.var_bwd = ctk.StringVar(value=self.config.movement_keys.get("backward", "S"))
        self.var_left = ctk.StringVar(value=self.config.movement_keys.get("left", "A"))
        self.var_right = ctk.StringVar(value=self.config.movement_keys.get("right", "D"))

        self.var_min_shot = ctk.IntVar(value=int(self.config.thresholds.get("min_shot_delay", 0.0)))
        self.var_max_shot = ctk.IntVar(value=int(self.config.thresholds.get("max_shot_delay", 150.0)))
        self.var_max_cs = ctk.IntVar(value=int(self.config.thresholds.get("max_cs_time", 100.0)))

        # Category: Keys
        keys_lbl = ctk.CTkLabel(scroll, text="Movement Keys", font=ctk.CTkFont(size=16, weight="bold"))
        keys_lbl.grid(row=0, column=0, sticky="w", pady=(10, 5))
        
        keys_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        keys_frame.grid(row=1, column=0, sticky="ew")
        
        for i, (label, var) in enumerate([("Forward", self.var_fwd), ("Backward", self.var_bwd), ("Left", self.var_left), ("Right", self.var_right)]):
            ctk.CTkLabel(keys_frame, text=label).grid(row=i, column=0, padx=5, pady=2, sticky="e")
            ctk.CTkEntry(keys_frame, textvariable=var, width=50).grid(row=i, column=1, padx=5, pady=2, sticky="w")

        # Category: Thresholds
        thresh_lbl = ctk.CTkLabel(scroll, text="Classification Thresholds (ms)", font=ctk.CTkFont(size=16, weight="bold"))
        thresh_lbl.grid(row=2, column=0, sticky="w", pady=(20, 5))
        
        thresh_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        thresh_frame.grid(row=3, column=0, sticky="ew")

        def add_slider(row, text, var, from_, to_):
            ctk.CTkLabel(thresh_frame, text=text).grid(row=row, column=0, padx=5, sticky="e")
            val_lbl = ctk.CTkLabel(thresh_frame, text=f"{var.get()} ms", width=50)
            val_lbl.grid(row=row, column=2, padx=5)
            
            def on_change(v, l=val_lbl, vr=var):
                l.configure(text=f"{int(float(v))} ms")
                vr.set(int(float(v)))
                
            slider = ctk.CTkSlider(thresh_frame, from_=from_, to=to_, variable=var, command=on_change)
            slider.grid(row=row, column=1, padx=10, pady=10)

        add_slider(0, "Min Shot Delay", self.var_min_shot, 0, 100)
        add_slider(1, "Max Shot Delay", self.var_max_shot, 100, 300)
        add_slider(2, "Max CS Time", self.var_max_cs, 0, 200)

        # Save Button
        save_btn = ctk.CTkButton(scroll, text="Save & Apply", command=self.save_settings, fg_color="green", hover_color="darkgreen")
        save_btn.grid(row=4, column=0, pady=30)

    def save_settings(self):
        # Update config
        self.config.set("movement_keys", "forward", self.var_fwd.get().upper()[:1])
        self.config.set("movement_keys", "backward", self.var_bwd.get().upper()[:1])
        self.config.set("movement_keys", "left", self.var_left.get().upper()[:1])
        self.config.set("movement_keys", "right", self.var_right.get().upper()[:1])

        self.config.set("thresholds", "min_shot_delay", float(self.var_min_shot.get()))
        self.config.set("thresholds", "max_shot_delay", float(self.var_max_shot.get()))
        self.config.set("thresholds", "max_cs_time", float(self.var_max_cs.get()))
        
        self.config.save()
        
        # Restart overlay if running to apply changes
        if self.listener is not None:
            self.toggle_overlay() # stops
            self.toggle_overlay() # starts with new config

    def toggle_overlay(self):
        if self.listener is None:
            # Start
            self.overlay = Overlay(self.config, master=self)
            self.listener = InputListener(self.overlay, self.config, self.stats)
            self.listener.start()
            
            self.status_label.configure(text="Overlay Status: RUNNING", text_color="green")
            self.start_btn.configure(text="Stop Overlay")
        else:
            # Stop
            self.listener.stop()
            self.listener = None
            self.overlay = None
            
            self.status_label.configure(text="Overlay Status: STOPPED", text_color="red")
            self.start_btn.configure(text="Start Overlay")

    def on_closing(self):
        if self.listener:
            self.listener.stop()
        self.destroy()


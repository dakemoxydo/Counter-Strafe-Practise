import tkinter as tk
from typing import List, Optional

from classifier import (
    LABEL_BAD,
    LABEL_COUNTER_STRAFE,
    LABEL_OVERLAP,
    ShotClassification,
)
from config import Config


class Overlay:
    def __init__(self, config: Optional[Config] = None, master: Optional[tk.Misc] = None) -> None:
        self.config = config if config is not None else Config()

        try:
            self.root = tk.Toplevel(master) if master is not None else tk.Tk()
        except tk.TclError as e:
            raise RuntimeError(
                f"Failed to initialize Tkinter. Ensure you have a display available. "
                f"Error: {e}"
            ) from e

        self.root.title("cStrafe UI by CS2Kitchen")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        # Load saved position from config
        overlay_config = self.config.overlay
        saved_x = overlay_config.get("position_x")
        saved_y = overlay_config.get("position_y")
        saved_font_size = overlay_config.get("font_size", 10)

        self.frame = tk.Frame(self.root, bd=2, relief="solid")
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Font sizes
        self.body_font_size = saved_font_size
        self.header_font_size = saved_font_size + 2
        self.retro_font = "Courier"

        self.header = tk.Label(
            self.frame,
            text="cStrafe UI",
            fg="white",
            bg="#303030",
            font=(self.retro_font, self.header_font_size, "bold"),
            anchor="center",
        )
        self.header.pack(fill=tk.X)

        self.body = tk.Label(
            self.frame,
            text="Waiting for input...",
            fg="white",
            bg="#202020",
            font=(self.retro_font, self.body_font_size),
            justify=tk.CENTER,
            anchor="center",
        )
        self.body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self.history_indicator = tk.Label(
            self.frame,
            text="",
            fg="white",
            bg="#202020",
            font=(self.retro_font, self.body_font_size - 1),
            justify=tk.CENTER,
            anchor="center",
        )
        self.history_indicator.pack(fill=tk.X, pady=(0, 4))

        self._offset_x: Optional[int] = None
        self._offset_y: Optional[int] = None
        self.header.bind("<ButtonPress-1>", self._on_mouse_down)
        self.header.bind("<B1-Motion>", self._on_mouse_move)
        self.header.bind("<ButtonRelease-1>", self._on_mouse_release)
        self.is_visible = True
        self._last_text: Optional[str] = None
        self._last_bg_colour: Optional[str] = None
        self._fade_job: Optional[str] = None
        self._default_bg = "#202020"

        # Position window after it's drawn to get correct dimensions
        self.root.after(100, lambda: self._restore_position(saved_x, saved_y))

    def _restore_position(self, saved_x: Optional[int], saved_y: Optional[int]) -> None:
        """Restore saved window position or center on screen."""
        self.root.update_idletasks()
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        if saved_x is not None and saved_y is not None:
            # Ensure window is within screen bounds
            x = max(0, min(saved_x, screen_width - window_width))
            y = max(0, min(saved_y, screen_height - window_height))
        else:
            # Center on screen
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2

        self.root.geometry(f"+{x}+{y}")

    def _on_mouse_down(self, event: tk.Event) -> None:
        self._offset_x = event.x
        self._offset_y = event.y

    def _on_mouse_move(self, event: tk.Event) -> None:
        if self._offset_x is not None and self._offset_y is not None:
            x = event.x_root - self._offset_x
            y = event.y_root - self._offset_y
            self.root.geometry(f"+{x}+{y}")

    def _on_mouse_release(self, event: tk.Event) -> None:
        """Save window position when dragging ends."""
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.config.update_overlay_position(x, y)
    def update_result(self, classification: ShotClassification, history: Optional[List[str]] = None) -> None:
        label = classification.label
        lines = [f"Classification: {label}"]
        if label == LABEL_COUNTER_STRAFE and classification.cs_time is not None and classification.shot_delay is not None:
            lines.append(f"CS time: {classification.cs_time:.0f} ms")
            lines.append(f"Shot delay: {classification.shot_delay:.0f} ms")
        elif label == LABEL_OVERLAP and classification.overlap_time is not None:
            lines.append(f"Overlap: {classification.overlap_time:.0f} ms")
        elif label == LABEL_BAD and classification.cs_time is not None and classification.shot_delay is not None:
            lines.append(f"CS time: {classification.cs_time:.0f} ms")
            lines.append(f"Shot delay: {classification.shot_delay:.0f} ms")

        colours = {
            LABEL_COUNTER_STRAFE: "#228b22",
            LABEL_OVERLAP: "#ff8c00",
            LABEL_BAD: "#cc0000",
        }
        target_bg = colours.get(label, self._default_bg)
        text = "\n".join(lines)

        dots_text = ""
        if history:
            dot_colors = {"Counter\u2011strafe": "🟢", "Overlap": "🟡", "Bad": "🔴"}
            dots_text = "".join(dot_colors.get(lbl, "⚪") for lbl in history[-10:])  # Show latest 10 shots

        def apply_update() -> None:
            # All state access on the main tkinter thread to avoid race conditions
            if text == self._last_text and target_bg == self._last_bg_colour:
                return
            self._last_text = text
            self._last_bg_colour = target_bg
            
            if self._fade_job is not None:
                self.root.after_cancel(self._fade_job)
                self._fade_job = None

            self.frame.configure(bg=target_bg)
            self.body.configure(text=text, bg=target_bg)
            self.history_indicator.configure(text=dots_text, bg=target_bg)

            if target_bg != self._default_bg:
                self._start_fade(target_bg, self._default_bg)

        self.root.after(0, apply_update)

    def _hex_to_rgb(self, hex_str: str) -> tuple[int, int, int]:
        return tuple(int(hex_str[i:i+2], 16) for i in (1, 3, 5))

    def _rgb_to_hex(self, rgb: tuple[float, float, float]) -> str:
        return f"#{int(rgb[0]):02x}{int(rgb[1]):02x}{int(rgb[2]):02x}"

    def _start_fade(self, start_color: str, end_color: str) -> None:
        start_rgb = self._hex_to_rgb(start_color)
        end_rgb = self._hex_to_rgb(end_color)
        steps = 40
        delay_ms = 25
        
        def fade_step(current_step: int):
            if current_step > steps:
                self._fade_job = None
                return
            
            ratio = current_step / steps
            current_rgb = (
                start_rgb[0] + (end_rgb[0] - start_rgb[0]) * ratio,
                start_rgb[1] + (end_rgb[1] - start_rgb[1]) * ratio,
                start_rgb[2] + (end_rgb[2] - start_rgb[2]) * ratio,
            )
            hex_color = self._rgb_to_hex(current_rgb)
            self.frame.configure(bg=hex_color)
            self.body.configure(bg=hex_color)
            self.history_indicator.configure(bg=hex_color)
            
            self._fade_job = self.root.after(delay_ms, fade_step, current_step + 1)

        # wait 800ms before fading
        self._fade_job = self.root.after(800, fade_step, 1)

    def run(self) -> None:
        self.root.mainloop()

    def _apply_font_sizes(self) -> None:
        self.header.configure(font=(self.retro_font, self.header_font_size, "bold"))
        self.body.configure(font=(self.retro_font, self.body_font_size))
        # Save font size to config
        self.config.update_font_size(self.body_font_size)

    def increase_size(self) -> None:
        def _do() -> None:
            if self.body_font_size < 24:
                self.body_font_size += 2
                self.header_font_size = self.body_font_size + 2
                self._apply_font_sizes()

        self.root.after(0, _do)

    def decrease_size(self) -> None:
        def _do() -> None:
            if self.body_font_size > 8:
                self.body_font_size -= 2
                self.header_font_size = self.body_font_size + 2
                self._apply_font_sizes()

        self.root.after(0, _do)

    def toggle_visibility(self) -> None:
        def do_toggle() -> None:
            if self.is_visible:
                self.root.withdraw()
            else:
                self.root.deiconify()
            self.is_visible = not self.is_visible

        self.root.after(0, do_toggle)

    def terminate(self) -> None:
        self.root.after(0, self.root.destroy)

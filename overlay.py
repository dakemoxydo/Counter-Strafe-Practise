import tkinter as tk
from typing import List, Optional

from classifier import (
    LABEL_BAD,
    LABEL_COUNTER_STRAFE,
    LABEL_OVERLAP,
    ShotClassification,
)
from config import Config
from constants import (
    Colors,
    FADE_DELAY_MS,
    FADE_START_DELAY_MS,
    FADE_STEPS,
    OverlayConfig,
    PROJECT_NAME,
    PROJECT_NAME_SHORT,
    format_history_dots,
)

# Fixed overlay window size
OVERLAY_WIDTH = OverlayConfig.WINDOW_WIDTH
OVERLAY_HEIGHT = OverlayConfig.WINDOW_HEIGHT


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

        self.root.title(f"{PROJECT_NAME} by dakemoxydo")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        # Enable transparency on Windows
        try:
            self.root.attributes("-transparentcolor", "white")
        except tk.TclError:
            pass  # Not supported on all systems

        # Load saved position from config
        overlay_config = self.config.overlay
        saved_x = overlay_config.get("position_x")
        saved_y = overlay_config.get("position_y")
        saved_font_size = overlay_config.get("font_size", OverlayConfig.DEFAULT_FONT_SIZE)

        # Configure fonts
        self.body_font_size = saved_font_size
        self.header_font_size = saved_font_size + 2
        self.history_font_size = max(saved_font_size - 2, 8)
        self.font_family = "Consolas"

        # Colors (using design constants)
        self.colors = {
            LABEL_COUNTER_STRAFE: Colors.CLASS_COUNTER_STRAFE,
            LABEL_OVERLAP: Colors.CLASS_OVERLAP,
            LABEL_BAD: Colors.CLASS_BAD,
        }
        self.default_bg = Colors.BG_DARK

        # Main frame with rounded corners effect
        self.frame = tk.Frame(
            self.root,
            bg=self.default_bg,
            bd=0,
            relief="flat",
            width=OVERLAY_WIDTH,
            height=OVERLAY_HEIGHT,
        )
        self.frame.pack(fill=tk.BOTH, expand=False)
        self.frame.pack_propagate(False)  # Prevent frame from shrinking to content

        # Header bar
        self.header = tk.Label(
            self.frame,
            text=f" {PROJECT_NAME_SHORT} ",
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_LIGHT,
            font=(self.font_family, self.header_font_size, "bold"),
            anchor="center",
        )
        self.header.pack(fill=tk.X)

        # Main body
        self.body = tk.Label(
            self.frame,
            text="Waiting for input...",
            fg=Colors.TEXT_SECONDARY,
            bg=self.default_bg,
            font=(self.font_family, self.body_font_size),
            justify=tk.CENTER,
            anchor="center",
        )
        self.body.pack(fill=tk.BOTH, expand=True, padx=OverlayConfig.OVERLAY_PADDING_X, pady=OverlayConfig.OVERLAY_PADDING_Y)

        # History indicator
        self.history_indicator = tk.Label(
            self.frame,
            text="",
            fg=Colors.TEXT_SECONDARY,
            bg=self.default_bg,
            font=(self.font_family, self.history_font_size),
            justify=tk.CENTER,
            anchor="center",
        )
        self.history_indicator.pack(fill=tk.X, pady=(0, OverlayConfig.OVERLAY_PADDING_Y))

        # Dragging state
        self._offset_x: Optional[int] = None
        self._offset_y: Optional[int] = None

        # Bind drag events to header
        self.header.bind("<ButtonPress-1>", self._on_mouse_down)
        self.header.bind("<B1-Motion>", self._on_mouse_move)
        self.header.bind("<ButtonRelease-1>", self._on_mouse_release)

        # Also allow dragging from body
        self.body.bind("<ButtonPress-1>", self._on_mouse_down)
        self.body.bind("<B1-Motion>", self._on_mouse_move)
        self.body.bind("<ButtonRelease-1>", self._on_mouse_release)

        self.history_indicator.bind("<ButtonPress-1>", self._on_mouse_down)
        self.history_indicator.bind("<B1-Motion>", self._on_mouse_move)
        self.history_indicator.bind("<ButtonRelease-1>", self._on_mouse_release)

        self.is_visible = True
        self._last_text: Optional[str] = None
        self._last_bg_colour: Optional[str] = None
        self._fade_job: Optional[str] = None

        # Position window after it's drawn to get correct dimensions
        self.root.after(100, lambda: self._restore_position(saved_x, saved_y))

    def _restore_position(self, saved_x: Optional[int], saved_y: Optional[int]) -> None:
        """Restore saved window position or center on screen."""
        self.root.update_idletasks()
        window_width = OVERLAY_WIDTH
        window_height = OVERLAY_HEIGHT
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        if saved_x is not None and saved_y is not None:
            # Clamp to screen bounds
            x = max(0, min(saved_x, screen_width - window_width))
            y = max(0, min(saved_y, screen_height - window_height))
        else:
            # Center on screen
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2

        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    def _on_mouse_down(self, event: tk.Event) -> None:
        """Start dragging the window."""
        self._offset_x = event.x
        self._offset_y = event.y

    def _on_mouse_move(self, event: tk.Event) -> None:
        """Drag the window."""
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
        """Update the overlay with new classification result."""
        label = classification.label

        # Format text based on classification
        lines = [f"▸ {label}"]
        if label == LABEL_COUNTER_STRAFE and classification.cs_time is not None and classification.shot_delay is not None:
            lines.append(f"  CS: {classification.cs_time:.0f} ms")
            lines.append(f"  Delay: {classification.shot_delay:.0f} ms")
        elif label == LABEL_OVERLAP and classification.overlap_time is not None:
            lines.append(f"  Overlap: {classification.overlap_time:.0f} ms")
        elif label == LABEL_BAD and classification.cs_time is not None and classification.shot_delay is not None:
            lines.append(f"  CS: {classification.cs_time:.0f} ms")
            lines.append(f"  Delay: {classification.shot_delay:.0f} ms")

        target_bg = self.colors.get(label, self.default_bg)
        text = "\n".join(lines)

        # Format history dots
        dots_text = ""
        if history:
            dots_text = format_history_dots(history)

        def apply_update() -> None:
            # All state access on the main tkinter thread to avoid race conditions
            if text == self._last_text and target_bg == self._last_bg_colour:
                return
            self._last_text = text
            self._last_bg_colour = target_bg

            if self._fade_job is not None:
                self.root.after_cancel(self._fade_job)
                self._fade_job = None

            # Update colors
            self.frame.configure(bg=target_bg)
            self.body.configure(text=text, bg=target_bg)
            self.history_indicator.configure(text=dots_text, bg=target_bg)

            # Start fade animation if not default background
            if target_bg != self.default_bg:
                self._start_fade(target_bg, self.default_bg)

        self.root.after(0, apply_update)

    def _hex_to_rgb(self, hex_str: str) -> tuple:
        """Convert hex color to RGB tuple."""
        return (
            int(hex_str[1:3], 16),
            int(hex_str[3:5], 16),
            int(hex_str[5:7], 16),
        )

    def _rgb_to_hex(self, rgb: tuple) -> str:
        """Convert RGB tuple to hex color."""
        return f"#{int(rgb[0]):02x}{int(rgb[1]):02x}{int(rgb[2]):02x}"

    def _start_fade(self, start_color: str, end_color: str) -> None:
        """Start the fade animation."""
        start_rgb = self._hex_to_rgb(start_color)
        end_rgb = self._hex_to_rgb(end_color)

        def fade_step(current_step: int):
            if current_step > FADE_STEPS:
                self._fade_job = None
                return

            ratio = current_step / FADE_STEPS
            current_rgb = (
                start_rgb[0] + (end_rgb[0] - start_rgb[0]) * ratio,
                start_rgb[1] + (end_rgb[1] - start_rgb[1]) * ratio,
                start_rgb[2] + (end_rgb[2] - start_rgb[2]) * ratio,
            )
            hex_color = self._rgb_to_hex(current_rgb)
            self.frame.configure(bg=hex_color)
            self.body.configure(bg=hex_color)
            self.history_indicator.configure(bg=hex_color)

            self._fade_job = self.root.after(FADE_DELAY_MS, fade_step, current_step + 1)

        # Wait before fading
        self._fade_job = self.root.after(FADE_START_DELAY_MS, fade_step, 1)

    def run(self) -> None:
        """Start the overlay mainloop."""
        self.root.mainloop()

    def _apply_font_sizes(self) -> None:
        """Apply font sizes to all labels."""
        self.header.configure(font=(self.font_family, self.header_font_size, "bold"))
        self.body.configure(font=(self.font_family, self.body_font_size))
        # Save font size to config
        self.config.update_font_size(self.body_font_size)
        # Ensure window size stays fixed
        self.root.geometry(f"{OVERLAY_WIDTH}x{OVERLAY_HEIGHT}")

    def increase_size(self) -> None:
        """Increase the font size."""
        def _do() -> None:
            if self.body_font_size < OverlayConfig.MAX_FONT_SIZE:
                self.body_font_size += OverlayConfig.FONT_SIZE_STEP
                self.header_font_size = self.body_font_size + 2
                self.history_font_size = max(self.body_font_size - 2, 8)
                self._apply_font_sizes()

        self.root.after(0, _do)

    def decrease_size(self) -> None:
        """Decrease the font size."""
        def _do() -> None:
            if self.body_font_size > OverlayConfig.MIN_FONT_SIZE:
                self.body_font_size -= OverlayConfig.FONT_SIZE_STEP
                self.header_font_size = self.body_font_size + 2
                self.history_font_size = max(self.body_font_size - 2, 8)
                self._apply_font_sizes()

        self.root.after(0, _do)

    def toggle_visibility(self) -> None:
        """Toggle overlay visibility."""
        def do_toggle() -> None:
            if self.is_visible:
                self.root.withdraw()
            else:
                self.root.deiconify()
            self.is_visible = not self.is_visible

        self.root.after(0, do_toggle)

    def terminate(self) -> None:
        """Close the overlay."""
        self.root.after(0, self.root.destroy)

import logging
import threading
import time
from typing import Optional

from pynput import keyboard, mouse

from classifier import (
    DEFAULT_MAX_CS_TIME,
    DEFAULT_MAX_SHOT_DELAY,
    DEFAULT_MIN_SHOT_DELAY,
    LABEL_BAD,
    LABEL_COUNTER_STRAFE,
    LABEL_OVERLAP,
    MovementClassifier,
    ShotClassification,
)
from config import Config
from statistics import StatisticsManager

logger = logging.getLogger(__name__)


class InputListener:
    def __init__(self, overlay: "Overlay", config: Optional[Config] = None, stats: Optional[StatisticsManager] = None) -> None:
        self.overlay = overlay
        self.config = config if config is not None else Config()
        self.stats = stats

        # Get movement keys from config
        move_keys = self.config.movement_keys
        forward = str(move_keys.get("forward", "W"))[0].upper()
        backward = str(move_keys.get("backward", "S"))[0].upper()
        left = str(move_keys.get("left", "A"))[0].upper()
        right = str(move_keys.get("right", "D"))[0].upper()

        self._movement_keys = {forward, backward, left, right}

        # Get thresholds from config
        thresholds = self.config.thresholds
        max_shot_delay = float(thresholds.get("max_shot_delay", DEFAULT_MAX_SHOT_DELAY))
        min_shot_delay = float(thresholds.get("min_shot_delay", DEFAULT_MIN_SHOT_DELAY))
        max_cs_time = float(thresholds.get("max_cs_time", DEFAULT_MAX_CS_TIME))

        # Initialise classifier with the configured key pairs and thresholds
        try:
            self.classifier = MovementClassifier(
                vertical_keys=(forward, backward),
                horizontal_keys=(left, right),
                max_shot_delay=max_shot_delay,
                min_shot_delay=min_shot_delay,
                max_cs_time=max_cs_time,
            )
        except Exception:
            # Fallback to default WASD if invalid configuration is provided
            logger.warning("Invalid key configuration, falling back to WASD defaults.")
            self.classifier = MovementClassifier()

        # Get hotkeys from config
        hotkeys = self.config.hotkeys
        self._toggle_key = hotkeys.get("toggle_visibility", "F6")
        self._exit_key = hotkeys.get("exit", "F8")
        self._increase_size_key = hotkeys.get("increase_size", "=")
        self._decrease_size_key = hotkeys.get("decrease_size", "-")

        self._lock = threading.Lock()
        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._mouse_listener: Optional[mouse.Listener] = None
        self._shutdown_event = threading.Event()

    def _get_key_name(self, key: keyboard.Key) -> Optional[str]:
        """Get the string name of a key for hotkey comparison."""
        try:
            # For character keys (a-z, 0-9, =, -, etc.)
            if hasattr(key, "char") and key.char is not None:
                return key.char.upper()
        except AttributeError:
            pass

        # For special keys (F1-F12, etc.)
        try:
            if hasattr(key, "name") and key.name is not None:
                return key.name.upper()
        except AttributeError:
            pass

        return None

    def start(self) -> None:
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._keyboard_listener.start()
        self._mouse_listener = mouse.Listener(
            on_click=self._on_click,
        )
        self._mouse_listener.start()

    def _on_key_press(self, key: keyboard.Key) -> None:
        key_name = self._get_key_name(key)

        if key_name == self._toggle_key.upper():
            self.overlay.toggle_visibility()
            return
        if key_name == self._exit_key.upper():
            self._shutdown_event.set()
            # stop() calls join() on the listener thread — calling it from
            # within the listener callback causes a deadlock.  Dispatch to a
            # short-lived daemon thread so the callback can return immediately.
            import threading as _threading
            _threading.Thread(target=self._shutdown, daemon=True).start()
            return
        if key_name == self._increase_size_key.upper():
            self.overlay.increase_size()
            return
        if key_name == self._decrease_size_key.upper():
            self.overlay.decrease_size()
            return

        timestamp = time.time() * 1000.0
        if key_name and key_name in self._movement_keys:
            with self._lock:
                self.classifier.on_press(key_name, timestamp)

    def _on_key_release(self, key: keyboard.Key) -> None:
        timestamp = time.time() * 1000.0
        key_name = self._get_key_name(key)
        if key_name and key_name in self._movement_keys:
            with self._lock:
                self.classifier.on_release(key_name, timestamp)

    def _on_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        if button != mouse.Button.left:
            return
        current_time = time.time() * 1000.0
        if pressed:
            with self._lock:
                base_result = self.classifier.classify_shot(current_time)
                final_result = self._build_classification(base_result)
            self.overlay.update_result(final_result)
            if self.stats:
                self.stats.record_shot(final_result)

    def stop(self) -> None:
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            self._keyboard_listener.join(timeout=1.0)
            self._keyboard_listener = None
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener.join(timeout=1.0)
            self._mouse_listener = None
        self._shutdown_event.set()

    def _shutdown(self) -> None:
        """Stop all listeners and terminate the overlay. Safe to call from any thread."""
        self.stop()
        self.overlay.terminate()

    def _build_classification(self, base: ShotClassification) -> ShotClassification:
        if base.label == LABEL_OVERLAP:
            return ShotClassification(label=LABEL_OVERLAP, overlap_time=base.overlap_time)
        if base.label == LABEL_COUNTER_STRAFE:
            cs_time = base.cs_time
            shot_delay = base.shot_delay
            if cs_time is not None and shot_delay is not None:
                if (
                    shot_delay < self.classifier.min_shot_delay
                    or shot_delay > self.classifier.max_shot_delay
                    or cs_time > self.classifier.max_cs_time
                ):
                    return ShotClassification(label=LABEL_BAD, cs_time=cs_time, shot_delay=shot_delay)
                return ShotClassification(label=LABEL_COUNTER_STRAFE, cs_time=cs_time, shot_delay=shot_delay)
            return ShotClassification(label=LABEL_BAD)
        return ShotClassification(label=LABEL_BAD)


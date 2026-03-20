import logging
import queue
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
    # Mapping русских букв к английским для поддержки русской раскладки
    KEYBOARD_LAYOUT_MAP = {
        'Ф': 'A', 'ф': 'a',  # Russian 'ф' -> English 'a'
        'В': 'W', 'в': 'w',  # Russian 'в' -> English 'w'
        'Ы': 'S', 'ы': 's',  # Russian 'ы' -> English 's'
        'Д': 'D', 'д': 'd',  # Russian 'д' -> English 'd'
        'A': 'A', 'a': 'a',  # English 'a' -> English 'a' (identity)
        'W': 'W', 'w': 'w',  # English 'w' -> English 'w' (identity)
        'S': 'S', 's': 's',  # English 's' -> English 's' (identity)
        'D': 'D', 'd': 'd',  # English 'd' -> English 'd' (identity)
    }

    def __init__(self, overlay: "Overlay", config: Optional[Config] = None, stats: Optional[StatisticsManager] = None) -> None:
        self.overlay = overlay
        self.config = config if config is not None else Config()
        self.stats = stats

        # Thread-safe queue for UI updates to prevent race conditions
        self._update_queue: queue.Queue[Optional[ShotClassification]] = queue.Queue()
        self._update_thread: Optional[threading.Thread] = None
        self._shutdown_flag = threading.Event()

        # Get movement keys from config
        move_keys = self.config.movement_keys
        
        def safe_first_char(val: str, default: str) -> str:
            s = str(val).strip()
            return s[0].upper() if s else default
            
        forward = safe_first_char(move_keys.get("forward", "W"), "W")
        backward = safe_first_char(move_keys.get("backward", "S"), "S")
        left = safe_first_char(move_keys.get("left", "A"), "A")
        right = safe_first_char(move_keys.get("right", "D"), "D")

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

    def _get_key_name(self, key: keyboard.Key | keyboard.KeyCode | None) -> Optional[str]:
        """Get the string name of a key for hotkey comparison."""
        if key is None:
            return None
        key_name = None
        try:
            if hasattr(key, "char") and key.char is not None:
                key_name = key.char
        except AttributeError:
            pass

        if key_name is None:
            try:
                if hasattr(key, "name") and key.name is not None:
                    key_name = key.name
            except AttributeError:
                pass

        # Convert Russian keyboard layout to English
        if key_name and key_name in self.KEYBOARD_LAYOUT_MAP:
            key_name = self.KEYBOARD_LAYOUT_MAP[key_name]

        return key_name

    def _process_update_queue(self) -> None:
        """Process UI updates from the queue in a dedicated thread."""
        logger.debug("Update queue processor started")
        while not self._shutdown_flag.is_set():
            try:
                result = self._update_queue.get(timeout=0.1)
                if result is None:
                    break
                self.overlay.update_result(result)
                self._update_queue.task_done()
            except queue.Empty:
                continue
            except Exception:
                logger.exception("Error processing update queue")
        logger.debug("Update queue processor stopped")

    def start(self) -> None:
        logger.info("Starting listeners: movement_keys=%r thresholds=(max_shot_delay=%r min_shot_delay=%r max_cs_time=%r)",
                    self._movement_keys, self.classifier.max_shot_delay,
                    self.classifier.min_shot_delay, self.classifier.max_cs_time)
        
        # Start UI update processor thread
        self._update_thread = threading.Thread(target=self._process_update_queue, daemon=True, name="UIUpdateProcessor")
        self._update_thread.start()
        
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
        if self._shutdown_flag.is_set():
            return

        try:
            key_name = self._get_key_name(key)
        except Exception:
            logger.exception("Error getting key name for key=%r", key)
            return

        logger.debug("Key press: key=%r key_name=%r movement_keys=%r", key, key_name, self._movement_keys)

        if key_name.upper() == self._toggle_key.upper():
            self.overlay.toggle_visibility()
            return
        if key_name.upper() == self._exit_key.upper():
            self._shutdown_flag.set()
            import threading as _threading
            _threading.Thread(target=self._shutdown, daemon=True).start()
            return
        if key_name.upper() == self._increase_size_key.upper():
            self.overlay.increase_size()
            return
        if key_name.upper() == self._decrease_size_key.upper():
            self.overlay.decrease_size()
            return

        timestamp = time.time() * 1000.0
        # DEBUG: Add logging to diagnose key matching issue
        logger.debug("DEBUG on_press: key_name=%r in movement_keys=%r -> %r", 
                     key_name, self._movement_keys, key_name.upper() if key_name else None)
        if key_name and key_name.upper() in self._movement_keys:
            with self._lock:
                self.classifier.on_press(key_name, timestamp)
                logger.debug("DEBUG on_press: classifier.on_press called with key=%r", key_name.upper())

    def _on_key_release(self, key: keyboard.Key) -> None:
        if self._shutdown_flag.is_set():
            return
        timestamp = time.time() * 1000.0
        try:
            key_name = self._get_key_name(key)
        except Exception:
            logger.exception("Error getting key name for key=%r", key)
            return
        logger.debug("Key release: key=%r key_name=%r", key, key_name)
        # DEBUG: Add logging to diagnose key matching issue
        logger.debug("DEBUG on_release: key_name=%r in movement_keys=%r -> %r", 
                     key_name, self._movement_keys, key_name.upper() if key_name else None)
        if key_name and key_name.upper() in self._movement_keys:
            with self._lock:
                self.classifier.on_release(key_name, timestamp)
                logger.debug("DEBUG on_release: classifier.on_release called with key=%r", key_name.upper())
                logger.debug("After release: held_keys=%r cs_release=%r cs_press=%r",
                             self.classifier.vertical.held_keys if key_name in {"W", "S"}
                             else self.classifier.horizontal.held_keys,
                             self.classifier.vertical.cs_release_time if key_name in {"W", "S"}
                             else self.classifier.horizontal.cs_release_time,
                             self.classifier.vertical.cs_press_time if key_name in {"W", "S"}
                             else self.classifier.horizontal.cs_press_time)

    def _on_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        if button != mouse.Button.left:
            return
        current_time = time.time() * 1000.0
        if pressed:
            with self._lock:
                logger.debug("Click: vertical state=%r", self.classifier.vertical)
                logger.debug("Click: horizontal state=%r", self.classifier.horizontal)
                result = self.classifier.classify_shot(current_time)
            logger.debug("Click: result=%r", result)
            # Use queue to prevent race conditions when updating UI
            self._update_queue.put(result)
            if self.stats:
                self.stats.record_shot(result)

    def stop(self) -> None:
        logger.info("Stopping InputListener...")
        self._shutdown_flag.set()
        
        # Signal update thread to stop
        self._update_queue.put(None)
        
        # Stop keyboard listener
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            if self._keyboard_listener.is_alive():
                self._keyboard_listener.join(timeout=2.0)
                if self._keyboard_listener.is_alive():
                    logger.warning("Keyboard listener did not stop gracefully")
            self._keyboard_listener = None
        
        # Stop mouse listener
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            if self._mouse_listener.is_alive():
                self._mouse_listener.join(timeout=2.0)
                if self._mouse_listener.is_alive():
                    logger.warning("Mouse listener did not stop gracefully")
            self._mouse_listener = None
        
        # Wait for update thread to finish
        if self._update_thread is not None and self._update_thread.is_alive():
            self._update_thread.join(timeout=2.0)
            if self._update_thread.is_alive():
                logger.warning("Update thread did not stop gracefully")
            self._update_thread = None
        
        logger.info("InputListener stopped")

    def _shutdown(self) -> None:
        """Stop all listeners and terminate the overlay. Safe to call from any thread."""
        self.stop()
        self.overlay.terminate()


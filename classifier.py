from dataclasses import dataclass, field
from typing import Optional, Tuple

# Default timing thresholds for counter-strafe classification
# These can be overridden via config.py
DEFAULT_MAX_SHOT_DELAY = 150.0  # ms - maximum delay after counter-strafe before shot
DEFAULT_MIN_SHOT_DELAY = 40.0   # ms - minimum delay required to fully decelerate in CS2
DEFAULT_MAX_CS_TIME = 100.0     # ms - maximum time between release and opposite key press

LABEL_COUNTER_STRAFE = "Counter\u2011strafe"
LABEL_OVERLAP = "Overlap"
LABEL_BAD = "Bad"


@dataclass
class AxisState:
    keys: Tuple[str, str]
    held_keys: set = field(default_factory=set)
    press_times: dict = field(default_factory=dict)
    cs_release_key: Optional[str] = None
    cs_release_time: Optional[float] = None
    cs_press_key: Optional[str] = None
    cs_press_time: Optional[float] = None
    # When the counter-key (D) is released, we record WHEN it was released
    # without touching cs_release_time (which holds A's release time) so that
    # classify_shot can still see the A→D sequence.  If the player then presses
    # A again, a new D→A CS cycle is started using this stored timestamp.
    cs_counter_key_released_at: Optional[float] = None
    overlap_start_time: Optional[float] = None

    def on_press(self, key: str, timestamp: float) -> None:
        # Ignore key-repeat events (key already held down)
        if key in self.held_keys:
            return
        other = self.keys[0] if key == self.keys[1] else self.keys[1]
        self.held_keys.add(key)
        self.press_times[key] = timestamp
        if other in self.held_keys and self.overlap_start_time is None:
            self.overlap_start_time = timestamp
        # Normal case: opposite key (A) was released first — record counter-press (D).
        if self.cs_release_key == other and self.cs_press_time is None:
            self.cs_press_key = key
            self.cs_press_time = timestamp
        # Rapid reversal: counter-key (D) was released and now the original
        # direction (A) is pressed — start a new CS sequence using D's release
        # time as the CS-release anchor.
        elif (
            self.cs_press_key == other
            and self.cs_counter_key_released_at is not None
        ):
            self.cs_release_key = other
            self.cs_release_time = self.cs_counter_key_released_at
            self.cs_press_key = key
            self.cs_press_time = timestamp
            self.cs_counter_key_released_at = None

    def on_release(self, key: str, timestamp: float) -> None:
        self.held_keys.discard(key)
        self.press_times.pop(key, None)

        if key == self.cs_press_key:
            # Releasing the counter-key (D after A→D sequence).
            # Do NOT update cs_release_time — it must stay as A's release time
            # so that classify_shot still sees cs_press_time(D) > cs_release_time(A).
            # Store when D was released separately for rapid-reversal detection.
            self.cs_counter_key_released_at = timestamp
        else:
            # Releasing the original/first key — start a fresh CS sequence.
            self.cs_release_key = key
            self.cs_release_time = timestamp
            self.cs_press_key = None
            self.cs_press_time = None
            self.cs_counter_key_released_at = None

    def classify_shot(self, shot_time: float) -> Tuple[str, Optional[float], Optional[float]]:

        if self.overlap_start_time is not None:
            if not (
                self.cs_press_time is not None
                and self.cs_release_time is not None
                and self.cs_release_time > self.overlap_start_time
                and self.cs_press_time > self.cs_release_time
            ):
                overlap_time = shot_time - self.overlap_start_time
                self._reset()
                return LABEL_OVERLAP, overlap_time, None
        if (
            self.cs_press_time is not None
            and self.cs_release_time is not None
            and self.cs_press_time > self.cs_release_time
        ):
            cs_time = self.cs_press_time - self.cs_release_time
            shot_delay = shot_time - self.cs_press_time
            self._reset()
            return LABEL_COUNTER_STRAFE, cs_time, shot_delay
        self._reset()
        return LABEL_BAD, None, None

    def _reset(self) -> None:
        self.cs_release_key = None
        self.cs_release_time = None
        self.cs_press_key = None
        self.cs_press_time = None
        self.cs_counter_key_released_at = None
        self.overlap_start_time = None
        self.held_keys.clear()
        self.press_times.clear()



@dataclass
class ShotClassification:
    label: str
    cs_time: Optional[float] = None
    shot_delay: Optional[float] = None
    overlap_time: Optional[float] = None


class MovementClassifier:
    """
    Classifies player movement based on key presses and releases.

    By default the classifier tracks the conventional vertical (forward/backward)
    and horizontal (left/right) movement keys. Custom key bindings can be
    supplied to accommodate different keyboard layouts or player preferences.
    """

    def __init__(
        self,
        *,
        vertical_keys: Tuple[str, str] = ("W", "S"),
        horizontal_keys: Tuple[str, str] = ("A", "D"),
        max_shot_delay: float = DEFAULT_MAX_SHOT_DELAY,
        min_shot_delay: float = DEFAULT_MIN_SHOT_DELAY,
        max_cs_time: float = DEFAULT_MAX_CS_TIME,
    ) -> None:
        v_keys = tuple(key.upper() for key in vertical_keys)
        h_keys = tuple(key.upper() for key in horizontal_keys)
        if len(set(v_keys)) != 2:
            raise ValueError(f"vertical_keys must contain two distinct keys, got {vertical_keys}")
        if len(set(h_keys)) != 2:
            raise ValueError(f"horizontal_keys must contain two distinct keys, got {horizontal_keys}")
        self.vertical = AxisState(keys=v_keys)
        self.horizontal = AxisState(keys=h_keys)
        self.max_shot_delay = max_shot_delay
        self.min_shot_delay = min_shot_delay
        self.max_cs_time = max_cs_time

    def on_press(self, key: str, timestamp: float) -> None:
        if key in self.vertical.keys:
            self.vertical.on_press(key, timestamp)
        elif key in self.horizontal.keys:
            self.horizontal.on_press(key, timestamp)

    def on_release(self, key: str, timestamp: float) -> None:
        if key in self.vertical.keys:
            self.vertical.on_release(key, timestamp)
        elif key in self.horizontal.keys:
            self.horizontal.on_release(key, timestamp)

    def classify_shot(self, shot_time: float) -> ShotClassification:
        v_label, v_val1, v_val2 = self.vertical.classify_shot(shot_time)
        h_label, h_val1, h_val2 = self.horizontal.classify_shot(shot_time)
        negativity = {
            LABEL_OVERLAP: 2,
            LABEL_COUNTER_STRAFE: 1,
            LABEL_BAD: 0,
        }
        v_score = negativity.get(v_label, 0)
        h_score = negativity.get(h_label, 0)
        if v_score > h_score:
            label, val1, val2 = v_label, v_val1, v_val2
        elif h_score > v_score:
            label, val1, val2 = h_label, h_val1, h_val2
        else:
            if v_val1 is not None and h_val1 is not None:
                if v_val1 >= h_val1:
                    label, val1, val2 = v_label, v_val1, v_val2
                else:
                    label, val1, val2 = h_label, h_val1, h_val2
            elif v_val1 is not None:
                label, val1, val2 = v_label, v_val1, v_val2
            else:
                label, val1, val2 = h_label, h_val1, h_val2
        if label == LABEL_COUNTER_STRAFE:
            return ShotClassification(label=label, cs_time=val1, shot_delay=val2)
        elif label == LABEL_OVERLAP:
            return ShotClassification(label=label, overlap_time=val1)
        return ShotClassification(label=label)
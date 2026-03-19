"""
Unit tests for the MovementClassifier in cStrafe UI.

Run with: py -m pytest test_classifier.py -v
"""

import pytest
from classifier import (
    DEFAULT_MAX_CS_TIME,
    DEFAULT_MAX_SHOT_DELAY,
    LABEL_BAD,
    LABEL_COUNTER_STRAFE,
    LABEL_OVERLAP,
    AxisState,
    MovementClassifier,
    ShotClassification,
)


class TestAxisState:
    """Tests for the AxisState class."""

    def test_on_press_adds_key_to_held_keys(self) -> None:
        state = AxisState(keys=("W", "S"))
        state.on_press("W", 100.0)
        assert "W" in state.held_keys
        assert state.press_times["W"] == 100.0

    def test_on_release_removes_key_from_held_keys(self) -> None:
        state = AxisState(keys=("W", "S"))
        state.on_press("W", 100.0)
        state.on_release("W", 150.0)
        assert "W" not in state.held_keys

    def test_on_release_clears_press_time(self) -> None:
        state = AxisState(keys=("W", "S"))
        state.on_press("W", 100.0)
        state.on_release("W", 150.0)
        assert "W" not in state.press_times

    def test_overlap_detection(self) -> None:
        """Test that overlap is detected when both keys are held."""
        state = AxisState(keys=("A", "D"))
        state.on_press("A", 100.0)
        state.on_press("D", 150.0)  # Press D while A is still held
        assert state.overlap_start_time == 150.0

    def test_counter_strafe_sequence(self) -> None:
        """Test counter-strafe: release A, press D."""
        state = AxisState(keys=("A", "D"))
        state.on_press("A", 100.0)
        state.on_release("A", 200.0)  # Release A
        state.on_press("D", 250.0)  # Press D (opposite)

        assert state.cs_release_time == 200.0
        assert state.cs_press_time == 250.0

    def test_reset_clears_all_state(self) -> None:
        state = AxisState(keys=("W", "S"))
        state.on_press("W", 100.0)
        state.on_press("S", 150.0)
        state._reset()

        assert state.cs_release_key is None
        assert state.cs_release_time is None
        assert state.cs_press_key is None
        assert state.cs_press_time is None
        assert state.overlap_start_time is None
        assert len(state.held_keys) == 0
        assert len(state.press_times) == 0


class TestMovementClassifierCounterStrafe:
    """Tests for counter-strafe classification."""

    def test_clean_counter_strafe_vertical(self) -> None:
        """Test clean counter-strafe on vertical axis."""
        classifier = MovementClassifier()
        # Press W, release W, press S, shoot
        classifier.on_press("W", 100.0)
        classifier.on_release("W", 200.0)
        classifier.on_press("S", 250.0)
        result = classifier.classify_shot(300.0)

        assert result.label == "Counter‑strafe"
        assert result.cs_time == 50.0  # 250 - 200
        assert result.shot_delay == 50.0  # 300 - 250

    def test_clean_counter_strafe_horizontal(self) -> None:
        """Test clean counter-strafe on horizontal axis."""
        classifier = MovementClassifier()
        # Press A, release A, press D, shoot
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 200.0)
        classifier.on_press("D", 230.0)
        result = classifier.classify_shot(280.0)

        assert result.label == "Counter‑strafe"
        assert result.cs_time == 30.0  # 230 - 200
        assert result.shot_delay == 50.0  # 280 - 230

    def test_counter_strafe_slow_shot_delay_raw(self) -> None:
        """Test that classifier returns Counter-strafe even with slow shot delay.
        
        Note: Threshold enforcement happens in input_events.py _build_classification().
        The classifier only detects the pattern and returns raw timing data.
        """
        classifier = MovementClassifier(max_shot_delay=230.0, max_cs_time=215.0)
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 200.0)
        classifier.on_press("D", 250.0)
        # Classifier returns Counter-strafe with raw timing data
        result = classifier.classify_shot(500.0)  # 250ms shot delay

        # Classifier detects the pattern, threshold check is in input_events
        assert result.label == "Counter‑strafe"
        assert result.shot_delay == 250.0  # Raw timing data

    def test_counter_strafe_slow_cs_time(self) -> None:
        """Test counter-strafe with slow CS time and shot delay becomes Bad."""
        classifier = MovementClassifier(max_shot_delay=230.0, max_cs_time=215.0)
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 200.0)
        classifier.on_press("D", 450.0)  # 250ms CS time (> 215)
        result = classifier.classify_shot(500.0)  # 50ms shot delay

        # Classifier detects the pattern regardless of timing
        assert result.label == "Counter‑strafe"
        assert result.cs_time == 250.0

    def test_counter_strafe_both_slow(self) -> None:
        """Test counter-strafe with both CS time and shot delay slow."""
        classifier = MovementClassifier(max_shot_delay=230.0, max_cs_time=215.0)
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 200.0)
        classifier.on_press("D", 450.0)  # 250ms CS time (> 215)
        result = classifier.classify_shot(700.0)  # 250ms shot delay (> 215)

        # Classifier detects pattern, threshold enforcement is in input_events
        assert result.label == "Counter‑strafe"
        assert result.cs_time == 250.0
        assert result.shot_delay == 250.0


class TestMovementClassifierOverlap:
    """Tests for overlap classification."""

    def test_overlap_detected(self) -> None:
        """Test that overlap is properly detected."""
        classifier = MovementClassifier()
        # Press A, press D while A is held (overlap), shoot
        classifier.on_press("A", 100.0)
        classifier.on_press("D", 150.0)  # Overlap starts
        result = classifier.classify_shot(200.0)

        assert result.label == "Overlap"
        assert result.overlap_time == 50.0  # 200 - 150

    def test_overlap_vertical(self) -> None:
        """Test overlap on vertical axis."""
        classifier = MovementClassifier()
        classifier.on_press("W", 100.0)
        classifier.on_press("S", 180.0)  # Overlap
        result = classifier.classify_shot(250.0)

        assert result.label == "Overlap"
        assert result.overlap_time == 70.0  # 250 - 180


class TestMovementClassifierBad:
    """Tests for bad movement classification."""

    def test_shot_without_movement(self) -> None:
        """Test shooting without any movement is Bad."""
        classifier = MovementClassifier()
        result = classifier.classify_shot(100.0)
        assert result.label == "Bad"

    def test_shot_while_holding_single_key(self) -> None:
        """Test shooting while holding a single key is Bad."""
        classifier = MovementClassifier()
        classifier.on_press("W", 100.0)
        result = classifier.classify_shot(200.0)
        assert result.label == "Bad"

    def test_shot_after_simple_release(self) -> None:
        """Test shooting after simple release (no opposite press) is Bad."""
        classifier = MovementClassifier()
        classifier.on_press("W", 100.0)
        classifier.on_release("W", 200.0)
        result = classifier.classify_shot(300.0)
        assert result.label == "Bad"


class TestMovementClassifierPriority:
    """Tests for axis priority when both axes have events."""

    def test_overlap_takes_priority_over_counter_strafe(self) -> None:
        """Test that Overlap takes priority over Counter-strafe."""
        classifier = MovementClassifier()
        # Horizontal: counter-strafe
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 200.0)
        classifier.on_press("D", 250.0)
        # Vertical: overlap
        classifier.on_press("W", 150.0)
        classifier.on_press("S", 180.0)  # Overlap

        result = classifier.classify_shot(300.0)
        assert result.label == "Overlap"

    def test_counter_strafe_takes_priority_over_bad(self) -> None:
        """Test that Counter-strafe takes priority over Bad."""
        classifier = MovementClassifier()
        # Horizontal: counter-strafe
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 200.0)
        classifier.on_press("D", 250.0)
        # Vertical: bad (just holding W)
        classifier.on_press("W", 150.0)

        result = classifier.classify_shot(300.0)
        assert result.label == "Counter‑strafe"


class TestShotClassification:
    """Tests for ShotClassification dataclass."""

    def test_counter_strafe_classification(self) -> None:
        result = ShotClassification(label="Counter‑strafe", cs_time=50.0, shot_delay=30.0)
        assert result.label == "Counter‑strafe"
        assert result.cs_time == 50.0
        assert result.shot_delay == 30.0
        assert result.overlap_time is None

    def test_overlap_classification(self) -> None:
        result = ShotClassification(label="Overlap", overlap_time=75.0)
        assert result.label == "Overlap"
        assert result.overlap_time == 75.0
        assert result.cs_time is None
        assert result.shot_delay is None

    def test_bad_classification(self) -> None:
        result = ShotClassification(label="Bad")
        assert result.label == "Bad"
        assert result.cs_time is None
        assert result.shot_delay is None
        assert result.overlap_time is None


class TestCustomKeyBindings:
    """Tests for custom key bindings."""

    def test_esdf_keys(self) -> None:
        """Test classifier with ESDF key bindings."""
        classifier = MovementClassifier(
            vertical_keys=("E", "D"),
            horizontal_keys=("S", "F"),
        )
        classifier.on_press("E", 100.0)
        classifier.on_release("E", 200.0)
        classifier.on_press("D", 250.0)
        result = classifier.classify_shot(300.0)

        assert result.label == "Counter‑strafe"
        assert result.cs_time == 50.0

    def test_invalid_vertical_keys(self) -> None:
        """Test that invalid vertical keys raise ValueError."""
        with pytest.raises(ValueError):
            MovementClassifier(vertical_keys=("W", "W"))

    def test_invalid_horizontal_keys(self) -> None:
        """Test that invalid horizontal keys raise ValueError."""
        with pytest.raises(ValueError):
            MovementClassifier(horizontal_keys=("A", "A"))

    def test_lowercase_keys_normalized(self) -> None:
        """Test that lowercase keys are normalized to uppercase."""
        classifier = MovementClassifier(
            vertical_keys=("w", "s"),
            horizontal_keys=("a", "d"),
        )
        # Should work with uppercase input
        classifier.on_press("W", 100.0)
        classifier.on_release("W", 200.0)
        classifier.on_press("S", 250.0)
        result = classifier.classify_shot(300.0)

        assert result.label == "Counter‑strafe"


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_rapid_key_presses(self) -> None:
        """Test rapid key presses and releases."""
        classifier = MovementClassifier()
        # Rapid tapping
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 110.0)
        classifier.on_press("D", 120.0)
        classifier.on_release("D", 130.0)
        classifier.on_press("A", 140.0)
        result = classifier.classify_shot(150.0)

        # This is actually a valid counter-strafe: release D -> press A
        # CS time: 140 - 130 = 10ms, shot delay: 150 - 140 = 10ms
        assert result.label == "Counter‑strafe"
        assert result.cs_time == 10.0
        assert result.shot_delay == 10.0

    def test_zero_delay_counter_strafe(self) -> None:
        """Test counter-strafe with minimal delay."""
        classifier = MovementClassifier()
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 200.0)
        classifier.on_press("D", 201.0)  # 1ms CS time
        result = classifier.classify_shot(202.0)  # 1ms shot delay

        assert result.label == "Counter‑strafe"
        assert result.cs_time == 1.0
        assert result.shot_delay == 1.0

    def test_release_counter_key_before_shot(self) -> None:
        """Test that releasing the counter-key before shooting still counts as a valid counter-strafe."""
        classifier = MovementClassifier()
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 200.0)
        classifier.on_press("D", 250.0)
        classifier.on_release("D", 280.0)  # Released counter-key before shooting
        result = classifier.classify_shot(300.0)

        assert result.label == "Counter‑strafe"
        assert result.cs_time == 50.0   # 250 - 200
        assert result.shot_delay == 50.0  # 300 - 250

    def test_state_reset_after_shot(self) -> None:
        """Test that state is properly reset after classification."""
        classifier = MovementClassifier()
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 200.0)
        classifier.on_press("D", 250.0)
        classifier.classify_shot(300.0)

        # After shot, pressing W should start fresh
        classifier.on_press("W", 400.0)
        result = classifier.classify_shot(500.0)

        # Should be Bad since there's no counter-strafe sequence
        assert result.label == "Bad"


# ---------------------------------------------------------------------------
# Tests for InputListener._build_classification()
# These tests exercise the threshold / micro-tap logic that lives in
# input_events.py, which is separate from the raw classifier.
# ---------------------------------------------------------------------------


class _StubClassifier:
    """Minimal stand-in for MovementClassifier to feed controlled values."""

    def __init__(
        self,
        max_shot_delay: float = 150.0,
        min_shot_delay: float = 0.0,
        max_cs_time: float = 100.0,
    ) -> None:
        self.max_shot_delay = max_shot_delay
        self.min_shot_delay = min_shot_delay
        self.max_cs_time = max_cs_time


class _StubOverlay:
    last_result: "ShotClassification | None" = None

    def update_result(self, result: "ShotClassification", history=None) -> None:
        self.last_result = result


def _make_listener(
    max_shot_delay: float = 150.0,
    min_shot_delay: float = 0.0,
    max_cs_time: float = 100.0,
) -> "InputListener":
    """Build an InputListener bypassing pynput and real config."""
    from input_events import InputListener

    overlay = _StubOverlay()
    listener = object.__new__(InputListener)
    listener.overlay = overlay
    listener.stats = None
    listener.classifier = _StubClassifier(max_shot_delay, min_shot_delay, max_cs_time)
    return listener


class TestBuildClassification:
    """Tests for InputListener._build_classification() threshold logic."""

    def _call(self, listener, base: "ShotClassification") -> "ShotClassification":
        from input_events import InputListener

        return InputListener._build_classification(listener, base)

    # --- Overlap passthrough ---------------------------------------------------

    def test_overlap_passthrough(self) -> None:
        """Overlap is always returned unchanged."""
        listener = _make_listener()
        base = ShotClassification(label=LABEL_OVERLAP, overlap_time=60.0)
        result = self._call(listener, base)
        assert result.label == LABEL_OVERLAP
        assert result.overlap_time == 60.0

    # --- Clean counter-strafe (within all thresholds) -------------------------

    def test_clean_counter_strafe_passes(self) -> None:
        """cs_time and shot_delay both within limits → Counter-strafe."""
        listener = _make_listener()
        base = ShotClassification(label=LABEL_COUNTER_STRAFE, cs_time=50.0, shot_delay=100.0)
        result = self._call(listener, base)
        assert result.label == LABEL_COUNTER_STRAFE

    # --- shot_delay too slow → Bad --------------------------------------------

    def test_shot_delay_exceeds_max_is_bad(self) -> None:
        """shot_delay > max_shot_delay → Bad."""
        listener = _make_listener(max_shot_delay=150.0)
        base = ShotClassification(label=LABEL_COUNTER_STRAFE, cs_time=50.0, shot_delay=151.0)
        result = self._call(listener, base)
        assert result.label == LABEL_BAD

    def test_shot_delay_exactly_at_max_is_ok(self) -> None:
        """shot_delay == max_shot_delay is still Counter-strafe (not strictly greater)."""
        listener = _make_listener(max_shot_delay=150.0)
        base = ShotClassification(label=LABEL_COUNTER_STRAFE, cs_time=50.0, shot_delay=150.0)
        result = self._call(listener, base)
        assert result.label == LABEL_COUNTER_STRAFE

    # --- shot_delay too fast → Bad --------------------------------------------

    def test_shot_delay_below_min_is_bad(self) -> None:
        """shot_delay < min_shot_delay → Bad."""
        listener = _make_listener(min_shot_delay=40.0)
        base = ShotClassification(label=LABEL_COUNTER_STRAFE, cs_time=50.0, shot_delay=39.0)
        result = self._call(listener, base)
        assert result.label == LABEL_BAD

    def test_shot_delay_exactly_at_min_is_ok(self) -> None:
        """shot_delay == min_shot_delay is still Counter-strafe."""
        listener = _make_listener(min_shot_delay=40.0)
        base = ShotClassification(label=LABEL_COUNTER_STRAFE, cs_time=50.0, shot_delay=40.0)
        result = self._call(listener, base)
        assert result.label == LABEL_COUNTER_STRAFE

    # --- cs_time too slow → Bad -----------------------------------------------

    def test_cs_time_too_slow_is_bad(self) -> None:
        """cs_time > max_cs_time → Bad, regardless of shot_delay."""
        listener = _make_listener(max_cs_time=100.0)
        base = ShotClassification(label=LABEL_COUNTER_STRAFE, cs_time=101.0, shot_delay=80.0)
        result = self._call(listener, base)
        assert result.label == LABEL_BAD

    # --- Bad passthrough ------------------------------------------------------

    def test_bad_passthrough(self) -> None:
        """Plain Bad base result stays Bad."""
        listener = _make_listener()
        base = ShotClassification(label=LABEL_BAD)
        result = self._call(listener, base)
        assert result.label == LABEL_BAD

    def test_counter_strafe_missing_timing_is_bad(self) -> None:
        """Counter-strafe with None cs_time/shot_delay falls back to Bad."""
        listener = _make_listener()
        base = ShotClassification(label=LABEL_COUNTER_STRAFE, cs_time=None, shot_delay=None)
        result = self._call(listener, base)
        assert result.label == LABEL_BAD

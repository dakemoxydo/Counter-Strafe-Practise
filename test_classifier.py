"""
Unit tests for the MovementClassifier in cStrafe UI.

Run with: py -m pytest test_classifier.py -v
"""

import pytest
from classifier import (
    DEFAULT_MAX_CS_TIME,
    DEFAULT_MAX_SHOT_DELAY,
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
        """Test that classifier detects counter-strafe pattern with slow shot delay."""
        classifier = MovementClassifier(max_shot_delay=300.0, max_cs_time=215.0, min_shot_delay=0.0)
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 200.0)
        classifier.on_press("D", 250.0)
        result = classifier.classify_shot(500.0)

        assert result.label == "Counter‑strafe"
        assert result.shot_delay == 250.0

    def test_counter_strafe_slow_cs_time(self) -> None:
        """Test counter-strafe with slow CS time but fast shot delay is OK (as per prototype)."""
        classifier = MovementClassifier(max_shot_delay=230.0, max_cs_time=215.0, min_shot_delay=0.0)
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 200.0)
        classifier.on_press("D", 450.0)  # 250ms CS time (> 215)
        result = classifier.classify_shot(500.0)  # 50ms shot delay

        # In prototype logic, cs_time > max_cs_time AND shot_delay > max_cs_time is Bad
        # Here shot_delay = 50 < 215, so it's Counter-strafe
        assert result.label == "Counter‑strafe"

    def test_counter_strafe_both_slow(self) -> None:
        """Test counter-strafe with both CS time and shot delay slow becomes Bad."""
        classifier = MovementClassifier(max_shot_delay=230.0, max_cs_time=215.0, min_shot_delay=0.0)
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 200.0)
        classifier.on_press("D", 450.0)
        result = classifier.classify_shot(700.0)

        assert result.label == "Bad"


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
        classifier = MovementClassifier(min_shot_delay=0.0)
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
        classifier = MovementClassifier(min_shot_delay=0.0)
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


class TestClassifierThresholdEnforcement:
    """Tests for threshold enforcement in MovementClassifier."""

    def test_shot_delay_exceeds_max_is_bad(self) -> None:
        """shot_delay > max_shot_delay → Bad."""
        classifier = MovementClassifier(max_shot_delay=230.0, min_shot_delay=0.0, max_cs_time=215.0)
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 200.0)
        classifier.on_press("D", 250.0)
        result = classifier.classify_shot(482.0)  # 232ms shot delay > 230
        assert result.label == "Bad"

    def test_shot_delay_exactly_at_max_is_ok(self) -> None:
        """shot_delay == max_shot_delay → Counter-strafe."""
        classifier = MovementClassifier(max_shot_delay=230.0, min_shot_delay=0.0, max_cs_time=215.0)
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 200.0)
        classifier.on_press("D", 250.0)
        result = classifier.classify_shot(480.0)  # 230ms shot delay == 230
        assert result.label == "Counter‑strafe"

    def test_cs_time_and_shot_delay_both_exceed_max_is_bad(self) -> None:
        """cs_time > max_cs_time AND shot_delay > max_cs_time → Bad."""
        classifier = MovementClassifier(max_shot_delay=230.0, min_shot_delay=0.0, max_cs_time=215.0)
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 200.0)
        classifier.on_press("D", 450.0)  # 250ms cs_time > 215
        result = classifier.classify_shot(700.0)  # 250ms shot delay > 215
        assert result.label == "Bad"

    def test_cs_time_exceeds_max_but_shot_delay_below_max_is_ok(self) -> None:
        """cs_time > max_cs_time but shot_delay <= max_cs_time → Counter-strafe."""
        classifier = MovementClassifier(max_shot_delay=230.0, min_shot_delay=0.0, max_cs_time=215.0)
        classifier.on_press("A", 100.0)
        classifier.on_release("A", 200.0)
        classifier.on_press("D", 450.0)  # 250ms cs_time > 215
        result = classifier.classify_shot(500.0)  # 50ms shot delay < 215
        assert result.label == "Counter‑strafe"

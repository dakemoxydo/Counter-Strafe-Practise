import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

from classifier import LABEL_COUNTER_STRAFE, ShotClassification

logger = logging.getLogger(__name__)

STAT_FILE = Path(__file__).parent / "stats.json"


@dataclass
class SessionStatsData:
    total_shots: int = 0
    total_counter_strafes: int = 0
    total_cs_time: float = 0.0
    total_shot_delay: float = 0.0
    recent_history: List[str] = None  # Store last 20 labels

    def __post_init__(self):
        if self.recent_history is None:
            self.recent_history = []


class StatisticsManager:
    """Tracks and persists session statistics to stats.json."""

    def __init__(self) -> None:
        self.data = SessionStatsData()
        self.load()

    def record_shot(self, classification: ShotClassification) -> None:
        self.data.total_shots += 1

        self.data.recent_history.append(classification.label)
        if len(self.data.recent_history) > 20:
            self.data.recent_history.pop(0)

        if classification.label == LABEL_COUNTER_STRAFE:
            self.data.total_counter_strafes += 1
            if classification.cs_time is not None:
                self.data.total_cs_time += classification.cs_time
            if classification.shot_delay is not None:
                self.data.total_shot_delay += classification.shot_delay

        self.save()

    @property
    def accuracy(self) -> float:
        if self.data.total_shots == 0:
            return 0.0
        return (self.data.total_counter_strafes / self.data.total_shots) * 100.0

    @property
    def avg_cs_time(self) -> float:
        if self.data.total_counter_strafes == 0:
            return 0.0
        return self.data.total_cs_time / self.data.total_counter_strafes

    @property
    def avg_shot_delay(self) -> float:
        if self.data.total_counter_strafes == 0:
            return 0.0
        return self.data.total_shot_delay / self.data.total_counter_strafes

    def reset_session(self) -> None:
        self.data = SessionStatsData()
        self.save()

    def load(self) -> None:
        if not STAT_FILE.exists():
            return
        try:
            with open(STAT_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                self.data = SessionStatsData(**loaded)
        except Exception as e:
            logger.warning(f"Could not load stats.json: {e}")

    def save(self) -> None:
        try:
            with open(STAT_FILE, "w", encoding="utf-8") as f:
                json.dump(asdict(self.data), f, indent=4)
        except Exception as e:
            logger.warning(f"Could not save stats.json: {e}")


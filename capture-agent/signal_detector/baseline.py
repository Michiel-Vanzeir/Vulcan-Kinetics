"""Rolling per-user typing baseline, as exponential moving averages."""

from dataclasses import dataclass

# Below these values a relative shift is meaningless (e.g. a deletion rate moving from 0).
_PAUSE_FLOOR_MS = 1.0
_DELETION_RATE_FLOOR = 0.01


@dataclass
class _UserBaseline:
    avg_pause_ms: float | None = None
    avg_deletion_rate: float | None = None
    emitted: tuple[float | None, float | None] | None = None


class BaselineTracker:
    """Tracks avg_pause_ms and avg_deletion_rate per user across contexts."""

    def __init__(self, alpha: float = 0.1, gap_cap_ms: int = 10_000, shift_threshold: float = 0.2):
        if not 0 < alpha <= 1:
            raise ValueError("alpha must be in (0, 1]")
        self._alpha = alpha
        self._gap_cap_ms = gap_cap_ms
        self._shift_threshold = shift_threshold
        self._users: dict[str, _UserBaseline] = {}

    def _ema(self, current: float | None, value: float) -> float:
        return value if current is None else current + self._alpha * (value - current)

    def observe_gap(self, user_id: str, gap_ms: int) -> None:
        """Add an inter-keystroke gap. Gaps of 10 s or more aren't typing and are ignored."""
        if 0 <= gap_ms < self._gap_cap_ms:
            user = self._users.setdefault(user_id, _UserBaseline())
            user.avg_pause_ms = self._ema(user.avg_pause_ms, gap_ms)

    def observe_deletion_rate(self, user_id: str, deletions: int, chars_typed: int) -> None:
        """Add one period's deletions per typed char. Periods without typing are ignored."""
        if chars_typed > 0:
            user = self._users.setdefault(user_id, _UserBaseline())
            user.avg_deletion_rate = self._ema(user.avg_deletion_rate, deletions / chars_typed)

    def get(self, user_id: str) -> dict[str, float | None]:
        """Current baseline for a user; values are None until observed."""
        user = self._users.get(user_id, _UserBaseline())
        return {"avg_pause_ms": user.avg_pause_ms, "avg_deletion_rate": user.avg_deletion_rate}

    def take_if_due(self, user_id: str) -> dict[str, float | None] | None:
        """Baseline to include in the next payload: first time it exists, then on a > 20% shift."""
        user = self._users.get(user_id)
        if user is None or (user.avg_pause_ms is None and user.avg_deletion_rate is None):
            return None
        if user.emitted is not None:
            last_pause, last_rate = user.emitted
            shifted = self._shifted(last_pause, user.avg_pause_ms, _PAUSE_FLOOR_MS) or self._shifted(
                last_rate, user.avg_deletion_rate, _DELETION_RATE_FLOOR
            )
            if not shifted:
                return None
        user.emitted = (user.avg_pause_ms, user.avg_deletion_rate)
        return self.get(user_id)

    def _shifted(self, last: float | None, current: float | None, floor: float) -> bool:
        if current is None:
            return False
        if last is None:
            return True
        return abs(current - last) > self._shift_threshold * max(abs(last), floor)

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from typing import Literal

RiskStatus = Literal["Normal", "Warning", "Critical"]
TrendLabel = Literal["stable", "declining", "critical"]
HISTORY_WINDOW_SECONDS = 60
ROLLING_BASELINE_SIZE = 8


def assess_status(hr: int, spo2: int) -> RiskStatus:
    if hr < 50 or hr > 150 or spo2 < 90:
        return "Critical"
    if hr < 60 or hr > 110 or spo2 < 94:
        return "Warning"
    return "Normal"


def prune_history(point_history: deque[dict[str, int | datetime]], current_time: datetime) -> None:
    while point_history:
        oldest_time = point_history[0]["timestamp"]
        if not isinstance(oldest_time, datetime):
            point_history.popleft()
            continue
        if current_time - oldest_time > timedelta(seconds=HISTORY_WINDOW_SECONDS):
            point_history.popleft()
            continue
        break


def spo2_drop_over_window(point_history: deque[dict[str, int | datetime]]) -> int | None:
    if len(point_history) < 2:
        return None

    oldest = point_history[0].get("spo2")
    latest = point_history[-1].get("spo2")
    if not isinstance(oldest, int) or not isinstance(latest, int):
        return None

    return oldest - latest


def is_spo2_decreasing_over_time(point_history: deque[dict[str, int | datetime]]) -> bool:
    if len(point_history) < 4:
        return False

    recent = list(point_history)[-6:]
    spo2_values: list[int] = [value for point in recent if isinstance((value := point.get("spo2")), int)]

    if len(spo2_values) < 4:
        return False

    non_increasing = all(
        next_value <= current_value
        for current_value, next_value in zip(spo2_values, spo2_values[1:])
    )
    return non_increasing and spo2_values[-1] < spo2_values[0]


def detect_sudden_spike(point_history: deque[dict[str, int | datetime]]) -> bool:
    if len(point_history) < 2:
        return False

    previous = point_history[-2]
    current = point_history[-1]

    prev_hr = previous.get("hr")
    prev_spo2 = previous.get("spo2")
    curr_hr = current.get("hr")
    curr_spo2 = current.get("spo2")
    if not all(isinstance(v, int) for v in [prev_hr, prev_spo2, curr_hr, curr_spo2]):
        return False

    hr_delta = abs(curr_hr - prev_hr)
    spo2_delta = abs(curr_spo2 - prev_spo2)
    return hr_delta >= 30 or spo2_delta >= 6


def detect_rolling_anomaly(point_history: deque[dict[str, int | datetime]]) -> bool:
    if len(point_history) < ROLLING_BASELINE_SIZE + 1:
        return False

    window = list(point_history)[-(ROLLING_BASELINE_SIZE + 1):]
    baseline = window[:-1]
    current = window[-1]

    baseline_hr = [int(point["hr"]) for point in baseline if isinstance(point.get("hr"), int)]
    baseline_spo2 = [int(point["spo2"]) for point in baseline if isinstance(point.get("spo2"), int)]

    current_hr = current.get("hr")
    current_spo2 = current.get("spo2")
    if not baseline_hr or not baseline_spo2:
        return False
    if not isinstance(current_hr, int) or not isinstance(current_spo2, int):
        return False

    avg_hr = sum(baseline_hr) / len(baseline_hr)
    avg_spo2 = sum(baseline_spo2) / len(baseline_spo2)

    hr_shift = abs(current_hr - avg_hr)
    spo2_shift = avg_spo2 - current_spo2
    return hr_shift >= 25 or spo2_shift >= 5


def classify_trend(
    status: RiskStatus,
    spo2_drop: int | None,
    point_history: deque[dict[str, int | datetime]],
    sudden_spike: bool,
    rolling_anomaly: bool,
) -> TrendLabel:
    if status == "Critical":
        return "critical"
    if sudden_spike or rolling_anomaly:
        return "declining"
    if spo2_drop is not None and spo2_drop >= 5:
        return "declining"
    if is_spo2_decreasing_over_time(point_history):
        return "declining"
    return "stable"

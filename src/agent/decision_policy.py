from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping


class DecisionState(StrEnum):
    NORMAL = "NORMAL"
    MONITOR = "MONITOR"
    WARNING = "WARNING"
    MAINTENANCE_ALERT = "MAINTENANCE_ALERT"
    EMERGENCY_STOP = "EMERGENCY_STOP"


@dataclass(frozen=True)
class Decision:
    state: DecisionState
    reason: str
    consecutive_anomaly_count: int
    is_anomaly: bool


@dataclass(frozen=True)
class DangerGroups:
    vibration: bool
    thermal_electrical: bool
    frequency: bool

    @property
    def active_count(self) -> int:
        return int(self.vibration) + int(self.thermal_electrical) + int(self.frequency)


def anomaly_strength(score: float, threshold: float) -> str:
    if score >= threshold:
        recovery_margin = score - threshold
        if recovery_margin >= max(abs(threshold) * 2.0, 0.02):
            return "very_normal"
        return "normal"

    anomaly_margin = threshold - score
    if anomaly_margin >= max(abs(threshold) * 2.0, 0.02):
        return "strong_anomaly"
    return "weak_anomaly"


def update_anomaly_counter(
    score: float,
    threshold: float,
    consecutive_anomaly_count: int,
) -> tuple[bool, int, str]:
    is_anomaly = score < threshold
    strength = anomaly_strength(score, threshold)
    if strength == "strong_anomaly":
        return True, consecutive_anomaly_count + 2, strength
    if strength == "weak_anomaly":
        return True, consecutive_anomaly_count + 1, strength
    if strength == "very_normal":
        return False, max(0, consecutive_anomaly_count - 2), strength
    return False, max(0, consecutive_anomaly_count - 1), strength


def detect_danger_groups(features: Mapping[str, float]) -> DangerGroups:
    vib_instability = float(features.get("vib_instability", 0))
    vib_sum = float(features.get("vib_sum", 0))
    vib_window_max = float(features.get("vib_sum_window_max", vib_sum))
    vib_hf_ratio = float(features.get("vib_hf_ratio", features.get("freq_ratio", 0)))
    temp_delta = float(features.get("temp_delta", 0))
    current = float(features.get("Current", 0))
    delta_current = float(features.get("delta_Current", 0))
    delta_temp = float(features.get("delta_temp_mot", 0))
    freq_ratio = float(features.get("freq_ratio", 0))
    freq_high = float(features.get("freq_high", 0))
    freq_high_window_max = float(features.get("freq_high_window_max", freq_high))

    vibration_danger = (
        vib_instability > 1.0
        or vib_hf_ratio > 2.0
        or vib_window_max > max(vib_sum * 1.5, vib_sum + 5.0)
    )
    thermal_electrical_danger = (
        (delta_temp > 0.3 and delta_current > 0.2)
        or (temp_delta > 35 and current > 2.5)
    )
    frequency_danger = (
        freq_ratio > 2.0
        or freq_high_window_max > max(freq_high * 1.5, freq_high + 25.0)
    )

    return DangerGroups(
        vibration=vibration_danger,
        thermal_electrical=thermal_electrical_danger,
        frequency=frequency_danger,
    )


def state_from_counter(
    consecutive_anomaly_count: int,
    is_anomaly: bool,
    score: float,
    threshold: float,
    danger_groups: DangerGroups,
    maintenance_alert_count: int = 5,
) -> DecisionState:
    emergency_count = max(8, maintenance_alert_count + 3)
    if (
        consecutive_anomaly_count >= emergency_count
        and is_anomaly
        and score < threshold - 0.02
        and danger_groups.thermal_electrical
        and (danger_groups.vibration or danger_groups.frequency)
    ):
        return DecisionState.EMERGENCY_STOP
    if consecutive_anomaly_count >= maintenance_alert_count:
        return DecisionState.MAINTENANCE_ALERT
    if consecutive_anomaly_count >= 3:
        return DecisionState.WARNING
    if consecutive_anomaly_count >= 1:
        return DecisionState.MONITOR
    return DecisionState.NORMAL


def generate_reason(
    score: float,
    threshold: float,
    is_anomaly: bool,
    consecutive_anomaly_count: int,
    strength: str,
    danger_groups: DangerGroups,
    features: Mapping[str, float],
) -> str:
    if not is_anomaly:
        if consecutive_anomaly_count > 0:
            if strength == "very_normal":
                return "Very normal score, alert counter cooling down faster"
            return "Normal score, alert counter cooling down gradually"
        return "Score above threshold, normal motor behavior"

    margin = threshold - score
    reasons: list[str] = []

    if danger_groups.vibration:
        reasons.append("High vibration instability -> possible mechanical fault")

    if danger_groups.thermal_electrical:
        reasons.append("Temperature and current rising -> possible overheating / overload")

    if danger_groups.frequency:
        reasons.append("High frequency vibration energy elevated -> possible bearing or friction issue")

    if danger_groups.active_count >= 2:
        reasons.append("Multiple signals abnormal -> critical condition")
    elif consecutive_anomaly_count >= 8 and danger_groups.vibration:
        reasons.append("Repeated mechanical anomaly -> maintenance alert, emergency gated off")

    if not reasons and strength == "weak_anomaly":
        reasons.append("Score slightly below threshold -> monitoring only")

    if strength == "strong_anomaly":
        reasons.append("Score far below threshold -> strong anomaly signal")

    if not reasons:
        reasons.append("Score below normal baseline threshold -> suspicious behavior")

    return "; ".join(dict.fromkeys(reasons))


def make_decision(
    score: float,
    threshold: float,
    consecutive_anomaly_count: int,
    features: Mapping[str, float],
    maintenance_alert_count: int = 5,
) -> Decision:
    is_anomaly, updated_count, strength = update_anomaly_counter(
        score=score,
        threshold=threshold,
        consecutive_anomaly_count=consecutive_anomaly_count,
    )
    danger_groups = detect_danger_groups(features)
    state = state_from_counter(
        updated_count,
        is_anomaly,
        score,
        threshold,
        danger_groups,
        maintenance_alert_count=maintenance_alert_count,
    )
    reason = generate_reason(
        score=score,
        threshold=threshold,
        is_anomaly=is_anomaly,
        consecutive_anomaly_count=updated_count,
        strength=strength,
        danger_groups=danger_groups,
        features=features,
    )
    return Decision(
        state=state,
        reason=reason,
        consecutive_anomaly_count=updated_count,
        is_anomaly=is_anomaly,
    )

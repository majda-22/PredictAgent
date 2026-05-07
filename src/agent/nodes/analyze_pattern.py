from collections import Counter

from src.agent.state import AgentState


PATTERNS = {"mechanical", "thermal", "electrical", "mixed", "unknown"}


def analyze_pattern(state: AgentState) -> AgentState:
    events = state.get("events", [])
    reasons = " ".join(str(event.get("reason", "")).lower() for event in events)
    temperatures = [float(event["temperature"]) for event in events if event.get("temperature") is not None]
    currents = [float(event["current"]) for event in events if event.get("current") is not None]
    vibrations = [float(event["vibration"]) for event in events if event.get("vibration") is not None]

    evidence: list[str] = []
    votes: Counter[str] = Counter()

    if "vibration" in reasons or (vibrations and max(vibrations) > 1.5 * max(min(vibrations), 1e-6)):
        votes["mechanical"] += 2
        evidence.append("Repeated vibration-related abnormality")

    if "temperature" in reasons or _range_is_large(temperatures, minimum_delta=10):
        votes["thermal"] += 2
        evidence.append("Temperature elevated or changing quickly")

    if "current" in reasons or _range_is_large(currents, minimum_delta=0.5):
        votes["electrical"] += 2
        evidence.append("Current/load behavior changed across recent events")

    if "multiple signals" in reasons:
        votes["mixed"] += 3
        evidence.append("Decision layer reported multiple abnormal signal groups")

    if not votes:
        pattern = "unknown"
        confidence = 0.3
        evidence.append("Insufficient evidence for a specific fault pattern")
    elif len([key for key, value in votes.items() if value >= 2]) > 1:
        pattern = "mixed"
        confidence = 0.75
    else:
        pattern, score = votes.most_common(1)[0]
        confidence = min(0.9, 0.45 + score * 0.18)

    if pattern not in PATTERNS:
        pattern = "unknown"

    return {
        **state,
        "pattern_analysis": {
            "pattern": pattern,
            "confidence": round(confidence, 2),
            "evidence": evidence,
        },
    }


def _range_is_large(values: list[float], minimum_delta: float) -> bool:
    if len(values) < 2:
        return False
    return max(values) - min(values) >= minimum_delta

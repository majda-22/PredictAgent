from src.storage.event_store import EventStore


CRITICAL_DECISIONS = {"MAINTENANCE_ALERT", "EMERGENCY_STOP"}


def should_trigger_agent(store: EventStore | None = None) -> tuple[bool, str]:
    event_store = store or EventStore()
    latest = event_store.latest_motor_state()
    if latest is None:
        return False, "no events available"
    latest_decision = str(latest.get("decision", "NORMAL"))
    latest_score = latest.get("score")

    if latest_decision == "NORMAL" and latest_score is None:
        return False, "latest event is warmup"

    if latest_decision == "NORMAL":
        trend_events = event_store.recent_events_for_trend(limit=20)
        if _score_trend_is_degrading(trend_events):
            return True, "anomaly score trend degrading"
        return False, "latest event is normal"

    if latest_decision in CRITICAL_DECISIONS:
        return True, "recent maintenance or emergency decision"

    last_10 = event_store.latest_events(limit=10)
    monitor_count = sum(event["decision"] == "MONITOR" for event in last_10)
    if latest_decision == "MONITOR" and monitor_count >= 6:
        return True, "repeated monitor decisions"

    trend_events = event_store.recent_events_for_trend(limit=20)
    if _score_trend_is_degrading(trend_events):
        return True, "anomaly score trend degrading"

    return False, "no trigger condition met"


def _score_trend_is_degrading(events: list[dict[str, object]]) -> bool:
    scores = [
        float(event["score"])
        for event in events
        if event.get("score") is not None
    ]
    if len(scores) < 12:
        return False

    first_half = scores[: len(scores) // 2]
    second_half = scores[len(scores) // 2 :]
    if not first_half or not second_half:
        return False

    first_avg = sum(first_half) / len(first_half)
    second_avg = sum(second_half) / len(second_half)
    lower_score_is_worse = second_avg < first_avg
    mostly_declining = sum(
        later < earlier
        for earlier, later in zip(scores, scores[1:])
    ) >= int(len(scores) * 0.65)
    return lower_score_is_worse and mostly_declining

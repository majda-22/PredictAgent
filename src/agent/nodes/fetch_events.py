from src.agent.state import AgentState
from src.storage.event_store import EventStore


def fetch_events(state: AgentState) -> AgentState:
    store = EventStore()
    non_normal_events = store.recent_non_normal_events(hours=1)
    trend_events = store.recent_events_for_trend(limit=200)
    latest_state = store.latest_motor_state()

    scores = [
        float(event["score"])
        for event in trend_events
        if event.get("score") is not None
    ]
    trend = {
        "total_events": len(trend_events),
        "non_normal_last_hour": len(non_normal_events),
        "score_count": len(scores),
        "score_latest": scores[-1] if scores else None,
        "score_min": min(scores) if scores else None,
        "score_mean": sum(scores) / len(scores) if scores else None,
        "monitor_count": sum(event["decision"] == "MONITOR" for event in trend_events),
        "maintenance_count": sum(event["decision"] == "MAINTENANCE_ALERT" for event in trend_events),
        "emergency_count": sum(event["decision"] == "EMERGENCY_STOP" for event in trend_events),
    }

    return {
        **state,
        "events": non_normal_events or trend_events[-20:],
        "trend": trend,
        "latest_motor_state": latest_state,
    }

from src.agent.state import AgentState


SEVERITY_ORDER = {
    "NORMAL": 0,
    "MONITOR": 1,
    "WARNING": 2,
    "MAINTENANCE_ALERT": 3,
    "EMERGENCY_STOP": 4,
}


def estimate_risk(state: AgentState) -> AgentState:
    events = state.get("events", [])
    trend = state.get("trend", {})
    pattern = state.get("pattern_analysis", {}).get("pattern", "unknown")
    max_severity = max(
        (SEVERITY_ORDER.get(str(event.get("decision")), 0) for event in events),
        default=0,
    )
    maintenance_count = int(trend.get("maintenance_count") or 0)
    emergency_count = int(trend.get("emergency_count") or 0)
    monitor_count = int(trend.get("monitor_count") or 0)

    if emergency_count > 0 or max_severity >= SEVERITY_ORDER["EMERGENCY_STOP"]:
        severity = "high"
        action = "Stop the motor and inspect the system before restarting."
    elif maintenance_count > 0 or max_severity >= SEVERITY_ORDER["MAINTENANCE_ALERT"]:
        severity = "medium"
        action = _maintenance_action(pattern)
    elif monitor_count >= 6 or max_severity >= SEVERITY_ORDER["WARNING"]:
        severity = "medium"
        action = "Keep the motor under observation and inspect if monitor events continue."
    else:
        severity = "low"
        action = "No immediate action. Continue monitoring the next operating window."

    return {
        **state,
        "risk": {
            "severity": severity,
            "estimated_time_to_failure": "unknown",
            "confidence": "low confidence" if len(events) < 10 else "needs more data",
            "recommended_action": action,
        },
    }


def _maintenance_action(pattern: str) -> str:
    if pattern == "mechanical":
        return "Inspect bearings, alignment, mounting, and vibration source within the next maintenance window."
    if pattern == "thermal":
        return "Check cooling, load level, and motor temperature rise before extended operation."
    if pattern == "electrical":
        return "Inspect supply voltage, current draw, wiring, and load changes."
    if pattern == "mixed":
        return "Inspect mechanical and electrical subsystems before continuing high-load operation."
    return "Inspect the motor and collect more data before deciding on component-level repair."

from pathlib import Path

from src.agent.llm_client import LLMClient
from src.agent.state import AgentState


REPORTS_DIR = Path("reports/agent")


INSTRUCTIONS = """
You are an electrical and predictive-maintenance assistant for a DC motor.
Use only the provided event data, deterministic analysis, and previous report summaries.
Never claim an exact time-to-failure unless the data supports it.
If information is missing, ask concise follow-up questions.
Recommend engineer alerts only when the evidence justifies it.
"""


def llm_reasoning(state: AgentState) -> AgentState:
    previous_reports = _load_previous_reports(limit=3)
    client = LLMClient()
    fallback = _fallback_analysis(state, previous_reports)
    if not client.available:
        return {
            **state,
            "previous_reports": previous_reports,
            "llm_analysis": {
                **fallback,
                "llm_enabled": False,
                "note": "LLM API key not configured; deterministic fallback used",
            },
            "missing_context_questions": fallback["missing_context_questions"],
        }

    llm_result = client.complete_json(
        instructions=INSTRUCTIONS,
        input_data={
            "brief": _brief_context(state, previous_reports),
            "required_schema": {
                "summary": "string",
                "comparison_to_previous_reports": "string",
                "missing_context_questions": ["string"],
                "send_engineer_alert": "boolean",
                "alert_rationale": "string",
                "recommended_next_steps": ["string"],
            },
        },
    )
    if not llm_result:
        llm_result = fallback
    elif "llm_error" in llm_result:
        llm_result = {
            **fallback,
            "llm_enabled": False,
            "note": "LLM request failed; deterministic fallback used",
            "llm_error": llm_result["llm_error"],
        }
    else:
        llm_result["llm_enabled"] = True
    return {
        **state,
        "previous_reports": previous_reports,
        "llm_analysis": llm_result,
        "missing_context_questions": llm_result.get("missing_context_questions", []),
    }


def _load_previous_reports(limit: int) -> list[dict[str, str]]:
    if not REPORTS_DIR.exists():
        return []
    report_files = sorted(
        REPORTS_DIR.glob("*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:limit]
    reports = []
    for path in report_files:
        reports.append(
            {
                "path": str(path),
                "summary": _first_sentence(path.read_text(encoding="utf-8", errors="ignore")),
            }
        )
    return reports


def _brief_context(state: AgentState, previous_reports: list[dict[str, str]]) -> str:
    risk = state.get("risk", {})
    pattern = state.get("pattern_analysis", {})
    trend = state.get("trend", {})
    latest = state.get("latest_motor_state") or {}
    return (
        f"Motor risk is {risk.get('severity', 'unknown')} with {pattern.get('pattern', 'unknown')} pattern; "
        f"latest decision={latest.get('decision', 'unknown')}, score={latest.get('score', 'unknown')}, "
        f"recent maintenance={trend.get('maintenance_count', 0)}, emergency={trend.get('emergency_count', 0)}. "
        f"Previous reports available: {len(previous_reports)}."
    )


def _first_sentence(text: str) -> str:
    compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if not compact:
        return ""
    first = compact.split(". ", 1)[0].strip()
    return first[:280]


def _fallback_analysis(
    state: AgentState,
    previous_reports: list[dict[str, str]],
) -> dict:
    risk = state.get("risk", {})
    pattern = state.get("pattern_analysis", {})
    severity = risk.get("severity", "unknown")
    questions = []
    if not state.get("events"):
        questions.append("No recent events were available; verify that MQTT event storage is running.")
    if pattern.get("pattern") in {"mixed", "unknown"}:
        questions.append("Can the engineer confirm whether vibration, current, or temperature changed first?")
    if not previous_reports:
        questions.append("No previous maintenance report is available for comparison.")

    return {
        "summary": (
            f"Deterministic analysis found {pattern.get('pattern', 'unknown')} behavior "
            f"with {severity} risk."
        ),
        "comparison_to_previous_reports": (
            "Previous reports available for comparison."
            if previous_reports
            else "No previous reports available."
        ),
        "missing_context_questions": questions,
        "send_engineer_alert": severity in {"medium", "high"},
        "alert_rationale": f"Severity is {severity}.",
        "recommended_next_steps": [risk.get("recommended_action", "Continue monitoring.")],
    }

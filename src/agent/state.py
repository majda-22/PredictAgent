from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    trigger_reason: str
    events: list[dict[str, Any]]
    trend: dict[str, Any]
    latest_motor_state: dict[str, Any] | None
    pattern_analysis: dict[str, Any]
    risk: dict[str, Any]
    previous_reports: list[dict[str, Any]]
    llm_analysis: dict[str, Any]
    missing_context_questions: list[str]
    report_text: str
    markdown_path: str | None
    pdf_path: str | None
    alert_status: dict[str, Any]

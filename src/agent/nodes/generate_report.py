from datetime import datetime

from src.agent.reports.report_template import (
    build_report_text,
    save_report_markdown,
    save_report_pdf,
)
from src.agent.state import AgentState


def generate_report(state: AgentState) -> AgentState:
    report_text = build_report_text(
        pattern_analysis=state.get("pattern_analysis", {}),
        risk=state.get("risk", {}),
        trend=state.get("trend", {}),
        events=state.get("events", []),
        llm_analysis=state.get("llm_analysis", {}),
    )
    report_id = "motor_report_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = save_report_markdown(report_text, report_id)
    pdf_path = save_report_pdf(report_text, report_id)
    return {
        **state,
        "report_text": report_text,
        "markdown_path": md_path,
        "pdf_path": pdf_path,
    }

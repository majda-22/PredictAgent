from pathlib import Path
from textwrap import wrap


REPORTS_DIR = Path("reports/agent")


def build_report_text(
    *,
    pattern_analysis: dict,
    risk: dict,
    trend: dict,
    events: list[dict],
    llm_analysis: dict | None = None,
) -> str:
    timeline = "\n".join(
        "- {timestamp} | {decision} | score={score} | {reason}".format(
            timestamp=event.get("timestamp") or event.get("created_at"),
            decision=event.get("decision"),
            score=_format_score(event.get("score")),
            reason=event.get("reason", ""),
        )
        for event in events[-12:]
    )
    evidence = "\n".join(
        f"- {item}" for item in pattern_analysis.get("evidence", [])
    )
    llm_section = _llm_section(llm_analysis or {})
    return f"""# Motor Maintenance Report

## Motor Health Summary

Recent non-normal events: {trend.get("non_normal_last_hour", 0)}
Recent monitor count: {trend.get("monitor_count", 0)}
Recent maintenance alerts: {trend.get("maintenance_count", 0)}
Recent emergency stops: {trend.get("emergency_count", 0)}
Latest score: {_format_score(trend.get("score_latest"))}

## Detected Pattern

Pattern: {pattern_analysis.get("pattern", "unknown")}
Confidence: {pattern_analysis.get("confidence", 0)}

## Evidence

{evidence or "- No clear evidence available"}

## Risk Level

Severity: {risk.get("severity", "unknown")}
Estimated time to failure: {risk.get("estimated_time_to_failure", "unknown")}
Confidence: {risk.get("confidence", "needs more data")}

## Recommended Action

{risk.get("recommended_action", "Continue monitoring.")}

{llm_section}

## Recent Event Timeline

{timeline or "- No events available"}
"""


def save_report_markdown(report_text: str, report_id: str) -> str:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    md_path = REPORTS_DIR / f"{report_id}.md"
    md_path.write_text(report_text, encoding="utf-8")
    return str(md_path)


def save_report_pdf(report_text: str, report_id: str) -> str:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = REPORTS_DIR / f"{report_id}.pdf"
    lines = []
    for line in report_text.splitlines():
        if not line:
            lines.append("")
            continue
        lines.extend(wrap(line, width=92) or [""])

    content_lines = ["BT", "/F1 10 Tf", "50 780 Td", "14 TL"]
    for line in lines[:52]:
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content_lines.append(f"({escaped}) Tj")
        content_lines.append("T*")
    content_lines.append("ET")
    content = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length " + str(len(content)).encode("ascii") + b" >> stream\n" + content + b"\nendstream endobj\n",
    ]

    with pdf_path.open("wb") as file:
        file.write(b"%PDF-1.4\n")
        offsets = []
        for obj in objects:
            offsets.append(file.tell())
            file.write(obj)
        xref_offset = file.tell()
        file.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        file.write(b"0000000000 65535 f \n")
        for offset in offsets:
            file.write(f"{offset:010d} 00000 n \n".encode("ascii"))
        file.write(
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
        )
    return str(pdf_path)


def _format_score(score: object) -> str:
    if score is None:
        return "unknown"


def _llm_section(llm_analysis: dict) -> str:
    if not llm_analysis:
        return ""
    questions = "\n".join(
        f"- {question}" for question in llm_analysis.get("missing_context_questions", [])
    )
    steps = "\n".join(
        f"- {step}" for step in llm_analysis.get("recommended_next_steps", [])
    )
    return f"""## LLM Maintenance Reasoning

LLM enabled: {llm_analysis.get("llm_enabled", False)}

Summary:
{llm_analysis.get("summary", "No LLM summary available.")}

Comparison to previous reports:
{llm_analysis.get("comparison_to_previous_reports", "No comparison available.")}

Engineer alert decision:
{llm_analysis.get("send_engineer_alert", False)} - {llm_analysis.get("alert_rationale", "")}

Missing context questions:
{questions or "- None"}

LLM recommended next steps:
{steps or "- None"}
"""
    try:
        return f"{float(score):.5f}"
    except (TypeError, ValueError):
        return "unknown"

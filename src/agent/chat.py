from pathlib import Path

from src.agent.llm_client import LLMClient
from src.storage.event_store import EventStore


REPORTS_DIR = Path("reports/agent")


CHAT_INSTRUCTIONS = """
You are a maintenance copilot for an electrical engineer.
Answer questions about the DC motor using only the supplied machine state,
event history, and maintenance reports.
Be clear about uncertainty.
Do not claim exact remaining useful life unless the data supports it.
If the user asks for motor control, explain the current command status but do not override safety logic.
"""


def answer_engineer_question(question: str) -> dict[str, object]:
    store = EventStore()
    latest_state = store.latest_motor_state()
    recent_events = store.latest_events(limit=50)
    reports = _latest_report_texts(limit=3)
    client = LLMClient()

    context = _brief_chat_context(question, latest_state, recent_events, reports)

    if not client.available:
        return {
            "answer": _fallback_answer(question, latest_state, recent_events, reports),
            "llm_enabled": False,
            "sources": _source_paths(reports),
        }

    answer = client.complete(
        instructions=CHAT_INSTRUCTIONS,
        input_text=context,
    )
    return {
        "answer": answer,
        "llm_enabled": True,
        "sources": _source_paths(reports),
    }


def _latest_report_texts(limit: int) -> list[dict[str, str]]:
    if not REPORTS_DIR.exists():
        return []
    report_files = sorted(
        REPORTS_DIR.glob("*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:limit]
    return [
        {
            "path": str(path),
            "text": _first_sentence(path.read_text(encoding="utf-8", errors="ignore")),
        }
        for path in report_files
    ]


def _source_paths(reports: list[dict[str, str]]) -> list[str]:
    return [report["path"] for report in reports]


def _brief_chat_context(
    question: str,
    latest_state: dict | None,
    recent_events: list[dict],
    reports: list[dict[str, str]],
) -> str:
    non_normal = [event for event in recent_events if event.get("decision") != "NORMAL"]
    if latest_state is None:
        machine_sentence = "No machine event is available yet."
    else:
        machine_sentence = (
            f"Latest state: decision={latest_state.get('decision')}, command={latest_state.get('command')}, "
            f"score={latest_state.get('score')}; non-normal events in last 50 rows={len(non_normal)}."
        )
    report_sentence = (
        f"Latest report summary: {reports[0]['text']}"
        if reports
        else "No previous maintenance report is available."
    )
    return f"Question: {question}. {machine_sentence} {report_sentence}"


def _first_sentence(text: str) -> str:
    compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if not compact:
        return ""
    return compact.split(". ", 1)[0].strip()[:280]


def _fallback_answer(
    question: str,
    latest_state: dict | None,
    recent_events: list[dict],
    reports: list[dict[str, str]],
) -> str:
    non_normal = [
        event for event in recent_events if event.get("decision") != "NORMAL"
    ]
    if latest_state is None:
        return "No machine events are available yet. Start the MQTT agent and publish sensor data first."

    latest_decision = latest_state.get("decision")
    latest_command = latest_state.get("command")
    latest_score = latest_state.get("score")
    report_note = (
        f"The latest report is {reports[0]['path']}."
        if reports
        else "No maintenance report has been generated yet."
    )
    return (
        f"Latest motor state: decision={latest_decision}, command={latest_command}, "
        f"score={latest_score}. Recent non-normal events in the last 50 rows: "
        f"{len(non_normal)}. {report_note} "
        "LLM reasoning is disabled because no LLM API key is configured."
    )

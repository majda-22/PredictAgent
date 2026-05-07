from langgraph.graph import END, StateGraph

from src.agent.nodes.analyze_pattern import analyze_pattern
from src.agent.nodes.estimate_risk import estimate_risk
from src.agent.nodes.fetch_events import fetch_events
from src.agent.nodes.generate_report import generate_report
from src.agent.nodes.llm_reasoning import llm_reasoning
from src.agent.nodes.send_alert import send_alert
from src.agent.state import AgentState
from src.agent.trigger import should_trigger_agent


NODES = [
    fetch_events,
    analyze_pattern,
    estimate_risk,
    llm_reasoning,
    generate_report,
    send_alert,
]


def build_compiled_graph():
    graph = StateGraph(AgentState)
    graph.add_node("fetch_events", fetch_events)
    graph.add_node("analyze_pattern", analyze_pattern)
    graph.add_node("estimate_risk", estimate_risk)
    graph.add_node("llm_reasoning", llm_reasoning)
    graph.add_node("generate_report", generate_report)
    graph.add_node("send_alert", send_alert)
    graph.set_entry_point("fetch_events")
    graph.add_edge("fetch_events", "analyze_pattern")
    graph.add_edge("analyze_pattern", "estimate_risk")
    graph.add_edge("estimate_risk", "llm_reasoning")
    graph.add_edge("llm_reasoning", "generate_report")
    graph.add_edge("generate_report", "send_alert")
    graph.add_edge("send_alert", END)
    return graph.compile()


def run_maintenance_agent(
    initial_state: AgentState | None = None,
    require_trigger: bool = True,
) -> AgentState:
    if require_trigger:
        should_run, trigger_reason = should_trigger_agent()
        if not should_run:
            return {
                **(initial_state or {}),
                "alert_status": {
                    "sent": False,
                    "channel": "not_triggered",
                    "detail": trigger_reason,
                },
            }

    state: AgentState = {
        **(initial_state or {}),
        "trigger_reason": trigger_reason if require_trigger else "manual run",
    }
    return build_compiled_graph().invoke(state)


def build_graph() -> list[str]:
    return [
        "fetch_events",
        "analyze_pattern",
        "estimate_risk",
        "llm_reasoning",
        "generate_report",
        "send_alert",
    ]


if __name__ == "__main__":
    final_state = run_maintenance_agent()
    print(final_state.get("risk"))
    print(final_state.get("llm_analysis"))
    print(final_state.get("pdf_path"))
    print(final_state.get("alert_status"))

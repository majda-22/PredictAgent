from pathlib import Path
from io import BytesIO
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import joblib
import numpy as np
import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.agent.decision_policy import DecisionState, make_decision
from src.agent.chat import answer_engineer_question
from src.agent.nodes.send_alert import _send_email_alert, _send_telegram_alert
from src.actions.mqtt_publisher import MQTTPublisher
from src.config import load_env
from src.features.esp32_feature_mapper import ESP32FeatureMapper
from src.storage.event_store import EventStore


load_env()
SCALER_FILE = PROJECT_ROOT / "models" / "scaler.joblib"
MODEL_FILE = PROJECT_ROOT / "models" / "isolation_forest_normal_behavior.joblib"
THRESHOLD_FILE = PROJECT_ROOT / "models" / "isolation_forest_threshold.npy"
FEATURE_COLUMNS_FILE = PROJECT_ROOT / "models" / "isolation_feature_columns.joblib"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
REDUCED_MODEL_FILE = PROJECT_ROOT / "models" / "model_reduced.pkl"
REDUCED_SCALER_FILE = PROJECT_ROOT / "models" / "scaler_reduced.pkl"
VIB_SCALER_FILE = PROJECT_ROOT / "models" / "vib_scaler.pkl"
REDUCED_FEATURE_COLUMNS_FILE = PROJECT_ROOT / "models" / "reduced_feature_columns.joblib"
REDUCED_THRESHOLD_FILE = PROJECT_ROOT / "models" / "reduced_threshold.npy"
REDUCED_RATIO_CLIP_BOUNDS_FILE = PROJECT_ROOT / "models" / "reduced_ratio_clip_bounds.joblib"
REGIME_MODEL_FILE = PROJECT_ROOT / "models" / "regime_kmeans.joblib"
REGIME_SCALER_FILE = PROJECT_ROOT / "models" / "regime_scaler.joblib"
REGIME_IFOREST_FILE = PROJECT_ROOT / "models" / "regime_isolation_forests.joblib"
REGIME_FEATURE_SCALERS_FILE = PROJECT_ROOT / "models" / "regime_feature_scalers.joblib"
REGIME_THRESHOLDS_FILE = PROJECT_ROOT / "models" / "regime_thresholds.joblib"
REGIME1_MODEL_FILE = PROJECT_ROOT / "models" / "regime1_kmeans.joblib"
REGIME1_IFOREST_FILE = PROJECT_ROOT / "models" / "regime1_sub_models.joblib"
REGIME1_FEATURE_SCALERS_FILE = PROJECT_ROOT / "models" / "regime1_sub_feature_scalers.joblib"
REGIME1_THRESHOLDS_FILE = PROJECT_ROOT / "models" / "regime1_sub_thresholds.joblib"
REDUCED_RAW_WINDOW_SIZE = 10
REGIME_COLUMNS = ["speed_rpm", "current_per_rpm"]
REGIME_COUNTER_THRESHOLDS = {0: 3, 2: 5}
REGIME1_COUNTER_THRESHOLDS = {0: 7, 1: 10}


COMMANDS = {
    DecisionState.NORMAL: "NO_ACTION",
    DecisionState.MONITOR: "MONITOR",
    DecisionState.WARNING: "MONITOR",
    DecisionState.MAINTENANCE_ALERT: "ALERT_MAINTENANCE",
    DecisionState.EMERGENCY_STOP: "STOP_MOTOR",
}

MQTT_COMMANDS = {
    "NO_ACTION": "NO_ACTION",
    "MONITOR": "MONITOR",
    "ALERT_MAINTENANCE": "ALERT_MAINTENANCE",
    "STOP_MOTOR": "STOP_MOTOR",
    "START_MOTOR": "START_MOTOR",
    "RESET_ALERTS": "RESET_ALERTS",
    "MANUAL_MODE": "MANUAL_MODE",
}

SETTINGS_STATE = {
    "temperature_alert_sensitivity": 72,
    "vibration_tolerance": 4.5,
    "alert_mode": True,
    "mqtt_broker_url": "mqtt://broker.predictagent.io:1883",
    "client_identity": "ESP32_NODE_ALPHA_01",
    "email_destination": "alerts@company.com",
    "telegram_chat_id": "@predict_alerts_bot",
}
STREAM_ALERT_THRESHOLD = int(os.getenv("STREAM_ALERT_SUCCESSIVE_MAINTENANCE_THRESHOLD", "10"))
STREAM_ALERT_COOLDOWN_SECONDS = int(os.getenv("STREAM_ALERT_COOLDOWN_SECONDS", "600"))


class PredictionRequest(BaseModel):
    features: dict[str, float] = Field(
        ...,
        description="Engineered/window feature values keyed by feature name.",
    )
    consecutive_anomaly_count: int = Field(
        0,
        ge=0,
        description="Current stream alert counter before this row is evaluated.",
    )


class PredictionResponse(BaseModel):
    score: float
    threshold: float
    is_anomaly: bool
    consecutive_anomalies: int
    decision: str
    reason: str
    command: str


class RawSensorRequest(BaseModel):
    timestamp: str
    temperature: float = Field(..., description="Motor temperature")
    current: float
    voltage: float
    vibration: float | None = Field(None, description="Raw vibration scalar if already computed on ESP32")
    vibration_x: float | None = None
    vibration_y: float | None = None
    vibration_z: float | None = None
    speed_rpm: float = 8000.0
    speed_hz: float | None = None
    ambient_temperature: float = 22.0


class RawPredictionResponse(BaseModel):
    buffer_ready: bool
    buffer_size: int
    regime: int | None = None
    sub_regime: int | None = None
    score: float | None
    threshold: float | None
    is_anomaly: bool
    consecutive_anomalies: int
    decision: str
    reason: str
    command: str
    event_id: int | None = None
    mqtt_published: bool = False
    mqtt_error: str | None = None
    live_alert_status: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    scaler_loaded: bool
    reduced_model_loaded: bool
    reduced_scaler_loaded: bool
    regime_model_loaded: bool
    threshold: float
    reduced_threshold: float
    feature_count: int
    reduced_feature_count: int
    raw_window_size: int


class AgentChatRequest(BaseModel):
    question: str


class AgentChatResponse(BaseModel):
    answer: str
    llm_enabled: bool
    sources: list[str]


class ManualCommandRequest(BaseModel):
    command: str


class ManualCommandResponse(BaseModel):
    command: str
    mqtt_published: bool
    mqtt_error: str | None = None


class SettingsUpdateRequest(BaseModel):
    temperature_alert_sensitivity: float | None = None
    vibration_tolerance: float | None = None
    alert_mode: bool | None = None
    mqtt_broker_url: str | None = None
    client_identity: str | None = None
    email_destination: str | None = None
    telegram_chat_id: str | None = None


class ArtifactBundle:
    def __init__(self) -> None:
        self.scaler = joblib.load(SCALER_FILE)
        self.model = joblib.load(MODEL_FILE)
        self.threshold = float(np.load(THRESHOLD_FILE))
        self.feature_columns = joblib.load(FEATURE_COLUMNS_FILE)
        self.reduced_model = joblib.load(REDUCED_MODEL_FILE)
        self.reduced_scaler = joblib.load(REDUCED_SCALER_FILE)
        self.vib_scaler = joblib.load(VIB_SCALER_FILE)
        self.reduced_feature_columns = joblib.load(REDUCED_FEATURE_COLUMNS_FILE)
        self.reduced_threshold = float(np.load(REDUCED_THRESHOLD_FILE))
        self.reduced_ratio_clip_bounds = joblib.load(REDUCED_RATIO_CLIP_BOUNDS_FILE)
        self.regime_model = joblib.load(REGIME_MODEL_FILE)
        self.regime_scaler = joblib.load(REGIME_SCALER_FILE)
        self.regime_models = joblib.load(REGIME_IFOREST_FILE)
        self.regime_feature_scalers = joblib.load(REGIME_FEATURE_SCALERS_FILE)
        self.regime_thresholds = joblib.load(REGIME_THRESHOLDS_FILE)
        self.regime1_model = joblib.load(REGIME1_MODEL_FILE)
        self.regime1_models = joblib.load(REGIME1_IFOREST_FILE)
        self.regime1_feature_scalers = joblib.load(REGIME1_FEATURE_SCALERS_FILE)
        self.regime1_thresholds = joblib.load(REGIME1_THRESHOLDS_FILE)


artifacts = ArtifactBundle()
event_store = EventStore()
mqtt_publisher = MQTTPublisher()
esp32_mapper = ESP32FeatureMapper(
    buffer_size=REDUCED_RAW_WINDOW_SIZE,
    vib_scaler=artifacts.vib_scaler,
    ratio_clip_bounds=artifacts.reduced_ratio_clip_bounds,
)
raw_consecutive_anomaly_count = 0
live_maintenance_alert_streak = 0
live_last_alert_at: datetime | None = None
live_alert_status: dict[str, Any] = {
    "sent": False,
    "detail": "No live stream alert sent yet.",
    "streak": 0,
    "cooldown_seconds": STREAM_ALERT_COOLDOWN_SECONDS,
}
app = FastAPI(
    title="DC Motor Anomaly Decision API",
    version="1.0.0",
    description="Scores engineered DC motor rows and returns an industrial decision.",
)

if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR), name="frontend")


def _validate_features(features: dict[str, Any]) -> None:
    missing = sorted(set(artifacts.feature_columns).difference(features))
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Missing required feature columns",
                "missing_features": missing,
            },
    )


def _score_and_decide(
    features: dict[str, float],
    consecutive_anomaly_count: int,
) -> PredictionResponse:
    feature_frame = pd.DataFrame(
        [[features[column] for column in artifacts.feature_columns]],
        columns=artifacts.feature_columns,
    )
    scaled_features = artifacts.scaler.transform(feature_frame)
    score = float(artifacts.model.decision_function(scaled_features)[0])
    decision = make_decision(
        score=score,
        threshold=artifacts.threshold,
        consecutive_anomaly_count=consecutive_anomaly_count,
        features=features,
    )

    return PredictionResponse(
        score=score,
        threshold=artifacts.threshold,
        is_anomaly=decision.is_anomaly,
        consecutive_anomalies=decision.consecutive_anomaly_count,
        decision=decision.state.value,
        reason=decision.reason,
        command=COMMANDS[decision.state],
    )


def _predict_from_features(
    features: dict[str, float],
    consecutive_anomaly_count: int,
) -> PredictionResponse:
    _validate_features(features)
    return _score_and_decide(features, consecutive_anomaly_count)


def _raw_vibration_magnitude(request: RawSensorRequest) -> float:
    if request.vibration is not None:
        return float(request.vibration)
    if request.vibration_x is None or request.vibration_y is None or request.vibration_z is None:
        raise HTTPException(
            status_code=400,
            detail="Provide either vibration or all three axes: vibration_x, vibration_y, vibration_z",
        )
    return float(np.sqrt(request.vibration_x**2 + request.vibration_y**2 + request.vibration_z**2))


def _reduced_features_for_policy(features: dict[str, float]) -> dict[str, float]:
    return {
        "Voltage": features["Voltage"],
        "Current": features["Current"],
        "temp_mot": features["temp_mot"],
        "temp_delta": features["temp_delta"],
        "delta_Current": features["delta_Current"],
        "delta_temp_mot": features["delta_temp"],
        "vib_instability": features["vib_instability"],
        "vib_sum": features["vib_sum"],
        "vib_sum_window_max": features["1x[Vibration]_rolling_max"] * 10.0,
        "freq_ratio": features["1x[Vibration]"],
        "freq_high_window_max": features["1x[Vibration]_rolling_max"],
    }


def _score_regime_row(feature_frame: pd.DataFrame) -> tuple[int, int | None, float, float]:
    regime = int(
        artifacts.regime_model.predict(
            artifacts.regime_scaler.transform(feature_frame[REGIME_COLUMNS])
        )[0]
    )
    if regime == 1:
        sub_regime = int(artifacts.regime1_model.predict(feature_frame[REGIME_COLUMNS])[0])
        scaled_features = artifacts.regime1_feature_scalers[sub_regime].transform(
            feature_frame
        )
        score = float(
            artifacts.regime1_models[sub_regime].decision_function(scaled_features)[0]
        )
        threshold = float(artifacts.regime1_thresholds[sub_regime])
        return regime, sub_regime, score, threshold

    scaled_features = artifacts.regime_feature_scalers[regime].transform(feature_frame)
    score = float(artifacts.regime_models[regime].decision_function(scaled_features)[0])
    threshold = float(artifacts.regime_thresholds[regime])
    return regime, None, score, threshold


def _record_and_publish_raw_event(
    request: RawSensorRequest,
    vibration: float,
    score: float | None,
    regime: int | None,
    decision: str,
    reason: str,
    command: str,
) -> tuple[int, bool, str | None]:
    event_id = event_store.record_prediction(
        timestamp=request.timestamp,
        temperature=request.temperature,
        current=request.current,
        voltage=request.voltage,
        vibration=vibration,
        score=score,
        regime=regime,
        decision=decision,
        reason=reason,
        command=command,
    )
    mqtt_command = MQTT_COMMANDS.get(command, "MONITOR")
    result = mqtt_publisher.publish_command(mqtt_command)
    return event_id, result.published, result.error


def _live_stream_alert_message(event_id: int, decision: str, score: float, reason: str) -> str:
    return (
        "PredictAgent live alert\n"
        f"More than {STREAM_ALERT_THRESHOLD} successive maintenance alerts detected.\n"
        f"Latest event: #{event_id}, decision={decision}, score={score:.5f}.\n"
        f"Reason: {reason}\n"
        "Recommended action: inspect mechanical and electrical subsystems before continuing high-load operation."
    )


def _cooldown_remaining_seconds(now: datetime) -> int:
    if live_last_alert_at is None:
        return 0
    elapsed = (now - live_last_alert_at).total_seconds()
    return max(0, int(STREAM_ALERT_COOLDOWN_SECONDS - elapsed))


def _send_live_stream_alert(message: str) -> None:
    global live_alert_status

    telegram = _send_telegram_alert(message, None)
    email = _send_email_alert(message)
    live_alert_status = {
        "sent": bool(telegram["sent"] or email["sent"]),
        "channel": "telegram/email",
        "detail": f"telegram={telegram['detail']}; email={email['detail']}",
        "streak": live_maintenance_alert_streak,
        "cooldown_seconds": STREAM_ALERT_COOLDOWN_SECONDS,
        "last_attempt_at": datetime.now(timezone.utc).isoformat(),
    }


def _maybe_queue_live_alert(
    *,
    background_tasks: BackgroundTasks,
    event_id: int,
    decision: str,
    score: float,
    reason: str,
) -> dict[str, Any]:
    global live_maintenance_alert_streak, live_last_alert_at, live_alert_status

    if decision == DecisionState.MAINTENANCE_ALERT.value:
        live_maintenance_alert_streak += 1
    else:
        live_maintenance_alert_streak = 0

    now = datetime.now(timezone.utc)
    cooldown_remaining = _cooldown_remaining_seconds(now)
    status = {
        "sent": False,
        "queued": False,
        "streak": live_maintenance_alert_streak,
        "threshold": STREAM_ALERT_THRESHOLD,
        "cooldown_remaining_seconds": cooldown_remaining,
        "detail": "Waiting for more than 10 successive maintenance alerts.",
    }

    if live_maintenance_alert_streak <= STREAM_ALERT_THRESHOLD:
        live_alert_status = {**live_alert_status, **status}
        return status

    if cooldown_remaining > 0:
        status["detail"] = "Live alert suppressed by cooldown."
        live_alert_status = {**live_alert_status, **status}
        return status

    live_last_alert_at = now
    message = _live_stream_alert_message(event_id, decision, score, reason)
    background_tasks.add_task(_send_live_stream_alert, message)
    status = {
        **status,
        "queued": True,
        "detail": "Live email/Telegram alert queued.",
        "last_queued_at": now.isoformat(),
        "cooldown_remaining_seconds": STREAM_ALERT_COOLDOWN_SECONDS,
    }
    live_alert_status = {**live_alert_status, **status}
    return status


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _score_to_display(score: Any) -> float:
    if score is None:
        return 0.0
    value = _safe_float(score)
    return max(0.0, min(1.0, abs(value)))


def _event_time(event: dict[str, Any]) -> str:
    raw = str(event.get("timestamp") or event.get("created_at") or "")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%H:%M:%S")
    except ValueError:
        return raw[-8:] if len(raw) >= 8 else raw


def _dashboard_payload(limit: int = 80) -> dict[str, Any]:
    events = event_store.recent_events_for_trend(limit=limit)
    latest = events[-1] if events else {}
    counts = Counter(str(event.get("decision", "UNKNOWN")) for event in events)
    non_normal = [
        event
        for event in events
        if str(event.get("decision", "NORMAL")) not in {"NORMAL", "MONITOR"}
    ]
    critical_count = counts.get("EMERGENCY_STOP", 0)
    maintenance_count = counts.get("MAINTENANCE_ALERT", 0) + counts.get("WARNING", 0)
    successful_count = counts.get("NORMAL", 0) + counts.get("MONITOR", 0)

    series = [
        {
            "id": int(event.get("id", index)),
            "time": _event_time(event),
            "temperature": _safe_float(event.get("temperature")),
            "current": _safe_float(event.get("current")),
            "voltage": _safe_float(event.get("voltage")),
            "vibration": _safe_float(event.get("vibration")),
            "score": _safe_float(event.get("score")),
            "score_display": _score_to_display(event.get("score")),
            "decision": str(event.get("decision", "NORMAL")),
            "reason": str(event.get("reason", "")),
            "command": str(event.get("command", "")),
        }
        for index, event in enumerate(events)
    ]
    recent_events = list(reversed(series[-12:]))
    latest_decision = str(latest.get("decision", "NORMAL"))
    health = "Optimal" if critical_count == 0 and maintenance_count < 3 else "Needs Attention"

    return {
        "health": health,
        "latest": {
            "temperature": _safe_float(latest.get("temperature"), 0.0),
            "current": _safe_float(latest.get("current"), 0.0),
            "voltage": _safe_float(latest.get("voltage"), 0.0),
            "vibration": _safe_float(latest.get("vibration"), 0.0),
            "score": _safe_float(latest.get("score"), 0.0),
            "score_display": _score_to_display(latest.get("score")),
            "decision": latest_decision,
            "reason": str(latest.get("reason", "No stream data available yet.")),
            "command": str(latest.get("command", "NO_ACTION")),
            "timestamp": str(latest.get("timestamp", "")),
        },
        "counts": {
            "critical": critical_count,
            "maintenance": maintenance_count,
            "successful": successful_count,
            "total": len(events),
            "by_decision": dict(counts),
        },
        "series": series,
        "events": recent_events,
        "prediction": {
            "hours_to_maintenance": 42 if non_normal else 120,
            "message": (
                "Maintenance should be scheduled soon based on repeated non-normal events."
                if non_normal
                else "No immediate maintenance window is predicted from the current stream."
            ),
        },
    }


def _event_export_rows(limit: int) -> list[dict[str, Any]]:
    return list(reversed(event_store.latest_events(limit=max(1, min(limit, 1000)))))


def _pdf_escape(text: object) -> str:
    return str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _simple_pdf(lines: list[str]) -> bytes:
    text_commands = ["BT", "/F1 9 Tf", "50 760 Td"]
    line_count = 0
    for line in lines:
        if line_count >= 58:
            break
        clipped = _pdf_escape(line[:115])
        text_commands.append(f"({clipped}) Tj")
        text_commands.append("0 -12 Td")
        line_count += 1
    text_commands.append("ET")
    content = "\n".join(text_commands).encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length " + str(len(content)).encode("ascii") + b" >> stream\n" + content + b"\nendstream endobj\n",
    ]
    buffer = BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = []
    for obj in objects:
        offsets.append(buffer.tell())
        buffer.write(obj)
    xref_offset = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets:
        buffer.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    buffer.write(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return buffer.getvalue()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model_loaded=artifacts.model is not None,
        scaler_loaded=artifacts.scaler is not None,
        reduced_model_loaded=artifacts.reduced_model is not None,
        reduced_scaler_loaded=artifacts.reduced_scaler is not None,
        regime_model_loaded=artifacts.regime_model is not None,
        threshold=artifacts.threshold,
        reduced_threshold=artifacts.reduced_threshold,
        feature_count=len(artifacts.feature_columns),
        reduced_feature_count=len(artifacts.reduced_feature_columns),
        raw_window_size=REDUCED_RAW_WINDOW_SIZE,
    )


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend build not found")
    return FileResponse(index_file)


@app.get("/api/dashboard")
def dashboard_data(limit: int = 80) -> dict[str, Any]:
    return _dashboard_payload(limit=max(10, min(limit, 300)))


@app.get("/api/events")
def events(limit: int = 50) -> dict[str, Any]:
    return {"events": list(reversed(event_store.latest_events(limit=max(1, min(limit, 300)))))}


@app.get("/api/events.csv")
def events_csv(limit: int = 300) -> Response:
    rows = _event_export_rows(limit)
    columns = [
        "id",
        "timestamp",
        "temperature",
        "current",
        "voltage",
        "vibration",
        "score",
        "regime",
        "decision",
        "reason",
        "command",
        "created_at",
    ]
    lines = [",".join(columns)]
    for row in rows:
        values = [str(row.get(column, "")).replace('"', '""') for column in columns]
        lines.append(",".join(f'"{value}"' if "," in value or "\n" in value else value for value in values))
    return Response(
        "\n".join(lines),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=predictagent_events.csv"},
    )


@app.get("/api/events.xlsx")
def events_xlsx(limit: int = 300) -> Response:
    rows = _event_export_rows(limit)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, index=False, sheet_name="events")
    buffer.seek(0)
    return Response(
        buffer.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=predictagent_events.xlsx"},
    )


@app.get("/api/events.pdf")
def events_pdf(limit: int = 80) -> Response:
    rows = _event_export_rows(limit=max(1, min(limit, 120)))
    lines = [
        "PredictAgent Events Export",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]
    for row in rows[-35:]:
        score = "warmup" if row.get("score") is None else f"{float(row.get('score')):.5f}"
        lines.append(
            f"#{row.get('id')} {row.get('timestamp')} {row.get('decision')} "
            f"score={score} command={row.get('command')}"
        )
        lines.append(f"Reason: {row.get('reason')}")
        lines.append("")
    return Response(
        _simple_pdf(lines),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=predictagent_events.pdf"},
    )


@app.get("/api/live-alert/status")
def live_alert() -> dict[str, Any]:
    return dict(live_alert_status)


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return dict(SETTINGS_STATE)


@app.post("/api/settings")
def update_settings(request: SettingsUpdateRequest) -> dict[str, Any]:
    updates = request.model_dump(exclude_none=True)
    SETTINGS_STATE.update(updates)
    return {"saved": True, "settings": dict(SETTINGS_STATE)}


@app.post("/api/command", response_model=ManualCommandResponse)
def manual_command(request: ManualCommandRequest) -> ManualCommandResponse:
    command = request.command.upper()
    if command not in MQTT_COMMANDS:
        raise HTTPException(status_code=400, detail=f"Unsupported command: {request.command}")
    result = mqtt_publisher.publish_command(command)
    return ManualCommandResponse(
        command=command,
        mqtt_published=result.published,
        mqtt_error=result.error,
    )


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest) -> PredictionResponse:
    return _predict_from_features(
        features=request.features,
        consecutive_anomaly_count=request.consecutive_anomaly_count,
    )


@app.post("/simulate-row", response_model=PredictionResponse)
def simulate_row(request: PredictionRequest) -> PredictionResponse:
    return _predict_from_features(
        features=request.features,
        consecutive_anomaly_count=request.consecutive_anomaly_count,
    )


@app.post("/agent/chat", response_model=AgentChatResponse)
def agent_chat(request: AgentChatRequest) -> AgentChatResponse:
    result = answer_engineer_question(request.question)
    return AgentChatResponse(
        answer=str(result["answer"]),
        llm_enabled=bool(result["llm_enabled"]),
        sources=list(result.get("sources", [])),
    )


@app.post("/predict-raw", response_model=RawPredictionResponse)
def predict_raw(request: RawSensorRequest, background_tasks: BackgroundTasks) -> RawPredictionResponse:
    global raw_consecutive_anomaly_count

    vibration = _raw_vibration_magnitude(request)
    speed_hz = request.speed_hz if request.speed_hz is not None else request.speed_rpm / 60.0
    features = esp32_mapper.map(
        current=request.current,
        voltage=request.voltage,
        temp_mot=request.temperature,
        temp_amb=request.ambient_temperature,
        speed_rpm=request.speed_rpm,
        speed_hz=speed_hz,
        vibration=vibration,
    )
    if not esp32_mapper.is_ready:
        reason = f"Collecting rolling window rows ({len(esp32_mapper.buffer)}/{REDUCED_RAW_WINDOW_SIZE})"
        command = "NO_ACTION"
        event_id, mqtt_published, mqtt_error = _record_and_publish_raw_event(
            request=request,
            vibration=vibration,
            score=None,
            regime=None,
            decision=DecisionState.NORMAL.value,
            reason=reason,
            command=command,
        )
        return RawPredictionResponse(
            buffer_ready=False,
            buffer_size=len(esp32_mapper.buffer),
            regime=None,
            sub_regime=None,
            score=None,
            threshold=0.0,
            is_anomaly=False,
            consecutive_anomalies=raw_consecutive_anomaly_count,
            decision=DecisionState.NORMAL.value,
            reason=reason,
            command=command,
            event_id=event_id,
            mqtt_published=mqtt_published,
            mqtt_error=mqtt_error,
            live_alert_status=live_alert_status,
        )

    feature_frame = pd.DataFrame(
        [[features[column] for column in artifacts.reduced_feature_columns]],
        columns=artifacts.reduced_feature_columns,
    )
    regime, sub_regime, score, threshold = _score_regime_row(feature_frame)
    is_anomaly = score < threshold
    policy_features = _reduced_features_for_policy(features)
    if regime == 1 and sub_regime is not None:
        maintenance_alert_count = REGIME1_COUNTER_THRESHOLDS.get(sub_regime, 7)
    else:
        maintenance_alert_count = REGIME_COUNTER_THRESHOLDS.get(regime, 5)
    decision = make_decision(
        score=score,
        threshold=threshold,
        consecutive_anomaly_count=raw_consecutive_anomaly_count,
        features=policy_features,
        maintenance_alert_count=maintenance_alert_count,
    )
    raw_consecutive_anomaly_count = decision.consecutive_anomaly_count
    command = COMMANDS[decision.state]
    event_id, mqtt_published, mqtt_error = _record_and_publish_raw_event(
        request=request,
        vibration=vibration,
        score=score,
        regime=regime,
        decision=decision.state.value,
        reason=decision.reason,
        command=command,
    )
    stream_alert_status = _maybe_queue_live_alert(
        background_tasks=background_tasks,
        event_id=event_id,
        decision=decision.state.value,
        score=score,
        reason=decision.reason,
    )

    return RawPredictionResponse(
        buffer_ready=True,
        buffer_size=len(esp32_mapper.buffer),
        regime=regime,
        sub_regime=sub_regime,
        score=score,
        threshold=threshold,
        is_anomaly=is_anomaly,
        consecutive_anomalies=decision.consecutive_anomaly_count,
        decision=decision.state.value,
        reason=decision.reason,
        command=command,
        event_id=event_id,
        mqtt_published=mqtt_published,
        mqtt_error=mqtt_error,
        live_alert_status=stream_alert_status,
    )

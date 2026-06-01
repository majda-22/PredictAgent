# PredictAgent

PredictAgent is a predictive-maintenance system for an industrial DC motor. It receives motor telemetry, transforms raw ESP32-style sensor rows into model features, detects abnormal behavior with Isolation Forest models, applies an industrial decision policy, and exposes the results through a FastAPI backend and a dashboard frontend.

The project also includes MQTT command publishing, Telegram/email alerts, LLM-assisted maintenance reasoning, PDF report generation, and a simulator for testing live streaming data.

## What The System Does

- Streams motor sensor data such as temperature, current, voltage, vibration, RPM, and ambient temperature.
- Builds rolling-window features from raw telemetry.
- Scores behavior using trained Isolation Forest models.
- Classifies operational decisions:
  - `NORMAL`
  - `MONITOR`
  - `WARNING`
  - `MAINTENANCE_ALERT`
  - `EMERGENCY_STOP`
- Publishes motor commands through MQTT.
- Stores events in SQLite for dashboard history and analysis.
- Generates reports and sends Telegram/email alerts.
- Uses a local Ollama LLM by default, with optional OpenAI or OpenRouter support, for short maintenance reasoning.
- Provides a dark/light web dashboard with live charts, alerts, analytics, insights, control, and settings pages.

## Project Structure

```text
src/
  api/                 FastAPI app, frontend serving, prediction endpoints
  agent/               LangGraph maintenance agent, LLM reasoning, reports, alerts
  actions/             MQTT command publisher
  features/            ESP32 raw telemetry feature mapper
  models/              Training/evaluation scripts
  simulation/          Live telemetry simulator
  storage/             SQLite event store
  streaming/           MQTT streaming agent

frontend/              Browser UI served by FastAPI
models/                Trained model/scaler artifacts
reports/               Evaluation reports and generated agent reports
docker-compose.yml     Deployment stack for API, MQTT, and simulator
Dockerfile             Runtime image for API/simulator
requirements-runtime.txt
DEPLOYMENT.md          Detailed Docker deployment commands
```

## Main Runtime Components

| Component | Description |
|---|---|
| FastAPI API | Serves prediction endpoints, dashboard data, exports, settings, commands, and frontend files. |
| Frontend | Dashboard UI at `http://127.0.0.1:8000/`. |
| MQTT Broker | Local Mosquitto broker used for motor command messages. |
| Simulator | Sends fake live ESP32 telemetry into `/predict-raw`. |
| Event Store | SQLite database containing prediction and decision history. |
| Maintenance Agent | Generates reports and sends Telegram/email alerts. |

## Environment Configuration

Copy `.env.example` to `.env` and fill the credentials:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=true
ALERT_EMAIL_FROM=
ALERT_EMAIL_TO=

LLM_PROVIDER=ollama
LLM_ENABLED=true
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.1

MQTT_ENABLED=true
MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_TOPIC=motor/commands

STREAM_ALERT_SUCCESSIVE_MAINTENANCE_THRESHOLD=10
STREAM_ALERT_COOLDOWN_SECONDS=600
```

Do not commit `.env`. It contains private credentials.

## Run With Docker

Start Docker Desktop, then run:

```powershell
docker compose up --build -d
```

Pull the local Ollama model once:

```powershell
docker exec predictagent-ollama ollama pull llama3.1
```

Open the frontend:

```text
http://127.0.0.1:8000/
```

Run the telemetry simulator:

```powershell
docker compose --profile tools run --rm simulator
```

Watch logs:

```powershell
docker compose logs -f api
docker compose logs -f mqtt
```

Stop everything:

```powershell
docker compose down
```

More deployment details are in [DEPLOYMENT.md](DEPLOYMENT.md).

## Run Locally Without Docker

Create and activate a virtual environment, then install dependencies:

```powershell
venv\Scripts\activate
pip install -r requirements.txt
```

Start the API/frontend server:

```powershell
venv\Scripts\python.exe -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```

Stream simulated data:

```powershell
venv\Scripts\python.exe -m src.simulation.stream_sensor_data --mode maintenance --rows 80 --delay 0.5
```

Available simulator modes:

```text
normal
maintenance
critical
```

## Important API Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | API/model health check. |
| `POST /predict-raw` | Score raw ESP32-style telemetry. |
| `POST /predict` | Score engineered feature rows. |
| `GET /api/dashboard` | Live dashboard payload. |
| `GET /api/events` | Recent event history. |
| `GET /api/events.csv` | CSV export. |
| `GET /api/events.xlsx` | Excel export. |
| `GET /api/events.pdf` | PDF export. |
| `POST /api/command` | Send manual MQTT command. |
| `GET /api/live-alert/status` | Live stream alert/cooldown status. |
| `POST /agent/chat` | Ask the maintenance agent a question. |

## Alerts

There are two alert paths:

1. Agent report alerts:

```powershell
venv\Scripts\python.exe -m src.agent.graph
```

This analyzes stored events, generates a report, and sends Telegram/email if severity justifies it.

2. Live streaming alerts:

During `/predict-raw`, the API sends Telegram/email only after more than 10 successive `MAINTENANCE_ALERT` rows. A cooldown prevents repeated alert spam.

Check status:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/live-alert/status -UseBasicParsing
```

## Exports

Download event history:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/events.csv -OutFile events.csv
Invoke-WebRequest http://127.0.0.1:8000/api/events.xlsx -OutFile events.xlsx
Invoke-WebRequest http://127.0.0.1:8000/api/events.pdf -OutFile events.pdf
```

The frontend also has export buttons on the Alerts and Analytics pages.

## Model Summary

The final anomaly detection approach uses Isolation Forest models trained on normal motor behavior. The decision policy combines model score, persistence counters, vibration/frequency danger, and thermal/electrical danger to avoid unnecessary shutdowns.

From the final evaluation:

- Precision: `0.4336`
- Recall: `1.0000`
- F1: `0.6049`
- False negatives: `0`

All labeled anomalies in the old validation dataset were escalated to at least `MAINTENANCE_ALERT`.

## Notes

- The LangGraph deprecation warning shown during agent runs is not a runtime failure.
- Ollama must have the configured `OLLAMA_MODEL` pulled before LLM reasoning can run.
- OpenRouter `429 Too Many Requests` means the LLM key is configured but the provider rate-limited the request.
- Docker requires Docker Desktop’s Linux engine to be running before `docker compose up --build -d`.

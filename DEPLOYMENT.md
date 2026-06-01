# PredictAgent Deployment

## Local Docker Compose Run

1. Fill `.env` with your real credentials.

2. Build and start the API plus MQTT broker:

```powershell
docker compose up --build -d
```

3. Pull the local Ollama model once:

```powershell
docker exec predictagent-ollama ollama pull llama3.1
```

4. Open the frontend:

```text
http://127.0.0.1:8000/
```

5. Check API health:

```powershell
docker compose ps
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing
```

6. Stream simulated motor data:

```powershell
docker compose --profile tools run --rm simulator
```

7. Watch logs:

```powershell
docker compose logs -f api
docker compose logs -f mqtt
docker compose logs -f ollama
```

8. Test exports:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/events.csv -OutFile events.csv
Invoke-WebRequest http://127.0.0.1:8000/api/events.xlsx -OutFile events.xlsx
Invoke-WebRequest http://127.0.0.1:8000/api/events.pdf -OutFile events.pdf
```

9. Check live alert cooldown status:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/live-alert/status -UseBasicParsing
```

10. Stop the stack:

```powershell
docker compose down
```

## Persistent Files

- SQLite events database: `runtime/motor_events.db`
- Generated reports: `reports/`
- Ollama models: Docker volume `nt_motor_ollama-data`
- MQTT broker data: Docker volume `nt_motor_mosquitto-data`

## Services

- `api`: FastAPI backend and frontend static server.
- `mqtt`: local Eclipse Mosquitto broker.
- `ollama`: local LLM server used by the maintenance agent.
- `simulator`: optional one-shot telemetry simulator enabled with `--profile tools`.

# PredictAgent Deployment

## Local Docker Compose Run

1. Fill `.env` with your real credentials.

2. Build and start the API plus MQTT broker:

```powershell
docker compose up --build -d
```

3. Open the frontend:

```text
http://127.0.0.1:8000/
```

4. Check API health:

```powershell
docker compose ps
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing
```

5. Stream simulated motor data:

```powershell
docker compose --profile tools run --rm simulator
```

6. Watch logs:

```powershell
docker compose logs -f api
docker compose logs -f mqtt
```

7. Test exports:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/events.csv -OutFile events.csv
Invoke-WebRequest http://127.0.0.1:8000/api/events.xlsx -OutFile events.xlsx
Invoke-WebRequest http://127.0.0.1:8000/api/events.pdf -OutFile events.pdf
```

8. Check live alert cooldown status:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/live-alert/status -UseBasicParsing
```

9. Stop the stack:

```powershell
docker compose down
```

## Persistent Files

- SQLite events database: `runtime/motor_events.db`
- Generated reports: `reports/`
- MQTT broker data: Docker volume `nt_motor_mosquitto-data`

## Services

- `api`: FastAPI backend and frontend static server.
- `mqtt`: local Eclipse Mosquitto broker.
- `simulator`: optional one-shot telemetry simulator enabled with `--profile tools`.

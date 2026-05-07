from __future__ import annotations

import argparse
import math
import random
import time
from datetime import datetime, timezone
from typing import Any

import requests


API_URL = "http://127.0.0.1:8000/predict-raw"


def build_row(index: int, mode: str) -> dict[str, Any]:
    phase = index / 7.0
    anomaly_boost = 0.0
    if mode == "maintenance":
        anomaly_boost = max(0.0, (index - 20) / 70.0)
    elif mode == "critical":
        anomaly_boost = 1.0 if index > 18 else index / 18.0

    temperature = 42.0 + math.sin(phase) * 1.8 + anomaly_boost * 24.0
    current = 10.5 + math.sin(phase * 1.2) * 0.9 + anomaly_boost * 8.0
    voltage = 220.0 + math.sin(phase * 0.6) * 2.2 - anomaly_boost * 4.5
    vibration = 0.45 + abs(math.sin(phase * 1.5)) * 0.22 + anomaly_boost * 3.8
    speed_rpm = 7900.0 + math.sin(phase * 0.8) * 160.0 - anomaly_boost * 340.0

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature": round(temperature + random.uniform(-0.25, 0.25), 3),
        "current": round(current + random.uniform(-0.12, 0.12), 3),
        "voltage": round(voltage + random.uniform(-0.4, 0.4), 3),
        "vibration": round(vibration + random.uniform(-0.03, 0.03), 4),
        "speed_rpm": round(speed_rpm + random.uniform(-25, 25), 2),
        "ambient_temperature": 24.0,
    }


def stream_rows(*, url: str, rows: int, delay: float, mode: str) -> None:
    for index in range(rows):
        payload = build_row(index, mode)
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        print(
            "row={row:03d} ready={ready} temp={temp:.1f} vib={vib:.2f} "
            "score={score} decision={decision} command={command} live_alert={live_alert}".format(
                row=index + 1,
                ready=result["buffer_ready"],
                temp=payload["temperature"],
                vib=payload["vibration"],
                score=(
                    "warmup"
                    if result["score"] is None
                    else f"{float(result['score']):.4f}"
                ),
                decision=result["decision"],
                command=result["command"],
                live_alert=result.get("live_alert_status", {}).get("detail", "not checked"),
            )
        )
        if delay > 0:
            time.sleep(delay)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream simulated ESP32 motor telemetry into the API.")
    parser.add_argument("--url", default=API_URL, help="Predict raw endpoint URL.")
    parser.add_argument("--rows", type=int, default=80, help="Number of rows to stream.")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between rows in seconds.")
    parser.add_argument(
        "--mode",
        choices=["normal", "maintenance", "critical"],
        default="maintenance",
        help="Telemetry pattern to simulate.",
    )
    args = parser.parse_args()
    stream_rows(url=args.url, rows=args.rows, delay=args.delay, mode=args.mode)


if __name__ == "__main__":
    main()

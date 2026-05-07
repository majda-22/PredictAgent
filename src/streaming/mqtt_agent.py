from __future__ import annotations

import json
import os
from typing import Any

import paho.mqtt.client as mqtt

from src.actions.mqtt_publisher import publish_command
from src.agent.graph import run_maintenance_agent
from src.agent.trigger import should_trigger_agent
from src.config import load_env
from src.models.predict_regime import predict
from src.storage.event_store import EventStore
from src.storage.event_store import save_event


load_env()

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
SENSOR_TOPIC = os.getenv("MQTT_SENSOR_TOPIC", "motor/sensors")
COMMAND_TOPIC = os.getenv("MQTT_TOPIC", "motor/commands")


def on_connect(
    client: mqtt.Client,
    userdata: Any,
    flags: mqtt.ConnectFlags,
    reason_code: mqtt.ReasonCode,
    properties: mqtt.Properties | None = None,
) -> None:
    if reason_code == 0:
        client.subscribe(SENSOR_TOPIC, qos=1)
        print(f"Subscribed to {SENSOR_TOPIC}")
        return
    print(f"MQTT connection failed: {reason_code}")


def on_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
    try:
        sensor_data = json.loads(msg.payload.decode("utf-8"))
        result = predict(sensor_data)
        event_id = save_event(sensor_data, result)
        publish_result = publish_command(result["command"])
        should_run_agent, trigger_reason = should_trigger_agent(EventStore())
        if should_run_agent:
            agent_state = run_maintenance_agent()
            print(
                "maintenance_agent_triggered reason={reason} severity={severity} report={report}".format(
                    reason=trigger_reason,
                    severity=agent_state.get("risk", {}).get("severity"),
                    report=agent_state.get("pdf_path"),
                )
            )
        print(
            "event_id={event_id} topic={topic} command={command} "
            "decision={decision} regime={regime} score={score} published={published}".format(
                event_id=event_id,
                topic=COMMAND_TOPIC,
                command=result["command"],
                decision=result["decision"],
                regime=result.get("regime"),
                score=result.get("score"),
                published=publish_result.published,
            )
        )
        if publish_result.error:
            print(f"MQTT publish warning: {publish_result.error}")
    except Exception as exc:
        print(f"Failed to process MQTT sensor message: {exc}")


def run() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    print(f"Listening on {SENSOR_TOPIC}, publishing commands to {COMMAND_TOPIC}")
    client.loop_forever()


if __name__ == "__main__":
    run()

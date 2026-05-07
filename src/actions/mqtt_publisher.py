import os
from dataclasses import dataclass

import paho.mqtt.client as mqtt

from src.config import load_env


load_env()

DEFAULT_TOPIC = "motor/commands"
VALID_COMMANDS = {
    "NO_ACTION",
    "MONITOR",
    "ALERT_MAINTENANCE",
    "STOP_MOTOR",
    "START_MOTOR",
    "RESET_ALERTS",
    "MANUAL_MODE",
}


@dataclass(frozen=True)
class MQTTPublishResult:
    published: bool
    topic: str
    command: str
    error: str | None = None


class MQTTPublisher:
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        topic: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.host = host or os.getenv("MQTT_HOST", "127.0.0.1")
        self.port = port or int(os.getenv("MQTT_PORT", "1883"))
        self.topic = topic or os.getenv("MQTT_TOPIC", DEFAULT_TOPIC)
        self.enabled = (
            enabled
            if enabled is not None
            else os.getenv("MQTT_ENABLED", "true").lower() == "true"
        )

    def publish_command(self, command: str) -> MQTTPublishResult:
        if command not in VALID_COMMANDS:
            return MQTTPublishResult(
                published=False,
                topic=self.topic,
                command=command,
                error=f"Invalid MQTT command: {command}",
            )

        if not self.enabled:
            return MQTTPublishResult(
                published=False,
                topic=self.topic,
                command=command,
                error="MQTT publishing disabled",
            )

        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            client.connect(self.host, self.port, keepalive=30)
            result = client.publish(self.topic, payload=command, qos=1, retain=False)
            result.wait_for_publish(timeout=3)
            client.disconnect()
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                return MQTTPublishResult(
                    published=False,
                    topic=self.topic,
                    command=command,
                    error=f"MQTT publish failed with code {result.rc}",
                )
        except Exception as exc:
            return MQTTPublishResult(
                published=False,
                topic=self.topic,
                command=command,
                error=str(exc),
            )

        return MQTTPublishResult(
            published=True,
            topic=self.topic,
            command=command,
        )


_default_publisher = MQTTPublisher()


def publish_command(command: str) -> MQTTPublishResult:
    return _default_publisher.publish_command(command)

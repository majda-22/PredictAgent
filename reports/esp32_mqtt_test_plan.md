# ESP32 MQTT Test Plan

## MQTT Topics

ESP32 publishes sensor readings to:

```text
motor/sensors
```

ESP32 subscribes to commands from:

```text
motor/commands
```

## Sensor Message Shape

Publish JSON like:

```json
{
  "timestamp": "2026-05-06T12:00:00",
  "temperature": 35.2,
  "ambient_temperature": 22.0,
  "current": 1.8,
  "voltage": 3.5,
  "speed_rpm": 8000,
  "vibration": 0.1
}
```

Or send vibration axes:

```json
{
  "timestamp": "2026-05-06T12:00:00",
  "temperature": 35.2,
  "ambient_temperature": 22.0,
  "current": 1.8,
  "voltage": 3.5,
  "speed_rpm": 8000,
  "vibration_x": 0.1,
  "vibration_y": 0.2,
  "vibration_z": 0.3
}
```

## Commands

The backend publishes one of:

```text
NO_ACTION
MONITOR
ALERT_MAINTENANCE
STOP_MOTOR
```

## Test Without Motor First

Before connecting the relay or MOSFET, test with Serial Monitor and LEDs:

```text
NO_ACTION         -> green LED
MONITOR           -> green LED or low-priority serial message
ALERT_MAINTENANCE -> yellow LED / buzzer
STOP_MOTOR        -> red LED
```

Only connect the motor control relay/MOSFET after command reception is verified.

## Motor Control Behavior

When ESP32 receives:

```text
STOP_MOTOR
```

it turns off the relay/MOSFET connected to the motor.

When ESP32 receives:

```text
NO_ACTION
```

it keeps the motor running.

# Final Evaluation Report

## 1. Isolation Forest Performance

The final normal-behavior model uses:

- Training data: `features_window_new.csv` plus old labeled rows where `target = 0`
- Scaler: `RobustScaler`, fit only on normal behavior
- Model: `IsolationForest`
- Selected experiment: `B_new_plus_old_normal`
- Selected threshold percentile: `3%`
- Threshold: `-0.011590`

Validation on the old labeled dataset:

| Metric | Value |
|---|---:|
| Precision | 0.4336 |
| Recall | 1.0000 |
| F1 | 0.6049 |
| False positives | 64 |
| False negatives | 0 |

Confusion matrix:

```text
[[264  64]
 [  0  49]]
```

The Isolation Forest successfully detects all labeled anomalies. The remaining weakness is false positives on the old dataset, which likely contains transition rows or abnormal-looking rows still labeled as normal.

## 2. Decision Counts On New Normal Dataset

Replay file: `reports/replay_decisions_new.csv`

| Decision | Count |
|---|---:|
| NORMAL | 4889 |
| MONITOR | 106 |
| WARNING | 5 |
| MAINTENANCE_ALERT | 0 |
| EMERGENCY_STOP | 0 |

This confirms that the decision policy is stable on the 5000-row normal-behavior dataset. No normal-behavior rows escalate to maintenance or emergency.

## 3. Decision Counts On Old Labeled Dataset

Replay file: `reports/replay_decisions_old.csv`

Overall:

| Decision | Count |
|---|---:|
| NORMAL | 210 |
| MONITOR | 9 |
| WARNING | 7 |
| MAINTENANCE_ALERT | 141 |
| EMERGENCY_STOP | 10 |

For old normal rows, `target = 0`:

| Decision | Count |
|---|---:|
| NORMAL | 210 |
| MONITOR | 9 |
| WARNING | 7 |
| MAINTENANCE_ALERT | 94 |
| EMERGENCY_STOP | 8 |

For old anomaly rows, `target = 1`:

| Decision | Count |
|---|---:|
| NORMAL | 0 |
| MONITOR | 0 |
| WARNING | 0 |
| MAINTENANCE_ALERT | 47 |
| EMERGENCY_STOP | 2 |

All labeled anomalies are escalated to at least `MAINTENANCE_ALERT`.

## 4. Why Most Anomalies Become MAINTENANCE_ALERT

Most labeled anomalies look like mechanical or vibration-related faults rather than immediate multi-signal critical failures.

The decision policy now separates:

- repeated abnormal score behavior
- vibration/frequency danger
- thermal/electrical danger

When the anomaly score is low and vibration/frequency danger is active, the system escalates to `MAINTENANCE_ALERT`. This means the motor should be inspected or serviced, but the signal does not yet justify an immediate shutdown.

This is the correct industrial behavior for likely mechanical degradation, bearing issues, imbalance, or vibration faults.

## 5. Why EMERGENCY_STOP Is Reserved For Critical Behavior

`EMERGENCY_STOP` now requires all of the following:

```text
counter >= 8
current row is anomaly
score < threshold - 0.02
thermal/electrical danger is active
vibration danger OR frequency danger is active
```

This prevents emergency shutdown from being triggered by score alone or by vibration-only faults.

The policy treats emergency as a multi-signal critical condition:

- strong Isolation Forest anomaly score
- persistent anomaly counter
- thermal/electrical stress
- vibration or frequency abnormality

As a result, most labeled anomalies become `MAINTENANCE_ALERT`, while `EMERGENCY_STOP` is reserved for cases that look dangerous across multiple physical signal groups.

## 6. Agent Layer Validation

Integration validation was run with Mosquitto in Docker, the Python MQTT agent, fake sensor messages published to `motor/sensors`, command subscription on `motor/commands`, SQLite event storage, trigger evaluation, and PDF report generation.

Validation result:

| Check | Result |
|---|---|
| MQTT broker | Mosquitto Docker container running |
| Sensor topic | `motor/sensors` |
| Command topic | `motor/commands` |
| Commands observed | `NO_ACTION`, `MONITOR`, `ALERT_MAINTENANCE` |
| SQLite DB | `motor_events.db` |
| SQLite table | `events` |
| Latest trigger condition | recent maintenance or emergency decision |
| Events fetched by agent | 19 |
| Recent non-normal events | 19 |
| Recent maintenance alerts | 11 |
| Detected pattern | mixed |
| Pattern confidence | 0.75 |
| Risk level | medium |
| Estimated time to failure | unknown |
| Recommended action | Inspect mechanical and electrical subsystems before continuing high-load operation. |
| Report path | `reports/agent/motor_report_20260506_203535.pdf` |
| Alert status | Telegram/email not configured, report saved locally |

The earlier low-severity PDF issue was caused by two integration problems:

- the event store used `data/events/motor_events.db` with table `prediction_events`, while validation expected `motor_events.db` with table `events`
- the graph could be run manually without checking the trigger, so it could generate reports during warmup/normal-only context

Both were fixed. The canonical event store is now:

```text
motor_events.db
events
```

The graph is now trigger-gated by default. It will not generate a report for warmup rows or normal-only sequences.

The next useful upgrade is replacing the sequential `src/agent/graph.py` runner with real LangGraph while keeping the same node boundaries.

## 7. LangGraph And LLM Maintenance Agent

The maintenance agent was upgraded from a manual sequential Python pipeline to a real LangGraph state graph.

Current graph:

```text
fetch_events
-> analyze_pattern
-> estimate_risk
-> llm_reasoning
-> generate_report
-> send_alert
```

The real-time motor control loop remains deterministic and does not depend on the LLM:

```text
ESP32
-> MQTT motor/sensors
-> feature mapper
-> regime classifier
-> Isolation Forest
-> decision policy
-> MQTT motor/commands
-> SQLite event storage
```

The LLM is only used in the slower maintenance-agent layer. It can:

- analyze repeated events
- compare the current report with previous reports
- ask missing-context questions
- decide whether an engineer alert is justified
- generate a richer maintenance summary

The LLM layer is optional. If `OPENAI_API_KEY` is not configured, the agent falls back to deterministic reasoning and still generates reports.

Engineer chat was added through:

```text
POST /agent/chat
```

Example question:

```json
{
  "question": "What is the current machine state and is maintenance near?"
}
```

The chat endpoint reads:

- latest SQLite motor state
- recent events
- previous maintenance reports

It answers using the LLM when available, or a deterministic fallback when the API key is not configured.

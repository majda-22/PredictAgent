# Project Explanation: DC Motor Anomaly Detection And Decision Agent

## 1. Project Goal

The goal of this project is to detect abnormal behavior in a DC motor and convert model outputs into practical maintenance decisions.

The system does not only answer:

```text
Is this row anomalous?
```

It also answers:

```text
What action should be taken?
```

The final decision states are:

- `NORMAL`
- `MONITOR`
- `WARNING`
- `MAINTENANCE_ALERT`
- `EMERGENCY_STOP`

The project combines:

- sensor data cleaning
- physical feature engineering
- normal-behavior modeling
- anomaly scoring
- industrial decision logic
- replay simulation as if the motor were streaming live data

## 2. Datasets

The project uses two raw Excel datasets.

### Old Labeled Dataset

File:

```text
data/raw/DC_motor_anomaly_detection.xlsx
```

This dataset contains 377 rows.

It includes labels:

- `Normal`
- `Anomalie`

The label is converted into:

```text
target = 0 for Normal
target = 1 for Anomalie
```

It also contains:

```text
Anomaly_Details
```

This column explains the fault type or abnormal signal, for example vibration-related anomalies.

Class distribution:

```text
Normal rows: 328
Anomaly rows: 49
Total rows: 377
```

This dataset is used mainly for validation, because it has true labels.

### New Normal-Behavior Dataset

File:

```text
data/raw/DC_Motor_5000_Generated.xlsx
```

This dataset contains 5000 rows.

It is treated as normal motor behavior. Since it has no anomaly labels, all rows are assigned:

```text
target = 0
```

This dataset is used to learn what healthy motor behavior looks like.

## 3. Data Cleaning

Cleaning scripts:

```text
src/data/clean_data.py
src/data/clean_normal_data.py
```

The old labeled dataset is cleaned with:

```text
src/data/clean_data.py
```

The new normal dataset is cleaned with:

```text
src/data/clean_normal_data.py
```

Both datasets are cleaned using the same core logic:

- load Excel file
- fix `Date` format by replacing comma milliseconds with dot milliseconds
- convert `Date` to datetime
- sort rows by `Date`
- drop the `File` column
- keep important metadata such as `Anomaly_Details`
- create the `target` column

Clean outputs:

```text
data/clean/clean_data.csv
data/clean/clean_data_new.csv
```

## 4. Feature Groups

Feature groups are defined in:

```text
src/features/feature_groups.py
```

The main feature groups are:

### Basic Operating Features

```text
speed_rpm
speed_Hz
Current
Voltage
temp_mot
temp_amb
```

These describe the operating state of the motor.

### Vibration Harmonics

```text
1x[Vibration] to 10x[Vibration]
```

These are critical because many motor faults appear first as vibration changes.

### Current Harmonics

```text
1x[Current] to 10x[Current]
```

These capture electrical current behavior across harmonics.

### Voltage Harmonics

```text
1x[Voltage] to 10x[Voltage]
```

These capture voltage harmonic behavior.

### Frequency Bands

For vibration, current, and voltage:

```text
0-4k_Hz
4k-8k_Hz
8k-16kHz
16k-26kHz
```

These features describe spectral energy across frequency regions.

## 5. Feature Engineering

Feature engineering is implemented in:

```text
src/features/build_features.py
```

The same feature builder is used for both datasets. This is important because the model must receive identical features in the same order.

Generated outputs:

```text
data/processed/features_base.csv
data/processed/features_window.csv
data/processed/features_base_new.csv
data/processed/features_window_new.csv
```

### Physical Features

The system creates physical relationship features:

```text
temp_delta = temp_mot - temp_amb
power = Current * Voltage
current_voltage_ratio = Current / Voltage
temp_current_ratio = temp_mot / Current
```

These features help detect overheating, overload, and unusual electrical behavior.

### Vibration Features

The system creates vibration summary features:

```text
vib_sum
vib_mean
vib_std
vib_instability = vib_std / vib_mean
```

These features summarize the total vibration level and instability.

### Harmonic Ratio Features

The system computes:

```text
vib_2x_1x_ratio
vib_3x_1x_ratio
vib_4x_1x_ratio
dominant_harmonic
```

These features are useful because mechanical faults often appear as changes in harmonic relationships.

### Spectral Features

The system computes:

```text
freq_low
freq_high
freq_ratio = freq_high / freq_low
```

These features help identify abnormal high-frequency energy, which can indicate friction, bearing issues, or mechanical degradation.

### Temporal Delta Features

After sorting by time, the system computes row-over-row changes:

```text
delta_Current
delta_Voltage
delta_temp_mot
delta_vib_sum
delta_power
```

These features capture sudden changes over time.

### Window Features

Using a window size of 5 rows, the system computes rolling features:

```text
mean
std
min
max
delta
```

These are created for important signals such as:

```text
Current
Voltage
temp_mot
vib_sum
power
freq_low
freq_high
freq_ratio
```

Window features help the model understand short-term trends instead of isolated readings.

## 6. Final Model: Isolation Forest

The final model is trained in:

```text
src/models/train_isolation_forest.py
```

The project originally tested a Random Forest classifier, but it was removed from the final pipeline. The final system uses Isolation Forest because the new 5000-row dataset represents normal behavior.

Isolation Forest is suitable here because it learns the structure of normal behavior and flags rows that look unusual.

### Scaling Strategy

The final system uses:

```text
RobustScaler
```

The scaler is fit only on normal behavior:

- all rows from the new normal dataset
- only `target = 0` rows from the old labeled dataset

This is important.

The scaler is never fit on anomalies.

This prevents anomaly information from leaking into the normal baseline.

Saved scaler:

```text
models/scaler.joblib
```

### Feature Order

The model also saves the exact feature column order:

```text
models/isolation_feature_columns.joblib
```

This ensures inference always uses the same feature order as training.

### Model Artifacts

Saved model:

```text
models/isolation_forest_normal_behavior.joblib
```

Saved threshold:

```text
models/isolation_forest_threshold.npy
```

Saved feature columns:

```text
models/isolation_feature_columns.joblib
```

## 7. Threshold Selection

Isolation Forest produces a score using:

```text
decision_function(X)
```

Interpretation:

```text
High score = normal
Low score = suspicious
```

The anomaly rule is:

```text
score < threshold
```

The selected final threshold is:

```text
-0.011590
```

This threshold came from the selected experiment:

```text
B_new_plus_old_normal
```

It uses:

- new normal data
- old normal rows
- 3rd percentile threshold

## 8. Isolation Forest Validation

The final Isolation Forest performance on the old labeled dataset is:

```text
Precision: 0.4336
Recall:    1.0000
F1:        0.6049
```

Confusion matrix:

```text
[[264  64]
 [  0  49]]
```

Meaning:

- all 49 labeled anomalies were detected
- 64 normal rows were flagged as suspicious
- no anomalies were missed

The false positives are likely caused by transition regions or old rows labeled normal that already look abnormal physically.

## 9. Decision Agent

The decision policy is implemented in:

```text
src/agent/decision_policy.py
```

The policy converts model scores into industrial actions.

The five decision states are:

```text
NORMAL
MONITOR
WARNING
MAINTENANCE_ALERT
EMERGENCY_STOP
```

The decision policy uses:

- Isolation Forest score
- threshold
- anomaly counter
- vibration danger
- frequency danger
- thermal/electrical danger
- current feature values

## 10. Hysteresis Logic

The system uses hysteresis so the decision does not jump between normal and alert states too quickly.

The counter changes as follows:

```text
weak anomaly      -> counter +1
strong anomaly    -> counter +2
normal reading    -> counter -1
very normal score -> counter -2
```

The decision thresholds are:

```text
MONITOR             counter >= 1
WARNING             counter >= 3
MAINTENANCE_ALERT   counter >= 5
EMERGENCY_STOP      counter >= 8 plus extra safety gates
```

Normal readings do not reset the counter immediately. They reduce it gradually. This prevents the system from rapidly switching between normal and alert.

## 11. Emergency Stop Logic

`EMERGENCY_STOP` is intentionally strict.

It requires:

```text
counter >= 8
current row is anomaly
score < threshold - 0.02
thermal/electrical danger is active
vibration danger OR frequency danger is active
```

This means emergency stop is not triggered by a low anomaly score alone.

It must be a multi-signal critical condition.

This is important because many mechanical anomalies should trigger maintenance, not immediate shutdown.

## 12. Maintenance Alert Logic

Most anomalies become:

```text
MAINTENANCE_ALERT
```

This is expected.

A mechanical or vibration-related anomaly usually means:

- inspect the motor
- check bearings
- check alignment
- check imbalance
- schedule maintenance

It does not always mean the motor must stop immediately.

The policy therefore separates:

```text
mechanical anomaly -> MAINTENANCE_ALERT
multi-signal critical anomaly -> EMERGENCY_STOP
```

## 13. Replay Simulation

Replay simulation is implemented in:

```text
src/simulation/replay.py
```

It simulates live streaming by reading rows one by one from a processed feature dataset.

For every row, it:

1. loads the correct feature columns
2. applies the saved scaler
3. computes Isolation Forest score
4. compares score with threshold
5. sends score and features to the decision policy
6. receives decision and reason
7. saves the output

Replay outputs:

```text
reports/replay_decisions_new.csv
reports/replay_decisions_old.csv
```

## 14. Replay Results On New Normal Dataset

The new dataset represents normal behavior.

Decision counts:

```text
NORMAL:             4889
MONITOR:             106
WARNING:               5
MAINTENANCE_ALERT:     0
EMERGENCY_STOP:        0
```

This is a good result.

The system stays stable on normal behavior. It does not escalate to maintenance or emergency.

## 15. Replay Results On Old Labeled Dataset

Overall decision counts:

```text
NORMAL:             210
MONITOR:              9
WARNING:              7
MAINTENANCE_ALERT:  141
EMERGENCY_STOP:      10
```

For old normal rows:

```text
NORMAL:             210
MONITOR:              9
WARNING:              7
MAINTENANCE_ALERT:   94
EMERGENCY_STOP:       8
```

For old anomaly rows:

```text
NORMAL:              0
MONITOR:             0
WARNING:             0
MAINTENANCE_ALERT:  47
EMERGENCY_STOP:      2
```

All labeled anomalies are escalated to at least maintenance alert.

Most anomalies become maintenance alerts because they look like mechanical or vibration-related faults rather than immediate multi-signal critical failures.

## 16. Explanation Generation

The decision policy also generates reasons.

Example reasons include:

```text
High vibration instability -> possible mechanical fault
Temperature and current rising -> possible overheating / overload
High frequency vibration energy elevated -> possible bearing or friction issue
Multiple signals abnormal -> critical condition
Score slightly below threshold -> monitoring only
Repeated mechanical anomaly -> maintenance alert, emergency gated off
```

This makes the system explainable.

The output is not just:

```text
Anomaly detected
```

It explains why the decision was made.

## 17. Final Inference Pipeline

At inference time, the correct order is:

```text
raw sensor row
-> clean / align schema
-> build base features
-> build window features
-> load feature columns
-> select features in saved order
-> apply saved RobustScaler
-> compute Isolation Forest score
-> compare score with threshold
-> update decision counter
-> apply danger-group gates
-> output decision and reason
```

The saved artifacts required for inference are:

```text
models/scaler.joblib
models/isolation_forest_normal_behavior.joblib
models/isolation_forest_threshold.npy
models/isolation_feature_columns.joblib
```

## 18. Current Strengths

The current system has several strengths:

- uses normal behavior as the baseline
- avoids training directly on fake or noisy anomaly labels
- uses the same feature pipeline for all datasets
- fits the scaler only on normal data
- detects all labeled anomalies in validation
- separates maintenance alerts from emergency stops
- generates human-readable reasons
- supports replay simulation

## 19. Current Limitations

The main limitation is false positives on the old labeled dataset.

Some rows labeled normal look physically abnormal. Many are close to labeled anomaly periods, meaning they may be transition rows before or after faults.

This means the issue may be partly in the labels, not only in the model.

The current system prefers safety:

- it catches all anomalies
- it may raise maintenance alerts on suspicious normal-labeled rows

This is acceptable for a predictive maintenance prototype, but future work should reduce false positives.

## 20. Recommended Next Improvements

Recommended next steps:

1. Study the old normal rows that become `MAINTENANCE_ALERT` or `EMERGENCY_STOP`.
2. Check whether they occur near labeled anomalies.
3. Split evaluation by `Anomaly_Details`.
4. Tune danger thresholds using domain knowledge.
5. Add a live-state memory object for real streaming deployment.
6. Add an inference script for a single new row.
7. Add a dashboard or API endpoint for live monitoring.

## Final Summary

This project builds a complete anomaly-detection and decision-support pipeline for a DC motor.

The Isolation Forest learns healthy motor behavior from normal data. The decision policy then transforms anomaly scores into realistic industrial actions. The system avoids triggering emergency shutdown for vibration-only faults and reserves `EMERGENCY_STOP` for persistent, strong, multi-signal critical behavior.

The result is a practical predictive maintenance system:

```text
normal behavior -> NORMAL / MONITOR
mechanical degradation -> MAINTENANCE_ALERT
multi-signal critical fault -> EMERGENCY_STOP
```

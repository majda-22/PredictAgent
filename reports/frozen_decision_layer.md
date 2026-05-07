# Frozen Decision Layer

The current decision layer is frozen for the next project phase.

Frozen components:

- `src/features/esp32_feature_mapper.py`
- `src/agent/decision_policy.py`
- `models/regime_kmeans.joblib`
- `models/regime_scaler.joblib`
- `models/regime_isolation_forests.joblib`
- `models/regime_feature_scalers.joblib`
- `models/regime_thresholds.joblib`
- `models/regime1_kmeans.joblib`
- `models/regime1_sub_models.joblib`
- `models/regime1_sub_feature_scalers.joblib`
- `models/regime1_sub_thresholds.joblib`
- `models/reduced_feature_columns.joblib`
- `models/reduced_ratio_clip_bounds.joblib`
- `models/vib_scaler.pkl`

Do not tune these again until the storage/action/agent layer has been tested.

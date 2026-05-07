from pathlib import Path
import sys
from typing import Any

import joblib
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.agent.decision_policy import DecisionState, make_decision
from src.features.esp32_feature_mapper import ESP32FeatureMapper


VIB_SCALER_FILE = PROJECT_ROOT / "models" / "vib_scaler.pkl"
REDUCED_FEATURE_COLUMNS_FILE = PROJECT_ROOT / "models" / "reduced_feature_columns.joblib"
REDUCED_RATIO_CLIP_BOUNDS_FILE = PROJECT_ROOT / "models" / "reduced_ratio_clip_bounds.joblib"
REGIME_MODEL_FILE = PROJECT_ROOT / "models" / "regime_kmeans.joblib"
REGIME_SCALER_FILE = PROJECT_ROOT / "models" / "regime_scaler.joblib"
REGIME_IFOREST_FILE = PROJECT_ROOT / "models" / "regime_isolation_forests.joblib"
REGIME_FEATURE_SCALERS_FILE = PROJECT_ROOT / "models" / "regime_feature_scalers.joblib"
REGIME_THRESHOLDS_FILE = PROJECT_ROOT / "models" / "regime_thresholds.joblib"
REGIME1_MODEL_FILE = PROJECT_ROOT / "models" / "regime1_kmeans.joblib"
REGIME1_IFOREST_FILE = PROJECT_ROOT / "models" / "regime1_sub_models.joblib"
REGIME1_FEATURE_SCALERS_FILE = PROJECT_ROOT / "models" / "regime1_sub_feature_scalers.joblib"
REGIME1_THRESHOLDS_FILE = PROJECT_ROOT / "models" / "regime1_sub_thresholds.joblib"
REGIME_COLUMNS = ["speed_rpm", "current_per_rpm"]
RAW_WINDOW_SIZE = 10
REGIME_COUNTER_THRESHOLDS = {0: 3, 2: 5}
REGIME1_COUNTER_THRESHOLDS = {0: 7, 1: 10}


COMMANDS = {
    DecisionState.NORMAL: "NO_ACTION",
    DecisionState.MONITOR: "MONITOR",
    DecisionState.WARNING: "MONITOR",
    DecisionState.MAINTENANCE_ALERT: "ALERT_MAINTENANCE",
    DecisionState.EMERGENCY_STOP: "STOP_MOTOR",
}


class RegimePredictor:
    def __init__(self) -> None:
        self.vib_scaler = joblib.load(VIB_SCALER_FILE)
        self.feature_columns = joblib.load(REDUCED_FEATURE_COLUMNS_FILE)
        self.ratio_clip_bounds = joblib.load(REDUCED_RATIO_CLIP_BOUNDS_FILE)
        self.regime_model = joblib.load(REGIME_MODEL_FILE)
        self.regime_scaler = joblib.load(REGIME_SCALER_FILE)
        self.regime_models = joblib.load(REGIME_IFOREST_FILE)
        self.regime_feature_scalers = joblib.load(REGIME_FEATURE_SCALERS_FILE)
        self.regime_thresholds = joblib.load(REGIME_THRESHOLDS_FILE)
        self.regime1_model = joblib.load(REGIME1_MODEL_FILE)
        self.regime1_models = joblib.load(REGIME1_IFOREST_FILE)
        self.regime1_feature_scalers = joblib.load(REGIME1_FEATURE_SCALERS_FILE)
        self.regime1_thresholds = joblib.load(REGIME1_THRESHOLDS_FILE)
        self.mapper = ESP32FeatureMapper(
            buffer_size=RAW_WINDOW_SIZE,
            vib_scaler=self.vib_scaler,
            ratio_clip_bounds=self.ratio_clip_bounds,
        )
        self.consecutive_anomaly_count = 0

    def reset(self) -> None:
        self.mapper.reset()
        self.consecutive_anomaly_count = 0

    def predict(self, data: dict[str, Any]) -> dict[str, Any]:
        vibration = vibration_magnitude(data)
        temperature = float(data["temperature"])
        current = float(data["current"])
        voltage = float(data["voltage"])
        speed_rpm = float(data.get("speed_rpm", 8000.0))
        speed_hz = float(data.get("speed_hz", speed_rpm / 60.0))
        ambient_temperature = float(data.get("ambient_temperature", 22.0))

        features = self.mapper.map(
            current=current,
            voltage=voltage,
            temp_mot=temperature,
            temp_amb=ambient_temperature,
            speed_rpm=speed_rpm,
            speed_hz=speed_hz,
            vibration=vibration,
        )

        if not self.mapper.is_ready:
            return {
                "buffer_ready": False,
                "buffer_size": len(self.mapper.buffer),
                "regime": None,
                "sub_regime": None,
                "score": None,
                "threshold": None,
                "is_anomaly": False,
                "consecutive_anomalies": self.consecutive_anomaly_count,
                "decision": DecisionState.NORMAL.value,
                "reason": f"Collecting rolling window rows ({len(self.mapper.buffer)}/{RAW_WINDOW_SIZE})",
                "command": "NO_ACTION",
            }

        feature_frame = pd.DataFrame(
            [[features[column] for column in self.feature_columns]],
            columns=self.feature_columns,
        )
        regime, sub_regime, score, threshold = self._score(feature_frame)
        maintenance_alert_count = self._maintenance_alert_count(regime, sub_regime)
        decision = make_decision(
            score=score,
            threshold=threshold,
            consecutive_anomaly_count=self.consecutive_anomaly_count,
            features=reduced_features_for_policy(features),
            maintenance_alert_count=maintenance_alert_count,
        )
        self.consecutive_anomaly_count = decision.consecutive_anomaly_count

        return {
            "buffer_ready": True,
            "buffer_size": len(self.mapper.buffer),
            "regime": regime,
            "sub_regime": sub_regime,
            "score": score,
            "threshold": threshold,
            "is_anomaly": decision.is_anomaly,
            "consecutive_anomalies": decision.consecutive_anomaly_count,
            "decision": decision.state.value,
            "reason": decision.reason,
            "command": COMMANDS[decision.state],
        }

    def _score(self, feature_frame: pd.DataFrame) -> tuple[int, int | None, float, float]:
        regime = int(
            self.regime_model.predict(
                self.regime_scaler.transform(feature_frame[REGIME_COLUMNS])
            )[0]
        )
        if regime == 1:
            sub_regime = int(self.regime1_model.predict(feature_frame[REGIME_COLUMNS])[0])
            scaled_features = self.regime1_feature_scalers[sub_regime].transform(
                feature_frame
            )
            score = float(
                self.regime1_models[sub_regime].decision_function(scaled_features)[0]
            )
            threshold = float(self.regime1_thresholds[sub_regime])
            return regime, sub_regime, score, threshold

        scaled_features = self.regime_feature_scalers[regime].transform(feature_frame)
        score = float(self.regime_models[regime].decision_function(scaled_features)[0])
        threshold = float(self.regime_thresholds[regime])
        return regime, None, score, threshold

    @staticmethod
    def _maintenance_alert_count(regime: int, sub_regime: int | None) -> int:
        if regime == 1 and sub_regime is not None:
            return REGIME1_COUNTER_THRESHOLDS.get(sub_regime, 7)
        return REGIME_COUNTER_THRESHOLDS.get(regime, 5)


def vibration_magnitude(data: dict[str, Any]) -> float:
    if data.get("vibration") is not None:
        return float(data["vibration"])
    if all(data.get(axis) is not None for axis in ["vibration_x", "vibration_y", "vibration_z"]):
        return float(
            np.sqrt(
                float(data["vibration_x"]) ** 2
                + float(data["vibration_y"]) ** 2
                + float(data["vibration_z"]) ** 2
            )
        )
    raise ValueError("Provide either vibration or vibration_x, vibration_y, vibration_z")


def reduced_features_for_policy(features: dict[str, float]) -> dict[str, float]:
    return {
        "Voltage": features["Voltage"],
        "Current": features["Current"],
        "temp_mot": features["temp_mot"],
        "temp_delta": features["temp_delta"],
        "delta_Current": features["delta_Current"],
        "delta_temp_mot": features["delta_temp"],
        "vib_instability": features["vib_instability"],
        "vib_sum": features["vib_sum"],
        "vib_sum_window_max": features["1x[Vibration]_rolling_max"] * 10.0,
        "freq_ratio": features["1x[Vibration]"],
        "freq_high_window_max": features["1x[Vibration]_rolling_max"],
    }


_predictor = RegimePredictor()


def predict(data: dict[str, Any]) -> dict[str, Any]:
    return _predictor.predict(data)


def reset_predictor() -> None:
    _predictor.reset()

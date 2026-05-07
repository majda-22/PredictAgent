from collections import deque
from typing import Any

import numpy as np
import pandas as pd


RAW_COLUMNS = [
    "Current",
    "Voltage",
    "temp_mot",
    "temp_amb",
    "speed_rpm",
    "speed_Hz",
    "speed_band",
    "1x[Vibration]",
]

BASE_FEATURES = [
    *RAW_COLUMNS,
    "power",
    "current_voltage_ratio",
    "temp_delta",
    "temp_current_ratio",
    "vib_sum",
    "vib_instability",
    "current_per_rpm",
    "power_per_rpm",
    "vib_per_rpm",
    "voltage_per_rpm",
    "temp_per_rpm",
    "temp_per_current",
    "temp_delta_per_current",
    "power_temp_ratio",
    "vi_consistency",
]

DELTA_COLUMNS = ["Current", "Voltage", "temp_mot", "1x[Vibration]"]
ROLLING_COLUMNS = ["Current", "Voltage", "temp_mot", "1x[Vibration]", "power"]
ROLLING_STATS = ["mean", "std", "max", "min"]
RATIO_FEATURES = [
    "temp_per_current",
    "temp_delta_per_current",
    "power_temp_ratio",
    "vi_consistency",
]

REDUCED_FEATURE_COLUMNS = [
    *BASE_FEATURES,
    "delta_Current",
    "delta_Voltage",
    "delta_temp",
    "delta_vib",
    *[
        f"{column}_rolling_{stat}"
        for column in ROLLING_COLUMNS
        for stat in ROLLING_STATS
    ],
]


class ESP32FeatureMapper:
    def __init__(
        self,
        buffer_size: int = 10,
        vib_scaler: Any | None = None,
        ratio_clip_bounds: dict[str, float] | None = None,
    ) -> None:
        self.buffer_size = buffer_size
        self.vib_scaler = vib_scaler
        self.ratio_clip_bounds = ratio_clip_bounds or {}
        self.buffer: deque[dict[str, float]] = deque(maxlen=buffer_size)

    def reset(self) -> None:
        self.buffer.clear()

    @property
    def is_ready(self) -> bool:
        return len(self.buffer) >= self.buffer_size

    def map(
        self,
        current: float,
        voltage: float,
        temp_mot: float,
        temp_amb: float,
        speed_rpm: float,
        speed_hz: float,
        vibration: float,
    ) -> dict[str, float]:
        vib_value = self._normalize_vibration(vibration)
        power = current * voltage
        temp_delta = temp_mot - temp_amb
        speed_safe = max(speed_rpm, 100.0)
        current_safe = max(current, 0.01)
        temp_safe = max(temp_mot, 1.0)
        row = {
            "Current": current,
            "Voltage": voltage,
            "temp_mot": temp_mot,
            "temp_amb": temp_amb,
            "speed_rpm": speed_rpm,
            "speed_Hz": speed_hz,
            "speed_band": float(speed_band(speed_rpm)),
            "1x[Vibration]": vib_value,
            "vib_sum": vib_value * 10.0,
            "vib_instability": 0.0,
            "power": power,
            "current_voltage_ratio": current / (voltage + 1e-5),
            "temp_delta": temp_delta,
            "temp_current_ratio": temp_mot / (current + 1e-5),
            "current_per_rpm": current / speed_safe,
            "power_per_rpm": power / speed_safe,
            "vib_per_rpm": (vib_value * 10.0) / speed_safe,
            "voltage_per_rpm": voltage / speed_safe,
            "temp_per_rpm": temp_mot / speed_safe,
            "temp_per_current": temp_mot / current_safe,
            "temp_delta_per_current": temp_delta / current_safe,
            "power_temp_ratio": power / temp_safe,
            "vi_consistency": power / speed_safe,
        }
        row = self._clip_ratio_features(row)

        self.buffer.append(row)
        return self._add_temporal(row)

    def _normalize_vibration(self, vibration: float) -> float:
        if self.vib_scaler is None:
            return vibration
        return float(
            self.vib_scaler.transform(
                pd.DataFrame([[vibration]], columns=["1x[Vibration]"])
            )[0][0]
        )

    def _clip_ratio_features(self, row: dict[str, float]) -> dict[str, float]:
        for column, upper_bound in self.ratio_clip_bounds.items():
            if column in row:
                row[column] = min(row[column], upper_bound)
        return row

    def _add_temporal(self, row: dict[str, float]) -> dict[str, float]:
        rows = list(self.buffer)
        previous = rows[-2] if len(rows) > 1 else row

        row = row.copy()
        row["delta_Current"] = row["Current"] - previous["Current"]
        row["delta_Voltage"] = row["Voltage"] - previous["Voltage"]
        row["delta_temp"] = row["temp_mot"] - previous["temp_mot"]
        row["delta_vib"] = row["1x[Vibration]"] - previous["1x[Vibration]"]

        history = pd.DataFrame(rows)
        for column in ROLLING_COLUMNS:
            values = history[column]
            row[f"{column}_rolling_mean"] = float(values.mean())
            row[f"{column}_rolling_std"] = float(values.std(ddof=0))
            row[f"{column}_rolling_max"] = float(values.max())
            row[f"{column}_rolling_min"] = float(values.min())

        return {column: float(row[column]) for column in REDUCED_FEATURE_COLUMNS}


def speed_band(rpm: float) -> int:
    if rpm < 8068:
        return 0
    if rpm < 9200:
        return 1
    if rpm < 9691:
        return 2
    return 3


def apply_ratio_clips(
    data: pd.DataFrame,
    ratio_clip_bounds: dict[str, float] | None,
) -> pd.DataFrame:
    if not ratio_clip_bounds:
        return data
    clipped = data.copy()
    for column, upper_bound in ratio_clip_bounds.items():
        if column in clipped.columns:
            clipped[column] = clipped[column].clip(upper=upper_bound)
    return clipped


def build_reduced_features_from_dataset(
    df: pd.DataFrame,
    vib_scaler: Any | None = None,
    ratio_clip_bounds: dict[str, float] | None = None,
) -> pd.DataFrame:
    data = df.copy()
    if vib_scaler is not None:
        data["1x[Vibration]"] = vib_scaler.transform(data[["1x[Vibration]"]])
    data["speed_band"] = data["speed_rpm"].apply(speed_band)

    vibration_cols = [f"{index}x[Vibration]" for index in range(1, 11)]
    data["vib_sum"] = df[vibration_cols].sum(axis=1)
    data["vib_instability"] = df[vibration_cols].std(axis=1) / (df[vibration_cols].mean(axis=1) + 1e-9)
    if vib_scaler is not None:
        # Keep training honest for prototype deployment: use the deployable proxy after
        # deriving the diagnostic instability from the full dataset.
        data["vib_sum"] = data["1x[Vibration]"] * 10.0

    data["power"] = data["Current"] * data["Voltage"]
    data["current_voltage_ratio"] = data["Current"] / (data["Voltage"] + 1e-5)
    data["temp_delta"] = data["temp_mot"] - data["temp_amb"]
    data["temp_current_ratio"] = data["temp_mot"] / (data["Current"] + 1e-5)

    speed_safe = data["speed_rpm"].clip(lower=100)
    current_safe = data["Current"].clip(lower=0.01)
    temp_safe = data["temp_mot"].clip(lower=1)
    data["current_per_rpm"] = data["Current"] / speed_safe
    data["power_per_rpm"] = data["power"] / speed_safe
    data["vib_per_rpm"] = data["vib_sum"] / speed_safe
    data["voltage_per_rpm"] = data["Voltage"] / speed_safe
    data["temp_per_rpm"] = data["temp_mot"] / speed_safe
    data["temp_per_current"] = data["temp_mot"] / current_safe
    data["temp_delta_per_current"] = data["temp_delta"] / current_safe
    data["power_temp_ratio"] = data["power"] / temp_safe
    data["vi_consistency"] = data["Voltage"] * data["Current"] / speed_safe
    data = apply_ratio_clips(data, ratio_clip_bounds)

    data["delta_Current"] = data["Current"].diff().fillna(0)
    data["delta_Voltage"] = data["Voltage"].diff().fillna(0)
    data["delta_temp"] = data["temp_mot"].diff().fillna(0)
    data["delta_vib"] = data["1x[Vibration]"].diff().fillna(0)

    for column in ROLLING_COLUMNS:
        rolling = data[column].rolling(window=10, min_periods=1)
        data[f"{column}_rolling_mean"] = rolling.mean()
        data[f"{column}_rolling_std"] = rolling.std(ddof=0).fillna(0)
        data[f"{column}_rolling_max"] = rolling.max()
        data[f"{column}_rolling_min"] = rolling.min()

    return data[REDUCED_FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).dropna()

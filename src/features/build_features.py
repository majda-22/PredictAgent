from pathlib import Path
import argparse

import numpy as np
import pandas as pd

try:
    from feature_groups import (
        basic_features,
        current_freq_bands,
        current_harmonics,
        vibration_features,
        vibration_freq_bands,
        voltage_freq_bands,
        voltage_harmonics,
    )
except ImportError:
    from .feature_groups import (
        basic_features,
        current_freq_bands,
        current_harmonics,
        vibration_features,
        vibration_freq_bands,
        voltage_freq_bands,
        voltage_harmonics,
    )


CLEAN_FILE = Path("data/clean/clean_data.csv")
FEATURES_BASE_FILE = Path("data/processed/features_base.csv")
FEATURES_WINDOW_FILE = Path("data/processed/features_window.csv")
WINDOW_SIZE = 5

LOW_FREQ_VIBRATION_COLUMNS = ["0-4k_Hz[Vibration]"]
HIGH_FREQ_VIBRATION_COLUMNS = [
    "8k-16kHz[Vibration]",
    "16k-26kHz[Vibration]",
]
DELTA_COLUMNS = [
    "Current",
    "Voltage",
    "temp_mot",
    "vib_sum",
    "power",
]
WINDOW_FEATURES = [
    "Current",
    "Voltage",
    "temp_mot",
    "vib_sum",
    "power",
    "freq_low",
    "freq_high",
    "freq_ratio",
]


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    ratio = numerator / denominator.replace(0, np.nan)
    return ratio.replace([np.inf, -np.inf], np.nan).fillna(0)


def _validate_columns(df: pd.DataFrame) -> None:
    required_columns = {
        "Date",
        "target",
        "Anomaly_Details",
        *basic_features,
        *vibration_features,
        *current_harmonics,
        *voltage_harmonics,
        *vibration_freq_bands,
        *current_freq_bands,
        *voltage_freq_bands,
    }
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {missing}")


def add_base_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["temp_delta"] = df["temp_mot"] - df["temp_amb"]
    df["power"] = df["Current"] * df["Voltage"]
    df["temp_current_ratio"] = _safe_ratio(df["temp_mot"], df["Current"])
    df["current_voltage_ratio"] = _safe_ratio(df["Current"], df["Voltage"])

    vibration_values = df[vibration_features]
    df["vib_sum"] = vibration_values.sum(axis=1)
    df["vib_mean"] = vibration_values.mean(axis=1)
    df["vib_std"] = vibration_values.std(axis=1)
    df["vib_instability"] = _safe_ratio(df["vib_std"], df["vib_mean"])

    df["vib_2x_1x_ratio"] = _safe_ratio(df["2x[Vibration]"], df["1x[Vibration]"])
    df["vib_3x_1x_ratio"] = _safe_ratio(df["3x[Vibration]"], df["1x[Vibration]"])
    df["vib_4x_1x_ratio"] = _safe_ratio(df["4x[Vibration]"], df["1x[Vibration]"])
    df["dominant_harmonic"] = (
        vibration_values.idxmax(axis=1).str.extract(r"(\d+)x", expand=False).astype(int)
    )

    df["freq_low"] = df[LOW_FREQ_VIBRATION_COLUMNS].sum(axis=1)
    df["freq_high"] = df[HIGH_FREQ_VIBRATION_COLUMNS].sum(axis=1)
    df["freq_ratio"] = _safe_ratio(df["freq_high"], df["freq_low"])

    return df


def add_delta_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for column in DELTA_COLUMNS:
        df[f"delta_{column}"] = df[column].diff().fillna(0)
    return df


def add_window_features(df: pd.DataFrame, window: int = WINDOW_SIZE) -> pd.DataFrame:
    df = df.copy()
    for column in WINDOW_FEATURES:
        rolling = df[column].rolling(window=window, min_periods=1)
        df[f"{column}_window_mean"] = rolling.mean()
        df[f"{column}_window_std"] = rolling.std().fillna(0)
        df[f"{column}_window_min"] = rolling.min()
        df[f"{column}_window_max"] = rolling.max()
        df[f"{column}_window_delta"] = (df[column] - df[column].shift(window - 1)).fillna(0)
    return df


def build_features(
    clean_file: Path = CLEAN_FILE,
    features_base_file: Path = FEATURES_BASE_FILE,
    features_window_file: Path = FEATURES_WINDOW_FILE,
    window: int = WINDOW_SIZE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(clean_file, parse_dates=["Date"])
    _validate_columns(df)
    df = df.sort_values("Date").reset_index(drop=True)

    base_df = add_delta_features(add_base_features(df))
    window_df = add_window_features(base_df, window=window)

    features_base_file.parent.mkdir(parents=True, exist_ok=True)
    base_df.to_csv(features_base_file, index=False)
    window_df.to_csv(features_window_file, index=False)
    return base_df, window_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build motor feature datasets.")
    parser.add_argument("--clean-file", type=Path, default=CLEAN_FILE)
    parser.add_argument("--base-file", type=Path, default=FEATURES_BASE_FILE)
    parser.add_argument("--window-file", type=Path, default=FEATURES_WINDOW_FILE)
    parser.add_argument("--window", type=int, default=WINDOW_SIZE)
    args = parser.parse_args()

    base, windowed = build_features(
        clean_file=args.clean_file,
        features_base_file=args.base_file,
        features_window_file=args.window_file,
        window=args.window,
    )
    print(f"Saved base features: {args.base_file} ({base.shape[0]} rows, {base.shape[1]} columns)")
    print(
        f"Saved window features: {args.window_file} "
        f"({windowed.shape[0]} rows, {windowed.shape[1]} columns)"
    )

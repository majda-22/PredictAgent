from pathlib import Path

import pandas as pd


RAW_FILE = Path("data/raw/DC_motor_anomaly_detection.xlsx")
CLEAN_FILE = Path("data/clean/clean_data.csv")
DATE_FORMAT = "%d/%m/%Y %H:%M:%S.%f"
TARGET_MAP = {
    "Normal": 0,
    "Anomalie": 1,
}
EXPECTED_COUNTS = {
    0: 328,
    1: 49,
}


def clean_data(raw_file: Path = RAW_FILE, clean_file: Path = CLEAN_FILE) -> pd.DataFrame:
    df = pd.read_excel(raw_file)

    required_columns = {"Date", "Anomaly", "Anomaly_Details"}
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {missing}")

    df["Date"] = df["Date"].astype(str).str.replace(",", ".", regex=False)
    df["Date"] = pd.to_datetime(df["Date"], format=DATE_FORMAT, errors="raise")

    df["target"] = df["Anomaly"].map(TARGET_MAP)
    if df["target"].isna().any():
        raise ValueError("Anomaly contains values outside Normal/Anomalie")

    df["target"] = df["target"].astype(int)
    df = df.drop(columns=["File"], errors="ignore")
    df = df.sort_values("Date").reset_index(drop=True)

    counts = df["target"].value_counts().to_dict()
    if counts != EXPECTED_COUNTS:
        raise ValueError(f"Unexpected target counts: {counts}")

    clean_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(clean_file, index=False)
    return df


if __name__ == "__main__":
    cleaned = clean_data()
    counts = cleaned["target"].value_counts().sort_index()
    print(f"Saved {len(cleaned)} rows to {CLEAN_FILE}")
    print(f"Normal rows: {counts.get(0, 0)}")
    print(f"Anomaly rows: {counts.get(1, 0)}")

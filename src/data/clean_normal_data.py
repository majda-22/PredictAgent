from pathlib import Path

import pandas as pd


RAW_FILE = Path("data/raw/DC_Motor_5000_Generated.xlsx")
CLEAN_FILE = Path("data/clean/clean_data_new.csv")
DATE_FORMAT = "%d/%m/%Y %H:%M:%S.%f"
SHEET_NAME = "DC_Motor_Data"


def clean_normal_data(
    raw_file: Path = RAW_FILE,
    clean_file: Path = CLEAN_FILE,
) -> pd.DataFrame:
    df = pd.read_excel(raw_file, sheet_name=SHEET_NAME, header=1)

    if "Date" not in df.columns:
        raise ValueError("Missing required column: Date")

    df["Date"] = df["Date"].astype(str).str.replace(",", ".", regex=False)
    df["Date"] = pd.to_datetime(df["Date"], format=DATE_FORMAT, errors="raise")

    df["Anomaly_Count"] = 0
    df["Anomaly"] = "Normal"
    df["Anomaly_Details"] = pd.NA
    df["target"] = 0

    df = df.drop(columns=["File"], errors="ignore")
    df = df.sort_values("Date").reset_index(drop=True)

    clean_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(clean_file, index=False)
    return df


if __name__ == "__main__":
    cleaned = clean_normal_data()
    print(f"Saved {len(cleaned)} rows to {CLEAN_FILE}")
    print(f"Target counts: {cleaned['target'].value_counts().sort_index().to_dict()}")

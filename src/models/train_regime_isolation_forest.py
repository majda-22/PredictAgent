from pathlib import Path
import sys

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sklearn.preprocessing import MinMaxScaler, StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.features.esp32_feature_mapper import (
    REDUCED_FEATURE_COLUMNS,
    RATIO_FEATURES,
    build_reduced_features_from_dataset,
)


NEW_NORMAL_FILE = Path("data/clean/clean_data_new.csv")
OLD_LABELED_FILE = Path("data/clean/clean_data.csv")
REGIME_MODEL_FILE = Path("models/regime_kmeans.joblib")
REGIME_SCALER_FILE = Path("models/regime_scaler.joblib")
REGIME_IFOREST_FILE = Path("models/regime_isolation_forests.joblib")
REGIME_FEATURE_SCALERS_FILE = Path("models/regime_feature_scalers.joblib")
REGIME_THRESHOLDS_FILE = Path("models/regime_thresholds.joblib")
REGIME1_MODEL_FILE = Path("models/regime1_kmeans.joblib")
REGIME1_IFOREST_FILE = Path("models/regime1_sub_models.joblib")
REGIME1_FEATURE_SCALERS_FILE = Path("models/regime1_sub_feature_scalers.joblib")
REGIME1_THRESHOLDS_FILE = Path("models/regime1_sub_thresholds.joblib")
VIB_SCALER_FILE = Path("models/vib_scaler.pkl")
FEATURE_COLUMNS_FILE = Path("models/reduced_feature_columns.joblib")
RATIO_CLIP_BOUNDS_FILE = Path("models/reduced_ratio_clip_bounds.joblib")
REPORT_FILE = Path("reports/regime_model_evaluation.csv")
SUMMARY_FILE = Path("reports/regime_model_summary.csv")
REGIME1_SPLIT_PLOT_FILE = Path("reports/regime1_subregime_split.png")
N_REGIMES = 3
RANDOM_STATE = 42
CONTAMINATION = 0.05
THRESHOLD_PERCENTILE = 2
REGIME_COLUMNS = ["speed_rpm", "current_per_rpm"]
REGIME_COUNTER_THRESHOLDS = {0: 3, 1: 7, 2: 5}
REGIME_CONFIGS = {
    0: {"n_estimators": 100, "contamination": 0.05},
    1: {"n_estimators": 300, "contamination": 0.08},
    2: {"n_estimators": 100, "contamination": 0.05},
}


def build_ratio_clip_bounds(normal_features: pd.DataFrame) -> dict[str, float]:
    bounds = {
        column: float(normal_features[column].quantile(0.99))
        for column in RATIO_FEATURES
    }
    bounds["temp_per_current"] = min(bounds["temp_per_current"], 80.0)
    return bounds


def regime_labels(
    features: pd.DataFrame,
    regime_scaler: StandardScaler,
    regime_model: KMeans,
) -> np.ndarray:
    return regime_model.predict(regime_scaler.transform(features[REGIME_COLUMNS]))


def train_regime_models(
    normal_features: pd.DataFrame,
    labels: np.ndarray,
) -> tuple[dict[int, StandardScaler], dict[int, IsolationForest], dict[int, float]]:
    feature_scalers: dict[int, StandardScaler] = {}
    models: dict[int, IsolationForest] = {}
    thresholds: dict[int, float] = {}

    for regime in sorted(set(labels)):
        regime_features = normal_features.loc[labels == regime, REDUCED_FEATURE_COLUMNS]
        scaler = StandardScaler()
        x_scaled = scaler.fit_transform(regime_features)
        config = REGIME_CONFIGS.get(
            int(regime),
            {"n_estimators": 150, "contamination": CONTAMINATION},
        )
        model = IsolationForest(
            n_estimators=config["n_estimators"],
            contamination=config["contamination"],
            random_state=RANDOM_STATE,
        )
        model.fit(x_scaled)
        scores = model.decision_function(x_scaled)
        threshold = float(np.percentile(scores, THRESHOLD_PERCENTILE))

        feature_scalers[int(regime)] = scaler
        models[int(regime)] = model
        thresholds[int(regime)] = threshold

    return feature_scalers, models, thresholds


def train_regime1_submodels(
    normal_features: pd.DataFrame,
    regimes: np.ndarray,
) -> tuple[KMeans, dict[int, StandardScaler], dict[int, IsolationForest], dict[int, float]]:
    regime1_features = normal_features.loc[regimes == 1]
    sub_kmeans = KMeans(n_clusters=2, random_state=RANDOM_STATE, n_init=20)
    sub_labels = sub_kmeans.fit_predict(regime1_features[REGIME_COLUMNS])
    plot_regime1_split(regime1_features, sub_labels)
    sub_scalers: dict[int, StandardScaler] = {}
    sub_models: dict[int, IsolationForest] = {}
    sub_thresholds: dict[int, float] = {}

    for sub_regime in sorted(set(sub_labels)):
        sub_features = regime1_features.loc[sub_labels == sub_regime, REDUCED_FEATURE_COLUMNS]
        scaler = StandardScaler()
        x_scaled = scaler.fit_transform(sub_features)
        model = IsolationForest(
            n_estimators=300,
            contamination=0.08,
            random_state=RANDOM_STATE,
        )
        model.fit(x_scaled)
        scores = model.decision_function(x_scaled)
        sub_scalers[int(sub_regime)] = scaler
        sub_models[int(sub_regime)] = model
        sub_thresholds[int(sub_regime)] = float(
            np.percentile(scores, THRESHOLD_PERCENTILE)
        )

    return sub_kmeans, sub_scalers, sub_models, sub_thresholds


def plot_regime1_split(regime1_features: pd.DataFrame, sub_labels: np.ndarray) -> None:
    REGIME1_SPLIT_PLOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    scatter = ax.scatter(
        regime1_features["speed_rpm"],
        regime1_features["current_per_rpm"],
        c=sub_labels,
        cmap="RdYlGn",
        alpha=0.5,
        s=16,
    )
    ax.set_xlabel("speed_rpm")
    ax.set_ylabel("current_per_rpm")
    ax.set_title("Regime 1 Sub-regime Split")
    ax.axvline(x=9691, color="red", linestyle="--", label="9691 rpm boundary")
    fig.colorbar(scatter, ax=ax, label="sub_regime")
    ax.legend()
    fig.tight_layout()
    fig.savefig(REGIME1_SPLIT_PLOT_FILE, dpi=150)
    plt.close(fig)


def score_by_regime(
    features: pd.DataFrame,
    regimes: np.ndarray,
    feature_scalers: dict[int, StandardScaler],
    models: dict[int, IsolationForest],
    thresholds: dict[int, float],
    regime1_kmeans: KMeans | None = None,
    regime1_feature_scalers: dict[int, StandardScaler] | None = None,
    regime1_models: dict[int, IsolationForest] | None = None,
    regime1_thresholds: dict[int, float] | None = None,
) -> pd.DataFrame:
    scored_parts = []
    for regime in sorted(set(regimes)):
        mask = regimes == regime
        regime_features = features.loc[mask, REDUCED_FEATURE_COLUMNS]
        if (
            int(regime) == 1
            and regime1_kmeans is not None
            and regime1_feature_scalers is not None
            and regime1_models is not None
            and regime1_thresholds is not None
        ):
            sub_labels = regime1_kmeans.predict(regime_features[REGIME_COLUMNS])
            for sub_regime in sorted(set(sub_labels)):
                sub_mask = sub_labels == sub_regime
                sub_features = regime_features.loc[sub_mask]
                scores = regime1_models[int(sub_regime)].decision_function(
                    regime1_feature_scalers[int(sub_regime)].transform(sub_features)
                )
                threshold = regime1_thresholds[int(sub_regime)]
                scored_parts.append(
                    pd.DataFrame(
                        {
                            "regime": int(regime),
                            "sub_regime": int(sub_regime),
                            "score": scores,
                            "threshold": threshold,
                            "predicted": (scores < threshold).astype(int),
                        },
                        index=sub_features.index,
                    )
                )
        else:
            scores = models[int(regime)].decision_function(
                feature_scalers[int(regime)].transform(regime_features)
            )
            threshold = thresholds[int(regime)]
            part = pd.DataFrame(
                {
                    "regime": int(regime),
                    "sub_regime": -1,
                    "score": scores,
                    "threshold": threshold,
                    "predicted": (scores < threshold).astype(int),
                },
                index=regime_features.index,
            )
            scored_parts.append(part)
    return pd.concat(scored_parts).sort_index()


def main() -> None:
    new_df = pd.read_csv(NEW_NORMAL_FILE, parse_dates=["Date"])
    old_df = pd.read_csv(OLD_LABELED_FILE, parse_dates=["Date"])
    old_normal_df = old_df[old_df["target"] == 0].copy()
    normal_fit_df = pd.concat([new_df, old_normal_df], axis=0, ignore_index=True)

    vib_scaler = MinMaxScaler()
    vib_scaler.fit(normal_fit_df[["1x[Vibration]"]])

    unclipped_normal = build_reduced_features_from_dataset(
        normal_fit_df,
        vib_scaler=vib_scaler,
    )
    ratio_clip_bounds = build_ratio_clip_bounds(unclipped_normal)
    normal_features = build_reduced_features_from_dataset(
        normal_fit_df,
        vib_scaler=vib_scaler,
        ratio_clip_bounds=ratio_clip_bounds,
    )
    old_features = build_reduced_features_from_dataset(
        old_df,
        vib_scaler=vib_scaler,
        ratio_clip_bounds=ratio_clip_bounds,
    )

    regime_scaler = StandardScaler()
    normal_regime_x = regime_scaler.fit_transform(normal_features[REGIME_COLUMNS])
    regime_model = KMeans(
        n_clusters=N_REGIMES,
        random_state=RANDOM_STATE,
        n_init=20,
    )
    normal_regimes = regime_model.fit_predict(normal_regime_x)
    feature_scalers, models, thresholds = train_regime_models(
        normal_features,
        normal_regimes,
    )
    regime1_kmeans, regime1_feature_scalers, regime1_models, regime1_thresholds = (
        train_regime1_submodels(normal_features, normal_regimes)
    )

    old_regimes = regime_labels(old_features, regime_scaler, regime_model)
    scored = score_by_regime(
        old_features,
        old_regimes,
        feature_scalers,
        models,
        thresholds,
        regime1_kmeans=regime1_kmeans,
        regime1_feature_scalers=regime1_feature_scalers,
        regime1_models=regime1_models,
        regime1_thresholds=regime1_thresholds,
    )
    y_true = old_df.loc[old_features.index, "target"].astype(int)
    scored["target"] = y_true
    scored["Date"] = old_df.loc[old_features.index, "Date"]
    scored["speed_rpm"] = old_df.loc[old_features.index, "speed_rpm"]
    scored["Current"] = old_df.loc[old_features.index, "Current"]
    scored["temp_mot"] = old_df.loc[old_features.index, "temp_mot"]
    scored["Anomaly_Details"] = old_df.loc[old_features.index, "Anomaly_Details"]

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REGIME_MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(REPORT_FILE, index=False)

    summary_rows = []
    normal_labeled = scored[scored["target"] == 0].copy()
    for regime in sorted(thresholds):
        regime_normal = normal_features.loc[normal_regimes == regime]
        old_part = scored[scored["regime"] == regime]
        summary_rows.append(
            {
                "regime": regime,
                "normal_train_rows": len(regime_normal),
                "threshold": thresholds[regime],
                "train_speed_mean": regime_normal["speed_rpm"].mean(),
                "train_current_per_rpm_mean": regime_normal["current_per_rpm"].mean(),
                "old_rows": len(old_part),
                "old_normal_fp": int(((old_part["target"] == 0) & (old_part["predicted"] == 1)).sum()),
                "old_anomaly_tp": int(((old_part["target"] == 1) & (old_part["predicted"] == 1)).sum()),
            }
        )
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(SUMMARY_FILE, index=False)

    joblib.dump(regime_model, REGIME_MODEL_FILE)
    joblib.dump(regime_scaler, REGIME_SCALER_FILE)
    joblib.dump(feature_scalers, REGIME_FEATURE_SCALERS_FILE)
    joblib.dump(models, REGIME_IFOREST_FILE)
    joblib.dump(thresholds, REGIME_THRESHOLDS_FILE)
    joblib.dump(regime1_kmeans, REGIME1_MODEL_FILE)
    joblib.dump(regime1_models, REGIME1_IFOREST_FILE)
    joblib.dump(regime1_feature_scalers, REGIME1_FEATURE_SCALERS_FILE)
    joblib.dump(regime1_thresholds, REGIME1_THRESHOLDS_FILE)
    joblib.dump(vib_scaler, VIB_SCALER_FILE)
    joblib.dump(REDUCED_FEATURE_COLUMNS, FEATURE_COLUMNS_FILE)
    joblib.dump(ratio_clip_bounds, RATIO_CLIP_BOUNDS_FILE)

    y_pred = scored["predicted"].to_numpy()
    print("Regime model validation on old labeled dataset:")
    print(f"Precision: {precision_score(y_true, y_pred, zero_division=0):.4f}")
    print(f"Recall: {recall_score(y_true, y_pred, zero_division=0):.4f}")
    print(f"F1: {f1_score(y_true, y_pred, zero_division=0):.4f}")
    print("Confusion matrix [[TN, FP], [FN, TP]]:")
    print(confusion_matrix(y_true, y_pred))
    print()
    print("Regime summary:")
    print(summary.to_string(index=False))
    print()
    print("Per-regime validation:")
    for regime in sorted(scored["regime"].unique()):
        part = scored[scored["regime"] == regime]
        print(f"Regime {regime} - n={len(part)}")
        print(f"  Precision: {precision_score(part['target'], part['predicted'], zero_division=0):.4f}")
        print(f"  Recall:    {recall_score(part['target'], part['predicted'], zero_division=0):.4f}")
        print(f"  F1:        {f1_score(part['target'], part['predicted'], zero_division=0):.4f}")
        print(confusion_matrix(part["target"], part["predicted"]))
    print()
    print("Regime 1 sub-regime validation:")
    regime1_scored = scored[scored["regime"] == 1]
    for sub_regime in sorted(regime1_scored["sub_regime"].unique()):
        part = regime1_scored[regime1_scored["sub_regime"] == sub_regime]
        print(f"Regime 1.{sub_regime} - n={len(part)}")
        print(f"  Precision: {precision_score(part['target'], part['predicted'], zero_division=0):.4f}")
        print(f"  Recall:    {recall_score(part['target'], part['predicted'], zero_division=0):.4f}")
        print(f"  F1:        {f1_score(part['target'], part['predicted'], zero_division=0):.4f}")
        print(confusion_matrix(part["target"], part["predicted"]))
    print()
    print("False-positive rate by speed band:")
    normal_labeled["speed_band"] = pd.qcut(
        normal_labeled["speed_rpm"],
        q=5,
        duplicates="drop",
    )
    print(
        normal_labeled.groupby("speed_band", observed=False)["predicted"]
        .mean()
        .to_string()
    )
    print()
    print(f"Saved evaluation: {REPORT_FILE}")
    print(f"Saved summary: {SUMMARY_FILE}")
    print(f"Saved regime model: {REGIME_MODEL_FILE}")


if __name__ == "__main__":
    main()

"""
Compute a single performance metric from a predictions CSV and a labels CSV.

Usage:
    python compute_metrics.py \
        --predictions <predictions.csv> --pred-col <column> \
        --labels <labels.csv> --label-col <column> \
        --metric <metric-name>

Supported metrics:
    Classification : auc-roc, auc-prc, accuracy, mcc, f1
    Regression     : rmse, mae, r2

Output: a single float printed to stdout.
"""

import argparse
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    accuracy_score,
    matthews_corrcoef,
    f1_score,
    mean_squared_error,
    mean_absolute_error,
    r2_score,
)

CLASSIFICATION_METRICS = {"auc-roc", "auc-prc", "accuracy", "mcc", "f1"}
REGRESSION_METRICS = {"rmse", "mae", "r2"}
ALL_METRICS = CLASSIFICATION_METRICS | REGRESSION_METRICS


def load_column(path: str, col: str) -> np.ndarray:
    df = pd.read_csv(path)
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not found in {path}. Available: {list(df.columns)}")
    return df[col].values


def compute(y_true: np.ndarray, y_pred: np.ndarray, metric: str) -> float:
    metric = metric.lower()
    if metric not in ALL_METRICS:
        raise ValueError(f"Unknown metric '{metric}'. Choose from: {sorted(ALL_METRICS)}")

    if metric == "auc-roc":
        return float(roc_auc_score(y_true, y_pred))
    if metric == "auc-prc":
        return float(average_precision_score(y_true, y_pred))
    if metric == "accuracy":
        # binarise predictions at 0.5 if they are probabilities
        y_bin = (y_pred >= 0.5).astype(int) if y_pred.dtype.kind == "f" else y_pred
        return float(accuracy_score(y_true, y_bin))
    if metric == "mcc":
        y_bin = (y_pred >= 0.5).astype(int) if y_pred.dtype.kind == "f" else y_pred
        return float(matthews_corrcoef(y_true, y_bin))
    if metric == "f1":
        y_bin = (y_pred >= 0.5).astype(int) if y_pred.dtype.kind == "f" else y_pred
        return float(f1_score(y_true, y_bin))
    if metric == "rmse":
        return float(np.sqrt(mean_squared_error(y_true, y_pred)))
    if metric == "mae":
        return float(mean_absolute_error(y_true, y_pred))
    if metric == "r2":
        return float(r2_score(y_true, y_pred))


def main():
    parser = argparse.ArgumentParser(description="Compute a performance metric.")
    parser.add_argument("--predictions", required=True, help="CSV with model predictions")
    parser.add_argument("--pred-col", required=True, help="Column name in predictions CSV")
    parser.add_argument("--labels", required=True, help="CSV with ground-truth labels")
    parser.add_argument("--label-col", required=True, help="Column name in labels CSV")
    parser.add_argument("--metric", required=True, help=f"Metric: {sorted(ALL_METRICS)}")
    args = parser.parse_args()

    y_pred = load_column(args.predictions, args.pred_col)
    y_true = load_column(args.labels, args.label_col)

    if len(y_pred) != len(y_true):
        print(
            f"ERROR: predictions ({len(y_pred)}) and labels ({len(y_true)}) have different lengths.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Drop rows where either value is NaN
    mask = ~(np.isnan(y_pred.astype(float)) | np.isnan(y_true.astype(float)))
    dropped = (~mask).sum()
    if dropped:
        print(f"WARNING: dropping {dropped} rows with NaN values.", file=sys.stderr)
    y_pred, y_true = y_pred[mask].astype(float), y_true[mask].astype(float)

    result = compute(y_true, y_pred, args.metric)
    print(result)


if __name__ == "__main__":
    main()

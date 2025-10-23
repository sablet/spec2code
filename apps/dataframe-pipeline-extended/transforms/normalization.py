# Auto-generated skeleton for Transform: normalize_minmax
from packages.spec2code.engine import Check, ExampleValue
from typing import Annotated
import pandas as pd


def normalize_minmax(
    data: Annotated[
        pd.DataFrame,
        ExampleValue[
            {
                "rows": [
                    {"timestamp": "2024-01-01", "value": 100},
                    {"timestamp": "2024-01-02", "value": 150},
                    {"timestamp": "2024-01-03", "value": 120},
                ]
            }
        ],
    ],
) -> Annotated[
    pd.DataFrame,
    Check["apps.dataframe-pipeline-extended.checks.dataframe_checks:check_normalized"],
]:
    """MinMax normalization (0-1 scaling)"""
    df = data.copy()
    min_val = df["value"].min()
    max_val = df["value"].max()
    df["normalized"] = (
        (df["value"] - min_val) / (max_val - min_val) if max_val > min_val else 0.0
    )
    return df


def normalize_zscore(
    data: Annotated[
        pd.DataFrame,
        ExampleValue[
            {
                "rows": [
                    {"timestamp": "2024-01-01", "value": 100},
                    {"timestamp": "2024-01-02", "value": 150},
                    {"timestamp": "2024-01-03", "value": 120},
                ]
            }
        ],
    ],
) -> Annotated[
    pd.DataFrame,
    Check["apps.dataframe-pipeline-extended.checks.dataframe_checks:check_normalized"],
]:
    """Z-score normalization (mean=0, std=1)"""
    df = data.copy()
    mean_val = df["value"].mean()
    std_val = df["value"].std()
    df["normalized"] = (df["value"] - mean_val) / std_val if std_val > 0 else 0.0
    return df


def normalize_robust(
    data: Annotated[
        pd.DataFrame,
        ExampleValue[
            {
                "rows": [
                    {"timestamp": "2024-01-01", "value": 100},
                    {"timestamp": "2024-01-02", "value": 150},
                    {"timestamp": "2024-01-03", "value": 120},
                ]
            }
        ],
    ],
) -> Annotated[
    pd.DataFrame,
    Check["apps.dataframe-pipeline-extended.checks.dataframe_checks:check_normalized"],
]:
    """Robust normalization (median/IQR based)"""
    df = data.copy()
    median_val = df["value"].median()
    q75 = df["value"].quantile(0.75)
    q25 = df["value"].quantile(0.25)
    iqr = q75 - q25
    df["normalized"] = (df["value"] - median_val) / iqr if iqr > 0 else 0.0
    return df

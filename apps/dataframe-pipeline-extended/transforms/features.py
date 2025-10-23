# Auto-generated skeleton for Transform: add_rolling_mean
from packages.spec2code.engine import Check, ExampleValue
from typing import Annotated
import pandas as pd


def add_rolling_mean(
    data: Annotated[
        pd.DataFrame,
        ExampleValue[
            {
                "rows": [
                    {"timestamp": "2024-01-01", "value": 100, "normalized": 0.0},
                    {"timestamp": "2024-01-02", "value": 150, "normalized": 1.0},
                    {"timestamp": "2024-01-03", "value": 120, "normalized": 0.4},
                ]
            }
        ],
    ],
    window: int,
) -> Annotated[
    pd.DataFrame,
    Check["apps.dataframe-pipeline-extended.checks.dataframe_checks:check_normalized"],
]:
    """Add rolling mean feature (window=2)"""
    df = data.copy()
    df["rolling_mean"] = df["value"].rolling(window=window, min_periods=1).mean()
    return df


def add_diff(
    data: Annotated[
        pd.DataFrame,
        ExampleValue[
            {
                "rows": [
                    {"timestamp": "2024-01-01", "value": 100, "normalized": 0.0},
                    {"timestamp": "2024-01-02", "value": 150, "normalized": 1.0},
                    {"timestamp": "2024-01-03", "value": 120, "normalized": 0.4},
                ]
            }
        ],
    ],
) -> Annotated[
    pd.DataFrame,
    Check["apps.dataframe-pipeline-extended.checks.dataframe_checks:check_normalized"],
]:
    """Add difference feature (current - previous)"""
    df = data.copy()
    df["diff"] = df["value"].diff().fillna(0)
    return df


def add_lag_features(
    data: Annotated[
        pd.DataFrame,
        ExampleValue[
            {
                "rows": [
                    {"timestamp": "2024-01-01", "value": 100, "normalized": 0.0},
                    {"timestamp": "2024-01-02", "value": 150, "normalized": 1.0},
                    {"timestamp": "2024-01-03", "value": 120, "normalized": 0.4},
                ]
            }
        ],
    ],
    n_lags: int,
) -> Annotated[
    pd.DataFrame,
    Check["apps.dataframe-pipeline-extended.checks.dataframe_checks:check_normalized"],
]:
    """Add lag features (previous N values)"""
    df = data.copy()
    for i in range(1, n_lags + 1):
        df[f"lag_{i}"] = df["value"].shift(i).fillna(0)
    return df

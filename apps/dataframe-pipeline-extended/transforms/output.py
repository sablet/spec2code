# Auto-generated skeleton for Transform: finalize_step_b
from packages.spec2code.engine import Check, ExampleValue
from typing import Annotated
import pandas as pd


def finalize_step_b(
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
    Check["apps.dataframe-pipeline-extended.checks.dataframe_checks:check_step_b"],
]:
    """Finalize to Step B format"""
    # Just return the data as-is, assuming all features have been added
    return data

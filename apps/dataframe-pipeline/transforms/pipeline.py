# Auto-generated skeleton for Transform: transform_step_a_to_step_b
from spec2code.engine import Check, ExampleValue
from typing import Annotated
import pandas as pd


def transform_step_a_to_step_b(
    step_a_data: Annotated[
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
) -> Annotated[pd.DataFrame, Check["apps.dataframe-pipeline.checks.dataframe_checks:check_step_b"]]:
    """Transform from Step A to Step B (add normalized column)"""
    # TODO: implement transform logic
    return {}

# Auto-generated skeleton for Transform: transform_bc_to_d
from spec2code.engine import Check, ExampleValue
from typing import Annotated
import pandas as pd


def transform_bc_to_d(
    data_b: Annotated[
        pd.DataFrame,
        ExampleValue[
            {
                "rows": [
                    {"id": 1, "value": 100, "processed": 110},
                    {"id": 2, "value": 200, "processed": 220},
                ]
            }
        ],
    ],
    data_c: Annotated[
        pd.DataFrame,
        ExampleValue[{"rows": [{"id": 1, "factor": 1.5}, {"id": 2, "factor": 2.0}]}],
    ],
) -> Annotated[pd.DataFrame, Check["apps.dataframe-abcd.checks.dataframe_checks:check_d"]]:
    """Transform from B and C to D (combine and calculate result)"""
    # TODO: implement transform logic
    return {}

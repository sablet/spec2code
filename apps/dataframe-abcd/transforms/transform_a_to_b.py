# Auto-generated skeleton for Transform: transform_a_to_b
from spec2code.engine import Check, ExampleValue
from typing import Annotated
import pandas as pd


def transform_a_to_b(
    data_a: Annotated[
        pd.DataFrame,
        ExampleValue[{"rows": [{"id": 1, "value": 100}, {"id": 2, "value": 200}]}],
    ],
) -> Annotated[pd.DataFrame, Check["apps.dataframe-abcd.checks.dataframe_checks:check_b"]]:
    """Transform from A to B (add processed column)"""
    # TODO: implement transform logic
    return {}

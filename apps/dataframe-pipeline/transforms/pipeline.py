# Auto-generated skeleton for Transform functions

from spec2code.engine import Check, ExampleValue
from typing import Annotated
import pandas as pd


# Auto-generated skeleton for Transform: transform_step_a_to_step_b
def transform_step_a_to_step_b(
    step_a_data: Annotated[
        pd.DataFrame,
        ExampleValue[{"__example_id__": "ex_step_a", "__example_value__": {"timestamp": "2024-01-01", "value": 100}}],
    ],
) -> Annotated[
    pd.DataFrame,
    Check["apps.dataframe-pipeline.checks.dataframe_checks:check_step_b"],
    ExampleValue[{"__example_id__": "ex_step_b", "__example_value__": {"valid": True}}],
]:
    """Transform from Step A to Step B (add normalized column)"""
    # TODO: implement transform logic
    return {}

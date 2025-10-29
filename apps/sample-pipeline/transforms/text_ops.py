# Auto-generated skeleton for Transform functions

from spec2code.engine import Check, ExampleValue
from typing import Annotated


# Auto-generated skeleton for Transform: measure_length
def measure_length(
    payload: Annotated[dict, ExampleValue[{"__example_id__": "ex_hello", "__example_value__": {"text": "hello"}}]],
    normalize: bool,
) -> Annotated[
    dict,
    Check["apps.sample-pipeline.checks.text_checks:length_positive"],
    ExampleValue[{"__example_id__": "ex_length", "__example_value__": {"length": 5, "normalized": False}}],
]:
    """文字数を数える"""
    # TODO: implement transform logic
    return {}

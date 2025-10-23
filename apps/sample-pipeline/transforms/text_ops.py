# Auto-generated skeleton for Transform: measure_length
from spec2code.engine import Check, ExampleValue
from typing import Annotated

def measure_length(payload: Annotated[dict, Check["apps.sample-pipeline.checks.text_checks:len_gt_0"], ExampleValue[{'text': 'hello'}]], normalize: bool) -> Annotated[dict, Check["apps.sample-pipeline.checks.text_checks:length_positive"]]:
    """文字数を数える"""
    # TODO: implement transform logic
    return {}

"""生成されたPandera Schema（DataFrame検証用）

このファイルは spectool が spec.yaml から自動生成します。
FrameSpec（YAML内のdataframes定義）からPandera SchemaModelを生成します。
"""
import pandera as pa
from pandera.typing import Index, Series
import pandas as pd
from typing import Any


class TestFrameSchema(pa.DataFrameModel):
    """Test DataFrame for CLI"""

    # Column定義
    value: Series[Any] = pa.Field(nullable=False)
    category: Series[str] = pa.Field(nullable=True)

    class Config:
        strict = False
        coerce = True

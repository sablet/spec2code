"""生成されたPandera Schema（DataFrame検証用）

このファイルは spectool が spec.yaml から自動生成します。
FrameSpec（YAML内のdataframes定義）からPandera SchemaModelを生成します。
"""
import pandera as pa
from pandera.typing import Index, Series
import pandas as pd
from typing import Any


class SampleFrameSchema(pa.DataFrameModel):
    """Simple DataFrame with basic columns"""

    # Index定義
    idx: Index[int] = pa.Field()

    # Column定義
    value: Series[float] = pa.Field(nullable=False)
    label: Series[str] = pa.Field(nullable=False)

    class Config:
        strict = False
        coerce = True

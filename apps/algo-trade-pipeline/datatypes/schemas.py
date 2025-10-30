"""生成されたPandera Schema（DataFrame検証用）

このファイルは spectool が spec.yaml から自動生成します。
FrameSpec（YAML内のdataframes定義）からPandera SchemaModelを生成します。
"""

import pandera as pa
from pandera.typing import Index, Series
import pandas as pd
from typing import Any


class OHLCVFrameSchema(pa.DataFrameModel):
    """OHLCV DataFrame where each row conforms to OHLCVRow structure"""

    # Index定義
    timestamp: Index[pd.DatetimeTZDtype] = pa.Field()  # Timestamp index

    # Column定義
    open: Series[float] = pa.Field(nullable=False)  # Open price
    high: Series[float] = pa.Field(nullable=False)  # High price
    low: Series[float] = pa.Field(nullable=False, ge=0)  # Low price
    close: Series[float] = pa.Field(nullable=False)  # Close price
    volume: Series[int] = pa.Field(nullable=True)  # Trading volume

    class Config:
        strict = False
        coerce = True

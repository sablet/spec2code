"""
生成されたPandera Schema（DataFrame検証用）

このファイルは spectool が spec.yaml から自動生成します。
FrameSpec（YAML内のdataframes定義）からPandera SchemaModelを生成します。
"""

import pandera.pandas as pa
from pandera.typing import Index, Series
import pandas as pd


class OHLCVFrameSchema(pa.DataFrameModel):
    """OHLCV DataFrame schema for validation"""

    # Index定義
    timestamp: Index[pd.DatetimeTZDtype] = pa.Field()

    # Column定義
    symbol: Series[str] = pa.Field(nullable=False)
    open: Series[float] = pa.Field(nullable=False, ge=0)
    high: Series[float] = pa.Field(nullable=False, ge=0)
    low: Series[float] = pa.Field(nullable=False, ge=0)
    close: Series[float] = pa.Field(nullable=False, ge=0)
    volume: Series[float] = pa.Field(nullable=False, ge=0)

    class Config:
        strict = True
        coerce = True


class FeatureFrameSchema(pa.DataFrameModel):
    """Feature DataFrame schema for validation"""

    # Index定義
    timestamp: Index[pd.DatetimeTZDtype] = pa.Field()

    # Column定義
    symbol: Series[str] = pa.Field(nullable=False)
    sma_20: Series[float] = pa.Field(nullable=True)
    rsi_14: Series[float] = pa.Field(nullable=True, ge=0, le=100)

    class Config:
        strict = True
        coerce = True

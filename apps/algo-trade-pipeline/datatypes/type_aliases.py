# Auto-generated Type Alias definitions with DataFrame schemas
from __future__ import annotations

from pandera.typing import Index, Series
from typing import Annotated
from typing import TypeAlias
import pandas as pd
import pandera as pa

# ==================== DataFrame Schemas ====================

# ===== OHLCVFrame: DataFrame Schema =====
# OHLCV DataFrame where each row conforms to OHLCVRow structure
class _OHLCVFrameSchemaModel(pa.SchemaModel):
    """OHLCV DataFrame where each row conforms to OHLCVRow structure"""

    timestamp: Index[pa.DateTime] = pa.Field(nullable=False)
    open: Series[float] = pa.Field(nullable=False)  # Open price
    high: Series[float] = pa.Field(nullable=False)  # High price
    low: Series[float] = pa.Field(nullable=False)  # Low price
    close: Series[float] = pa.Field(nullable=False)  # Close price
    volume: Series[int | None] = pa.Field(nullable=True)  # Trading volume

    @pa.check("low")
    def _check_low_ge(cls, s: pd.Series) -> pd.Series:
        return s.ge(0)  # Low price must be non-negative

    class Config:
        coerce = True
        ordered = False
        strict = False


OHLCVFrameSchema = _OHLCVFrameSchemaModel.to_schema()


def validate_ohlcv_frame(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV DataFrame where each row conforms to OHLCVRow structure - Runtime validation"""
    return OHLCVFrameSchema.validate(df)


# ==================== Type Aliases ====================

# Multi-asset OHLCV DataFrame with MultiIndex structure (symbol, column)
MultiAssetOHLCVFrame: TypeAlias = pd.DataFrame

# OHLCV DataFrame where each row conforms to OHLCVRow structure
OHLCVFrame: TypeAlias = Annotated[pd.DataFrame, validate_ohlcv_frame]

# Feature DataFrame (flattened from MultiIndex)
FeatureFrame: TypeAlias = pd.DataFrame

# Target variable DataFrame (single column)
TargetFrame: TypeAlias = pd.DataFrame

# Aligned feature and target DataFrames (cleaned, index-matched)
AlignedFeatureTarget: TypeAlias = tuple[FeatureFrame, TargetFrame]

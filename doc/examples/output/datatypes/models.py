"""
生成されたPython型定義（YAMLから自動生成）

このファイルは spectool が spec.yaml から自動生成します。
YAMLのdatatypesセクションからPydantic/Enum/TypeAliasを生成します。
"""

from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


# === Pydanticモデル（YAML datatypes から生成） ===

class MarketDataConfig(BaseModel):
    """Market data ingestion configuration"""
    symbols: list[str] = Field(..., description="List of symbols to fetch")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    provider: str = Field(default="yahoo", description="Data provider")


class OHLCVRowModel(BaseModel):
    """Row model for OHLCV DataFrame"""
    timestamp: datetime
    symbol: str
    open: float = Field(..., ge=0)
    high: float = Field(..., ge=0)
    low: float = Field(..., ge=0)
    close: float = Field(..., ge=0)
    volume: float = Field(..., ge=0)


class FeatureRowModel(BaseModel):
    """Row model for Feature DataFrame"""
    timestamp: datetime
    symbol: str
    sma_20: float | None = None
    rsi_14: float | None = Field(None, ge=0, le=100)


# === Enum定義（YAML datatypes から生成） ===

class AssetClass(str, Enum):
    """Asset class types"""
    EQUITY = "EQUITY"
    CRYPTO = "CRYPTO"
    FOREX = "FOREX"

# Auto-generated Pydantic models
from __future__ import annotations
from .enums import CVMethod
from .enums import PositionSignal
from pydantic import BaseModel
from typing import Any
import datetime
import pandas as pd


class MarketDataIngestionConfig(BaseModel):
    """Configuration for market data ingestion (symbols, date range, provider)"""

    model_config = {"arbitrary_types_allowed": True}
    symbols: list[str]
    start_date: str
    end_date: str
    provider: str


class ProviderBatchCollection(BaseModel):
    """Collection of raw data batches from multiple providers"""

    model_config = {"arbitrary_types_allowed": True}
    batches: list[dict]


class NormalizedOHLCVBundle(BaseModel):
    """Normalized OHLCV data bundle from multiple providers"""

    model_config = {"arbitrary_types_allowed": True}
    data: dict


class MarketDataSnapshotMeta(BaseModel):
    """Metadata for persisted market data snapshot"""

    model_config = {"arbitrary_types_allowed": True}
    snapshot_id: str
    timestamp: str
    symbols: list[str]


class OHLCVRow(BaseModel):
    """Single OHLCV row data structure for validation"""

    model_config = {"arbitrary_types_allowed": True}
    timestamp: datetime.datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = None


class OHLCVFrame(BaseModel):
    """OHLCV DataFrame where each row conforms to OHLCVRow structure"""

    model_config = {"arbitrary_types_allowed": True}
    pass


class SimpleCVConfig(BaseModel):
    """Cross-validation configuration (method, splits, test_size, gap)"""

    model_config = {"arbitrary_types_allowed": True}
    method: CVMethod
    n_splits: int
    test_size: float = None
    gap: int = 0


class CVResult(BaseModel):
    """Cross-validation training result (models, metrics, OOS predictions)"""

    model_config = {"arbitrary_types_allowed": True}
    fold_results: list[Any]
    oos_predictions: pd.DataFrame = None


class PredictionData(BaseModel):
    """Single prediction data point (timestamp, symbol, prediction, actual)"""

    model_config = {"arbitrary_types_allowed": True}
    timestamp: str
    symbol: str
    prediction: float
    actual_return: float = None


class RankedPredictionData(BaseModel):
    """Prediction data with ranking percentile"""

    model_config = {"arbitrary_types_allowed": True}
    timestamp: str
    symbol: str
    prediction: float
    actual_return: float = None
    prediction_rank_pct: float


class SelectedCurrencyData(BaseModel):
    """Selected currency with position signal (BUY/SELL/HOLD)"""

    model_config = {"arbitrary_types_allowed": True}
    timestamp: str
    symbol: str
    prediction: float
    signal: PositionSignal


class TradingCostConfig(BaseModel):
    """Trading cost configuration (swap rates, spreads)"""

    model_config = {"arbitrary_types_allowed": True}
    swap_rates: dict[str, float]
    spread_costs: dict[str, float]


class SelectedCurrencyDataWithCosts(BaseModel):
    """Selected currency data with adjusted returns (swap & spread)"""

    model_config = {"arbitrary_types_allowed": True}
    timestamp: str
    symbol: str
    prediction: float
    signal: PositionSignal
    adjusted_return: float


class SimulationResult(BaseModel):
    """Portfolio simulation result (returns, positions, equity curve)"""

    model_config = {"arbitrary_types_allowed": True}
    portfolio_returns: list[float]
    equity_curve: pd.Series = None


class PerformanceMetrics(BaseModel):
    """Performance metrics (annual return, Sharpe, max drawdown, etc.)"""

    model_config = {"arbitrary_types_allowed": True}
    annual_return: float
    annual_volatility: float = None
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float = None

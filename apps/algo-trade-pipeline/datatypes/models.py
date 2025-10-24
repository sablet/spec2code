# Auto-generated Pydantic models
from __future__ import annotations
from .enums import CVMethod
from .enums import PositionSignal
from pydantic import BaseModel
from typing import Any
import pandas as pd


class MarketDataIngestionConfig(BaseModel):
    """Configuration for market data ingestion (symbols, date range, provider)"""

    symbols: list[str]
    start_date: str
    end_date: str
    provider: str


class MarketDataSnapshotMeta(BaseModel):
    """Metadata for persisted market data snapshot"""

    snapshot_id: str
    timestamp: str
    symbols: list[str]


class SimpleCVConfig(BaseModel):
    """Cross-validation configuration (method, splits, test_size, gap)"""

    method: CVMethod
    n_splits: int
    test_size: float = None
    gap: int = 0


class CVResult(BaseModel):
    """Cross-validation training result (models, metrics, OOS predictions)"""

    fold_results: list[Any]
    oos_predictions: pd.DataFrame = None


class PredictionData(BaseModel):
    """Single prediction data point (timestamp, symbol, prediction, actual)"""

    timestamp: str
    symbol: str
    prediction: float
    actual_return: float = None


class RankedPredictionData(BaseModel):
    """Prediction data with ranking percentile"""

    timestamp: str
    symbol: str
    prediction: float
    actual_return: float = None
    prediction_rank_pct: float


class SelectedCurrencyData(BaseModel):
    """Selected currency with position signal (BUY/SELL/HOLD)"""

    timestamp: str
    symbol: str
    prediction: float
    signal: PositionSignal


class TradingCostConfig(BaseModel):
    """Trading cost configuration (swap rates, spreads)"""

    swap_rates: dict[str, float]
    spread_costs: dict[str, float]


class SelectedCurrencyDataWithCosts(BaseModel):
    """Selected currency data with adjusted returns (swap & spread)"""

    timestamp: str
    symbol: str
    prediction: float
    signal: PositionSignal
    adjusted_return: float


class SimulationResult(BaseModel):
    """Portfolio simulation result (returns, positions, equity curve)"""

    portfolio_returns: list[float]
    equity_curve: pd.Series = None


class PerformanceMetrics(BaseModel):
    """Performance metrics (annual return, Sharpe, max drawdown, etc.)"""

    annual_return: float
    annual_volatility: float = None
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float = None

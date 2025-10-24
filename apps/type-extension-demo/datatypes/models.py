# Auto-generated Pydantic models
from __future__ import annotations
from pydantic import BaseModel


class CVConfig(BaseModel):
    """Cross-validation configuration"""

    n_splits: int = 5
    test_size: float = None
    gap: int = 0


class PerformanceMetrics(BaseModel):
    """Trading performance metrics"""

    annual_return: float
    sharpe_ratio: float
    max_drawdown: float

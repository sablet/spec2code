# Auto-generated Enum definitions
from __future__ import annotations
from enum import Enum


class CVMethod(Enum):
    """Cross-validation method types"""

    TIME_SERIES = "TIME_SERIES"
    EXPANDING_WINDOW = "EXPANDING_WINDOW"
    SLIDING_WINDOW = "SLIDING_WINDOW"


class PositionSignal(Enum):
    """Trading position signal"""

    BUY = 1
    SELL = -1
    HOLD = 0

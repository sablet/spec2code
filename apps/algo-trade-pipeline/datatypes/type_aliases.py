# Auto-generated Type Alias definitions
from __future__ import annotations

from typing import TypeAlias
import pandas as pd

# Multi-asset OHLCV DataFrame with MultiIndex structure (symbol, column)
MultiAssetOHLCVFrame: TypeAlias = pd.DataFrame

# Standard OHLCV DataFrame (open, high, low, close, volume)
OHLCVFrame: TypeAlias = pd.DataFrame

# Feature DataFrame (flattened from MultiIndex)
FeatureFrame: TypeAlias = pd.DataFrame

# Target variable DataFrame (single column)
TargetFrame: TypeAlias = pd.DataFrame

# Aligned feature and target DataFrames (cleaned, index-matched)
AlignedFeatureTarget: TypeAlias = tuple[pd.DataFrame, pd.DataFrame]

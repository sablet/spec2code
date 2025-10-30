"""
生成されたTypeAlias（AnnotatedメタデータでExampleSpec/CheckedSpecを付与）

このファイルは spectool が spec.yaml から自動生成します。
新アーキテクチャでは、全ての型にAnnotatedメタ型でメタデータを付与します。
"""

from typing_extensions import Annotated, TypeAlias
import pandas as pd
from spectool.core.base.meta_types import (
    PydanticRowRef,
    GeneratorSpec,
    CheckedSpec,
    ExampleSpec,
)

# 生成されたPython型定義からインポート
from apps.sample_pipeline.datatypes.models import (
    MarketDataConfig,
    OHLCVRowModel,
    FeatureRowModel,
    AssetClass,
)


# === Pydanticモデル型（ExampleSpec/CheckedSpecでAnnotated） ===

MarketDataConfigType: TypeAlias = Annotated[
    MarketDataConfig,
    ExampleSpec(examples=[
        {
            "symbols": ["AAPL", "GOOGL"],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "provider": "yahoo"
        }
    ]),
    CheckedSpec(functions=["apps.sample_pipeline.checks:validate_market_data_config"]),
]


# === Enum型（ExampleSpec/CheckedSpecでAnnotated） ===

AssetClassType: TypeAlias = Annotated[
    AssetClass,
    ExampleSpec(examples=["EQUITY", "CRYPTO"]),
    CheckedSpec(functions=["apps.sample_pipeline.checks:validate_asset_class"]),
]


# === DataFrame型（PydanticRowRef + GeneratorSpec + CheckedSpec） ===

OHLCVFrame: TypeAlias = Annotated[
    pd.DataFrame,
    PydanticRowRef(model=OHLCVRowModel),
    GeneratorSpec(factory="apps.sample_pipeline.generators:generate_ohlcv_frame"),
    CheckedSpec(functions=["apps.sample_pipeline.checks:check_ohlcv_valid"]),
]

FeatureFrame: TypeAlias = Annotated[
    pd.DataFrame,
    PydanticRowRef(model=FeatureRowModel),
]

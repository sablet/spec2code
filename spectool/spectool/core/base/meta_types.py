"""メタ型定義

Annotatedメタデータとして型とメタ情報を統合するためのデータクラス。
ランタイム・型チェッカー双方で活用可能な拡張可能なメタデータシステム。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class PydanticRowRef:
    """DataFrameの各行がPydanticモデルに対応することを示すメタデータ

    Usage:
        OHLCVFrame: TypeAlias = Annotated[
            pd.DataFrame,
            PydanticRowRef(model="apps.models:OHLCVRowModel"),
        ]

    Attributes:
        model: Pydanticモデルへの参照（"module.path:ClassName"形式）
    """

    model: str

    def __repr__(self) -> str:
        return f"PydanticRowRef(model={self.model!r})"


@dataclass(frozen=True)
class SchemaSpec:
    """DataFrame制約の詳細定義（YAML由来）

    Usage:
        MarketData: TypeAlias = Annotated[
            pd.DataFrame,
            SchemaSpec(
                index={"name": "timestamp", "dtype": "datetime"},
                columns=[{"name": "price", "dtype": "float"}],
            ),
        ]

    Attributes:
        index: Index定義（単一またはMultiIndex）
        columns: Column定義のリスト
        checks: DataFrameレベルチェック定義
        strict: 定義されていないカラムを許可しない
    """

    index: dict[str, Any] | list[dict[str, Any]] | None = None
    columns: list[dict[str, Any]] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    strict: bool = False

    def __repr__(self) -> str:
        return (
            f"SchemaSpec(index={self.index!r}, "
            f"columns={len(self.columns)} cols, "
            f"checks={len(self.checks)} checks, "
            f"strict={self.strict})"
        )


@dataclass(frozen=True)
class GeneratorSpec:
    """データ生成関数への参照

    Usage:
        # 単一factory形式（従来）
        OHLCVFrame: TypeAlias = Annotated[
            pd.DataFrame,
            GeneratorSpec(factory="apps.generators:generate_ohlcv_frame"),
        ]

        # 複数generators形式（新アーキテクチャ）
        OHLCVFrame: TypeAlias = Annotated[
            pd.DataFrame,
            GeneratorSpec(generators=["gen_ohlcv_1", "gen_ohlcv_2"]),
        ]

    Attributes:
        factory: 生成関数への参照（"module.path:function_name"形式）- 単一factory形式用
        generators: Generator IDのリスト - 複数generators形式用

    Note:
        factory または generators のいずれか一方を指定する必要があります
    """

    factory: str | None = None
    generators: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        if self.factory:
            return f"GeneratorSpec(factory={self.factory!r})"
        return f"GeneratorSpec(generators={self.generators!r})"


@dataclass(frozen=True)
class CheckedSpec:
    """バリデーション関数リストへの参照

    Usage:
        OHLCVFrame: TypeAlias = Annotated[
            pd.DataFrame,
            CheckedSpec(functions=["apps.checks:check_ohlcv", "apps.checks:validate_prices"]),
        ]

    Attributes:
        functions: Check関数リスト（"module.path:function_name"形式）
    """

    functions: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"CheckedSpec(functions={self.functions!r})"


@dataclass(frozen=True)
class ExampleSpec:
    """例示データ（Enum等で使用）

    Usage:
        AssetClass: TypeAlias = Annotated[
            AssetClassEnum,
            ExampleSpec(examples=["EQUITY", "CRYPTO"]),
        ]

    Attributes:
        examples: 例示データのリスト
    """

    examples: list[Any] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"ExampleSpec(examples={len(self.examples)} items)"


@dataclass(frozen=True)
class Check(Generic[T]):
    """Check関数への参照を示すマーカー型

    Usage:
        def transform(
            data: Annotated[pd.DataFrame, Check["apps.checks:validate_ohlcv"]]
        ) -> ResultType:
            ...

    Attributes:
        ref: Check関数への参照（"module.path:function_name"形式）
    """

    ref: str

    def __repr__(self) -> str:
        return f"Check[{self.ref!r}]"


@dataclass(frozen=True)
class ExampleValue(Generic[T]):
    """Example値を埋め込むマーカー型

    Usage:
        def transform(
            threshold: Annotated[float, ExampleValue[0.5]]
        ) -> ResultType:
            ...

    Attributes:
        value: 例示データの値
    """

    value: T

    def __repr__(self) -> str:
        return f"ExampleValue[{self.value!r}]"

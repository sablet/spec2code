# 新アーキテクチャ（ハイブリッドアプローチ）入出力サンプル

このディレクトリには、新アーキテクチャ完成時の具体的な入出力例が含まれています。

## 目的

- **レビュー＋完了判定**のための参考資料
- Phase完了時に、実際に生成されるべきファイルの具体例を提供
- 新旧システムの違いを明確化

## ディレクトリ構成

```
doc/examples/
├── README.md                           # このファイル
├── input/
│   └── sample_spec.yaml                # 新形式のYAML入力例
└── output/
    └── datatypes/
        ├── models.py                   # 生成されたPython型定義
        ├── type_aliases.py             # 生成されたTypeAlias（Annotatedメタ型付き）
        └── schemas.py                  # 生成されたPandera Schema
```

## 入力：新形式のYAML (`input/sample_spec.yaml`)

### ハイブリッドアプローチの特徴

**全ての型定義をYAMLで記述 + ExampleSpec/CheckedSpecでAnnotatedメタ型を自動生成**

```yaml
# Pydanticモデル定義（YAMLで定義）
datatypes:
  - id: MarketDataConfig
    pydantic_model:
      fields: [...]
    examples:                          # ← ExampleSpecに変換
      - symbols: ["AAPL", "GOOGL"]
        start_date: "2024-01-01"
        ...
    check_functions:                   # ← CheckedSpecに変換
      - "apps.sample_pipeline.checks:validate_market_data_config"

  - id: AssetClass
    enum:
      members: [...]
    examples: ["EQUITY", "CRYPTO"]     # ← ExampleSpecに変換
    check_functions: [...]             # ← CheckedSpecに変換

# DataFrame定義（メタデータ付き）
dataframes:
  - id: OHLCVFrame
    datatype_ref: "OHLCVRowModel"     # Row modelを参照
    generator_factory: "..."           # ← GeneratorSpecに変換
    check_functions: [...]             # ← CheckedSpecに変換
    index: [...]
    columns: [...]
```

### 既存システムとの違い

| 項目 | 既存システム | 新システム（ハイブリッド） |
|------|------------|--------------------------|
| **Pydanticモデル** | YAMLで定義→コード生成 | **YAMLで定義→コード生成** |
| **Enum** | YAMLで定義→コード生成 | **YAMLで定義→コード生成** |
| **DataFrame制約** | YAMLで定義 | **YAMLで定義（同様）** |
| **TypeAlias生成** | なし | **Annotatedメタ型で生成** ⭐新機能 |
| **メタデータ** | examples/checksは別セクション | **型定義にインライン** ⭐新機能 |

## 出力ファイル

### 1. Python型定義 (`output/datatypes/models.py`)

**YAMLから自動生成されたPydantic/Enum定義**

```python
# YAMLのdatatypesセクションから生成
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
    # ...

class AssetClass(str, Enum):
    """Asset class types"""
    EQUITY = "EQUITY"
    CRYPTO = "CRYPTO"
    FOREX = "FOREX"
```

**生成方法**:
```bash
spectool gen input/sample_spec.yaml
# → output/datatypes/models.py が生成される
```

### 2. TypeAlias定義 (`output/datatypes/type_aliases.py`)

**Annotatedメタ型でExampleSpec/CheckedSpecを付与**

```python
from spectool.core.base.meta_types import ExampleSpec, CheckedSpec

# Pydanticモデル型
MarketDataConfigType: TypeAlias = Annotated[
    MarketDataConfig,
    ExampleSpec(examples=[{"symbols": ["AAPL", "GOOGL"], ...}]),
    CheckedSpec(functions=["apps.sample_pipeline.checks:validate_market_data_config"]),
]

# Enum型
AssetClassType: TypeAlias = Annotated[
    AssetClass,
    ExampleSpec(examples=["EQUITY", "CRYPTO"]),
    CheckedSpec(functions=["apps.sample_pipeline.checks:validate_asset_class"]),
]

# DataFrame型
OHLCVFrame: TypeAlias = Annotated[
    pd.DataFrame,
    PydanticRowRef(model=OHLCVRowModel),
    GeneratorSpec(factory="apps.sample_pipeline.generators:generate_ohlcv_frame"),
    CheckedSpec(functions=["apps.sample_pipeline.checks:check_ohlcv_valid"]),
]
```

**メタ型の役割**:
- `ExampleSpec`: 例示データ（テスト・ドキュメント用）
- `CheckedSpec`: バリデーション関数リスト
- `PydanticRowRef`: DataFrame各行がPydanticモデルに対応
- `GeneratorSpec`: データ生成関数の参照

**生成方法**:
```bash
spectool gen input/sample_spec.yaml
# → output/datatypes/type_aliases.py も同時に生成される（⭐新機能）
```

### 3. Pandera Schema (`output/datatypes/schemas.py`)

**DataFrame検証用のSchemaModel**

```python
class OHLCVFrameSchema(pa.DataFrameModel):
    timestamp: Index[pd.DatetimeTZDtype] = pa.Field()
    symbol: Series[str] = pa.Field(nullable=False)
    open: Series[float] = pa.Field(nullable=False, ge=0)
    # ...
```

**生成方法**:
```bash
spectool gen input/sample_spec.yaml
# → output/datatypes/schemas.py も同時に生成される（既存同様）
```

## Phase完了判定での使用方法

### Phase 5完了時（TypeAlias生成）

```bash
# 1. サンプルspecでコード生成
spectool gen doc/examples/input/sample_spec.yaml

# 2. 生成結果と期待出力を比較
diff apps/sample-pipeline/datatypes/type_aliases.py doc/examples/output/datatypes/type_aliases.py

# 3. 構文チェック
python -m py_compile apps/sample-pipeline/datatypes/type_aliases.py
```

### Phase 6完了時（Pandera Schema生成）

```bash
# 1. サンプルspecでコード生成（genコマンドで全て生成）
spectool gen doc/examples/input/sample_spec.yaml

# 2. 生成Schemaで検証動作確認
python -c "
from apps.sample_pipeline.datatypes.schemas import OHLCVFrameSchema
import pandas as pd
df = pd.DataFrame({
    'timestamp': pd.to_datetime(['2024-01-01']),
    'symbol': ['AAPL'],
    'open': [150.0],
    'high': [155.0],
    'low': [149.0],
    'close': [154.0],
    'volume': [1000000.0]
}).set_index('timestamp')
validated = OHLCVFrameSchema.validate(df)
print('✅ Validation OK')
"
```

### Phase 8完了時（統合テスト）

```bash
# 1. CLIで一連の操作を実行（既存のコマンド）
spectool validate doc/examples/input/sample_spec.yaml
spectool gen doc/examples/input/sample_spec.yaml
spectool validate-integrity doc/examples/input/sample_spec.yaml

# 2. 生成ファイルがすべて動作することを確認
python -c "
from apps.sample_pipeline.datatypes.type_aliases import MarketDataConfigType, OHLCVFrame, FeatureFrame
from apps.sample_pipeline.datatypes.schemas import OHLCVFrameSchema, FeatureFrameSchema
print('✅ All imports OK')
"
```

## 生成フロー全体像

```
sample_spec.yaml (YAML定義)
    │
    └─→ spectool gen (1コマンドで全て生成)
            │
            ├─→ models.py (Pydantic/Enum生成) ← 既存同様
            │
            ├─→ type_aliases.py (Annotatedメタ型生成) ← ⭐新機能
            │      ├─ MarketDataConfigType (ExampleSpec + CheckedSpec)
            │      ├─ AssetClassType (ExampleSpec + CheckedSpec)
            │      └─ OHLCVFrame (PydanticRowRef + GeneratorSpec + CheckedSpec)
            │
            ├─→ schemas.py (Pandera Schema生成) ← 既存同様
            │
            ├─→ checks/ (check skeleton生成) ← 既存同様
            │
            └─→ transforms/ (transform skeleton生成) ← 既存同様
```

## 新旧対応表

| ファイル | 既存システム | 新システム（ハイブリッド） |
|---------|------------|--------------------------|
| **型定義** | `models.py` (YAMLから自動生成) | `models.py` (YAMLから自動生成) ✅同様 |
| **TypeAlias** | なし | `type_aliases.py` (Annotatedメタ付き) ⭐新機能 |
| **Schema** | `schemas.py` (Pandera) | `schemas.py` (Pandera) ✅同様 |
| **Spec構造** | datatypes + examples + checks (別セクション) | datatypes (examples/checks内包) ⭐改善 |

## まとめ

このサンプルは、以下を明確にします：

1. **入力YAML**: 全ての型定義をYAMLで記述（既存と同様）
2. **Python型定義**: YAMLから自動生成（既存と同様）
3. **TypeAlias生成**: **ExampleSpec/CheckedSpecでAnnotated型を生成** ⭐新機能
4. **Pandera Schema**: DataFrame検証用のSchemaModel（既存と同様）

新アーキテクチャでは、**YAML定義を維持しつつ、Annotatedメタ型で型とメタデータを統合**することで、ランタイム・型チェッカー双方での活用が可能になります。

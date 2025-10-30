型主導のSpec/Code一貫化 設計ドキュメント（ハイブリッドアプローチ）

## 目的

**単一の真実（Single Source of Truth）** として型定義を中心に据え、以下を実現：

1. **データ型定義**: Pythonの型システムを活用（Pydantic/Enum/Generic）
2. **DataFrame制約**: YAMLで表現不可能な部分（MultiIndex、列レベルチェック）を定義
3. **パイプライン定義**: Transform/DAG Stageを宣言的に管理
4. **一貫性保証**: spec validation、gen code、valid code、convert specの4系統を常に同期

## 設計原則

### データ型の定義戦略

```
┌─────────────────────────────────────────────────┐
│ 型定義（Python）: 型安全性が重要                │
│ - Pydanticモデル (BaseModel)                    │
│ - Enum (標準Enum)                               │
│ - TypeAlias (list/dict/tuple)                   │
│ → IDEサポート、型チェッカー利用可能            │
└─────────────────────────────────────────────────┘
                    ↓ 参照
┌─────────────────────────────────────────────────┐
│ DataFrame制約（YAML）: 表現不可能な部分         │
│ - MultiIndex定義                                │
│ - 列レベルのチェック (ge, le, isin...)         │
│ - Index制約 (unique, monotonic, tz_aware)       │
│ - PydanticRowModelとの紐付け                    │
└─────────────────────────────────────────────────┘
                    ↓ 使用
┌─────────────────────────────────────────────────┐
│ パイプライン定義（YAML）: 実装とは分離         │
│ - Transform定義（impl参照、型参照）             │
│ - DAG Stage定義（入出力型、選択モード）         │
│ - Check/Example/Generator紐付け                 │
└─────────────────────────────────────────────────┘
```

**判断基準**:
- Pydantic/Enumで表現可能 → Pythonコードで定義
- DataFrame固有の制約 → YAMLで定義
- 実装から独立したフロー → YAMLで定義

⸻

## 全体アーキテクチャ

```
        +---------------------+
        |   User Spec (YAML)  |
        | - DataFrame制約      |
        | - Transform定義      |
        | - DAG Stage定義      |
        +----------+----------+
                   |
                   v
           Loader / Normalizer
         (Python型参照・解決)
                   |
                   v
            **Normalized IR**
                   |
       +-----------+------------+-----------+---------------+
       |                        |           |               |
       v                        v           v               v
  spec validation        gen code from   valid code     convert spec
  (IRに対する検証)          spec (型/補助)  from spec       (OpenAPI等)
                                          (Pandera/Pydantic)
```

- **Python型定義**: 型安全性を最大化（Pydantic/Enum/TypeAlias）
- **YAML Spec**: DataFrame制約とパイプライン定義のみ
- **IR（中間表現）**: 唯一のソース、各処理はIR→成果物の純関数
- **Loader/Normalizer**: Python型参照を解決し、IRに変換

⸻

## パッケージ構成と依存規約

```
spectool/
  core/
    base/           # ★データ定義だけ（最下層）
      ir.py         # IR（中間表現）- DataFrame中心
      meta_types.py # メタ型定義（SchemaSpec等）
    engine/         # ★Spec→IR の実装（唯一の賢い層）
      loader.py     # YAML読み込み + Python型参照解決
      normalizer.py # メタのRegistry、優先度マージ(finalize)
      validate.py   # IR検証（意味論）
  backends/         # IR→成果物（純関数）
    py_code.py        # 型aliases/Annotated/アクセサ等
    py_validators.py  # Pandera/Pydantic 検証コード
    convert_openapi.py
    convert_md.py
  cli.py            # 入口（load→normalize→validate→backend呼び）
```

### Import Linter ルール

```ini
[importlinter]
root_package = spectool

[contract:layers_architecture]
type = layers
layers =
    spectool.core.base
    spectool.core.engine
    spectool.backends
    spectool.cli

[contract:forbid_backends_to_engine]
type = forbidden
source_modules = spectool.backends
forbidden_modules =
    spectool.core.engine.loader
    spectool.core.engine.normalizer
    spectool.core.engine.validate

[contract:independence_backends]
type = independence
modules =
    spectool.backends.py_code
    spectool.backends.py_validators
    spectool.backends.convert_openapi
```

⸻

## IR（中間表現）設計

### 設計思想

**DataFrame制約のみをIRで管理し、他の型はPythonコード参照で解決**

### 型定義（抜粋）

```python
# spectool/core/base/ir.py
from dataclasses import dataclass, field
from typing import Optional, Literal

DType = Literal["float64","float32","int64","int32","string","bool","datetime64[ns]","datetime64[ns, UTC]"]

@dataclass
class IndexRule:
    name: str
    dtype: DType
    unique: bool = False
    monotonic: bool = False
    tz_aware: bool = False

@dataclass
class ColumnRule:
    name: str
    dtype_final: Optional[DType] = None
    nullable_final: Optional[bool] = None
    checks: list[dict] = field(default_factory=list)  # ge, le, isin等
    sources: list[str] = field(default_factory=list)  # [\"pydantic\",\"schema\",...]

@dataclass
class MultiIndexLevel:
    name: str
    dtype: DType
    unique: bool = False

@dataclass
class FrameSpec:
    id: str                      # e.g. \"OHLCVFrame\"
    is_dataframe: bool           # True
    index: Optional[list[IndexRule]] = None
    multi_index: Optional[list[MultiIndexLevel]] = None
    columns: list[ColumnRule]
    checks: list[dict] = field(default_factory=list)  # DFレベルのrelation等
    row_model: Optional[str] = None   # \"pkg.mod:OHLCVRowModel\" (Python参照)
    generator_refs: list[str] = field(default_factory=list)
    check_refs: list[str] = field(default_factory=list)

@dataclass
class TransformSpec:
    id: str
    impl: str                    # \"pkg.mod:function_name\"
    file_path: str
    parameters: list[dict]       # {name, type_ref, optional, default}
    return_type_ref: str
    description: str

@dataclass
class DAGStageSpec:
    stage_id: str
    selection_mode: Literal["single", "exclusive", "multiple"]
    input_type: str              # Python型参照 or DataFrame ID
    output_type: str
    max_select: Optional[int] = None
    candidates: list[str] = field(default_factory=list)  # transform_ids
    collect_output: bool = False
    description: str

@dataclass
class CheckSpec:
    id: str
    impl: str
    file_path: str
    description: str

@dataclass
class ExampleSpec:
    id: str
    input: dict
    expected: dict
    description: str

@dataclass
class GeneratorSpec:
    id: str
    impl: str
    file_path: str
    parameters: list[dict] = field(default_factory=list)
    description: str

@dataclass
class SpecIR:
    frames: list[FrameSpec]
    transforms: list[TransformSpec]
    dag_stages: list[DAGStageSpec]
    checks: list[CheckSpec]
    examples: list[ExampleSpec]
    generators: list[GeneratorSpec]
    version: str = "1"
```

⸻

## メタ（Annotated にぶら下げる拡張）

### メタ型（例）

```python
# spectool/core/base/meta_types.py
from dataclasses import dataclass

@dataclass
class SchemaSpec:
    """DataFrame制約の定義（Pandas固有）"""
    index: Optional[list[dict]]       # {name,dtype,unique,...}
    multi_index: Optional[list[dict]] # MultiIndex構造
    columns: list[dict]               # {name,dtype?,nullable?,checks?}
    checks: list[dict]                # relation/range など

@dataclass
class PydanticRowRef:
    """PydanticモデルのPython型参照"""
    model_path: str           # \"pkg.mod:OHLCVRowModel\"

@dataclass
class GeneratorRef:
    """Generator関数のPython型参照"""
    factory: str              # \"pkg.mod:generate_ohlcv_frame\"

@dataclass
class CheckRef:
    """Check関数のPython型参照"""
    functions: list[str]      # [\"pkg.mod:check_ohlcv\", ...]
```

### ハンドラRegistry（拡張に耐えるプラグイン機構）

```python
# spectool/core/engine/normalizer.py （抜粋）
_HANDLER_REG: dict[type, object] = {}

def register_meta_handler(meta_type: type):
    def _wrap(handler):
        _HANDLER_REG[meta_type] = handler
        return handler
    return _wrap

@register_meta_handler(SchemaSpec)
class SchemaHandler:
    @staticmethod
    def contribute_to_ir(ir_ctx: dict, meta: SchemaSpec) -> None:
        # IR構築に寄与
        for col_def in meta.columns:
            col_name = col_def["name"]
            ir_ctx["columns"].setdefault(col_name, {})
            ir_ctx["columns"][col_name]["schema_dtype"] = col_def.get("dtype")
            ir_ctx["columns"][col_name]["schema_nullable"] = col_def.get("nullable")
            ir_ctx["columns"][col_name]["checks"] = col_def.get("checks", [])
            ir_ctx["columns"][col_name]["sources"].append("schema")

@register_meta_handler(PydanticRowRef)
class PydanticRowHandler:
    @staticmethod
    def contribute_to_ir(ir_ctx: dict, meta: PydanticRowRef) -> None:
        # PydanticモデルからDataFrame列定義を推論
        model_path = meta.model_path
        # importlib経由でモデルをロードし、fieldsを抽出
        # 各fieldに対してcolumnを登録
        ...

def apply_meta(ir_ctx: dict, metas: list[object]) -> dict:
    for m in metas:
        h = _HANDLER_REG.get(type(m))
        if h and hasattr(h, "contribute_to_ir"):
            h.contribute_to_ir(ir_ctx, m)
    return ir_ctx

def finalize_ir(ir_ctx: dict) -> dict:
    # 列ごとに最終 dtype/nullable を決定（優先度: Pydantic > Schema）
    for e in ir_ctx.get("columns", {}).values():
        e["dtype_final"] = e.get("pydantic_type") or e.get("schema_dtype")
        if "nullable_final" not in e:
            e["nullable_final"] = e.get("pydantic_nullable", e.get("schema_nullable"))
    return ir_ctx
```

⸻

## 型定義の実例

### Python型定義（apps/プロジェクト名/datatypes/）

```python
# apps/algo-trade-pipeline/datatypes/models.py
from pydantic import BaseModel
from enum import Enum
from typing import TypeAlias
from datetime import datetime

# Pydanticモデル
class OHLCVRowModel(BaseModel):
    """単一行のOHLCVデータ構造"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None

class MarketDataIngestionConfig(BaseModel):
    """市場データ取得設定"""
    symbols: list[str]
    start_date: str
    end_date: str
    provider: str

class SimpleCVConfig(BaseModel):
    """クロスバリデーション設定"""
    method: "CVMethod"
    n_splits: int
    test_size: float | None = None
    gap: int = 0

# Enum
class CVMethod(Enum):
    TIME_SERIES = "TIME_SERIES"
    EXPANDING_WINDOW = "EXPANDING_WINDOW"
    SLIDING_WINDOW = "SLIDING_WINDOW"

class PositionSignal(Enum):
    BUY = 1
    SELL = -1
    HOLD = 0

# Generic TypeAlias
PredictionDataList: TypeAlias = list["PredictionData"]
SimpleLGBMParams: TypeAlias = dict[str, Any]

# Tuple TypeAlias
AlignedFeatureTarget: TypeAlias = tuple[pd.DataFrame, pd.DataFrame]
```

### DataFrame制約（YAML Spec）

```yaml
# specs/algo-trade-pipeline.yaml

version: "1"
meta:
  name: "algo-trade-pipeline"

# DataFrameのみYAMLで定義
dataframes:
  - id: OHLCVFrame
    description: "OHLCV DataFrame where each row conforms to OHLCVRowModel"
    row_model: "apps.algo-trade-pipeline.datatypes.models:OHLCVRowModel"
    check_ids: [check_ohlcv]
    generator_ids: [gen_ohlcv_frame]
    index:
      - name: timestamp
        dtype: datetime
        unique: false
        monotonic: false
    columns:
      - name: open
        dtype: float
        nullable: false
      - name: high
        dtype: float
        nullable: false
      - name: low
        dtype: float
        nullable: false
        checks:
          - type: ge
            value: 0
            description: "Low price must be non-negative"
      - name: close
        dtype: float
        nullable: false
      - name: volume
        dtype: int
        nullable: true

  - id: MultiAssetOHLCVFrame
    description: "Multi-asset OHLCV DataFrame with MultiIndex"
    check_ids: [check_multiasset_frame]
    generator_ids: [gen_multiasset_frame]
    multi_index:
      levels:
        - name: symbol
          dtype: string
        - name: timestamp
          dtype: datetime
    columns:
      - name: open
        dtype: float
        nullable: false
      - name: high
        dtype: float
        nullable: false
      - name: low
        dtype: float
        nullable: false
      - name: close
        dtype: float
        nullable: false
      - name: volume
        dtype: int
        nullable: true
```

### パイプライン定義（YAML Spec）

```yaml
# specs/algo-trade-pipeline.yaml (続き)

checks:
  - id: check_ohlcv
    description: "Validate OHLCV DataFrame structure"
    impl: "apps.algo-trade-pipeline.checks.feature_checks:check_ohlcv"
    file_path: "checks/feature_checks.py"

  - id: check_ingestion_config
    description: "Validate ingestion config"
    impl: "apps.algo-trade-pipeline.checks.market_data_checks:check_ingestion_config"
    file_path: "checks/market_data_checks.py"

generators:
  - id: gen_ohlcv_frame
    description: "Generate a resampled OHLCV frame"
    impl: "apps.algo-trade-pipeline.generators.feature_engineering:generate_ohlcv_frame"
    file_path: "generators/feature_engineering.py"

  - id: gen_multiasset_frame
    description: "Build a sample multi-asset OHLCV frame"
    impl: "apps.algo-trade-pipeline.generators.market_data:generate_multiasset_frame"
    file_path: "generators/market_data.py"

transforms:
  - id: fetch_yahoo_finance_ohlcv
    description: "Fetch OHLCV data from Yahoo Finance"
    impl: "apps.algo-trade-pipeline.transforms.market_data:fetch_yahoo_finance_ohlcv"
    file_path: "transforms/market_data.py"
    parameters:
      - name: config
        type: "MarketDataIngestionConfig"  # ← Python型参照
    return_type: "ProviderBatchCollection"

  - id: resample_ohlcv
    description: "Resample OHLCV to specified frequency"
    impl: "apps.algo-trade-pipeline.transforms.features:resample_ohlcv"
    file_path: "transforms/features.py"
    parameters:
      - name: df
        type: "MultiAssetOHLCVFrame"  # ← DataFrame ID参照
      - name: freq
        type: "builtins:str"
        default: "1h"
    return_type: "OHLCVFrame"

  - id: train_lightgbm_cv
    description: "Train LightGBM with cross-validation"
    impl: "apps.algo-trade-pipeline.transforms.model:train_lightgbm_cv"
    file_path: "transforms/model.py"
    parameters:
      - name: aligned_data
        type: "AlignedFeatureTarget"  # ← Python TypeAlias参照
      - name: cv_config
        type: "SimpleCVConfig"
        optional: true
      - name: lgbm_params
        type: "SimpleLGBMParams"
        optional: true
    return_type: "CVResult"

dag_stages:
  - stage_id: "data_fetch"
    description: "Fetch market data from provider"
    selection_mode: "single"
    input_type: "MarketDataIngestionConfig"  # Python型参照
    output_type: "ProviderBatchCollection"

  - stage_id: "resample"
    description: "Resample OHLCV to target frequency"
    selection_mode: "single"
    input_type: "MultiAssetOHLCVFrame"  # DataFrame ID参照
    output_type: "OHLCVFrame"

  - stage_id: "indicator_calculation"
    description: "Calculate technical indicators (select multiple)"
    selection_mode: "multiple"
    max_select: null
    input_type: "OHLCVFrame"
    output_type: "FeatureFrame"
    # Candidates auto-collected: calculate_rsi, calculate_adx, etc.

  - stage_id: "model_training"
    description: "Train LightGBM with cross-validation"
    selection_mode: "single"
    input_type: "AlignedFeatureTarget"
    output_type: "CVResult"

  - stage_id: "performance_evaluation"
    description: "Calculate performance metrics"
    selection_mode: "single"
    input_type: "SimulationResult"
    output_type: "PerformanceMetrics"
    collect_output: true
```

### 公開API（生成コード）

```python
# apps/algo-trade-pipeline/datatypes/type_aliases.py (生成)
from typing_extensions import Annotated, TypeAlias
import pandas as pd
from spectool.core.base.meta_types import SchemaSpec, PydanticRowRef, GeneratorRef, CheckRef

# DataFrameのみAnnotatedメタで拡張
OHLCVFrame: TypeAlias = Annotated[
    pd.DataFrame,
    PydanticRowRef("apps.algo-trade-pipeline.datatypes.models:OHLCVRowModel"),
    SchemaSpec(
        index=[{"name": "timestamp", "dtype": "datetime", "unique": False}],
        multi_index=None,
        columns=[
            {"name": "open", "dtype": "float", "nullable": False},
            {"name": "high", "dtype": "float", "nullable": False},
            {"name": "low", "dtype": "float", "nullable": False,
             "checks": [{"type": "ge", "value": 0}]},
            {"name": "close", "dtype": "float", "nullable": False},
            {"name": "volume", "dtype": "int", "nullable": True},
        ],
        checks=[]
    ),
    GeneratorRef("apps.algo-trade-pipeline.generators.feature_engineering:generate_ohlcv_frame"),
    CheckRef(["apps.algo-trade-pipeline.checks.feature_checks:check_ohlcv"]),
]

MultiAssetOHLCVFrame: TypeAlias = Annotated[
    pd.DataFrame,
    SchemaSpec(
        index=None,
        multi_index=[
            {"name": "symbol", "dtype": "string"},
            {"name": "timestamp", "dtype": "datetime"}
        ],
        columns=[...],
        checks=[]
    ),
    GeneratorRef("apps.algo-trade-pipeline.generators.market_data:generate_multiasset_frame"),
    CheckRef(["apps.algo-trade-pipeline.checks.market_data_checks:check_multiasset_frame"]),
]
```

**ポイント**:
- Python型（Pydantic/Enum/TypeAlias）はそのまま利用
- DataFrameのみ `Annotated` で制約を追加
- 型安全性とDataFrame固有制約の両立

⸻

## バックエンド（IR→成果物）

### 1) gen code from spec（型/補助生成）

**生成物**: DataFrame TypeAlias（Annotatedメタ付き）

```python
# spectool/backends/py_code.py
def generate_dataframe_aliases(ir: SpecIR, output_path: Path) -> None:
    """FrameSpecからAnnotated TypeAliasを生成"""
    for frame in ir.frames:
        # SchemaSpec構築
        schema_meta = SchemaSpec(
            index=frame.index,
            multi_index=frame.multi_index,
            columns=[asdict(col) for col in frame.columns],
            checks=frame.checks
        )

        # PydanticRowRef構築
        row_ref = None
        if frame.row_model:
            row_ref = PydanticRowRef(frame.row_model)

        # Annotated TypeAlias生成
        alias_code = f"""
{frame.id}: TypeAlias = Annotated[
    pd.DataFrame,
    {repr(row_ref)},
    {repr(schema_meta)},
    GeneratorRef({frame.generator_refs}),
    CheckRef({frame.check_refs}),
]
"""
        # ファイルに書き込み
        ...
```

### 2) valid code from spec（実行時検証コード）

**生成物**: Pandera SchemaModel

```python
# spectool/backends/py_validators.py
def generate_pandera_schemas(ir: SpecIR, output_path: Path) -> None:
    """FrameSpecからPandera SchemaModelを生成"""
    for frame in ir.frames:
        schema_lines = [f"class {frame.id}Schema(pa.DataFrameModel):"]

        # Index定義
        if frame.index:
            for idx in frame.index:
                schema_lines.append(f"    {idx.name}: Index[{idx.dtype}] = pa.Field(...)")

        # MultiIndex定義
        if frame.multi_index:
            schema_lines.append("    class Config:")
            schema_lines.append("        multiindex_name = [" +
                              ", ".join(f'"{lvl.name}"' for lvl in frame.multi_index) + "]")

        # Column定義
        for col in frame.columns:
            checks_str = ""
            if col.checks:
                checks_list = [f"pa.Check.{chk['type']}({chk.get('value', '')})"
                              for chk in col.checks]
                checks_str = f", checks=[{', '.join(checks_list)}]"

            schema_lines.append(
                f"    {col.name}: Series[{col.dtype_final}] = "
                f"pa.Field(nullable={col.nullable_final}{checks_str})"
            )

        # ファイルに書き込み
        ...
```

### 3) spec validation

```python
# spectool/core/engine/validate.py
def validate_ir(ir: SpecIR) -> list[str]:
    """IRの意味論チェック"""
    errors = []

    # DataFrame制約の妥当性検証
    errors.extend(_validate_dataframe_specs(ir.frames))

    # Transform定義の妥当性検証
    errors.extend(_validate_transform_specs(ir.transforms))

    # DAG Stage定義の妥当性検証
    errors.extend(_validate_dag_stage_specs(ir.dag_stages))

    # Python型参照の解決可能性チェック
    errors.extend(_validate_type_references(ir))

    return errors

def _validate_dataframe_specs(frames: list[FrameSpec]) -> list[str]:
    errors = []
    for frame in frames:
        # 重複列チェック
        col_names = [col.name for col in frame.columns]
        if len(col_names) != len(set(col_names)):
            errors.append(f"DataFrame '{frame.id}': duplicate column names")

        # dtype整合性チェック
        for col in frame.columns:
            if not col.dtype_final:
                errors.append(f"DataFrame '{frame.id}': column '{col.name}' has no dtype")

    return errors
```

### 4) convert spec（OpenAPI等）

```python
# spectool/backends/convert_openapi.py
def convert_to_openapi(ir: SpecIR) -> dict:
    """IRからOpenAPI schemaを生成"""
    components = {"schemas": {}}

    # DataFrameはarrayとして表現
    for frame in ir.frames:
        properties = {}
        required = []

        for col in frame.columns:
            properties[col.name] = {
                "type": _map_dtype_to_json_type(col.dtype_final)
            }
            if not col.nullable_final:
                required.append(col.name)

        components["schemas"][frame.id] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }

    return {"openapi": "3.0.0", "components": components}
```

⸻

## CLI（単一路線）

```bash
# DataFrame TypeAlias生成
spectool gen-code path/to/spec.yaml -o apps/project/datatypes/type_aliases.py

# Pandera Schema生成
spectool gen-validators path/to/spec.yaml -o apps/project/validators/schemas.py

# Spec検証
spectool validate path/to/spec.yaml

# OpenAPI変換
spectool convert path/to/spec.yaml --fmt openapi -o openapi.json
```

すべてのサブコマンドは `load → normalize → validate → IR` を通るため常に同期。

⸻

## テスト戦略

### 1. IRスナップショット

```python
def test_ir_snapshot():
    spec = load_spec("specs/algo-trade-pipeline.yaml")
    ir = normalize_to_ir(spec)
    snapshot = json.dumps(asdict(ir), indent=2, default=str)
    assert snapshot == expected_snapshot
```

### 2. バックエンドスナップショット

```python
def test_code_generation():
    ir = load_and_normalize("specs/sample.yaml")
    generated_code = generate_dataframe_aliases(ir, output_path)
    assert generated_code == expected_code_snapshot
```

### 3. 煙テスト（GeneratorRef）

```python
def test_generator_smoke():
    from apps.algo_trade_pipeline.generators.feature_engineering import generate_ohlcv_frame
    from apps.algo_trade_pipeline.validators.schemas import OHLCVFrameSchema

    # Generator実行
    df = generate_ohlcv_frame()

    # Pandera検証
    OHLCVFrameSchema.validate(df)  # エラーなく通過すればOK
```

### 4. 往復/契約テスト

```python
def test_roundtrip():
    # 生成されたPandera Schemaをimport
    from apps.project.validators.schemas import OHLCVFrameSchema

    # 生成されたGeneratorをimport
    from apps.project.generators.feature_engineering import generate_ohlcv_frame

    # 生成→検証の往復
    df = generate_ohlcv_frame()
    validated_df = OHLCVFrameSchema.validate(df)
    assert validated_df is not None
```

⸻

## バージョニング & マイグレーション

- `meta.version` を Spec に保持
- Normalizer で `migrate_v1_to_v2()` を実装
- 後方互換の崩壊はすべて Normalizer に集約（バックエンドは IR だけを消費）

⸻

## 実装ガイド（キーポイント）

### 優先度マージ
- Pydantic > SchemaSpec > その他（列dtype/nullable）
- `PydanticRowRef` から列定義を抽出し、`SchemaSpec` とマージ

### 未知メタは無視
- 将来の前方互換性を確保
- 新しいメタ型を追加してもエラーにならない

### 出典（sources）を列に残す
- 説明責任/デバッグ用
- "この列のdtypeはPydanticから来た"等を記録

### テンプレはロジックレス
- 条件分岐は Normalizer で解決
- バックエンドは単純なテンプレート展開のみ

### パフォーマンス
- 検証は原則「入口」で一度だけ（デコレータで適用）
- 重い Pandera はバッチ境界で実行

### エラーレポート
- Pandera/Pydantic のメッセージをSpecの項目名にひも付けて出す
- 例：`OHLCVFrame.columns.low: must be >= 0`

⸻

## 具体例

### A) PydanticRowRefのみ（SchemaSpecなし）

```python
# Python型定義
class OHLCVRowModel(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None

# YAML Spec（最小限）
dataframes:
  - id: OHLCVFrame
    row_model: "apps.algo-trade-pipeline.datatypes.models:OHLCVRowModel"
    check_ids: [check_ohlcv]
    generator_ids: [gen_ohlcv_frame]
    index:
      - name: timestamp
        dtype: datetime
```

→ PydanticRowModelから列定義を自動推論

### B) SchemaSpecで追加制約

```yaml
dataframes:
  - id: OHLCVFrame
    row_model: "apps.algo-trade-pipeline.datatypes.models:OHLCVRowModel"
    columns:
      - name: low
        checks:  # ← Pydanticでは表現困難な制約
          - type: ge
            value: 0
      - name: volume
        nullable: true  # ← Pydanticの定義を上書き
```

→ PydanticとSchemaSpecをマージ（優先度: Pydantic < SchemaSpec）

### C) MultiIndex（Pandasでしか表現不可能）

```yaml
dataframes:
  - id: MultiAssetOHLCVFrame
    multi_index:
      levels:
        - name: symbol
          dtype: string
        - name: timestamp
          dtype: datetime
    columns:
      - name: open
        dtype: float
      - name: close
        dtype: float
```

### D) GeneratorRefによる例データ生成

```python
# Generator定義（Python）
def generate_ohlcv_frame() -> pd.DataFrame:
    """最新の仕様でOHLCVFrameを生成"""
    dates = pd.date_range("2024-01-01", periods=100, freq="1h")
    return pd.DataFrame({
        "open": np.random.rand(100) * 100,
        "high": np.random.rand(100) * 100,
        "low": np.random.rand(100) * 100,
        "close": np.random.rand(100) * 100,
        "volume": np.random.randint(1000, 10000, 100),
    }, index=dates)

# YAML Spec
dataframes:
  - id: OHLCVFrame
    generator_ids: [gen_ohlcv_frame]

# CI煙テスト
def test_ohlcvframe_smoke():
    from apps.project.generators import generate_ohlcv_frame
    from apps.project.validators import OHLCVFrameSchema

    df = generate_ohlcv_frame()
    OHLCVFrameSchema.validate(df)  # 最新仕様で検証
```

⸻

## セキュリティ/安全運用

- Generator/Checked/Transform のロードは importlib で明示
- 許可パスのホワイトリストを検討
- 生成コードの出力先は 相対パス禁止 / 既存ファイル上書き時は要 `--force`

⸻

## まとめ

### 設計の核心

1. **型定義はPython**: Pydantic/Enum/TypeAliasで型安全に
2. **DataFrame制約はYAML**: 表現不可能な部分のみSpec化
3. **パイプライン定義はYAML**: 実装から独立した宣言的管理
4. **IRで一元化**: Spec→IR→各バックエンドの放射状設計

### 利点

- ✅ 型安全性: Pythonの型チェッカーが使える
- ✅ IDEサポート: 補完、型推論、リファクタリング
- ✅ 宣言的管理: DataFrame制約とパイプラインはYAMLで一元管理
- ✅ 拡張性: 新しいメタ/バックエンドはプラグインとして追加
- ✅ 一貫性: 4系統（validation/gen/valid/convert）が常に同期

この設計により、型安全性と宣言的管理の両立を実現し、長期運用に耐える型主導パイプラインを構築できます。

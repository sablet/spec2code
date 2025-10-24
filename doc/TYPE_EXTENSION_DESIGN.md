# spec2code 型システム拡張設計書

## 概要

本ドキュメントは、spec2codeの型システムを拡張し、Pythonの高度な型表現（TypeAlias, Enum, Generic, Union, Literal, Pydantic Model, pandas MultiIndex）をサポートするための設計仕様を記述する。

これにより、algo-tradeパイプラインのような複雑なデータフローを、完全に型安全かつ宣言的に記述できるようになる。

## 拡張の背景

### 現在の制約

現在のspec2codeは以下の型表現に限定されている：

- **基本型**: `builtins:str`, `builtins:int`, `pandas:DataFrame` 等
- **カスタム型**: JSON Schemaで定義した`dict`構造
- **型注釈**: `Annotated[T, Check[...], ExampleValue[...]]`

### 不足している型表現

algo-tradeパイプライン（TransformFn/doc/DAG_PIPELINE_DESIGN.md）の分析により、以下の型表現が必要と判明：

1. **TypeAlias** - `AlignedFeatureTarget = tuple[pd.DataFrame, pd.DataFrame]`
2. **Enum** - `PositionSignal(Enum)` with BUY/SELL/HOLD
3. **Generic型** - `list[PredictionData]`, `Dict[str, Any]`
4. **Union型** - `SimpleCVConfig | None`
5. **Literal型** - `Literal["equal", "weighted", "risk_parity"]`
6. **Pydantic Model** - `SimpleCVConfig`, `PerformanceMetrics`
7. **pandas MultiIndex** - `MultiAssetOHLCVFrame`

---

## 拡張仕様

### 1. TypeAlias（型エイリアス）

#### 目的
複雑な複合型に名前を付けて再利用可能にする。

#### YAML仕様

```yaml
datatypes:
  - id: AlignedFeatureTarget
    description: "Aligned features and target tuple"
    type_alias:
      type: tuple
      elements:
        - native: "pandas:DataFrame"
        - native: "pandas:DataFrame"
    # 生成コード: AlignedFeatureTarget = tuple[pd.DataFrame, pd.DataFrame]

  - id: FeatureFrame
    description: "Feature DataFrame alias"
    type_alias:
      type: simple
      target: "pandas:DataFrame"
    # 生成コード: FeatureFrame = pd.DataFrame
```

#### 生成コード例

```python
# datatypes/type_aliases.py
import pandas as pd
from typing import TypeAlias

AlignedFeatureTarget: TypeAlias = tuple[pd.DataFrame, pd.DataFrame]
FeatureFrame: TypeAlias = pd.DataFrame
TargetFrame: TypeAlias = pd.DataFrame
```

#### モデル定義

```python
class TypeAliasConfig(BaseModel):
    """TypeAlias configuration"""
    type: Literal["simple", "tuple", "dict"]
    target: str | None = None  # for simple type
    elements: list[dict[str, Any]] = Field(default_factory=list)  # for tuple
    key_type: str | None = None  # for dict
    value_type: str | None = None  # for dict
```

---

### 2. Enum型定義

#### 目的
固定値セット（特にビジネスドメインの状態）をEnumクラスとして定義する。

#### YAML仕様

```yaml
datatypes:
  - id: PositionSignal
    description: "Trading position signal"
    enum:
      base_type: int
      members:
        - name: BUY
          value: 1
          description: "Long position"
        - name: SELL
          value: -1
          description: "Short position"
        - name: HOLD
          value: 0
          description: "No position"

  - id: ConvertType
    description: "Target conversion type"
    enum:
      base_type: str
      members:
        - name: RETURN
          value: "return"
        - name: DIRECTION
          value: "direction"
        - name: LOG_RETURN
          value: "log_return"
```

#### 生成コード例

```python
# datatypes/enums.py
from enum import Enum

class PositionSignal(Enum):
    """Trading position signal"""
    BUY = 1
    SELL = -1
    HOLD = 0

class ConvertType(Enum):
    """Target conversion type"""
    RETURN = "return"
    DIRECTION = "direction"
    LOG_RETURN = "log_return"
```

#### モデル定義

```python
class EnumMember(BaseModel):
    """Enum member definition"""
    name: str
    value: int | str | float
    description: str = ""

class EnumConfig(BaseModel):
    """Enum configuration"""
    base_type: Literal["int", "str", "float"]
    members: list[EnumMember]
```

---

### 3. Generic型（list[T], Dict[K,V]）

#### 目的
リストや辞書の要素型を明示的に指定する。

#### YAML仕様

```yaml
datatypes:
  - id: PredictionDataList
    description: "List of prediction data"
    generic:
      container: list
      element_type:
        datatype_ref: PredictionData
    # 生成コード: list[PredictionData]

  - id: SimpleLGBMParams
    description: "LightGBM hyperparameters"
    generic:
      container: dict
      key_type:
        native: "builtins:str"
      value_type:
        native: "typing:Any"
    # 生成コード: Dict[str, Any]
```

#### 生成コード例（型注釈として使用）

```python
def generate_predictions(
    cv_result: CVResult,
    aligned_data: AlignedFeatureTarget,
) -> list[PredictionData]:  # ← Generic型を使用
    ...
```

#### モデル定義

```python
class GenericConfig(BaseModel):
    """Generic type configuration"""
    container: Literal["list", "dict", "set", "tuple"]
    element_type: dict[str, Any] | None = None  # for list/set
    key_type: dict[str, Any] | None = None  # for dict
    value_type: dict[str, Any] | None = None  # for dict
    elements: list[dict[str, Any]] = Field(default_factory=list)  # for tuple
```

---

### 4. Union型（T | None, T1 | T2）

#### 目的
複数の型のいずれかを許容する（特にOptional型）。

#### YAML仕様

```yaml
# Option 1: 簡易版（Optional専用）
parameters:
  - name: cv_config
    datatype_ref: SimpleCVConfig
    optional: true
    # 生成コード: cv_config: SimpleCVConfig | None

# Option 2: 完全版（複数型Union）
parameters:
  - name: config
    union:
      - datatype_ref: SimpleCVConfig
      - datatype_ref: AdvancedCVConfig
      - native: "builtins:None"
    # 生成コード: config: SimpleCVConfig | AdvancedCVConfig | None
```

#### 生成コード例

```python
def train_lightgbm_cv(
    aligned_data: AlignedFeatureTarget,
    *,
    cv_config: SimpleCVConfig | None = None,
    lgbm_params: Dict[str, Any] | None = None,
) -> CVResult:
    ...
```

#### モデル定義

```python
class Parameter(BaseModel):
    """Function parameter definition"""
    name: str
    datatype_ref: str | None = None
    native: str | None = None
    optional: bool = False  # 簡易版
    union: list[dict[str, Any]] = Field(default_factory=list)  # 完全版
```

---

### 5. Literal型

#### 目的
パラメータの取りうる値を文字列リテラルで制限する。

#### YAML仕様

```yaml
parameters:
  - name: allocation_method
    literal:
      - "equal"
      - "weighted"
      - "risk_parity"
    default: "equal"
    # 生成コード: allocation_method: Literal["equal", "weighted", "risk_parity"] = "equal"

  - name: cv_method
    literal:
      - "TIME_SERIES"
      - "EXPANDING_WINDOW"
      - "SLIDING_WINDOW"
```

#### 生成コード例

```python
from typing import Literal

def simulate_buy_scenario(
    selected_currencies: list[SelectedCurrencyDataWithCosts],
    *,
    allocation_method: Literal["equal", "weighted", "risk_parity"] = "equal",
) -> SimulationResult:
    ...
```

#### モデル定義

```python
class Parameter(BaseModel):
    """Function parameter definition"""
    name: str
    datatype_ref: str | None = None
    native: str | None = None
    literal: list[str] = Field(default_factory=list)
    default: Any = None
```

---

### 6. Pydantic Model定義

#### 目的
構造化データをPydantic BaseModelとして自動生成する。

#### YAML仕様

```yaml
datatypes:
  - id: SimpleCVConfig
    description: "Cross-validation configuration"
    pydantic_model:
      fields:
        - name: method
          type:
            literal:
              - "TIME_SERIES"
              - "EXPANDING_WINDOW"
              - "SLIDING_WINDOW"
          required: true
        - name: n_splits
          type:
            native: "builtins:int"
          default: 5
        - name: test_size
          type:
            native: "builtins:float"
          optional: true
        - name: gap
          type:
            native: "builtins:int"
          default: 0

  - id: PerformanceMetrics
    description: "Trading performance metrics"
    pydantic_model:
      fields:
        - name: annual_return
          type:
            native: "builtins:float"
        - name: annual_volatility
          type:
            native: "builtins:float"
        - name: sharpe_ratio
          type:
            native: "builtins:float"
        - name: max_drawdown
          type:
            native: "builtins:float"
        - name: calmar_ratio
          type:
            native: "builtins:float"
```

#### 生成コード例

```python
# datatypes/models.py
from pydantic import BaseModel, Field
from typing import Literal

class SimpleCVConfig(BaseModel):
    """Cross-validation configuration"""
    method: Literal["TIME_SERIES", "EXPANDING_WINDOW", "SLIDING_WINDOW"]
    n_splits: int = 5
    test_size: float | None = None
    gap: int = 0

class PerformanceMetrics(BaseModel):
    """Trading performance metrics"""
    annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float
```

#### モデル定義

```python
class PydanticField(BaseModel):
    """Pydantic model field definition"""
    name: str
    type: dict[str, Any]  # TypeConfig (recursive)
    required: bool = True
    optional: bool = False
    default: Any = None
    description: str = ""

class PydanticModelConfig(BaseModel):
    """Pydantic model configuration"""
    fields: list[PydanticField]
    base_class: str = "BaseModel"  # 将来的にカスタムベースクラスをサポート
```

---

### 7. pandas MultiIndex構造

#### 目的
MultiIndex DataFrameの構造を検証可能にする。

#### YAML仕様

```yaml
datatypes:
  - id: MultiAssetOHLCVFrame
    description: "Multi-asset OHLCV DataFrame with MultiIndex columns"
    pandas_multiindex:
      axis: 1  # 0=index, 1=columns
      levels:
        - name: symbol
          type: string
          description: "Asset symbol (e.g., USDJPY, SPY)"
        - name: indicator
          type: string
          enum:
            - "open"
            - "high"
            - "low"
            - "close"
            - "volume"
            - "rsi_14"
            - "adx_14"
          description: "OHLCV or indicator column"
      index_type: "datetime"  # DatetimeIndex
    check_ids:
      - check_multiasset_frame
```

#### 生成コード例（Check関数のみ生成）

```python
# checks/multiindex_checks.py
import pandas as pd

def check_multiasset_frame(payload: dict) -> bool:
    """Validate MultiAssetOHLCVFrame structure

    Auto-generated validation logic for MultiIndex DataFrame:
    - axis=1 (columns)
    - levels: symbol (string), indicator (string with enum)
    - index: DatetimeIndex
    """
    # TODO: implement MultiIndex validation
    # Expected structure:
    # - isinstance(df.columns, pd.MultiIndex)
    # - df.columns.names == ['symbol', 'indicator']
    # - isinstance(df.index, pd.DatetimeIndex)
    return True
```

#### モデル定義

```python
class MultiIndexLevel(BaseModel):
    """MultiIndex level definition"""
    name: str
    type: Literal["string", "int", "float", "datetime"]
    enum: list[str] = Field(default_factory=list)
    description: str = ""

class PandasMultiIndexConfig(BaseModel):
    """pandas MultiIndex configuration"""
    axis: Literal[0, 1]  # 0=index, 1=columns
    levels: list[MultiIndexLevel]
    index_type: str | None = None  # e.g., "datetime", "int"
```

---

## 実装計画

### Phase 1: モデル拡張（engine.py）

#### 1.1 DataTypeモデルの拡張

```python
class DataType(BaseModel):
    """Data structure definition"""

    model_config = {"protected_namespaces": ()}

    id: str
    description: str
    check_ids: list[str] = Field(default_factory=list)
    example_ids: list[str] = Field(default_factory=list)

    # 既存（JSON Schema）
    schema_def: dict[str, Any] | None = Field(default=None, alias="schema")

    # 新規拡張
    type_alias: TypeAliasConfig | None = None
    enum: EnumConfig | None = None
    generic: GenericConfig | None = None
    pandas_multiindex: PandasMultiIndexConfig | None = None
    pydantic_model: PydanticModelConfig | None = None

    @field_validator("schema_def", "type_alias", "enum", "generic", "pandas_multiindex", "pydantic_model")
    @classmethod
    def exactly_one_type_def(cls, v, info):
        """Exactly one type definition must be specified"""
        type_fields = ["schema_def", "type_alias", "enum", "generic", "pandas_multiindex", "pydantic_model"]
        defined = [f for f in type_fields if info.data.get(f) is not None]
        if len(defined) != 1:
            raise ValueError(f"Exactly one type definition required, got: {defined}")
        return v
```

#### 1.2 Parameterモデルの拡張

```python
class Parameter(BaseModel):
    """Function parameter definition"""

    name: str

    # 既存
    datatype_ref: str | None = None
    native: str | None = None

    # 新規拡張
    optional: bool = False
    literal: list[str] = Field(default_factory=list)
    union: list[dict[str, Any]] = Field(default_factory=list)
    default: Any = None
```

---

### Phase 2: コード生成ロジック拡張

#### 2.1 型アノテーション生成関数の拡張

```python
def _build_type_string(
    spec: Spec,
    type_config: dict[str, Any],
    app_root: Path,
) -> tuple[str, set[str]]:
    """Unified type string builder

    Handles:
    - datatype_ref
    - native
    - literal
    - union
    - generic
    - optional

    Returns:
        (type_string, import_set)
    """
    imports = set()

    # Handle literal
    if "literal" in type_config and type_config["literal"]:
        imports.add("from typing import Literal")
        values = ", ".join(f'"{v}"' for v in type_config["literal"])
        return f"Literal[{values}]", imports

    # Handle union
    if "union" in type_config and type_config["union"]:
        union_parts = []
        for union_item in type_config["union"]:
            part_str, part_imports = _build_type_string(spec, union_item, app_root)
            union_parts.append(part_str)
            imports.update(part_imports)
        return " | ".join(union_parts), imports

    # Handle datatype_ref (with generic/enum/etc lookup)
    if "datatype_ref" in type_config and type_config["datatype_ref"]:
        datatype = next((dt for dt in spec.datatypes if dt.id == type_config["datatype_ref"]), None)
        if datatype:
            if datatype.enum:
                imports.add(f"from apps.{spec.meta.name}.datatypes.enums import {datatype.id}")
                return datatype.id, imports
            elif datatype.pydantic_model:
                imports.add(f"from apps.{spec.meta.name}.datatypes.models import {datatype.id}")
                return datatype.id, imports
            elif datatype.type_alias:
                imports.add(f"from apps.{spec.meta.name}.datatypes.type_aliases import {datatype.id}")
                return datatype.id, imports
            elif datatype.generic:
                # Build generic type string
                return _build_generic_type(spec, datatype, app_root)
            else:
                # Fallback to dict
                return "dict", imports

    # Handle native
    if "native" in type_config and type_config["native"]:
        module, type_name = type_config["native"].split(":")
        if module == "builtins":
            return type_name, imports
        elif module == "pandas":
            imports.add("import pandas as pd")
            return f"pd.{type_name}", imports
        else:
            imports.add(f"import {module}")
            return f"{module}.{type_name}", imports

    # Default
    return "dict", imports
```

#### 2.2 スケルトン生成の拡張

```python
def generate_skeleton(spec: Spec, project_root: Path = Path(".")) -> None:
    """Generate skeleton code including datatypes"""

    app_root = project_root / "apps" / spec.meta.name

    # 1. Generate Enum definitions
    enum_datatypes = [dt for dt in spec.datatypes if dt.enum]
    if enum_datatypes:
        _generate_enum_file(spec, enum_datatypes, app_root)

    # 2. Generate Pydantic models
    model_datatypes = [dt for dt in spec.datatypes if dt.pydantic_model]
    if model_datatypes:
        _generate_pydantic_models(spec, model_datatypes, app_root)

    # 3. Generate TypeAliases
    alias_datatypes = [dt for dt in spec.datatypes if dt.type_alias]
    if alias_datatypes:
        _generate_type_aliases(spec, alias_datatypes, app_root)

    # 4. Generate Check functions (existing logic)
    # ...

    # 5. Generate Transform functions (existing logic with extended type annotation)
    # ...
```

---

### Phase 3: 検証ロジック拡張

```python
def validate_integrity(self, project_root: Path = Path(".")) -> dict[str, list[str]]:
    """Validate spec-implementation integrity"""

    errors: dict[str, list[str]] = {
        "check_functions": [],
        "check_locations": [],
        "transform_functions": [],
        "transform_signatures": [],
        "example_schemas": [],
        "enum_definitions": [],  # 新規
        "pydantic_models": [],   # 新規
        "type_aliases": [],      # 新規
    }

    # ... existing validation ...

    # Validate Enum definitions
    for datatype in self.spec.datatypes:
        if datatype.enum:
            module_path = f"apps.{self.spec.meta.name}.datatypes.enums"
            try:
                module = importlib.import_module(module_path)
                enum_class = getattr(module, datatype.id)
                # Validate enum members
                for member in datatype.enum.members:
                    if not hasattr(enum_class, member.name):
                        errors["enum_definitions"].append(
                            f"Enum '{datatype.id}' missing member: {member.name}"
                        )
            except (ImportError, AttributeError) as e:
                errors["enum_definitions"].append(
                    f"Enum '{datatype.id}' not found: {e}"
                )

    # Validate Pydantic models
    for datatype in self.spec.datatypes:
        if datatype.pydantic_model:
            # Similar validation logic
            ...

    return errors
```

---

## テスト計画

### Test 1: TypeAlias生成テスト

```python
def test_type_alias_generation(temp_project_dir, sample_spec_yaml):
    """Test TypeAlias generation"""
    sample_spec_yaml["datatypes"] = [
        {
            "id": "FeatureFrame",
            "description": "Feature DataFrame alias",
            "type_alias": {
                "type": "simple",
                "target": "pandas:DataFrame"
            }
        },
        {
            "id": "AlignedFeatureTarget",
            "description": "Aligned tuple",
            "type_alias": {
                "type": "tuple",
                "elements": [
                    {"native": "pandas:DataFrame"},
                    {"native": "pandas:DataFrame"}
                ]
            }
        }
    ]

    # ... generate and validate ...
```

### Test 2: Enum生成テスト

```python
def test_enum_generation(temp_project_dir, sample_spec_yaml):
    """Test Enum generation"""
    sample_spec_yaml["datatypes"] = [
        {
            "id": "PositionSignal",
            "description": "Position signal",
            "enum": {
                "base_type": "int",
                "members": [
                    {"name": "BUY", "value": 1},
                    {"name": "SELL", "value": -1},
                    {"name": "HOLD", "value": 0}
                ]
            }
        }
    ]

    # ... generate, import, and validate enum ...
```

### Test 3: Literal型パラメータテスト

```python
def test_literal_parameter(temp_project_dir, sample_spec_yaml):
    """Test Literal type parameter"""
    sample_spec_yaml["transforms"] = [
        {
            "id": "simulate",
            "description": "Simulate trading",
            "impl": "apps.test.transforms.simulation:simulate",
            "file_path": "transforms/simulation.py",
            "parameters": [
                {
                    "name": "method",
                    "literal": ["equal", "weighted", "risk_parity"],
                    "default": "equal"
                }
            ],
            "return_native": "builtins:dict"
        }
    ]

    # ... validate signature includes Literal["equal", "weighted", "risk_parity"] ...
```

### Test 4: Pydantic Model生成テスト

```python
def test_pydantic_model_generation(temp_project_dir, sample_spec_yaml):
    """Test Pydantic model generation"""
    sample_spec_yaml["datatypes"] = [
        {
            "id": "SimpleCVConfig",
            "description": "CV config",
            "pydantic_model": {
                "fields": [
                    {
                        "name": "n_splits",
                        "type": {"native": "builtins:int"},
                        "default": 5
                    },
                    {
                        "name": "test_size",
                        "type": {"native": "builtins:float"},
                        "optional": True
                    }
                ]
            }
        }
    ]

    # ... generate, import, instantiate, and validate model ...
```

### Test 5: Optional型パラメータテスト

```python
def test_optional_parameter(temp_project_dir, sample_spec_yaml):
    """Test Optional type parameter"""
    sample_spec_yaml["datatypes"].append({
        "id": "CVConfig",
        "description": "CV config",
        "pydantic_model": {"fields": [{"name": "n_splits", "type": {"native": "builtins:int"}}]}
    })

    sample_spec_yaml["transforms"] = [
        {
            "id": "train",
            "parameters": [
                {
                    "name": "cv_config",
                    "datatype_ref": "CVConfig",
                    "optional": True
                }
            ],
            "return_native": "builtins:dict"
        }
    ]

    # ... validate signature includes cv_config: CVConfig | None ...
```

---

## サンプルSpec

完全な型拡張機能を使用したサンプル仕様を`specs/type-extension-demo.yaml`として作成する。

```yaml
version: "1"
meta:
  name: "type-extension-demo"
  description: "Demonstration of all type extension features"

datatypes:
  # 1. Enum
  - id: PositionSignal
    description: "Trading position signal"
    enum:
      base_type: int
      members:
        - name: BUY
          value: 1
        - name: SELL
          value: -1
        - name: HOLD
          value: 0

  # 2. Pydantic Model
  - id: CVConfig
    description: "Cross-validation configuration"
    pydantic_model:
      fields:
        - name: n_splits
          type:
            native: "builtins:int"
          default: 5
        - name: test_size
          type:
            native: "builtins:float"
          optional: true

  # 3. TypeAlias
  - id: FeatureTarget
    description: "Feature and target tuple"
    type_alias:
      type: tuple
      elements:
        - native: "pandas:DataFrame"
        - native: "pandas:DataFrame"

  # 4. Generic (list)
  - id: SignalList
    description: "List of position signals"
    generic:
      container: list
      element_type:
        datatype_ref: PositionSignal

transforms:
  - id: generate_signals
    description: "Generate trading signals"
    impl: "apps.type-extension-demo.transforms.signals:generate_signals"
    file_path: "transforms/signals.py"
    parameters:
      - name: data
        native: "pandas:DataFrame"
      - name: method
        literal:
          - "momentum"
          - "mean_reversion"
        default: "momentum"
      - name: cv_config
        datatype_ref: CVConfig
        optional: true
    return_datatype_ref: SignalList
```

---

## 実装優先度

### Phase 1 (High Priority)
1. ✅ Pydantic Model定義
2. ✅ Generic型（list[T]）
3. ✅ Optional型（T | None）

### Phase 2 (Medium Priority)
4. ✅ Enum型
5. ✅ Literal型
6. ✅ TypeAlias

### Phase 3 (Low Priority)
7. ✅ pandas MultiIndex
8. Union型（完全版: T1 | T2 | T3）

---

## 拡張後の利点

### 1. 完全な型安全性
- mypyによる静的型チェックが可能
- IDEの補完機能が完全動作
- リファクタリング時の自動追跡

### 2. 自己文書化
- Enum/Literalにより許容値が明確
- Pydantic Modelで構造が明示的
- TypeAliasで複雑な型に意味のある名前

### 3. ランタイム検証
- Pydantic Modelによるバリデーション
- Enumによる値制約
- Generic型による要素検証

### 4. チーム開発の効率化
- 仕様YAMLから型定義が自動生成
- 実装者は型に従うだけでOK
- レビュー時の型整合性チェックが容易

---

## 参考リンク

- **設計元**: `TransformFn/doc/DAG_PIPELINE_DESIGN.md`
- **コアエンジン**: `packages/spec2code/engine.py`
- **既存仕様**: `specs/dataframe-pipeline-extended.yaml`
- **PEP 613 (TypeAlias)**: https://peps.python.org/pep-0613/
- **PEP 586 (Literal)**: https://peps.python.org/pep-0586/
- **Pydantic**: https://docs.pydantic.dev/

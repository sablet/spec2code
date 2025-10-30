# Spec2Code → 型主導アーキテクチャ 移行方針書（ハイブリッドアプローチ）

> **📁 具体的な入出力サンプルは [`doc/examples/`](examples/) を参照**
> 新アーキテクチャでの実際のYAML入力例と生成されるPythonコード例を確認できます。

## 目的

既存の `packages/spec2code/` を「型主導のSpec/Code一貫化」アーキテクチャ（ハイブリッドアプローチ）に移行する。

### ハイブリッドアプローチとは

**全ての型定義をYAML + Annotatedメタ型でメタデータを統合**

- ✅ **型安全性**: Pydantic/Enum/TypeAliasをYAMLから生成（既存同様）
- ✅ **メタデータ統合**: ExampleSpec/CheckedSpecでAnnotated型を生成（新機能）
- ✅ **関心事の分離**: 型定義 vs 制約 vs フロー vs メタデータ

## 既存システム分析

### ファイル構成（現状）

```
packages/spec2code/
├── engine.py              (3497行) - 巨大なモノリシックファイル
├── config_model.py        (269行)  - DAGStage/ExtendedSpec定義
├── config_validator.py    (338行)  - Config検証ロジック
├── config_runner.py       (123行)  - Config実行ランナー
└── card_exporter.py       (626行)  - フロントエンドカード出力
```

### engine.py の責務（問題点）

**現在のengine.pyは以下すべてを担当している**：

1. **データモデル定義** (L35-390)
   - Pydanticモデル: `Check`, `Example`, `DataType`, `Parameter`, `Transform`, `DAGEdge`, `Meta`, `Spec`

2. **Spec読み込み・正規化** (L391-555)
   - `load_spec()`: YAML読み込み
   - `_convert_dag_to_stages()`: DAG→Stage変換

3. **型解決・アノテーション構築** (L596-1019)
   - `_resolve_native_type()`, `_resolve_datatype_reference()`
   - `_build_type_string()`, `_build_type_annotation()`

4. **コード生成** (L1020-1989)
   - `_generate_check_skeletons()`, `_generate_transform_skeletons()`
   - `_generate_type_aliases()`, `_generate_enum_file()`, `_generate_pydantic_models()`
   - `_generate_dataframe_schemas()`: Pandera Schema生成

5. **検証・実行エンジン** (L1990-3497)
   - `Engine` クラス
   - `validate_integrity()`: 仕様実装の整合性検証

**問題点**：
- 単一ファイルに3500行、複数の責務が混在
- テストしにくい
- 拡張しにくい（新機能追加時に全体に影響）

### 既存specの特徴（algo-trade-pipeline.yaml）

```yaml
# 既存システムは全てをYAMLで定義
datatypes:
  - id: MarketDataIngestionConfig
    pydantic_model:           # ← YAMLでPydantic定義
      fields: [...]
  - id: CVMethod
    enum:                     # ← YAMLでEnum定義
      base_type: str
      members: [...]
  - id: OHLCVFrame
    dataframe_schema:         # ← YAMLでDataFrame Schema定義
      index: [...]
      columns: [...]
```

**既存システムの思想**: Specから全てを生成（宣言的）

## 新アーキテクチャ（目標）

### 設計思想

**ハイブリッドアプローチ：YAML定義 + Annotatedメタ型生成**

```
┌─────────────────────────────────────────────────┐
│ YAML定義: 全ての型とメタデータを宣言的に記述   │
│ - Pydanticモデル定義 + examples + check_functions│
│ - Enum定義 + examples + check_functions         │
│ - DataFrame制約 + datatype_ref + generator_factory│
│ - パイプライン定義                              │
└─────────────────────────────────────────────────┘
                    ↓ spectool gen
        ┌───────────┴───────────┬──────────────┐
        ↓                       ↓              ↓
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ models.py        │  │ type_aliases.py  │  │ schemas.py       │
│ (既存同様)       │  │ (⭐新機能)       │  │ (既存同様)       │
│                  │  │                  │  │                  │
│ class Market...  │  │ MarketData...Type│  │ class ...Schema  │
│ class AssetClass │  │ AssetClassType   │  │                  │
│ class OHLCV...   │  │ OHLCVFrame       │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

### ディレクトリ構成

```
spectool/
  core/
    base/                    # ★純粋なデータ定義（最下層）
      ir.py                  # IR（DataFrame制約中心）
      meta_types.py          # メタ型定義
    engine/                  # ★Spec→IR変換（唯一の賢い層）
      loader.py              # YAML読み込み + Python型参照解決
      normalizer.py          # メタRegistry + 優先度マージ
      validate.py            # IR検証（意味論チェック）
  backends/                  # ★IR→成果物（純関数）
    py_code.py               # DataFrame TypeAlias生成
    py_validators.py         # Pandera Schema生成
    convert_openapi.py       # OpenAPI変換
    convert_md.py            # Markdown生成
  cli.py                     # エントリポイント
```

**設計原則**：
1. **全てYAML定義**: Pydantic/Enum/DataFrameを宣言的に記述（既存同様）
2. **メタデータ内包**: examples/check_functionsを型定義に含める（新機能）
3. **二重生成**: models.py（実装）+ type_aliases.py（メタ型）を生成
4. **IRで一元化**: Spec→IR→各バックエンド（放射状）
5. **Annotatedメタ型**: 型とメタデータを統合（PydanticRowRef, GeneratorSpec, CheckedSpec, ExampleSpec）

## 新旧対応表

| 既存ファイル/機能 | 新アーキテクチャ | 移行方針 |
|------------------|-----------------|---------|
| **engine.py: Pydanticモデル定義（YAML→コード生成）** | `backends/py_code.py` (models.py生成) | **リファクタ移行（同様）** |
| **engine.py: Enum定義（YAML→コード生成）** | `backends/py_code.py` (models.py生成) | **リファクタ移行（同様）** |
| **engine.py: Generic/TypeAlias定義（YAML→コード生成）** | `backends/py_code.py` (type_aliases.py生成) | **リファクタ＋拡張（Annotated追加）** ⭐新機能 |
| **engine.py: DataFrame Schema定義** | `core/base/ir.py` (FrameSpec) | **そのまま移行** |
| **engine.py: load_spec()** | `core/engine/loader.py` | **リファクタ移行（同様）** |
| **engine.py: 型解決ロジック** | `core/engine/normalizer.py` | **リファクタ移行** |
| **engine.py: Pandera Schema生成** | `backends/py_validators.py` | **リファクタ移行（同様）** |
| **engine.py: Engine検証** | `core/engine/validate.py` | **リファクタ移行** |
| **なし（新機能）** | `backends/py_code.py` (TypeAlias生成) | **新規追加（Annotatedメタ型）** ⭐新機能 |
| **config_model.py** | `core/config/` (別パッケージ) | **そのまま移行** |
| **config_validator.py** | `core/config/` (別パッケージ) | **そのまま移行** |
| **config_runner.py** | `core/config/` (別パッケージ) | **そのまま移行** |
| **card_exporter.py** | `backends/convert_cards.py` | **リファクタ移行** |

## 再利用可能な部分

### 1. DataFrame Schema定義（そのまま移行）

**既存のDataFrame Schema定義は新IRで再利用可能**：

```python
# 既存: engine.py
class DataType(BaseModel):
    dataframe_schema: DataFrameSchemaConfig | None

# 新: core/base/ir.py
@dataclass
class FrameSpec:
    id: str
    index: Optional[list[IndexRule]]
    multi_index: Optional[list[MultiIndexLevel]]
    columns: list[ColumnRule]
    checks: list[dict]
    row_model: Optional[str]  # Python型参照
```

**移行アクション**：
- 既存の `dataframe_schema` 構造を `FrameSpec` にマッピング
- Index/Column定義はほぼ同一構造で移行可能

### 2. Config系モジュール（ほぼそのまま再利用）

**既存のConfig系は実行時の設定管理として有効**：

```python
# config_model.py → core/config/model.py
# config_validator.py → core/config/validator.py
# config_runner.py → core/config/runner.py
```

**移行アクション**：
- `core/config/` パッケージとして独立させる
- 新アーキテクチャとの統合は `cli.py` で行う

### 3. Transform/DAG Stage定義（ほぼそのまま移行）

**既存のTransform/DAG Stage定義は新IRで再利用可能**：

```python
# 既存: engine.py
class Transform(BaseModel):
    id: str
    impl: str
    parameters: list[Parameter]
    return_datatype_ref: str

# 新: core/base/ir.py
@dataclass
class TransformSpec:
    id: str
    impl: str
    parameters: list[dict]  # {name, type_ref, optional, default}
    return_type_ref: str
```

**移行アクション**：
- 構造はほぼ同一、IRに変換するだけ

### 4. インポート文の整形・ファイル書き込み（部分的に再利用）

**既存の生成関数から再利用可能な部分**：
- インポート文の整形 (`_render_imports()` L1049)
- ファイル書き込みロジック (`_write_transform_file()` L1616)
- 既存関数の検出 (`_extract_existing_function_names()` L1506)

**移行アクション**：
- ユーティリティ関数としてbackendsで再利用

## ゼロから作成・大幅リファクタする部分

> **📁 具体的な入出力サンプルは [`doc/examples/`](examples/) を参照**

### 0. メタ型定義【新規】

**必要な理由**：
- Annotatedメタデータとして型とメタ情報を統合
- ランタイム・型チェッカー双方で活用可能な設計
- 拡張可能なメタデータシステム

**実装内容** (`core/base/meta_types.py`)：

メタ型クラス（dataclass）：
- `PydanticRowRef`: DataFrameの各行がPydanticモデルに対応
- `SchemaSpec`: DataFrame制約の詳細定義（YAML由来）
- `GeneratorSpec`: データ生成関数への参照（`factory: str`）
- `CheckedSpec`: バリデーション関数リストへの参照（`functions: list[str]`）
- `ExampleSpec`: 例示データ（Enum等で使用）

**生成コード例**（詳細は [`doc/examples/output/datatypes/type_aliases.py`](examples/output/datatypes/type_aliases.py)）：
```python
OHLCVFrame: TypeAlias = Annotated[
    pd.DataFrame,
    PydanticRowRef(model=OHLCVRowModel),
    GeneratorSpec(factory="apps.generators:generate_ohlcv_frame"),
    CheckedSpec(functions=["apps.checks:check_ohlcv"]),
]
```

### 1. IR（中間表現）設計【リファクタ】

**必要な理由**：
- 既存システムはSpecを直接処理（中間表現が弱い）
- 新システムでは「Spec→IR→各バックエンド」の一貫性が必須
- **DataFrame中心のIR**（Pydantic/Enum/GenericはPython型参照で解決）

**実装内容** (`core/base/ir.py`)：

主要なIRデータクラス：
- `FrameSpec`: DataFrame制約定義（index, columns, checks, row_model参照）
- `EnumSpec`: Enum定義（メタデータ付き）
- `TransformSpec`: Transform定義（parameters, return_type_ref）
- `DAGStageSpec`: DAG Stage定義（input_type, output_type, candidates）
- `SpecIR`: 統合IR（frames, enums, transforms, dag_stages等）

重要フィールド：
- `row_model: str` - Python型参照（例: `"pkg.mod:OHLCVRowModel"`）
- `generator_factory: str` - 生成関数参照（例: `"apps.gen:func"`）
- `check_functions: list[str]` - Check関数リスト

### 2. Loader（Python型参照解決）【新規】

**必要な理由**：
- 既存システムはYAMLからコード生成
- 新システムではPython型を参照するため、解決機構が必要

**実装内容** (`core/engine/loader.py`)：

主要関数：
- `load_spec(spec_path) -> SpecIR`: YAMLを読み込み、IRに変換
- `_load_dataframe_specs()`: DataFrame定義をFrameSpecに変換
- `_load_enum_specs()`: Enum定義をEnumSpecに変換
- `_load_transform_specs()`: Transform定義をTransformSpecに変換
- `_load_dag_stage_specs()`: DAG Stage定義をDAGStageSpecに変換

処理フロー：
1. YAMLを`yaml.safe_load()`でパース
2. 各セクション（dataframes, enums, transforms, dag_stages等）を対応するSpecに変換
3. SpecIRに統合して返却

入力例は [`doc/examples/input/sample_spec.yaml`](examples/input/sample_spec.yaml) を参照。

### 3. Normalizer（メタハンドラRegistry）【新規】

**必要な理由**：
- 拡張性（新しいメタの追加が容易）
- 前方互換性（未知メタを無視できる）
- PydanticRowRefからDataFrame列定義を推論

**実装内容** (`core/engine/normalizer.py`)：

主要機能：
- **メタハンドラRegistry**: `register_meta_handler()` で拡張可能
- **PydanticRowHandler**: `row_model`からDataFrame列定義を推論
  - Pydantic `model_fields` を解析
  - 既存列定義とマージ（優先度: Pydantic < SchemaSpec）
- **normalize_ir()**: IRに対してハンドラを適用

処理フロー：
1. `FrameSpec.row_model` が設定されている場合
2. 動的に`importlib`でPydanticモデルをロード
3. `model_fields`から列定義を抽出
4. 既存の列定義とマージ（SchemaSpecが優先）

### 4. バックエンド層【大幅リファクタ】

**必要な理由**：
- 既存のコード生成は `engine.py` に散在
- 新システムではバックエンドを純関数化（IRのみに依存）
- **DataFrame/Enum TypeAlias生成**（メタ型でAnnotated）

**実装方針**：

#### `backends/py_code.py`（TypeAlias生成）

主要関数：
- `generate_dataframe_aliases(ir, output_path)`: DataFrame TypeAlias生成
- `generate_enum_aliases(ir, output_path)`: Enum TypeAlias生成（必要な場合）

生成内容：
- `Annotated[pd.DataFrame, PydanticRowRef(...), GeneratorSpec(...), CheckedSpec(...)]`
- `row_model`からPydanticモデルをインポート
- メタ型パラメータの設定（factory, functions等）

生成例は [`doc/examples/output/datatypes/type_aliases.py`](examples/output/datatypes/type_aliases.py) を参照。

#### `backends/py_validators.py`（Pandera Schema生成）

主要関数：
- `generate_pandera_schemas(ir, output_path)`: Pandera SchemaModel生成

生成内容：
- `class {FrameID}Schema(pa.DataFrameModel):`
- Index/MultiIndex定義
- Column定義（dtype, nullable, checks）

生成例は [`doc/examples/output/datatypes/schemas.py`](examples/output/datatypes/schemas.py) を参照。

### 5. 検証ロジック【大幅リファクタ】

**必要な理由**：
- 既存の検証は `Engine` クラスのメソッドとして実装（2000行以上）
- 新システムではIRに対する意味論チェックとして独立

**実装方針** (`core/engine/validate.py`)：

主要関数：
- `validate_ir(ir) -> list[str]`: IR全体の意味論チェック（エラーメッセージリスト返却）
- `_validate_dataframe_specs()`: DataFrame定義の妥当性チェック（重複列、dtype等）
- `_validate_transform_specs()`: Transform定義の妥当性チェック
- `_validate_dag_stage_specs()`: DAG Stage定義の妥当性チェック
- `_validate_type_references()`: Python型参照の解決可能性チェック

検証項目：
- 重複列名
- dtype未設定
- Python型参照の解決可能性（`importlib`で実際にimport試行）
- Transform parametersの型参照妥当性
- DAG cycleチェック（必要に応じて）

## 既存YAMLからの移行戦略

### Step 1: YAMLにメタデータフィールドを追加

**既存のdatatypesにexamples/check_functionsを追加**：

新形式のYAML例は [`doc/examples/input/sample_spec.yaml`](examples/input/sample_spec.yaml) を参照。

主な変更点：
- 各datatype定義に `examples` フィールドを追加
- 各datatype定義に `check_functions` フィールドを追加
- DataFrame定義に `datatype_ref` フィールドを追加（row_model参照）
- DataFrame定義に `generator_factory` フィールドを追加

```yaml
# 変更前（既存）
datatypes:
  - id: MarketDataConfig
    pydantic_model:
      fields: [...]

# 変更後（新システム）
datatypes:
  - id: MarketDataConfig
    pydantic_model:
      fields: [...]
    examples:                          # ← 追加
      - symbols: ["AAPL", "GOOGL"]
        ...
    check_functions:                   # ← 追加
      - "apps.checks:validate_market_data_config"
```

### Step 2: 生成内容の拡張

**既存のgenコマンドを拡張**：

```bash
# 既存コマンドは変更なし
spectool gen spec.yaml

# 生成されるファイル（既存）
# - models.py (Pydantic/Enum)
# - schemas.py (Pandera Schema)
# - checks/ (check skeletons)
# - transforms/ (transform skeletons)

# 生成されるファイル（新規追加）⭐
# - type_aliases.py (Annotatedメタ型)
```

**CLIコマンド体系は既存のまま**：
1. `spectool validate` - specのバリデーション
2. `spectool gen` - spec→コード生成（type_aliases.pyを追加生成）
3. `spectool validate-integrity` - コードがspecに従うかバリデーション
4. `spectool convert` - specの形式変換

### Step 3: 自動マイグレーションスクリプト

**機能** (`scripts/add_metadata_to_spec.py`)：
- `add_example_placeholders()`: datatypesにexamplesフィールドを追加
- `add_check_function_placeholders()`: datatypesにcheck_functionsフィールドを追加
- `migrate_spec()`: 既存specにメタデータフィールドを追加

## 移行フェーズ（コマンド判定可能な成功基準付き）

### Phase 1: IR基盤（データ構造定義）

**目標**: IRデータ構造とメタ型を定義し、インポート可能にする

**実装ファイル**:
- `spectool/core/base/ir.py`
- `spectool/core/base/meta_types.py`
- `spectool/core/base/__init__.py`

**テスト用入力**: なし（データ構造定義のみ）

**成功判定コマンド**:
```bash
# 1. IRモジュールがインポート可能
python -c "from spectool.core.base.ir import SpecIR, FrameSpec, EnumSpec, TransformSpec; print('✅ IR import OK')"

# 2. メタ型モジュールがインポート可能
python -c "from spectool.core.base.meta_types import PydanticRowRef, GeneratorSpec, CheckedSpec, ExampleSpec; print('✅ Meta types import OK')"

# 3. 単体テストが通る
pytest spectool/tests/test_ir_dataclasses.py -v
# 期待: PASSED (全テストが通る)

# 4. メタ型のテストが通る
pytest spectool/tests/test_meta_types.py -v
# 期待: PASSED (メタ型の動的インポート等が動作)

# 5. 型チェックが通る
pyright spectool/core/base/
# 期待: 0 errors
```

**成功基準**:
- ✅ すべてのIRデータクラス（FrameSpec, EnumSpec含む）がインポート可能
- ✅ すべてのメタ型（PydanticRowRef, GeneratorSpec, CheckedSpec, ExampleSpec）がインポート可能
- ✅ `pytest spectool/tests/test_ir_dataclasses.py` が全件PASSED
- ✅ `pytest spectool/tests/test_meta_types.py` が全件PASSED
- ✅ `pyright spectool/core/base/` がエラー0

**想定所要時間**: 2-3日

---

### Phase 2: Loader実装（YAML→IR変換）

**目標**: サンプルYAMLをIRに変換できる

**実装ファイル**:
- `spectool/core/engine/loader.py`
- `spectool/core/engine/__init__.py`

**テスト用入力**:
- `spectool/tests/fixtures/minimal_spec.yaml` (最小限のDataFrame定義)
- `spectool/tests/fixtures/sample_spec.yaml` (複数のDataFrame + Transform)

**成功判定コマンド**:
```bash
# 1. Loaderがインポート可能
python -c "from spectool.core.engine.loader import load_spec; print('✅ Loader import OK')"

# 2. 最小限のYAMLをロード可能
python -c "
from spectool.core.engine.loader import load_spec
ir = load_spec('spectool/tests/fixtures/minimal_spec.yaml')
assert len(ir.frames) == 1
assert ir.frames[0].id == 'SampleFrame'
print('✅ Minimal YAML load OK')
"

# 3. Loaderテストが通る
pytest spectool/tests/test_loader.py -v
# 期待: PASSED (全テストが通る)

# 4. IRスナップショット一致
pytest spectool/tests/test_loader_snapshot.py -v
# 期待: PASSED (生成されたIRがスナップショットと一致)
```

**成功基準**:
- ✅ `minimal_spec.yaml` がIRに変換できる
- ✅ `pytest spectool/tests/test_loader.py` が全件PASSED
- ✅ IRスナップショットテストが通る

**想定所要時間**: 3-4日

---

### Phase 3: Normalizer実装（IR正規化）

**目標**: PydanticRowRefからDataFrame列定義を推論できる

**実装ファイル**:
- `spectool/core/engine/normalizer.py`

**テスト用入力**:
- `spectool/tests/fixtures/pydantic_rowref_spec.yaml` (row_model参照あり)
- `apps/test-project/datatypes/models.py` (テスト用Pydanticモデル)

**成功判定コマンド**:
```bash
# 1. Normalizerがインポート可能
python -c "from spectool.core.engine.normalizer import normalize_ir; print('✅ Normalizer import OK')"

# 2. PydanticRowRefハンドラが動作
python -c "
from spectool.core.engine.loader import load_spec
from spectool.core.engine.normalizer import normalize_ir
ir = load_spec('spectool/tests/fixtures/pydantic_rowref_spec.yaml')
normalized = normalize_ir(ir)
# PydanticモデルからDataFrame列が推論されることを確認
assert len(normalized.frames[0].columns) > 0
print('✅ PydanticRowRef inference OK')
"

# 3. Normalizerテストが通る
pytest spectool/tests/test_normalizer.py -v
# 期待: PASSED (PydanticRowRef推論、優先度マージ等)

# 4. Normalizerスナップショットテスト
pytest spectool/tests/test_normalizer_snapshot.py -v
# 期待: PASSED (正規化後のIRがスナップショットと一致)
```

**成功基準**:
- ✅ PydanticRowRefから列定義が自動推論される
- ✅ `pytest spectool/tests/test_normalizer.py` が全件PASSED
- ✅ 優先度マージ（Pydantic < SchemaSpec）が正しく動作

**想定所要時間**: 3-4日

---

### Phase 4: Validator実装（IR検証）

**目標**: IRの意味論チェックとPython型参照の検証

**実装ファイル**:
- `spectool/core/engine/validate.py`

**テスト用入力**:
- `spectool/tests/fixtures/valid_spec.yaml` (エラーなし)
- `spectool/tests/fixtures/invalid_spec_duplicate_cols.yaml` (重複列エラー)
- `spectool/tests/fixtures/invalid_spec_missing_type.yaml` (型参照エラー)

**成功判定コマンド**:
```bash
# 1. Validatorがインポート可能
python -c "from spectool.core.engine.validate import validate_ir; print('✅ Validator import OK')"

# 2. 正常なspecのバリデーションが通る
python -c "
from spectool.core.engine.loader import load_spec
from spectool.core.engine.normalizer import normalize_ir
from spectool.core.engine.validate import validate_ir
ir = load_spec('spectool/tests/fixtures/valid_spec.yaml')
normalized = normalize_ir(ir)
errors = validate_ir(normalized)
assert len(errors) == 0
print('✅ Valid spec validation OK')
"

# 3. 不正なspecでエラー検出
python -c "
from spectool.core.engine.loader import load_spec
from spectool.core.engine.validate import validate_ir
ir = load_spec('spectool/tests/fixtures/invalid_spec_duplicate_cols.yaml')
errors = validate_ir(ir)
assert len(errors) > 0
assert any('duplicate column' in e for e in errors)
print('✅ Invalid spec detection OK')
"

# 4. Validatorテストが通る
pytest spectool/tests/test_validator.py -v
# 期待: PASSED (各種エラー検出ロジックのテスト)
```

**成功基準**:
- ✅ 正常なspecでエラー0
- ✅ 不正なspecで適切なエラーメッセージ
- ✅ `pytest spectool/tests/test_validator.py` が全件PASSED
- ✅ Python型参照の検証が動作

**想定所要時間**: 3-4日

---

### Phase 5: バックエンド（TypeAlias生成）

**目標**: IRからDataFrame TypeAlias（Annotatedメタ付き）を生成

**実装ファイル**:
- `spectool/backends/py_code.py`
- `spectool/backends/__init__.py`

**テスト用入力**:
- `spectool/tests/fixtures/sample_spec.yaml`

**成功判定コマンド**:
```bash
# 1. バックエンドがインポート可能
python -c "from spectool.backends.py_code import generate_dataframe_aliases; print('✅ Backend import OK')"

# 2. TypeAliasファイルを生成
python -m spectool.backends.py_code \
  spectool/tests/fixtures/sample_spec.yaml \
  -o spectool/tests/output/type_aliases.py
# 期待: exit code 0

# 3. 生成されたファイルが存在し、インポート可能
python -c "
import sys
sys.path.insert(0, 'spectool/tests/output')
from type_aliases import SampleFrame
print('✅ Generated TypeAlias import OK')
"

# 4. 生成コードスナップショットテスト
pytest spectool/tests/test_backend_py_code.py::test_typealias_generation_snapshot -v
# 期待: PASSED (生成コードがスナップショットと一致)

# 5. 生成コードの構文チェック
python -m py_compile spectool/tests/output/type_aliases.py
# 期待: exit code 0 (構文エラーなし)
```

**成功基準**:
- ✅ TypeAliasファイルが生成される
- ✅ 生成コードが構文エラーなし
- ✅ 生成コードがインポート可能
- ✅ `pytest spectool/tests/test_backend_py_code.py` が全件PASSED
- ✅ スナップショットテストが通る

**想定所要時間**: 2-3日

---

### Phase 6: バックエンド（Pandera Schema生成）

**目標**: IRからPandera SchemaModelを生成

**実装ファイル**:
- `spectool/backends/py_validators.py`

**テスト用入力**:
- `spectool/tests/fixtures/sample_spec.yaml`

**成功判定コマンド**:
```bash
# 1. バックエンドがインポート可能
python -c "from spectool.backends.py_validators import generate_pandera_schemas; print('✅ Validator backend import OK')"

# 2. Pandera Schemaファイルを生成
python -m spectool.backends.py_validators \
  spectool/tests/fixtures/sample_spec.yaml \
  -o spectool/tests/output/schemas.py
# 期待: exit code 0

# 3. 生成されたSchemaが動作
python -c "
import sys
import pandas as pd
sys.path.insert(0, 'spectool/tests/output')
from schemas import SampleFrameSchema
# サンプルDataFrameで検証
df = pd.DataFrame({'col1': [1, 2], 'col2': [3.0, 4.0]})
validated = SampleFrameSchema.validate(df)
print('✅ Generated Pandera Schema validation OK')
"

# 4. 生成コードスナップショットテスト
pytest spectool/tests/test_backend_py_validators.py::test_pandera_generation_snapshot -v
# 期待: PASSED (生成コードがスナップショットと一致)

# 5. 既存システムとの出力比較
pytest spectool/tests/test_backend_parity.py::test_pandera_output_equivalent -v
# 期待: PASSED (既存システムと新システムの出力が等価)
```

**成功基準**:
- ✅ Pandera Schemaファイルが生成される
- ✅ 生成Schemaで検証が動作
- ✅ `pytest spectool/tests/test_backend_py_validators.py` が全件PASSED
- ✅ 既存システムとの出力パリティテストが通る

**想定所要時間**: 3-4日

---

### Phase 7: マイグレーションツール

**目標**: 既存YAMLを新形式に自動変換

**実装ファイル**:
- `scripts/extract_python_types.py`
- `scripts/migrate_spec_to_hybrid.py`

**テスト用入力**:
- `specs/algo-trade-pipeline.yaml` (既存spec)

**成功判定コマンド**:
```bash
# 1. Python型抽出スクリプトが動作
python scripts/extract_python_types.py \
  specs/algo-trade-pipeline.yaml \
  -o spectool/tests/output/migrated/datatypes/models.py
# 期待: exit code 0

# 2. 抽出されたPython型がインポート可能
python -c "
import sys
sys.path.insert(0, 'spectool/tests/output/migrated')
from datatypes.models import MarketDataIngestionConfig, CVMethod
print('✅ Extracted Python types import OK')
"

# 3. spec変換スクリプトが動作
python scripts/migrate_spec_to_hybrid.py \
  specs/algo-trade-pipeline.yaml \
  -o spectool/tests/output/migrated/
# 期待: exit code 0

# 4. 変換されたspecがロード可能
python -c "
from spectool.core.engine.loader import load_spec
ir = load_spec('spectool/tests/output/migrated/spec.yaml')
assert len(ir.frames) > 0
assert len(ir.transforms) > 0
print('✅ Migrated spec load OK')
"

# 5. マイグレーション正確性テスト
pytest spectool/tests/test_migration.py -v
# 期待: PASSED (DataFrame定義の数、Transform数等が一致)

# 6. 変換前後でDataFrame定義が等価
pytest spectool/tests/test_migration_equivalence.py -v
# 期待: PASSED (DataFrame制約が保持されている)
```

**成功基準**:
- ✅ Python型抽出が成功（exit code 0）
- ✅ 抽出されたPython型がインポート可能
- ✅ spec変換が成功（exit code 0）
- ✅ 変換されたspecがロード可能
- ✅ `pytest spectool/tests/test_migration.py` が全件PASSED
- ✅ DataFrame定義の等価性が保証される

**想定所要時間**: 3-4日

---

### Phase 8: 統合テスト + CLI完成

**目標**: 全機能を統合し、CLIから利用可能にする

**実装ファイル**:
- `spectool/cli.py`
- `spectool/__main__.py`

**テスト用入力**:
- `spectool/tests/fixtures/sample_spec.yaml`
- `spectool/tests/output/migrated/spec.yaml` (Phase 7で生成)

**成功判定コマンド**:
```bash
# 1. CLIがインストール可能
pip install -e .
spectool --version
# 期待: spectool version X.X.X

# 2. spectool validate コマンド
spectool validate spectool/tests/fixtures/sample_spec.yaml
# 期待: exit code 0, "✅ Validation passed"

spectool validate spectool/tests/fixtures/invalid_spec_duplicate_cols.yaml
# 期待: exit code 1, エラーメッセージ出力

# 3. spectool gen コマンド（既存コマンド）
spectool gen spectool/tests/fixtures/sample_spec.yaml
# 期待: exit code 0
# 生成ファイルの確認
test -f apps/sample-project/datatypes/models.py
test -f apps/sample-project/datatypes/type_aliases.py  # ← 新規生成ファイル
test -f apps/sample-project/datatypes/schemas.py
# 期待: 全てのファイルが存在

# 4. spectool validate-integrity コマンド
spectool validate-integrity spectool/tests/fixtures/sample_spec.yaml
# 期待: exit code 0

# 5. 変換されたspec（Phase 7）でも動作
spectool validate spectool/tests/output/migrated/spec.yaml
# 期待: exit code 0

spectool gen spectool/tests/output/migrated/spec.yaml
# 期待: exit code 0

# 6. 新システム統合テスト
pytest spectool/tests/test_integration.py -v
# 期待: PASSED (全機能統合テスト)

# 7. CLIエンドツーエンドテスト
pytest spectool/tests/test_cli_e2e.py -v
# 期待: PASSED (CLIコマンドの動作確認)

# 8. 既存システムとの出力パリティテスト
pytest spectool/tests/test_migration_parity.py -v
# 期待: PASSED (新旧システムの生成コードが等価)

# 9. Import Linter チェック
lint-imports
# 期待: exit code 0 (層違反なし)
```

**成功基準**:
- ✅ `spectool --version` が動作
- ✅ `spectool validate` が正常/異常両方で正しく動作
- ✅ `spectool gen` がmodels.py + type_aliases.py + schemas.pyを生成
- ✅ `spectool validate-integrity` が動作
- ✅ 変換されたspecでも全コマンドが動作
- ✅ `pytest spectool/tests/test_integration.py` が全件PASSED
- ✅ `pytest spectool/tests/test_cli_e2e.py` が全件PASSED（CLI動作確認）
- ✅ `pytest spectool/tests/test_migration_parity.py` が全件PASSED（出力パリティ）
- ✅ `lint-imports` がエラー0

**想定所要時間**: 3-4日

**重要な注意事項**:
既存の `packages/tests/` は内部実装に依存しているため、新システムでは動作しません。代わりに、以下のテスト戦略を採用します：
1. **エンドツーエンドテスト** (`test_cli_e2e.py`): CLIコマンドの結果を検証
2. **出力パリティテスト** (`test_migration_parity.py`): 新旧システムの生成コードを比較
3. **統合テスト** (`test_integration.py`): 新システムの全機能を統合的に検証

---

## Phase間の依存関係

```
Phase 1 (IR基盤)
    ↓
Phase 2 (Loader) ←──────┐
    ↓                   │
Phase 3 (Normalizer)    │
    ↓                   │
Phase 4 (Validator)     │
    ↓                   │
Phase 5 (TypeAlias生成) │
    ↓                   │
Phase 6 (Pandera生成)   │
    ↓                   │
Phase 7 (Migration) ────┘ (Phase 2以降が必要)
    ↓
Phase 8 (統合 + CLI)
```

## Phase完了チェックリスト

各Phase完了時に以下を実行：

```bash
# Phase完了確認スクリプト
./scripts/check_phase_completion.sh <phase_number>

# 例: Phase 1完了確認
./scripts/check_phase_completion.sh 1
# 期待出力:
# ✅ Phase 1: IR基盤
#   ✅ Import test passed
#   ✅ Unit tests passed (5/5)
#   ✅ Type check passed (0 errors)
# 🎉 Phase 1 completed successfully!
```

各Phaseの完了スクリプトは以下の構成：

```bash
# scripts/check_phase_completion.sh
#!/bin/bash
case "$1" in
  "1")
    python -c "from spectool.core.base.ir import SpecIR; print('✅ Import OK')" && \
    pytest spectool/tests/test_ir_dataclasses.py -v --tb=short && \
    pyright spectool/core/base/
    ;;
  "2")
    python -c "from spectool.core.engine.loader import load_spec; print('✅ Import OK')" && \
    pytest spectool/tests/test_loader.py -v --tb=short && \
    pytest spectool/tests/test_loader_snapshot.py -v --tb=short
    ;;
  # ... 他のPhase
esac
```

## Import Linter設定

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
    spectool.backends.convert_cards
```

## 移行中の並行稼働

**戦略**: 既存システムと新システムを並行稼働させる

| Phase | 既存システム | 新システム | 検証方法 |
|-------|------------|----------|---------|
| **1-4** | 継続使用 | 開発中 | 単体テスト |
| **5-6** | 継続使用 | コード生成テスト | 出力比較テスト |
| **7** | 継続使用 | マイグレーション実行 | 変換前後の等価性テスト |
| **8** | 並行稼働 | 統合テスト | 出力パリティテスト |
| **完了後** | 退避 (`packages/spec2code_legacy/`) | 本番運用 | - |

**判定コマンド**:
```bash
# Phase 6完了後: 既存システムとの出力比較
make compare-output
# 期待: "✅ All outputs are equivalent"

# Phase 7完了後: マイグレーション検証
make validate-migration
# 期待: "✅ Migration successful, all specs converted"

# Phase 8完了後: 出力パリティテスト
pytest spectool/tests/test_migration_parity.py -v
# 期待: PASSED (新旧システムの生成コードが等価)
```

## テスト戦略

### 1. IRスナップショットテスト
```python
def test_ir_snapshot():
    spec_ir = load_spec("specs/algo-trade-pipeline-new.yaml")
    ir_normalized = normalize_ir(spec_ir)
    snapshot = json.dumps(asdict(ir_normalized), indent=2, default=str)
    assert snapshot == expected_snapshot
```

### 2. マイグレーション正確性テスト
```python
def test_migration_accuracy():
    # 既存specから変換
    migrate_spec("specs/algo-trade-pipeline.yaml", "specs/migrated/")

    # 両方をロードして比較
    old_spec = old_engine.load_spec("specs/algo-trade-pipeline.yaml")
    new_ir = load_spec("specs/migrated/spec.yaml")

    # DataFrame定義が一致することを確認
    assert_dataframes_equivalent(old_spec.datatypes, new_ir.frames)
```

### 3. バックエンド出力比較テスト
```python
def test_code_generation_parity():
    # 既存システムと新システムの出力を比較
    old_output = old_generate_pandera_schema(old_spec)
    new_output = generate_pandera_schemas(new_ir, output_path)
    assert normalize_code(old_output) == normalize_code(new_output)
```

### 4. CLIエンドツーエンドテスト
```python
def test_cli_validate_command():
    # CLIコマンドの実行を検証（内部実装に依存しない）
    result = subprocess.run(
        ["spectool", "validate", "specs/sample.yaml"],
        capture_output=True
    )
    assert result.returncode == 0
    assert "✅ Validation passed" in result.stdout.decode()

def test_cli_gen_code_command():
    # コード生成コマンドの実行を検証
    result = subprocess.run(
        ["spectool", "gen-code", "specs/sample.yaml", "-o", "output/gen.py"],
        capture_output=True
    )
    assert result.returncode == 0
    assert Path("output/gen.py").exists()
    # 生成ファイルがインポート可能であることを確認
    import output.gen
```

### 5. 新システム統合テスト
```python
def test_full_workflow_integration():
    # Loader → Normalizer → Validator → Backend の統合フロー
    ir = load_spec("specs/sample.yaml")
    normalized = normalize_ir(ir)
    errors = validate_ir(normalized)
    assert len(errors) == 0

    # コード生成まで
    generate_dataframe_aliases(normalized, "output/aliases.py")
    generate_pandera_schemas(normalized, "output/schemas.py")

    # 生成コードが動作することを確認
    assert Path("output/aliases.py").exists()
    assert Path("output/schemas.py").exists()
```

## リスクと対策

| リスク | 影響 | 対策 |
|--------|------|------|
| 既存specの大規模変更 | 移行コスト増大 | マイグレーションツールの自動化 |
| Python型定義の抽出ミス | 型不一致エラー | 抽出結果の検証テスト |
| 出力の微妙な差異 | テストが失敗 | 正規化関数で差異を吸収 |
| 大規模リファクタによるバグ混入 | 品質低下 | 段階的移行＋スナップショットテスト |
| 移行期間の長期化 | 開発効率低下 | Phase区切りで最小価値を提供 |

## 成功基準

1. **機能完全性**: 既存システムのすべての機能が新システムで動作
2. **マイグレーション完了**: algo-trade-pipeline.yamlが新形式で動作
3. **テスト完全性**: 新システム用の統合テスト・E2Eテスト・出力パリティテストがすべてパス
4. **コード品質**: Import Linterによる層違反がゼロ
5. **ドキュメント完全性**: 新アーキテクチャのドキュメントが完備
6. **パフォーマンス**: 新システムが既存システムと同等以上の速度
7. **出力等価性**: 新旧システムの生成コードが機能的に等価

## まとめ

### ハイブリッドアプローチの利点

1. **YAML定義維持**: 既存のYAMLベース定義を維持（既存資産活用）
2. **メタデータ統合**: examples/check_functionsを型定義に内包→一元化
3. **二重生成**: models.py（実装）+ type_aliases.py（メタ型）で使い分け可能
4. **型安全性**: 生成されたPython型で型チェッカー利用可能
5. **Annotatedメタ型**: 型とメタデータを統合し、ランタイム・型チェッカー双方で活用

### 移行の核心

- **YAML定義**: 既存同様にPydantic/Enum/DataFrameをYAMLで定義
- **メタデータ追加**: examples/check_functionsをYAML内で指定（新機能）
- **二重生成**: models.py（既存）+ type_aliases.py（新規）
- **メタ型システム**: `PydanticRowRef`, `GeneratorSpec`, `CheckedSpec`, `ExampleSpec`
- **Transform/DAG Stage**: YAMLのまま（既存同様）
- **検証・生成ロジック**: IRベースにリファクタ

### 新しい生成コード形式

**Pydanticモデル型**（新機能）:
```python
MarketDataConfigType: TypeAlias = Annotated[
    MarketDataConfig,
    ExampleSpec(examples=[{...}]),
    CheckedSpec(functions=["apps.checks:validate_market_data_config"]),
]
```

**DataFrame型**（新機能）:
```python
OHLCVFrame: TypeAlias = Annotated[
    pd.DataFrame,
    PydanticRowRef(model=OHLCVRowModel),
    GeneratorSpec(factory="apps.generators:generate_ohlcv_frame"),
    CheckedSpec(functions=["apps.checks:check_ohlcv"]),
]
```

**Enum型**（新機能）:
```python
AssetClassType: TypeAlias = Annotated[
    AssetClass,
    ExampleSpec(examples=["EQUITY", "CRYPTO"]),
    CheckedSpec(functions=["apps.checks:validate_asset_class"]),
]
```

この方針に基づき、段階的にアーキテクチャを移行することで、**YAML定義を維持しつつ、Annotatedメタ型で型とメタデータを統合**し、拡張性の高いシステムを実現します。

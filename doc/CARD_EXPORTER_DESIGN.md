# Card Exporter 設計書

## 目的

YAML仕様ファイルをフロントエンドで表示可能なJSON形式に変換するコマンドの実装。

### 要件
- **データ完全性**: YAMLの全情報を欠落なくJSONに変換
- **表示目的**: フロントエンドはカード型UIでグラフィカルに表示（複雑な機能は不要）
- **シンプル設計**: 過度な後方互換性や抽象化を避け、実装の複雑度を最小化

## 設計サマリー

### 主要な設計判断

1. **SpecIR構造の直接反映**
   - `asdict()` でdataclassをJSON化
   - 不要な型変換・パース処理を排除
   - SpecIRの全フィールドを `data` キーに格納

2. **型定義のカテゴリ分離**
   - 旧: `dtype` カテゴリに全型を統合
   - 新: `dtype_frame`, `dtype_enum`, `dtype_pydantic`, `dtype_alias`, `dtype_generic` に分離
   - フロントエンド側で型別UIを実装可能

3. **メタデータキーの廃止**
   - 旧: `metadata` キー（曖昧）
   - 新: `data` キー（直感的）

4. **フロントエンド変更の許容**
   - 後方互換性に固執せず、必要ならフロントエンド側も修正
   - シンプルな実装を優先

## アーキテクチャ

```
YAML Spec → [Loader] → SpecIR → [Card Exporter] → JSON → Frontend Display
```

### コンポーネント構成

```
spectool/
├── core/
│   └── export/
│       ├── __init__.py
│       └── card_exporter.py     # 新規作成
└── main.py                       # export_cards コマンド追加

frontend/public/cards/
└── all-cards.json                # 出力ファイル
```

## 基本方針

### シンプル化の原則

1. **SpecIRの構造を直接反映** - 不要な変換を避ける
2. **型参照は文字列のまま出力** - パース処理は不要
3. **フロントエンド側で必要な変更を許容** - 後方互換性に固執しない
4. **実装の複雑度を最小化** - 過度な抽象化を避ける

### SpecIRからの直接マッピング

| SpecIR要素 | JSONカテゴリ | 備考 |
|-----------|------------|-----|
| `checks` | `check` | そのまま |
| `generators` | `generator` | そのまま |
| `frames` | `dtype_frame` | 新カテゴリ |
| `enums` | `dtype_enum` | 新カテゴリ |
| `pydantic_models` | `dtype_pydantic` | 新カテゴリ |
| `type_aliases` | `dtype_alias` | 新カテゴリ |
| `generics` | `dtype_generic` | 新カテゴリ |
| `examples` | `example` | そのまま |
| `transforms` | `transform` | そのまま |
| `dag_stages` | `dag_stage` | そのまま |

**設計判断:** 型定義を無理に統合せず、カテゴリを分離して出力。フロントエンド側で型別のUIを実装可能。

## JSON出力形式

### 全体構造

```json
{
  "specs": [
    {
      "source_file": "algo-trade-pipeline.yaml",
      "spec_name": "algo-trade-pipeline",
      "version": "1",
      "description": "Algorithmic trading DAG pipeline"
    }
  ],
  "cards": [ /* 全カード */ ],
  "dag_stage_groups": [ /* DAGステージグループ */ ]
}
```

### カード共通構造

全カードは以下の共通フィールドを持つ：

```json
{
  "id": "カードID",
  "category": "カテゴリ",
  "name": "表示名",
  "description": "説明",
  "source_spec": "spec名",
  "data": { /* カテゴリ固有のデータ */ }
}
```

**設計判断:** `metadata`キーを`data`に変更。より直感的で、「メタデータ」という曖昧な概念を排除。

### カード詳細スキーマ

#### check カード（CheckSpec → JSON）

```json
{
  "id": "check_ohlcv",
  "category": "check",
  "name": "check_ohlcv",
  "description": "Validate OHLCV DataFrame structure",
  "source_spec": "algo-trade-pipeline",
  "data": {
    "impl": "apps.algo-trade-pipeline.checks.feature_checks:check_ohlcv",
    "file_path": "checks/feature_checks.py",
    "input_type_ref": "OHLCVFrame",
    "spec_metadata": {
      "logic_steps": ["Step 1", "Step 2"],
      "implementation_hints": ["Hint 1"],
      "explicit_checks": ["Check 1"]
    }
  }
}
```

**マッピング:** CheckSpec の全フィールドを `data` 直下に配置（`id`, `description` 除く）

#### generator カード（GeneratorDef → JSON）

```json
{
  "id": "gen_ohlcv_frame",
  "category": "generator",
  "name": "gen_ohlcv_frame",
  "description": "Generate a resampled OHLCV frame",
  "source_spec": "algo-trade-pipeline",
  "data": {
    "impl": "apps.algo-trade-pipeline.generators.feature_engineering:generate_ohlcv_frame",
    "file_path": "generators/feature_engineering.py",
    "return_type_ref": "OHLCVFrame",
    "parameters": [
      {
        "name": "period",
        "type_ref": "builtins:int",
        "optional": false,
        "default": 14,
        "description": "Period for calculation"
      }
    ],
    "spec_metadata": { /* 同上 */ }
  }
}
```

**マッピング:** GeneratorDef の全フィールドを `data` 直下に配置

#### dtype_enum カード（EnumSpec → JSON）

```json
{
  "id": "CVMethod",
  "category": "dtype_enum",
  "name": "CVMethod",
  "description": "Cross-validation method types",
  "source_spec": "algo-trade-pipeline",
  "data": {
    "base_type": "str",
    "members": [
      {
        "name": "TIME_SERIES",
        "value": "TIME_SERIES",
        "description": "Time-series CV split"
      }
    ],
    "examples": [],
    "check_functions": []
  }
}
```

**マッピング:** EnumSpec の全フィールドを直接配置

#### dtype_pydantic カード（PydanticModelSpec → JSON）

```json
{
  "id": "MarketDataIngestionConfig",
  "category": "dtype_pydantic",
  "name": "MarketDataIngestionConfig",
  "description": "Configuration for market data ingestion",
  "source_spec": "algo-trade-pipeline",
  "data": {
    "fields": [
      {
        "name": "symbols",
        "type_ref": "list[builtins:str]",
        "optional": false,
        "default": null,
        "description": "List of trading symbols"
      }
    ],
    "base_class": "BaseModel",
    "examples": [],
    "check_functions": ["check_ingestion_config"]
  }
}
```

**マッピング:** PydanticModelSpec の全フィールドを直接配置（fieldsはそのまま）

#### dtype_alias カード（TypeAliasSpec → JSON）

```json
{
  "id": "AlignedFeatureTarget",
  "category": "dtype_alias",
  "name": "AlignedFeatureTarget",
  "description": "Aligned feature and target DataFrames",
  "source_spec": "algo-trade-pipeline",
  "data": {
    "type_def": {
      "alias_type": "tuple",
      "elements": [
        {"datatype_ref": "FeatureFrame"},
        {"datatype_ref": "TargetFrame"}
      ]
    },
    "examples": [],
    "check_functions": ["check_aligned_data"]
  }
}
```

**マッピング:** TypeAliasSpec の `type_def` をそのまま配置

#### dtype_frame カード（FrameSpec → JSON）

```json
{
  "id": "OHLCVFrame",
  "category": "dtype_frame",
  "name": "OHLCVFrame",
  "description": "OHLCV DataFrame with schema validation",
  "source_spec": "algo-trade-pipeline",
  "data": {
    "index": {
      "name": "timestamp",
      "dtype": "datetime",
      "nullable": false,
      "description": "Timestamp index"
    },
    "columns": [
      {
        "name": "open",
        "dtype": "float",
        "nullable": false,
        "description": "Open price"
      }
    ],
    "strict": false,
    "coerce": true,
    "check_functions": ["check_ohlcv"],
    "examples": []
  }
}
```

**マッピング:** FrameSpec の全フィールドを直接配置

#### dtype_generic カード（GenericSpec → JSON）

```json
{
  "id": "PredictionDataList",
  "category": "dtype_generic",
  "name": "PredictionDataList",
  "description": "List of prediction data points",
  "source_spec": "algo-trade-pipeline",
  "data": {
    "container": "list",
    "element_type": {"datatype_ref": "PredictionData"},
    "examples": [],
    "check_functions": ["check_prediction_data"]
  }
}
```

**マッピング:** GenericSpec の全フィールドを直接配置

#### example カード（ExampleCase → JSON）

```json
{
  "id": "ex_ingestion_config",
  "category": "example",
  "name": "ex_ingestion_config",
  "description": "Market data ingestion config example",
  "source_spec": "algo-trade-pipeline",
  "data": {
    "datatype_ref": "MarketDataIngestionConfig",
    "transform_ref": "",
    "input": {
      "symbols": ["USDJPY", "EURUSD"],
      "start_date": "2024-01-01",
      "end_date": "2024-01-31",
      "provider": "yahoo"
    },
    "expected": {
      "valid": true
    }
  }
}
```

**マッピング:** ExampleCase の全フィールドを直接配置

#### transform カード（TransformSpec → JSON）

```json
{
  "id": "fetch_yahoo_finance_ohlcv",
  "category": "transform",
  "name": "fetch_yahoo_finance_ohlcv",
  "description": "Fetch OHLCV data from Yahoo Finance API",
  "source_spec": "algo-trade-pipeline",
  "data": {
    "impl": "apps.algo-trade-pipeline.transforms.market_data:fetch_yahoo_finance_ohlcv",
    "file_path": "transforms/market_data.py",
    "return_type_ref": "ProviderBatchCollection",
    "parameters": [
      {
        "name": "config",
        "type_ref": "MarketDataIngestionConfig",
        "optional": false,
        "default": null,
        "description": ""
      }
    ],
    "default_args": {},
    "spec_metadata": { /* 同上 */ }
  }
}
```

**マッピング:** TransformSpec の全フィールドを直接配置

#### dag_stage カード（DAGStageSpec → JSON）

```json
{
  "id": "stage_market_data_fetch",
  "category": "dag_stage",
  "name": "stage_market_data_fetch",
  "description": "Fetch market data from provider",
  "source_spec": "algo-trade-pipeline",
  "data": {
    "selection_mode": "single",
    "max_select": null,
    "input_type": "MarketDataIngestionConfig",
    "output_type": "ProviderBatchCollection",
    "candidates": ["fetch_yahoo_finance_ohlcv"],
    "default_transform_id": "fetch_yahoo_finance_ohlcv",
    "publish_output": false,
    "collect_output": false
  }
}
```

**マッピング:** DAGStageSpec の全フィールドを直接配置（`stage_id` 除く）

## 実装計画

### Phase 1: 基本変換機能

**ファイル:** `spectool/core/export/card_exporter.py`

**関数:**
```python
def export_spec_to_cards(spec_ir: SpecIR, spec_file: str) -> dict[str, Any]:
    """SpecIRをJSONカード形式に変換

    Args:
        spec_ir: 正規化済みSpecIR
        spec_file: 元のspecファイル名（source_file用）

    Returns:
        {
            "metadata": {...},
            "cards": [...],
            "dag_stage_groups": []
        }
    """
```

**処理フロー:**
```
1. メタデータ抽出
2. checks カード生成
3. generators カード生成
4. datatypes カード生成（5種類統合）
5. examples カード生成
6. transforms カード生成
7. dag_stages カード生成
8. 統合JSON構築
```

### Phase 2: CLIコマンド追加

**ファイル:** `spectool/main.py`

```python
def export_cards(self, *specs: str, output: str = "frontend/public/cards") -> None:
    """Export YAML specs to JSON cards

    Args:
        *specs: Spec YAML files (e.g., specs/*.yaml)
        output: Output directory

    Example:
        python -m spectool export-cards specs/*.yaml --output frontend/public/cards
    """
```

**処理フロー:**
```
1. 出力ディレクトリ作成
2. 各specファイルをループ:
   a. load_spec() → SpecIR
   b. normalize_ir() → 正規化
   c. export_spec_to_cards() → カードJSON
   d. 統合データに追加
3. all-cards.json に書き込み
```

### Phase 3: Makefile統合

**追加ターゲット:**
```makefile
.PHONY: export-cards
export-cards:
	uv run python -m spectool export-cards specs/*.yaml --output frontend/public/cards
```

## 実装の詳細

### 基本変換ロジック

**原則: dataclassの直接JSON変換**

```python
from dataclasses import asdict

def spec_to_card(spec_obj, category: str, spec_name: str) -> dict:
    """SpecIR要素をカードに変換（共通処理）"""
    data = asdict(spec_obj)
    card_id = data.pop("id")
    description = data.pop("description", "")

    return {
        "id": card_id,
        "category": category,
        "name": card_id,
        "description": description,
        "source_spec": spec_name,
        "data": data  # 残りのフィールドを全て含める
    }
```

**設計判断:** `asdict()` を使用してdataclassを辞書化。不要な変換処理を排除。

### カテゴリ別処理

```python
def export_spec_to_cards(spec_ir: SpecIR, spec_file: str) -> dict:
    """SpecIRをカードJSONに変換"""
    spec_name = Path(spec_file).stem
    cards = []

    # 各カテゴリを処理
    for check in spec_ir.checks:
        cards.append(spec_to_card(check, "check", spec_name))

    for gen in spec_ir.generators:
        cards.append(spec_to_card(gen, "generator", spec_name))

    for frame in spec_ir.frames:
        cards.append(spec_to_card(frame, "dtype_frame", spec_name))

    for enum in spec_ir.enums:
        cards.append(spec_to_card(enum, "dtype_enum", spec_name))

    # ... 以下同様

    return {
        "metadata": {
            "spec_name": spec_ir.meta.name,
            "version": spec_ir.meta.version,
            "description": spec_ir.meta.description
        },
        "cards": cards
    }
```

### エラーハンドリング

```python
# 各specの処理は独立して失敗を許容
for spec_file in spec_files:
    try:
        ir = load_spec(spec_file)
        normalized = normalize_ir(ir)
        cards_data = export_spec_to_cards(normalized, spec_file)
        all_data.append(cards_data)
    except Exception as e:
        print(f"⚠️ Skipped {spec_file}: {e}")
        continue
```

## テスト計画

### テストケース

1. **基本変換テスト**
   - 各カテゴリのカード生成確認
   - メタデータの保存確認

2. **型情報テスト**
   - DataFrame, Enum, Pydantic, TypeAlias, Generic それぞれ
   - type_refのパース確認

3. **SpecMetadata テスト**
   - logic_steps, hints, checks の展開確認

4. **複数spec統合テスト**
   - specs/*.yaml 全ファイル処理
   - all-cards.json の構造検証

5. **後方互換性テスト**
   - 旧JSONスキーマとの互換性確認
   - フロントエンドでの表示確認

### テストファイル

```
spectool/tests/
└── test_card_exporter.py
```

## 実装の複雑度

**予想コード量:**
- `card_exporter.py`: ~100行（`asdict()` 活用で大幅削減）
- `main.py` 追加: ~30行
- Makefile追加: ~3行

**設計判断:** 旧実装（~600行）から大幅に簡素化。dataclass直接変換により冗長なヘルパー関数を排除。

## マイルストーン

- [ ] `spectool/core/export/__init__.py` 作成
- [ ] `spectool/core/export/card_exporter.py` 実装（~100行）
- [ ] `main.py` に `export_cards` コマンド追加
- [ ] Makefile に `export-cards` ターゲット追加
- [ ] テストコード作成（`test_card_exporter.py`）
- [ ] 全specでの動作確認
- [ ] フロントエンド側のスキーマ更新（必要に応じて）
- [ ] ドキュメント更新（README, CLAUDE.md）

## 参考

- 旧実装: `git show spec2code_v1:packages/spec2code/card_exporter.py` (~600行)
- 旧CLI: `git show spec2code_v1:main.py`
- 旧出力例: `frontend/public/cards/all-cards.json`

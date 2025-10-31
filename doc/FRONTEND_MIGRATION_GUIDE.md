# フロントエンド移行ガイド - Card Exporter スキーマ変更

## 概要

Card Exporterの新実装により、`all-cards.json`のスキーマが変更されました。
フロントエンド側で以下の修正が必要です。

## スキーマ変更点サマリー

| 変更項目 | 旧 | 新 | 影響度 |
|---------|----|----|--------|
| データキー | `metadata` | `data` | **高** |
| Checkカテゴリ | `"checks"` | `"check"` | **高** |
| 型定義カテゴリ | `"dtype"` | 5種類に分離 | **中** |

---

## 1. データキー名の変更 (metadata → data)

### 変更理由
より直感的な命名とするため、`metadata`（曖昧）から`data`（明確）に変更。

### 旧スキーマ
```json
{
  "id": "check_ohlcv",
  "category": "check",
  "name": "check_ohlcv",
  "description": "Validate OHLCV DataFrame",
  "source_spec": "algo-trade-pipeline",
  "metadata": {
    "impl": "apps.algo_trade_pipeline.checks:check_ohlcv",
    "file_path": "checks/feature_checks.py",
    "input_type_ref": "OHLCVFrame"
  }
}
```

### 新スキーマ
```json
{
  "id": "check_ohlcv",
  "category": "check",
  "name": "check_ohlcv",
  "description": "Validate OHLCV DataFrame",
  "source_spec": "algo-trade-pipeline",
  "data": {
    "impl": "apps.algo_trade_pipeline.checks:check_ohlcv",
    "file_path": "checks/feature_checks.py",
    "input_type_ref": "OHLCVFrame",
    "spec_metadata": {
      "logic_steps": [...],
      "implementation_hints": [...],
      "explicit_checks": [...]
    }
  }
}
```

---

## 2. 型定義カテゴリの分離

### 変更理由
フロントエンド側で型別のUI実装を可能にするため、カテゴリを細分化。

### 旧カテゴリ
- `"dtype"` - 全ての型定義を統合

### 新カテゴリ
- `"dtype_frame"` - DataFrame定義（pandera schema）
- `"dtype_enum"` - Enum定義
- `"dtype_pydantic"` - Pydanticモデル定義
- `"dtype_alias"` - 型エイリアス定義（tuple, union等）
- `"dtype_generic"` - Generic型定義（list, dict等）

### カテゴリ別の例

#### dtype_frame
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
      "nullable": false
    },
    "columns": [
      {"name": "open", "dtype": "float", "nullable": false},
      {"name": "high", "dtype": "float", "nullable": false},
      {"name": "low", "dtype": "float", "nullable": false},
      {"name": "close", "dtype": "float", "nullable": false},
      {"name": "volume", "dtype": "float", "nullable": false}
    ],
    "strict": false,
    "coerce": true,
    "check_functions": ["check_ohlcv"],
    "examples": []
  }
}
```

#### dtype_enum
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

#### dtype_pydantic
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
    "check_functions": []
  }
}
```

#### dtype_alias
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

#### dtype_generic
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
    "check_functions": []
  }
}
```

---

## 3. Checkカテゴリ名の変更

### 変更内容
- 旧: `"checks"` (複数形)
- 新: `"check"` (単数形)

### 変更理由
他のカテゴリ名との統一性向上（transform, example, generator等も単数形）。

---

## フロントエンド修正内容

### 修正ファイル: `frontend/components/card-library.tsx`

#### 1. convertJsonToCards関数の修正 (line 134)

**修正前:**
```typescript
const metadata = card.metadata || {}
```

**修正後:**
```typescript
const metadata = card.data || {}
```

#### 2. iconMapの修正 (line 122-130)

**修正前:**
```typescript
const iconMap: Record<string, any> = {
  "checks": CheckCircle,
  "dtype": FileType,
  "example": FileText,
  "transform": Shuffle,
  "dag": Workflow,
  "dag_stage": Workflow,
  "generator": Sparkles,
}
```

**修正後:**
```typescript
const iconMap: Record<string, any> = {
  "check": CheckCircle,           // checks → check
  "dtype_frame": FileType,        // 新規追加
  "dtype_enum": FileType,         // 新規追加
  "dtype_pydantic": FileType,     // 新規追加
  "dtype_alias": FileType,        // 新規追加
  "dtype_generic": FileType,      // 新規追加
  "example": FileText,
  "transform": Shuffle,
  "dag": Workflow,
  "dag_stage": Workflow,
  "generator": Sparkles,
}
```

#### 3. カテゴリ判定の修正 (複数箇所)

**修正前:**
```typescript
{selectedCard.category === "checks" && ...}
{selectedCard.category === "dtype" && ...}
```

**修正後:**
```typescript
{selectedCard.category === "check" && ...}
{selectedCard.category.startsWith("dtype") && ...}
```

#### 4. defaultCardsの修正 (line 57-117)

**修正前:**
```typescript
const defaultCards: CardDefinition[] = [
  {
    id: "check_example",
    name: "check_example",
    category: "checks",  // ← 修正
    ...
  },
  {
    id: "ExampleFrame",
    name: "ExampleFrame",
    category: "dtype",  // ← 修正
    ...
  },
]
```

**修正後:**
```typescript
const defaultCards: CardDefinition[] = [
  {
    id: "check_example",
    name: "check_example",
    category: "check",  // ← checks から check に変更
    ...
  },
  {
    id: "ExampleFrame",
    name: "ExampleFrame",
    category: "dtype_frame",  // ← dtype から dtype_frame に変更
    ...
  },
]
```

---

## テスト方法

1. バックエンドでカード生成
   ```bash
   make export-cards
   ```

2. フロントエンド起動
   ```bash
   cd frontend && npm run dev
   ```

3. 確認項目
   - [ ] カードライブラリページが正常に表示される
   - [ ] 各カテゴリのカードが表示される
   - [ ] カード詳細が正しく表示される
   - [ ] 型定義カード（dtype_*）が適切なアイコンで表示される
   - [ ] 検索・フィルタリングが動作する

---

## 補足

### SpecMetadata のサポート

新スキーマでは、CheckSpec、GeneratorDef、TransformSpecに `spec_metadata` フィールドが追加されました：

```json
"spec_metadata": {
  "logic_steps": ["Step 1", "Step 2"],
  "implementation_hints": ["Hint 1"],
  "explicit_checks": ["Check 1"]
}
```

これにより、実装者向けのメタ情報がフロントエンドで表示可能になります。
表示UIの実装は任意ですが、詳細パネルに追加すると便利です。

### 後方互換性

旧スキーマとの後方互換性は**ありません**。
フロントエンドの修正なしに新しいJSONを読み込むとエラーが発生します。

---

## まとめ

| 修正箇所 | 行数 | 難易度 | 必須 |
|---------|-----|--------|-----|
| convertJsonToCards | 1行 | 簡単 | ✅ |
| iconMap | 5行追加 | 簡単 | ✅ |
| カテゴリ判定 | 複数箇所 | 簡単 | ✅ |
| defaultCards | 数行 | 簡単 | ⚠️ (任意) |

**推定作業時間:** 15-30分

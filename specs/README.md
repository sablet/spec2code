# Spec仕様書記述ガイド

このディレクトリにはspectoolの仕様ファイル（YAML）を配置します。仕様ファイルは、データ型・変換処理・DAG構造を宣言的に記述し、システムが自動的にスケルトンコードを生成するための入力として使用されます。

## 目次

- [基本構造](#基本構造)
- [トップレベルフィールド](#トップレベルフィールド)
- [データ型定義（datatypes）](#データ型定義datatypes)
- [変換処理定義（transforms）](#変換処理定義transforms)
- [検証関数定義（checks）](#検証関数定義checks)
- [例示データ定義（examples）](#例示データ定義examples)
- [生成関数定義（generators）](#生成関数定義generators)
- [DAGステージ定義（dag_stages）](#dagステージ定義dag_stages)
- [型参照の記法](#型参照の記法)
- [命名規則](#命名規則)
- [制約事項](#制約事項)
- [ベストプラクティス](#ベストプラクティス)

---

## 基本構造

仕様ファイルは以下のトップレベルフィールドを持つYAML文書です：

```yaml
version: "1"
meta:
  name: "project_name"
  description: "Project description"

checks: [...]
examples: [...]
generators: [...]
datatypes: [...]
transforms: [...]
dag_stages: [...]
```

**必須フィールド**:
- `version`: 仕様バージョン（現在は `"1"` 固定）
- `meta.name`: プロジェクト名（`snake_case`推奨、生成されるディレクトリ名に使用）
- `datatypes`: データ型定義リスト
- `transforms`: 変換処理定義リスト

**オプションフィールド**:
- `meta.description`: プロジェクトの説明
- `checks`: 検証関数定義リスト
- `examples`: 例示データリスト
- `generators`: データ生成関数定義リスト
- `dag_stages`: DAGステージ定義リスト

---

## トップレベルフィールド

### version

仕様フォーマットのバージョン番号。現在は `"1"` のみサポート。

```yaml
version: "1"
```

### meta

プロジェクトのメタデータ。

```yaml
meta:
  name: "algo_trade_pipeline"
  description: "Algorithmic trading pipeline with advanced type features"
```

**フィールド**:
- `name` (必須): プロジェクト名（`snake_case`推奨）。`apps/{name}/` ディレクトリに生成される
- `description` (オプション): プロジェクトの説明

**制約**:
- `name` は有効なPythonモジュール名として使用できる必要がある
- ハイフン `-` は避け、アンダースコア `_` を使用すること

---

## データ型定義（datatypes）

データ型は以下のいずれかの形式で定義できます：

1. **Pydanticモデル** (`pydantic_model`)
2. **型エイリアス** (`type_alias`)
3. **Enum型** (`enum`)
4. **Generic型** (`generic`)

### 共通フィールド

すべてのデータ型定義に共通するフィールド：

```yaml
- id: TypeName
  description: "型の説明"
  check_functions:
    - check_function_id
  examples:
    - {...}
```

**フィールド**:
- `id` (必須): 型のID（`PascalCase`推奨）
- `description` (オプション): 型の説明
- `check_functions` (オプション): この型を検証するcheck関数のIDリスト
- `examples` (オプション): 検証用の例示データ

### Pydanticモデル定義

構造化されたデータモデルを定義します。

```yaml
- id: MarketDataIngestionConfig
  description: "市場データ取得設定"
  pydantic_model:
    fields:
      - name: symbols
        type:
          generic:
            container: list
            element_type:
              native: "builtins:str"
        description: "取引シンボルリスト"
      - name: start_date
        type:
          native: "builtins:str"
        description: "開始日 (YYYY-MM-DD)"
      - name: provider
        type:
          native: "builtins:str"
        default: "yahoo"
        description: "データプロバイダ名"
```

**フィールドの型定義**:

各フィールドは `type` フィールドで型を指定します：

- **ネイティブ型**: `native: "module:TypeName"`
  ```yaml
  type:
    native: "builtins:str"
  ```

- **データ型参照**: `datatype_ref: TypeID`
  ```yaml
  type:
    datatype_ref: CVMethod
  ```

- **Generic型**: `generic`
  ```yaml
  type:
    generic:
      container: list
      element_type:
        native: "builtins:str"
  ```

**フィールド属性**:
- `name` (必須): フィールド名
- `type` (必須): 型定義
- `description` (オプション): フィールドの説明
- `optional` (オプション): `true` の場合、`Optional[T]` となる
- `default` (オプション): デフォルト値

### 型エイリアス定義

既存の型に別名を付けます。

**単純なエイリアス**:

```yaml
- id: OHLCVFrame
  description: "OHLCV DataFrame"
  type_alias:
    type: simple
    target: "pandas:DataFrame"
```

**タプル型エイリアス**:

```yaml
- id: AlignedFeatureTarget
  description: "アラインされた特徴量とターゲット"
  type_alias:
    type: tuple
    elements:
      - datatype_ref: FeatureFrame
      - datatype_ref: TargetFrame
```

**フィールド**:
- `type`: `"simple"` または `"tuple"`
- `target` (単純型の場合): ターゲット型参照
- `elements` (タプル型の場合): 要素型のリスト

### Enum型定義

列挙型を定義します。

```yaml
- id: CVMethod
  description: "クロスバリデーション方法"
  enum:
    base_type: str
    members:
      - name: TIME_SERIES
        value: "TIME_SERIES"
        description: "時系列CV分割"
      - name: EXPANDING_WINDOW
        value: "EXPANDING_WINDOW"
        description: "拡張ウィンドウ分割"
```

**フィールド**:
- `base_type`: 基底型（`"str"`, `"int"`, `"float"`）
- `members`: メンバーリスト
  - `name` (必須): メンバー名
  - `value` (必須): メンバー値
  - `description` (オプション): 説明

### Generic型定義

コンテナ型を定義します。

**リスト型**:

```yaml
- id: PredictionDataList
  description: "予測データリスト"
  generic:
    container: list
    element_type:
      datatype_ref: PredictionData
```

**辞書型**:

```yaml
- id: SimpleLGBMParams
  description: "LightGBMパラメータ辞書"
  generic:
    container: dict
    key_type:
      native: "builtins:str"
    value_type:
      native: "typing:Any"
```

**フィールド**:
- `container`: `"list"`, `"dict"`, `"set"`, `"tuple"`
- `element_type` (list/set/tupleの場合): 要素型
- `key_type` (dictの場合): キー型
- `value_type` (dictの場合): 値型

### DataFrame型定義（拡張）

DataFrameの構造を詳細に定義する場合、`dataframe_schema` と `schema` を使用できます。

```yaml
- id: OHLCVFrame
  description: "OHLCV DataFrame"
  type_alias:
    type: simple
    target: "pandas:DataFrame"
  dataframe_schema:
    index:
      name: timestamp
      dtype: datetime
      nullable: false
    columns:
      - name: open
        dtype: float
        nullable: false
        description: "始値"
      - name: high
        dtype: float
        nullable: false
      - name: low
        dtype: float
        nullable: false
        checks:
          - type: ge
            value: 0
            description: "最低価格は非負"
    strict: false
    coerce: true
    ordered: false
  schema:
    type: array
    items:
      type: object
      properties:
        timestamp:
          type: string
          format: date-time
        open:
          type: number
        high:
          type: number
```

**dataframe_schema フィールド**:
- `index`: Index定義
- `columns`: Columnリスト
- `strict`: 未定義カラムを許可しない
- `coerce`: 型強制
- `ordered`: カラム順序を強制

**schema フィールド**:
- JSONスキーマ形式で行データを定義

---

## 変換処理定義（transforms）

DAGの処理ノードを定義します。

```yaml
- id: fetch_yahoo_finance_ohlcv
  description: "Yahoo Finance APIからOHLCVデータを取得"
  impl: "apps.algo_trade_pipeline.transforms.market_data:fetch_yahoo_finance_ohlcv"
  file_path: "transforms/market_data.py"
  parameters:
    - name: config
      datatype_ref: MarketDataIngestionConfig
  return_type_ref: ProviderBatchCollection
```

**必須フィールド**:
- `id`: Transform ID
- `impl`: 実装関数の完全修飾名（`"module.path:function_name"`）
- `file_path`: 生成先ファイルパス（`apps/{name}/` からの相対パス）

**オプションフィールド**:
- `description`: 説明（日本語推奨）
- `parameters`: パラメータリスト
  - `name` (必須): パラメータ名
  - `datatype_ref` または `native`: 型参照
  - `optional`: オプション引数か
  - `default`: デフォルト値
  - `literal`: リテラル値リスト（選択肢）
- `return_type_ref`: 戻り値型参照
- `spec_metadata`: 実装者向けのヒント（実装ステップ、注意点、依存関係など）。詳細は下記参照

### spec_metadata（推奨）

実装者向けのヒントを記述できます。**すべての関数（transforms, checks, generators）で統一されたスキーマを使用します**：

```yaml
spec_metadata:
  logic_steps:
    - "各プロバイダバッチからDataFrameを抽出"
    - "カラム名を標準OHLCV形式にマッピング (open, high, low, close, volume)"
    - "タイムスタンプをUTC datetime形式に変換する (pd.to_datetime().tz_localize('UTC'))"
    - "データの完全性を検証し、OHLC値が欠損している行を削除"
    - "すべての正規化されたDataFrameを単一の結果に結合 (pd.concat())"
  implementation_hints:
    - "pandasでDataFrame操作、datetimeでタイムスタンプ変換を行う"
    - "プロバイダ固有のカラムマッピングは設定ファイルまたはルックアップテーブルが必要な可能性"
    - "UTC変換によりプロバイダ間のタイムゾーン一貫性を確保"
```

**フィールド説明**:
- `logic_steps` (必須): 実装すべきロジックのステップを順序立てて記述。「何をするか」に焦点を当てる。**日本語で記述することを推奨**
- `implementation_hints` (必須): 実装のヒント、注意点、依存ライブラリ、制約など。「どう実装するか」に焦点を当てる。**日本語で記述することを推奨**
- `explicit_checks` (オプション、デフォルト空リスト): 実装時に追加すべき検証を明示。**空リスト省略可能**
  - **省略または空リスト**: 素朴に実装、pandas/numpyの標準例外に任せる
  - **記述あり**: 記載された検証のみ追加、それ以外の防御的チェックは追加しない

**設計方針**:
- **日本語推奨**: レビューしやすくするため、`logic_steps`と`implementation_hints`は日本語で記述することを推奨
- **仕様と実装の分離**: `logic_steps`は仕様レベル、`implementation_hints`は実装レベル
- **擬似コードの排除**: 詳細な擬似コードは実装者の創意工夫の余地を残すため記述しない
- **シンプル性の重視**: 複雑度や依存関係は`implementation_hints`に統合し、スキーマを簡潔に保つ
- **暗黙的挙動の排除**: `explicit_checks`により「記載された検証のみ」を徹底し、勝手な補正・フォールバックを防止

**spec_metadata での重要な情報（transforms 特有）**:
- `logic_steps`: **ビジネスロジックの処理フローを記述**（例: データ抽出 → 変換 → 集約 → 結合）
- `implementation_hints`:
  - 依存ライブラリとその使用目的
  - データ変換のエッジケース処理（欠損値、異常値、境界条件）
  - 外部リソースやAPI呼び出しに関する注意事項
  - パフォーマンス最適化のポイント（大規模データ処理時）
- `explicit_checks`:
  - 特定の入力検証が必要な場合のみ記述
  - 記載された検証以外の防御的if文は追加しない

**explicit_checks の記述例**:

```yaml
# 素朴な実装（検証なし）
spec_metadata:
  logic_steps:
    - "close価格の前日比変化を計算"
    - "RSI計算式を適用"
  implementation_hints:
    - "taライブラリ推奨"
  # explicit_checks は省略可（デフォルト空リスト = 素朴な実装）

# 特定の検証のみ追加
spec_metadata:
  logic_steps:
    - "APIに接続してデータ取得"
  implementation_hints:
    - "yfinanceライブラリ使用"
  explicit_checks:
    - "symbols リストが空でないことを確認 → ValueError('Empty symbols list')"
    - "start_date < end_date を確認 → ValueError('Invalid date range')"
```

### スケルトン生成時の docstring フォーマット

#### explicit_checks が空（省略）の場合

```python
def calculate_rsi(df: OHLCVFrame, period: int = 14) -> FeatureFrame:
    """
    Calculate RSI indicator

    Policy: Implement straightforwardly without defensive checks or custom exception handling

    Logic steps:
    - close価格の前日比変化を計算
    - RSI計算式を適用

    Implementation hints:
    - taライブラリ推奨
    - period期間分の初期NaNが発生
    """
    # TODO: Implement
    raise NotImplementedError
```

#### explicit_checks に記載がある場合

```python
def fetch_data(config: Config) -> Data:
    """
    Fetch data from API

    Explicit checks (validate only these):
    - symbols リストが空でないことを確認 → ValueError('Empty symbols')
    - start_date < end_date を確認 → ValueError('Invalid date range')

    Do NOT add other defensive checks beyond what is explicitly listed above.

    Logic steps:
    - APIに接続してデータ取得

    Implementation hints:
    - yfinanceライブラリ使用
    """
    # TODO: Implement with explicit checks
    raise NotImplementedError
```

**explicit_checks の記述フォーマット**:
```
"<条件説明> → <例外名>('<エラーメッセージ>')"
```

**具体例**:
```yaml
explicit_checks:
  - "空のDataFrameを処理しない → ValueError('Empty DataFrame')"
  - "period < 1 を補正しない → ValueError('Invalid period: {period}')"
  - "'close'列なしで処理しない → KeyError('close column required')"
  - "symbols リストが空でないことを確認 → ValueError('Empty symbols list')"
```

**フォーマットの意図**:
- **何をチェックするか**: 条件説明（左側）
- **どう失敗するか**: 例外名とメッセージ（右側）
- **排他性**: 記載されたもの以外は追加しない

---

**🚨 重要な警告**:

`explicit_checks` に記載された検証**以外**の防御的チェックは追加しないでください。

**NG例**（勝手な補正・フォールバック）:
```python
# ❌ 仕様にない防御的コード
if df.empty:
    return pd.DataFrame()  # 空を空で返す

if period < 1:
    period = 14  # デフォルト値で補正

# ❌ 勝手なエラーハンドリング
try:
    result = some_operation()
except Exception:
    return None  # エラーを握りつぶす
```

**OK例**（素朴な実装）:
```python
# ✅ pandas/numpyの標準例外に任せる
result = df['close'].rolling(window=period).mean()  # period < 1 なら自然にエラー
```

これにより、**仕様と実装の乖離を防ぎ、予測可能で保守性の高いコード生成**を実現します。

---

## 検証関数定義（checks）

データ検証関数を定義します。

```yaml
- id: check_ohlcv
  description: "OHLCV価格制約と時系列異常を検証"
  impl: "apps.algo_trade_pipeline.checks.feature_checks:check_ohlcv"
  file_path: "checks/feature_checks.py"
  input_type_ref: OHLCVFrame
  spec_metadata:
    logic_steps:
      - "np.isinf(df.select_dtypes(include=[np.number])).any().any() で Inf値検出"
      - "df.index.duplicated().any() でインデックス重複チェック"
      - "(df['high'] >= df[['open', 'close']].max(axis=1)).all() で価格上限制約"
      - "(df['low'] <= df[['open', 'close']].min(axis=1)).all() で価格下限制約"
      - "df['close'].pct_change().abs() > 0.5 で異常変動率検出"
    implementation_hints:
      - "価格制約: max(axis=1)/min(axis=1) で行ごとの最大・最小を取得して比較"
      - "時系列ギャップ: mode() で最頻値を期待頻度とし、その2倍を閾値とする"
      - "dataframe_schemaでカラム存在・dtype・NaN・単調性は既にカバー済み"
```

**必須フィールド**:
- `id`: Check ID
- `impl`: 実装関数の完全修飾名
- `file_path`: 生成先ファイルパス

**オプションフィールド**:
- `description`: 説明（日本語推奨）
- `input_type_ref`: 入力型参照
- `spec_metadata`: 実装者向けのヒント。transforms と同じスキーマ（`logic_steps` + `implementation_hints`）を使用

**spec_metadata での重要な情報（checks 特有）**:
- `logic_steps`: **検証すべき条件を具体的なコードレベルで記述**（例: `df.isnull().any()`, `len(x) > 0`）
- `implementation_hints`:
  - 検証閾値の根拠（なぜその値を使うか）
  - dataframe_schema や Pydantic で既にカバーされている検証との重複を避けるための注意
  - エッジケースやデータ特性に応じた調整ポイント

---

## 例示データ定義（examples）

データ型の検証用サンプルデータを定義します。

```yaml
- id: ex_ingestion_config
  description: "市場データ取得設定の例"
  datatype_ref: MarketDataIngestionConfig
  input:
    symbols: ["USDJPY", "EURUSD"]
    start_date: "2024-01-01"
    end_date: "2024-01-31"
    provider: "yahoo"
  expected:
    valid: true
```

**必須フィールド**:
- `id`: Example ID
- `datatype_ref`: 対象データ型のID
- `input`: サンプル入力データ

**オプションフィールド**:
- `description`: 説明
- `expected`: 期待される出力・検証結果

---

## 生成関数定義（generators）

テストデータやモックデータを生成する関数を定義します。

```yaml
- id: gen_ohlcv_frame
  description: "リサンプルされたOHLCVフレームを生成"
  impl: "apps.algo_trade_pipeline.generators.feature_engineering:generate_ohlcv_frame"
  file_path: "generators/feature_engineering.py"
  return_type_ref: OHLCVFrame
  spec_metadata:
    logic_steps:
      - "1時間頻度でdatetimeインデックスを作成"
      - "価格制約を満たす現実的なOHLCV値を生成"
      - "high >= max(open, close) かつ low <= min(open, close) を保証"
      - "オプションでランダムな整数値のvolume列を追加"
    implementation_hints:
      - "pandasとnumpyを使用して効率的にデータ生成"
      - "テストデータの現実性のため価格制約を維持する必要がある"
```

**必須フィールド**:
- `id`: Generator ID
- `impl`: 実装関数の完全修飾名
- `file_path`: 生成先ファイルパス
- `return_type_ref`: 戻り値型参照

**オプションフィールド**:
- `description`: 説明（日本語推奨）
- `parameters`: パラメータリスト
- `spec_metadata`: 実装者向けのヒント。transforms と同じスキーマ（`logic_steps` + `implementation_hints`）を使用

**spec_metadata での重要な情報（generators 特有）**:
- `logic_steps`: **データ生成の手順を順序立てて記述**（例: インデックス作成 → 値生成 → 制約適用）
- `implementation_hints`:
  - テストデータとして現実的な値の範囲や分布
  - 生成データが満たすべき制約条件（price constraints, 時系列順序など）
  - パフォーマンス考慮事項（大量データ生成時のメモリ効率など）

---

## DAGステージ定義（dag_stages）

DAGの実行ステージを定義します。各ステージは入力型から出力型への変換を行います。

```yaml
- stage_id: "data_fetch"
  description: "プロバイダから市場データを取得"
  selection_mode: "single"
  input_type: MarketDataIngestionConfig
  output_type: ProviderBatchCollection
  candidates:
    - fetch_yahoo_finance_ohlcv
```

**必須フィールド**:
- `stage_id`: ステージID
- `selection_mode`: 選択モード
  - `"single"`: 1つのtransformのみ選択
  - `"exclusive"`: 1つのtransformを選択（複数候補から）
  - `"multiple"`: 複数のtransformを選択可能
- `input_type`: 入力型ID
- `output_type`: 出力型ID
- `candidates`: 使用可能なtransform IDリスト

**オプションフィールド**:
- `description`: 説明
- `max_select`: 最大選択数（`multiple` モード時）
- `default_transform_id`: デフォルトtransform ID
- `publish_output`: 出力を公開するか
- `collect_output`: 出力を収集するか（最終結果として保存）

### selection_mode の詳細

- **single**: 常に1つのtransformを実行（候補が1つのみの場合）
- **exclusive**: 複数候補から1つを選択して実行
- **multiple**: 複数のtransformを並列または連続実行
  - 例: 複数のテクニカル指標を同時に計算

---

## 型参照の記法

### ネイティブ型参照

Pythonの組み込み型やライブラリ型を参照する場合：

```yaml
native: "module:TypeName"
```

**例**:
- `"builtins:str"` → `str`
- `"builtins:int"` → `int`
- `"builtins:float"` → `float`
- `"builtins:bool"` → `bool`
- `"typing:Any"` → `Any`
- `"pandas:DataFrame"` → `DataFrame`
- `"pandas:Series"` → `Series`
- `"datetime:datetime"` → `datetime`

### データ型参照

同じ仕様内で定義されたデータ型を参照する場合：

```yaml
datatype_ref: TypeID
```

**例**:
```yaml
type:
  datatype_ref: MarketDataIngestionConfig
```

### Generic型の型参照

Generic型のネスト：

```yaml
type:
  generic:
    container: list
    element_type:
      generic:
        container: dict
        key_type:
          native: "builtins:str"
        value_type:
          datatype_ref: PredictionData
```

---

## 命名規則

### ID命名規則

- **データ型ID**: `PascalCase`（例: `MarketDataIngestionConfig`, `OHLCVFrame`）
- **Transform ID**: `snake_case`（例: `fetch_yahoo_finance_ohlcv`, `calculate_rsi`）
- **Check ID**: `snake_case`（例: `check_ingestion_config`, `check_ohlcv`）
- **Example ID**: `ex_` プレフィックス + `snake_case`（例: `ex_ingestion_config`）
- **Generator ID**: `gen_` プレフィックス + `snake_case`（例: `gen_provider_batches`）
- **Stage ID**: `snake_case`（例: `data_fetch`, `model_training`）

### メタデータ命名規則

- **meta.name**: `snake_case`（例: `algo_trade_pipeline`）

---

## 制約事項

### 必須要件

1. **meta.name の一意性**: プロジェクト名は一意である必要がある
2. **ID の一意性**: 各カテゴリ内でIDは一意である必要がある
3. **型参照の整合性**: 参照されるデータ型は定義されている必要がある
4. **impl パスの一貫性**: `impl` フィールドは `file_path` と整合性がある必要がある
   - 例: `impl: "apps.project.transforms.foo:bar"` → `file_path: "transforms/foo.py"`

### 型定義の制約

1. **データ型は以下のいずれか1つの形式のみを持つ**:
   - `pydantic_model`
   - `type_alias`
   - `enum`
   - `generic`

2. **循環参照の禁止**: データ型定義に循環参照があってはならない

3. **DAGの非循環性**: `dag_stages` で定義されるDAGは非循環である必要がある

### ファイル生成の制約

1. **既存ファイルの保護**: スケルトン生成は既存ファイルを上書きしない
2. **ファイルパスの相対性**: `file_path` は `apps/{meta.name}/` からの相対パスである必要がある

---

## ベストプラクティス

### 1. 型定義を先に行う

データ型を先に定義し、その後transformやcheckを定義することで、型の一貫性を保ちやすくなります。

### 2. 説明を充実させる

`description` フィールドを積極的に使用し、生成されるdocstringを充実させます。**レビューしやすくするため、日本語で記述することを推奨します**。

### 3. 例示データを提供する

`examples` を定義することで、データ型の検証が自動化されます。

### 4. spec_metadata を活用する

`spec_metadata` に実装ステップ (`logic_steps`) と実装ヒント (`implementation_hints`) を記述することで、実装者への明確なガイダンスを提供できます。仕様レベルの「何をするか」と実装レベルの「どう実装するか」を分離して記述することで、実装者の理解を助けます。

### 5. DAGステージの粒度

DAGステージは単一責任の原則に従い、各ステージが明確な役割を持つようにします。

### 6. チーム協業

仕様ファイルをバージョン管理に含め、チーム全体で仕様をレビューしてから実装を開始します。

### 7. 継続的な検証

`make validate` を定期的に実行し、仕様と実装の整合性を保ちます。

### 8. ファイルの分割

大規模なプロジェクトでは、機能ごとにファイルパスを分割し、モジュール構造を明確にします。

---

## スキーマ変更の検出

このディレクトリには `.schema_snapshot.json` ファイルがあり、IRスキーマの構造をハッシュ値で記録しています。

### スキーマ変更時の手順

`spectool/spectool/core/base/ir.py` を変更した場合：

1. **変更を検証する**:
   ```bash
   make test-schema-sync
   ```

2. **README.mdを更新する**:
   - 追加されたフィールド: ドキュメントに追加
   - 削除されたフィールド: ドキュメントから削除
   - 変更されたフィールド: ドキュメントを更新

3. **スナップショットを更新する**:
   ```bash
   make update-schema-snapshot
   ```

4. **変更をコミットする**:
   ```bash
   git add specs/README.md specs/.schema_snapshot.json
   git commit -m "docs: Update spec README for schema changes"
   ```

### CI/CDでの自動チェック

GitHub ActionsでPR作成時に自動的にスキーマとドキュメントの同期状態をチェックします。スキーマが変更されているのにREADMEが更新されていない場合、PRに警告コメントが追加されます。

---

## サンプル仕様

完全なサンプル仕様は以下を参照してください：

- `algo-trade-pipeline.yaml`: 複雑なDAGパイプラインの例
- `test_metadata.yaml`: メタデータ検証用の最小例

---

## 参照

- プロジェクトルートの `CLAUDE.md`: 開発ワークフロー全体のガイド
- `spectool/spectool/core/base/ir.py`: 内部中間表現（IR）のデータ構造定義
  - `SpecIR`: 統合IR（中間表現）のルートデータ構造
  - `MetaSpec`: プロジェクトメタデータ
  - `FrameSpec`: DataFrame型定義
  - `EnumSpec`: Enum型定義
  - `PydanticModelSpec`: Pydanticモデル定義
  - `TypeAliasSpec`: 型エイリアス定義
  - `GenericSpec`: Generic型定義
  - `TransformSpec`: Transform関数定義
  - `DAGStageSpec`: DAGステージ定義
  - `CheckSpec`: Check関数定義
  - `ExampleCase`: 例示データ定義
  - `GeneratorDef`: Generator関数定義
- `spectool/spectool/core/engine/loader.py`: YAML仕様のロード処理
- `spectool/spectool/core/engine/validate_ir.py`: IR検証ロジック

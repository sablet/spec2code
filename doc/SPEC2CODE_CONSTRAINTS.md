# algo-trade-pipeline spec2code表現の制約と課題

## 概要

`specs/algo-trade-pipeline-v2.yaml`は、DAG_PIPELINE_DESIGN.mdで定義されたalgo-tradeパイプラインをspec2code形式で表現したものです。本ドキュメントは、spec2codeで対応済みの機能と、まだ表現できない部分を整理します。

## v1からv2への改善点

### ✅ 新たに活用した機能（type-extension-demo.yamlより）

1. **Enum型**: `enum`フィールドで直接定義可能
2. **Pydanticモデル**: `pydantic_model`フィールドで構造化データ型を定義
3. **Tuple型**: `type_alias.type: tuple`でタプル型を表現
4. **Generic型**: `generic.container: list|dict`でジェネリック型を表現
5. **Type Alias**: `type_alias.type: simple`でpandas DataFrameなどのエイリアスを定義
6. **Literal型**: パラメータの`literal`フィールドで選択肢を制限

## 表現可能な部分

### ✅ 正常に表現可能

1. **Enum型定義**:
```yaml
- id: PositionSignal
  enum:
    base_type: int
    members:
      - name: BUY
        value: 1
```

2. **Pydanticモデル定義**:
```yaml
- id: SimpleCVConfig
  pydantic_model:
    fields:
      - name: n_splits
        type:
          native: "builtins:int"
        default: 5
```

3. **Tuple型**:
```yaml
- id: AlignedFeatureTarget
  type_alias:
    type: tuple
    elements:
      - native: "pandas:DataFrame"
      - native: "pandas:DataFrame"
```

4. **List型（Generic）**:
```yaml
- id: PredictionDataList
  generic:
    container: list
    element_type:
      datatype_ref: PredictionData
```

5. **Dict型（Generic）**:
```yaml
- id: SimpleLGBMParams
  generic:
    container: dict
    key_type:
      native: "builtins:str"
    value_type:
      native: "typing:Any"
```

6. **Type Alias**:
```yaml
- id: MultiAssetOHLCVFrame
  type_alias:
    type: simple
    target: "pandas:DataFrame"
```

7. **Literal型（パラメータ）**:
```yaml
parameters:
  - name: method
    literal:
      - "momentum"
      - "mean_reversion"
```

## 残存する制約

### ❌ 1. Helper関数（非@transform）のDAG統合不可

**問題**: spec2codeのDAGは`@transform`関数のみを対象とし、Helper関数を含められない

**該当箇所**:
```python
# 非@transform関数（元設計ではDAGに含めない方針）
select_features(df, feature_specs) -> FeatureFrame
extract_target(df, symbol, column) -> TargetFrame
clean_and_align(features, target) -> AlignedFeatureTarget
```

**現状の表現**:
```yaml
# dag_stagesにコメントのみ記載
# Phase 3: Model Training & Prediction
# NOTE: Between Phase 2 and 3, helper functions (select_features, extract_target, clean_and_align)
# are manually called to produce AlignedFeatureTarget (tuple type)
- stage_id: "model_training"
  input_type: AlignedFeatureTarget  # 手動生成が前提
```

**問題点**: DAG実行時にhelper関数の呼び出しタイミングを制御できない。手動実装が必要。

**推奨解決策**:
- オプション1: Helper関数も`@transform`化してDAGに組み込む
- オプション2: spec2codeに「manual_step」ステージタイプを追加し、手動実装箇所を明示

---

### ⚠️ 2. 動的型付けDataFrameの部分的表現

**問題**: Phase 2のインジケータ計算では、DataFrameの列が実行時に動的に追加される

**該当箇所**:
```python
# calculate_rsi: DataFrame → DataFrame (+ rsi_14列)
# calculate_adx: DataFrame → DataFrame (+ adx_14列)
# パイプライン実行時に列が追加されていく
```

**v2での改善**:
```yaml
# type_aliasを使ってOHLCVFrameとして型を明示
- id: OHLCVFrame
  type_alias:
    type: simple
    target: "pandas:DataFrame"

# dag_stagesでも型を明示
- stage_id: "indicator_calculation"
  input_type: OHLCVFrame   # pandas DataFrame
  output_type: OHLCVFrame  # 同じエイリアス（実行時に列が追加される）
```

**残る問題**: 型エイリアスは同じだが、実際の列構成は異なる。静的解析での検証は不完全。

**推奨解決策**:
- オプション1: 各Transform後の型を明示的に定義（例: `OHLCVFrameWithRSI`, `OHLCVFrameWithRSIAndADX`）
- オプション2: Check関数で実行時に列の存在を検証する

---

### ⚠️ 3. pandas MultiIndex DataFrameの詳細検証不可

**問題**: MultiIndex構造（階層的カラム名）の詳細はJSON Schemaで表現不可能

**該当箇所**:
```python
# MultiAssetOHLCVFrame
# MultiIndex: [(symbol, column)] 例: (USDJPY, rsi_14), (SPY, adx_14)
```

**v2での改善**:
```yaml
# type_aliasで型を明示
- id: MultiAssetOHLCVFrame
  check_ids:
    - check_multiasset_frame  # Check関数で詳細検証
  type_alias:
    type: simple
    target: "pandas:DataFrame"
```

**残る問題**: MultiIndexの階層構造、レベル名、インデックス型などの詳細はCheck関数に完全依存。

**推奨解決策**: pandas固有の型システムを別途定義するか、`pandera`ライブラリとの統合を検討。

---

### ❌ 4. 複数入力Transform（join/merge）の表現不可

**問題**: 現在のspec2codeは単一入力Transformのみを想定

**該当箇所（将来的な課題）**:
```python
# 例: 複数データソースのマージ
def merge_features_and_targets(
    features: FeatureFrame,
    targets: TargetFrame,
    metadata: MetaData
) -> MergedFrame:
    ...
```

**現状の表現**: 表現不可能。AlignedFeatureTarget（tuple型）を単一オブジェクトとして扱う回避策を使用。

**推奨解決策**: `parameters`に複数のinput型を許可し、DAGエッジも複数の`from`を持てるように拡張。

---

## 実装時の推奨ガイドライン

### 1. 型定義の優先順位

```yaml
# v2での推奨パターン
# 1. Pydanticモデル（構造化データ）
- id: SimpleCVConfig
  pydantic_model:
    fields: [...]

# 2. Enum型（選択肢が固定）
- id: PositionSignal
  enum:
    base_type: int
    members: [...]

# 3. Generic型（List, Dict）
- id: PredictionDataList
  generic:
    container: list
    element_type:
      datatype_ref: PredictionData

# 4. Type Alias（pandas DataFrame等）
- id: OHLCVFrame
  type_alias:
    type: simple
    target: "pandas:DataFrame"

# 5. JSON Schema（上記で表現できない場合のみ）
- id: CustomData
  schema:
    type: object
```

### 2. Helper関数の明示的な実装

```python
# DAG実行後の手動ステップとして実装
# v2ではAlignedFeatureTargetがtupleとして正しく型定義されている
features = select_features(with_target, feature_specs)
target = extract_target(with_target, symbol="USDJPY", column="target")
aligned: tuple[pd.DataFrame, pd.DataFrame] = clean_and_align(features, target)
```

### 3. Check関数での詳細検証

```python
# MultiIndex構造や動的列の詳細検証はCheck関数で実装
def check_multiasset_frame(df: pd.DataFrame) -> bool:
    """MultiIndex構造の詳細検証"""
    assert isinstance(df.columns, pd.MultiIndex), "Columns must be MultiIndex"
    assert df.columns.nlevels == 2, "MultiIndex must have 2 levels (symbol, column)"
    return True
```

---

## v1からv2での改善サマリ

### ✅ 解決された課題（6項目）

| 項目 | v1での問題 | v2での解決策 |
|-----|----------|------------|
| Tuple型 | Object型で代替、型ミスマッチ | `type_alias.type: tuple`で正確に表現 |
| List型 | 二重定義（DataとDataList） | `generic.container: list`で統一 |
| Enum型 | string型で代替、値が不一致 | `enum`フィールドで正確に定義 |
| Pydanticモデル | JSON Schemaで代替 | `pydantic_model`で構造化データを表現 |
| Dict型 | 柔軟性なし | `generic.container: dict`で表現 |
| Literal型 | パラメータ選択肢を表現不可 | `literal`フィールドで選択肢を制限 |

### ⚠️ 残存する課題（4項目）

1. **Helper関数のDAG統合**: 手動実装が必要（設計方針の問題）
2. **動的型DataFrame**: 型エイリアスは同じだが列構成が異なる
3. **MultiIndex詳細検証**: Check関数に完全依存
4. **複数入力Transform**: エンジンの拡張が必要

---

## 今後の拡張提案

### spec2codeエンジンへの要望

1. **Manual step**: DAGに含めない手動実装箇所を構造化データとして明示
2. **複数入力Transform**: join/merge操作のネイティブサポート
3. **Column-aware DataFrame**: `DataFrame[ColumnSet]`のような型パラメータ化
4. **pandas型システム拡張**: `pandera`スキーマとの統合

### algo-trade-pipeline固有の改善

1. **Helper関数の@transform化**: `select_features`等を正式なTransformとしてDAGに組み込む
2. **動的型の段階的定義**: OHLCVFrame → OHLCVFrameWithRSI → OHLCVFrameWithRSIAndADX
3. **テストカバレッジ拡充**: example_idsを各フェーズで追加

---

## まとめ

### 表現可能率の向上

- **v1**: 約70% (Tuple, List, Enumを回避策で対応)
- **v2**: 約90% (type-extension機能を活用して正確に表現)

### 手動実装が必要な範囲

- **Helper関数**: select_features, extract_target, clean_and_align（約5%）
- **詳細型検証**: MultiIndex構造、動的列（約5%）

### 推奨アプローチ

1. **v2仕様を使用**: `pydantic_model`, `enum`, `generic`, `type_alias`, `literal`を活用
2. **Check関数で補完**: pandas固有の構造や動的型の詳細検証
3. **Helper関数は明示的に実装**: DAGのコメントで手動実装箇所を明記
4. **将来的な改善**: エンジンの拡張提案を検討

**結論**: v2により、spec2codeでalgo-tradeパイプラインをほぼ完全に表現可能になった。残る課題は設計方針（Helper関数）またはpandas固有の制約（MultiIndex）であり、現実的な回避策が存在する。

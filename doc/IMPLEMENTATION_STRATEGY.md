# spectool実装方針 & 並列作業計画

**作成日時**: 2025-10-30

---

## 📊 現状サマリー

| カテゴリ | 既存テスト | 追加テスト | 実装状況 |
|---------|-----------|-----------|----------|
| TypeAlias/Schema生成 | 15 | 0 | ✅ 完了 |
| IR基盤 | 18 | 0 | ✅ 完了 |
| **Validation強化** | **0** | **31** | ⚠️ **部分的** |
| **スケルトン生成** | **11** | **0** | ❌ **未実装** |
| **DAG実行** | **14** | **0** | ❌ **未実装** |
| **Integrity検証** | **13** | **0** | ❌ **未実装** |
| **Config実行** | **21** | **7** | ❌ **未実装** |
| **合計** | **92** | **38** | - |

---

## 🎯 実装方針（優先度順）

### Phase 1: Validation強化 (最優先) 🔴
**工数**: 1-2日
**並列度**: ★★☆☆☆

**実装内容**:
1. エラー収集機能 - 例外を投げずにエラーリストを返す
2. エラー継続機能 - 最初のエラー後も検証を継続
3. エッジケース検証:
   - DAG stage候補ゼロ検出
   - DataType check関数ゼロ検出
   - Example/Generatorゼロ検出

**ファイル**: `spectool/core/engine/validate.py` (既存の拡張)

**並列可能**: なし（他機能の基盤）

---

### Phase 2: スケルトン生成 (高優先) 🟠
**工数**: 3-4日
**並列度**: ★★★★☆

**実装内容**:
1. Check関数スケルトン生成
2. Transform関数スケルトン生成（型アノテーション含む）
3. Generator関数スケルトン生成
4. Import管理・ファイル更新ロジック

**ファイル**: `spectool/backends/py_skeleton.py` (新規)
**依存**: `spectool/core/base/meta_types.py`に`Check`/`ExampleValue`追加

**並列可能**:
- ✅ DAG実行エンジン実装（独立）
- ✅ Integrity検証実装（スケルトン生成後に統合テスト）

---

### Phase 3: DAG実行エンジン (高優先) 🟠
**工数**: 2-3日
**並列度**: ★★★★★

**実装内容**:
1. トポロジカルソート
2. Transform関数の動的実行
3. 結果収集
4. エラーハンドリング

**ファイル**: `spectool/core/engine/dag_runner.py` (新規)

**並列可能**:
- ✅ スケルトン生成実装（完全独立）
- ✅ Integrity検証実装（完全独立）
- ⚠️ Config実行実装（DAG実行を利用するため依存あり）

---

### Phase 4: Integrity検証 (中優先) 🟡
**工数**: 1-2日
**並列度**: ★★★★☆

**実装内容**:
1. Check/Transform/Generator関数の存在・位置・シグネチャ検証
2. 型アノテーション検証
3. Example値のスキーマ検証

**ファイル**: `spectool/core/engine/integrity.py` (新規)

**並列可能**:
- ✅ スケルトン生成実装（完全独立）
- ✅ DAG実行実装（完全独立）
- ⚠️ Config実行実装（Integrity検証を利用する可能性）

---

### Phase 5: Config駆動実行 (中優先) 🟡
**工数**: 2-3日
**並列度**: ★☆☆☆☆

**実装内容**:
1. Config YAMLモデル定義
2. Config検証ロジック
3. ConfigRunnerによるDAG実行
4. パラメータオーバーライド

**ファイル**:
- `spectool/core/engine/config_model.py` (新規)
- `spectool/core/engine/config_runner.py` (新規)
- `spectool/core/engine/config_validator.py` (新規)

**依存**: DAG実行エンジン必須

**並列可能**: なし（DAG実行完了後）

---


## 🔧 並列実装の具体的な進め方

### ステップ1: 基盤準備（即時実行）
```python
# spectool/core/base/meta_types.py に追加
class Check(Generic[T]): ...
class ExampleValue(Generic[T]): ...
```
**担当**: メインスレッド
**工数**: 30分

---

### ステップ2: 並列実装開始（同時起動）

#### 🔵 Agent 1: スケルトン生成
**ファイル**: `spectool/backends/py_skeleton.py`
**工数**: 3-4日
**タスク**:
1. Check関数スケルトン生成
2. Transform関数スケルトン生成
3. Generator関数スケルトン生成
4. 型アノテーション生成
5. Import管理

**成果物**: 11テストPASS

---

#### 🟢 Agent 2: DAG実行エンジン
**ファイル**: `spectool/core/engine/dag_runner.py`
**工数**: 2-3日
**タスク**:
1. トポロジカルソート実装
2. Transform動的実行
3. 結果収集
4. エラーハンドリング

**成果物**: 14テストPASS

---

#### 🟡 Agent 3: Integrity検証
**ファイル**: `spectool/core/engine/integrity.py`
**工数**: 1-2日
**タスク**:
1. 関数存在・位置検証
2. シグネチャ検証
3. 型アノテーション検証
4. Exampleスキーマ検証

**成果物**: 13テストPASS

---

#### 🟣 Agent 4: Validation強化（メイン）
**ファイル**: `spectool/core/engine/validate.py`
**工数**: 1-2日
**タスク**:
1. エラー収集機構
2. 検証継続機構
3. エッジケース検証（候補ゼロ等）
4. エラーメッセージ改善

**成果物**: 31テストPASS

---

### ステップ3: 統合テスト（並列完了後）
**工数**: 0.5日
**内容**:
- 各機能の統合動作確認
- 相互依存のバグ修正
- パフォーマンステスト

---

### ステップ4: Config実行実装（統合後）
**ファイル**: 3ファイル
**工数**: 2-3日
**依存**: DAG実行エンジン必須

---

## 📋 並列実装時のチェックリスト

### 事前準備
- [ ] `meta_types.py`に`Check`/`ExampleValue`追加
- [ ] 各Agentに明確なタスク定義を渡す
- [ ] テストファイルを各Agentに割り当て

### 実装中
- [ ] 各Agent: 自分のテストが全てPASSすることを確認
- [ ] 各Agent: 既存テスト（80件）を壊さないことを確認
- [ ] 定期的な進捗確認（1日1回）

### 統合前
- [ ] Agent 1: スケルトン生成の11テストPASS
- [ ] Agent 2: DAG実行の14テストPASS
- [ ] Agent 3: Integrity検証の13テストPASS
- [ ] Agent 4: Validation強化の31テストPASS

### 統合後
- [ ] 全150テストPASS（既存80 + 新規70）
- [ ] ruff format/check PASS
- [ ] 統合動作確認

---

## 💡 リスク管理

### 🔴 高リスク
- **Agentが既存コードを壊す**: 既存80テストを常時監視
- **Agent間の命名衝突**: 事前に命名規則を統一

### 🟡 中リスク
- **統合時の不整合**: 統合テストで早期発見
- **パフォーマンス問題**: 実装完了後に最適化

### 🟢 低リスク
- **テスト不足**: 既に98テストあり
- **仕様変更**: IRモデルは安定

---

## 🎯 成功基準

### 最小基準（MVP）
- [ ] スケルトン生成: 10/11テストPASS
- [ ] DAG実行: 12/14テストPASS
- [ ] Integrity検証: 10/13テストPASS
- [ ] Validation強化: 28/31テストPASS
- [ ] **合計**: 60/69テストPASS (87%)

### 目標基準
- [ ] スケルトン生成: 11/11テストPASS (100%)
- [ ] DAG実行: 14/14テストPASS (100%)
- [ ] Integrity検証: 13/13テストPASS (100%)
- [ ] Validation強化: 31/31テストPASS (100%)
- [ ] **合計**: 69/69テストPASS (100%)

### 完全達成
- [ ] 上記 + Config実行: 28/28テストPASS
- [ ] 全150テストPASS (100%)
- [ ] ruff format/check PASS
- [ ] ドキュメント完備

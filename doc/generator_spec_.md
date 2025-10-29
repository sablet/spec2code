# Generator機能実装チケット

## 背景
- 現状のバリデータは各 `datatype` に少なくとも1件の `example` を要求している。
- 仕様上、複雑なデータ構造では静的 `example` の準備が難しいケースがあるため、代替手段としてデータ生成用の `generator` 関数を追加したい。
- `specs/algo-trade-pipeline.yaml` のように `examples` はトップレベルセクションとして定義され、`datatype` から ID 参照している。`generator` も同様の設計を採用する。

## スコープ
- YAML 仕様: `generators` トップレベルセクションを追加し、`datatypes` から `generator_refs` (複数可) を参照できるようにする。
- エンジン: バリデーションおよびスケルトン生成で `generator` 情報を扱う。
- テスト: 正常系と異常系をカバーする統合テストを追加。
- ドキュメント: 仕様変更を説明する開発者向けドキュメントを更新。

## 完了条件 (Definition of Done)
- `Spec` モデルに `generators` 定義が追加され、`DataType` が `example_refs` または `generator_refs` のいずれかを少なくとも1件持つことを検証している。
- `generate_skeleton()` が `generator` 定義に応じたスケルトンファイルを生成する (既存ファイルは上書きしない)。
- `Engine.validate_integrity()` が generator の存在確認・ファイル配置・シグネチャ整合性を検証し、結果カテゴリに `generator_functions`/`generator_locations`/`generator_signatures` を追加している。
- `packages/tests` に generator 機能の正常系・未実装・シグネチャ不一致などのテストが追加され、`make test` が通る。
- 仕様変更を説明するリリースノートまたはドキュメントが整備されている (`doc` 配下など)。

## タスク
1. ✅ 仕様設計を確定し、チケットを作成 (本ドキュメント)。
2. `packages/spec2code/engine.py` の Pydantic モデル拡張:
   - `GeneratorSpec` モデルを追加 (`description`, `impl`, `file_path`, `parameters` 等)。
   - `Spec` に `generators: Dict[str, GeneratorSpec]` を追加。
   - `DataType` に `generator_refs: List[str]` を追加し、`root_validator` で `example_refs` / `generator_refs` の必須チェックを実装。
3. スケルトン生成処理の更新:
   - `generators` 定義に基づいて対応ファイルを生成。
   - 生成テンプレートに `description` を docstring として反映。
4. バリデーション処理の拡張:
   - generator 関連の import / file path / signature チェックを追加。
   - 既存のカテゴリ整合性を保ちつつ検出結果のレポートを拡張。
5. テスト追加・更新:
   - `packages/tests/test_integrity_validation.py` 等に generator 正常系・異常系テストを追加。
   - スケルトン生成テストに generator ケースを追加。
6. ドキュメント更新:
   - 仕様 (`SPEC2CODE_CONSTRAINTS.md` 等) を generator 対応へ更新。
   - 必要に応じて CLI ヘルプや README を更新。
7. リリースノートまたは変更履歴の追記。

## 留意事項・検討ポイント
- `generator_refs` は複数指定を許容し、どの generator を実行するかの判断やマージは利用側 (今後追加される API や外部スクリプト) に委ねる。
- 将来的なサンプル自動生成 API は、`generator_refs` を順次実行して得られたデータを `examples` に書き出す薄いラッパー (`Engine.materialize_examples()` など) を想定。現行タスクでは API 実装を行わず、呼び出し可能な generator が存在する状態を整えることに専念する。
- `parameters` のパースとシグネチャ照合は transform と同じユーティリティを共通使用できるように整理し、重複実装を避ける。
- 既存の spec は `generator_refs` を省略して `example_refs` のみでも問題なく動作する。後方互換性を確保し、既存 YAML に変更を要求しない。

## 参考情報
- 現行仕様: `specs/algo-trade-pipeline.yaml` における `examples` セクションと `datatype.example_refs` の関係。
- コア実装: `packages/spec2code/engine.py` の `Spec` / `DataType` / `generate_skeleton` / `Engine.validate_integrity`。
- テストベース: `packages/tests/test_integrity_validation.py` および `packages/tests/conftest.py`。

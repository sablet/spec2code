# Release Notes

## 2025-10-29 Generatorサポート

- `generators` トップレベル定義を追加し、データ生成用の関数を仕様で記述可能にした。
- `DataType` に `generator_refs` を導入し、`example_refs` とのいずれか（または両方）を必須とする完全性チェックを実装。
- スケルトン生成で generator モジュールを自動作成し、既存ファイルには追記のみを行う安全な生成フローを維持。
- `Engine.validate_integrity()` に generator の存在確認・ファイル配置・シグネチャ検証を追加し、結果サマリに専用カテゴリを拡張。
- 統合テストを更新し、正常系・実装漏れ・シグネチャ不一致・ファイル位置ずれのケースをカバー。
- ドキュメントに generator の使い方と DataType 要件を追記。

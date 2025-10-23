.PHONY: help gen run clean format check test

# デフォルトのspec
SPEC ?= specs/spec.yaml

help: ## ヘルプを表示
	@echo "Spec2Code - スケルトンコード生成・検証システム"
	@echo ""
	@echo "使い方:"
	@echo "  make gen [SPEC=specs/xxx.yaml]    スケルトンコード生成"
	@echo "  make run [SPEC=specs/xxx.yaml]    DAG実行・検証"
	@echo "  make clean                         生成されたコードを削除"
	@echo "  make format                        コードフォーマット"
	@echo "  make check                         コード品質チェック"
	@echo "  make test                          テスト実行"
	@echo ""
	@echo "例:"
	@echo "  make gen                           デフォルト仕様でスケルトン生成"
	@echo "  make gen SPEC=specs/custom.yaml    カスタム仕様でスケルトン生成"
	@echo "  make run                           デフォルト仕様でDAG実行"
	@echo ""

gen: ## スケルトンコード生成
	@echo "🔨 スケルトンコード生成中: $(SPEC)"
	uv run python spec2code_cli.py gen $(SPEC)

run: ## DAG実行・検証
	@echo "🚀 DAG実行・検証中: $(SPEC)"
	uv run python spec2code_cli.py run $(SPEC)

clean: ## 生成されたコードを削除
	@echo "🗑️  生成されたコードを削除中..."
	rm -rf apps/*
	@echo "✅ 削除完了"

format: ## コードフォーマット
	@echo "🎨 コードフォーマット中..."
	uv run ruff format .
	@echo "✅ フォーマット完了"

check: ## コード品質チェック
	@echo "🔍 コード品質チェック中..."
	uv run ruff check .
	@echo "✅ チェック完了"

test: format check ## テスト実行（フォーマット + チェック）
	@echo "✅ 全テスト完了"

# 複数のspecを一括生成
gen-all: ## 全てのspecファイルからスケルトン生成
	@echo "🔨 全specファイルからスケルトン生成中..."
	@for spec in specs/*.yaml; do \
		echo ""; \
		echo "📄 処理中: $$spec"; \
		uv run python spec2code_cli.py gen $$spec; \
	done
	@echo ""
	@echo "✅ 全てのスケルトン生成完了"

# 複数のspecを一括実行
run-all: ## 全てのspecファイルでDAG実行
	@echo "🚀 全specファイルでDAG実行中..."
	@for spec in specs/*.yaml; do \
		echo ""; \
		echo "📄 処理中: $$spec"; \
		uv run python spec2code_cli.py run $$spec; \
	done
	@echo ""
	@echo "✅ 全てのDAG実行完了"

# プロジェクト構造表示
tree: ## プロジェクト構造を表示
	@tree -L 3 -I '.venv|__pycache__|.git|.ruff_cache|output' || ls -la

# 開発環境セットアップ
setup: ## 開発環境セットアップ
	@echo "🔧 開発環境セットアップ中..."
	uv sync
	@echo "✅ セットアップ完了"

.PHONY: help gen run validate clean format check test gen-all run-all validate-all run-config run-config-all validate-config validate-config-all tree setup duplication lint typecheck complexity front-run front-build front-install export-cards

# UV_CACHE_DIR ?= $(CURDIR)/.uv-cache
# export UV_CACHE_DIR

# デフォルトのspec
SPEC ?= specs/spec.yaml
# デフォルトのconfig
CONFIG ?= configs/pipeline-config-minmax.yaml
# チェック対象ディレクトリ
CHECK_DIRS ?= packages apps

help: ## ヘルプを表示
	@echo "Spec2Code - スケルトンコード生成・検証システム"
	@echo ""
	@echo "基本コマンド:"
	@echo "  make gen [SPEC=specs/xxx.yaml]        スケルトンコード生成"
	@echo "  make run [SPEC=specs/xxx.yaml]        DAG実行・検証"
	@echo "  make validate [SPEC=specs/xxx.yaml]   仕様と実装の整合性検証"
	@echo ""
	@echo "Config実行コマンド:"
	@echo "  make run-config [CONFIG=configs/xxx.yaml]      Config駆動でDAG実行"
	@echo "  make run-config-all                            全Configで実行"
	@echo "  make validate-config [CONFIG=configs/xxx.yaml] Config整合性検証"
	@echo "  make validate-config-all                       全Configで整合性検証"
	@echo ""
	@echo "開発コマンド:"
	@echo "  make format                           コードフォーマット"
	@echo "  make lint                             Lintチェック"
	@echo "  make typecheck                        型チェック"
	@echo "  make complexity                       複雑度チェック"
	@echo "  make duplication                      重複コードチェック"
	@echo "  make check                            品質チェック（全て）"
	@echo "  make test                             テスト実行"
	@echo ""
	@echo "一括実行コマンド:"
	@echo "  make gen-all                          全specでスケルトン生成"
	@echo "  make run-all                          全specでDAG実行"
	@echo "  make validate-all                     全specで整合性検証"
	@echo ""
	@echo "フロントエンド開発:"
	@echo "  make front-run                        フロントエンド開発サーバー起動"
	@echo "  make front-build                      フロントエンドビルド"
	@echo "  make front-install                    フロントエンド依存関係インストール"
	@echo ""
	@echo "例:"
	@echo "  make gen                              デフォルト仕様でスケルトン生成"
	@echo "  make gen SPEC=specs/custom.yaml       カスタム仕様でスケルトン生成"
	@echo "  make run-config                       デフォルトConfigで実行"
	@echo "  make run-config CONFIG=configs/pipeline-config-robust-all.yaml"
	@echo ""

gen: ## スケルトンコード生成
	uv run python main.py gen $(SPEC)
	@make format

run: ## DAG実行・検証
	uv run python main.py run $(SPEC)

validate: ## 仕様と実装の整合性検証
	uv run python main.py validate $(SPEC)

run-config: ## Config駆動でDAG実行
	uv run python main.py run_config $(CONFIG)

run-config-all: ## 全てのconfigファイルでDAG実行
	@for config in configs/*.yaml; do \
		echo ""; \
		echo "�� 処理中: $$config"; \
		uv run python main.py run_config $$config || true; \
	done
	echo ""

validate-config: ## Config整合性検証
	uv run python main.py validate_config $(CONFIG)

validate-config-all: ## 全てのconfigファイルで整合性検証
	@for config in configs/*.yaml; do \
		echo ""; \
		echo "�� 処理中: $$config"; \
		uv run python main.py validate_config $$config || true; \
	done
	echo ""

format: ## コードフォーマット
	uv run ruff format $(CHECK_DIRS)

lint: ## Lintチェック
	uv run ruff check --fix --unsafe-fixes packages/spec2code

typecheck: ## 型チェック
	uv run mypy packages/spec2code

complexity: ## 複雑度チェック
	uv run xenon -b B -m B -a A packages/spec2code

duplication: ## 重複コードチェック
	npx jscpd --config .jscpd.json packages/spec2code

module-lines: ## モジュール行数チェック（max-module-lines=500）
	uv run pylint packages/spec2code --rcfile=pyproject.toml

# check: duplication module-lines format lint typecheck complexity ## コード品質チェック（全て）
check: duplication format lint typecheck complexity ## コード品質チェック（全て）

test:
	uv run python -m pytest -v

all_test:## テスト実行（フォーマット + チェック + pytest）
	@make format 
	@make check 
	@make test


# 複数のspecを一括生成
gen-all: ## 全てのspecファイルからスケルトン生成
	@for spec in specs/*.yaml; do \
		echo ""; \
		echo "�� 処理中: $$spec"; \
		uv run python main.py gen $$spec; \
	done
	uv run ruff format apps/ 2>/dev/null || true

# 複数のspecを一括実行
run-all: ## 全てのspecファイルでDAG実行
	@for spec in specs/*.yaml; do \
		echo ""; \
		echo "�� 処理中: $$spec"; \
		uv run python main.py run $$spec; \
	done
	echo ""

# 複数のspecを一括検証
validate-all: ## 全てのspecファイルで整合性検証
	@for spec in specs/*.yaml; do \
		echo ""; \
		echo "�� 処理中: $$spec"; \
		uv run python main.py validate $$spec; \
	done
	echo ""

# プロジェクト構造表示
tree: ## プロジェクト構造を表示
	@tree -L 3 -I '.venv|__pycache__|.git|.ruff_cache|output' || ls -la

# 開発環境セットアップ
setup: ## 開発環境セットアップ
	uv sync

# フロントエンド開発
export-cards: ## YAML仕様をJSON cardに変換
	@mkdir -p frontend/public/cards
	uv run python main.py export_cards specs/*.yaml --output=frontend/public/cards
	@echo "✓ All cards exported to frontend/public/cards/"

front-run: export-cards ## フロントエンド開発サーバー起動
	cd frontend && npm run dev

front-build: export-cards ## フロントエンドビルド
	cd frontend && npm run build

front-install: ## フロントエンド依存関係インストール
	cd frontend && npm install --legacy-peer-deps

.PHONY: help gen run validate validate-spec clean format check test gen-all run-all validate-all run-config run-config-all validate-config validate-config-all tree bootstrap install install-python install-frontend duplication lint typecheck complexity front-run front-build export-cards callgraph spectool-test

# UV_CACHE_DIR ?= $(CURDIR)/.uv-cache
# export UV_CACHE_DIR

# デフォルトのspec
SPEC ?= specs/spec.yaml
# デフォルトのconfig
CONFIG ?= configs/pipeline-config-minmax.yaml
# チェック対象ディレクトリ（spectool追加）
CHECK_DIRS ?= apps main.py tools spectool
# Lint/Type/Complexity/Dead-codeチェック対象（spectool追加）
LINT_DIRS ?= spectool/spectool main.py

help: ## ヘルプを表示
	@echo "Spec2Code - スケルトンコード生成・検証システム"
	@echo ""
	@echo "基本コマンド:"
	@echo "  make gen [SPEC=specs/xxx.yaml]        スケルトンコード生成"
	@echo "  make run [SPEC=specs/xxx.yaml]        DAG実行・検証"
	@echo "  make validate [SPEC=specs/xxx.yaml]   仕様と実装の整合性検証"
	@echo "  make validate-spec [SPEC=specs/xxx.yaml]  仕様構造のみ検証"
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
	@echo "  make dead-code                        未使用コード検出"
	@echo "  make callgraph [CALLGRAPH_ARGS=...]   静的コールグラフ解析"
	@echo "  make deps                             依存関係チェック"
	@echo "  make check                            品質チェック（全て）"
	@echo "  make test                             テスト実行"
	@echo ""
	@echo "セットアップコマンド:"
	@echo "  make bootstrap                        システムツールインストール（初回のみ）"
	@echo "  make install                          プロジェクト依存関係インストール"
	@echo "  make install-python                   Python依存関係のみ"
	@echo "  make install-frontend                 フロントエンド依存関係のみ"
	@echo ""
	@echo "一括実行コマンド:"
	@echo "  make gen-all                          全specでスケルトン生成"
	@echo "  make run-all                          全specでDAG実行"
	@echo "  make validate-all                     全specで整合性検証"
	@echo ""
	@echo "フロントエンド開発:"
	@echo "  make front-run                        フロントエンド開発サーバー起動"
	@echo "  make front-build                      フロントエンドビルド"
	@echo ""
	@echo "例:"
	@echo "  make gen                              デフォルト仕様でスケルトン生成"
	@echo "  make gen SPEC=specs/custom.yaml       カスタム仕様でスケルトン生成"
	@echo "  make run-config                       デフォルトConfigで実行"
	@echo "  make run-config CONFIG=configs/pipeline-config-robust-all.yaml"
	@echo ""

gen: ## スケルトンコード生成
	uv run python -m spectool gen $(SPEC)
	@make format

run: ## DAG実行・検証
	uv run python main.py run $(SPEC)

validate: ## 仕様と実装の整合性検証
	uv run python -m spectool validate-integrity $(SPEC)

validate-spec: ## 仕様構造の検証（実装チェックなし）
	uv run python -m spectool validate $(SPEC)

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
	uv run ruff check --fix --unsafe-fixes $(LINT_DIRS)

typecheck: ## 型チェック
	uv run mypy $(LINT_DIRS)

complexity: ## 複雑度チェック
	uv run xenon -b B -m B -a A $(LINT_DIRS)

duplication: ## 重複コードチェック
	npx jscpd --config .jscpd.json

dead-code: ## 未使用コード検出
	uv run vulture $(LINT_DIRS) --min-confidence 80

CALLGRAPH_ARGS ?=
callgraph: ## 静的コールグラフ解析
	uv run python tools/static_callgraph.py $(CALLGRAPH_ARGS)

deps: ## 依存関係チェック
	uv run deptry .

module-lines: ## モジュール行数チェック（max-module-lines=500）
	uv run pylint $(LINT_DIRS) --rcfile=pyproject.toml

check: format duplication dead-code callgraph deps module-lines lint typecheck complexity ## は現在通らないので別

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
		uv run python -m spectool gen $$spec; \
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
		uv run python -m spectool validate-integrity $$spec; \
	done
	echo ""

# プロジェクト構造表示
tree: ## プロジェクト構造を表示
	@tree -L 3 -I '.venv|__pycache__|.git|.ruff_cache|output' || ls -la

# 開発環境セットアップ
bootstrap: ## システムツールインストール（初回のみ）
	curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
	nvm install 24
	npm install -g @anthropic-ai/claude-code
	npm -g install jscpd
	curl -LsSf https://astral.sh/uv/install.sh | sh

install-python: ## Python依存関係インストール
	uv sync --all-groups

# フロントエンド開発
export-cards: ## YAML仕様をJSON cardに変換
	@mkdir -p frontend/public/cards
	uv run python main.py export_cards specs/*.yaml --output=frontend/public/cards
	@echo "✓ All cards exported to frontend/public/cards/"

front-run: export-cards ## フロントエンド開発サーバー起動
	cd frontend && npm run dev

front-build: export-cards ## フロントエンドビルド
	cd frontend && npm run build

install-frontend: ## フロントエンド依存関係インストール
	cd frontend && npm install --legacy-peer-deps

install: install-python install-frontend ## プロジェクト依存関係インストール（全て）

front-check: ## フロントエンドの静的チェック（knip / lint / jscpd）
	cd frontend && ( \
		rc=0; \
		npx --no-install knip || rc=$$?; \
		npm run lint || rc=$$?; \
		npx --no-install jscpd --config .jscpd.json || rc=$$?; \
		exit $$rc; \
	)
	

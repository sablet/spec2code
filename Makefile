.PHONY: help gen run validate clean format check test gen-all run-all validate-all run-config run-config-all tree setup

# デフォルトのspec
SPEC ?= specs/spec.yaml
# デフォルトのconfig
CONFIG ?= configs/pipeline-config-minmax.yaml

help: ## ヘルプを表示
	@echo "Spec2Code - スケルトンコード生成・検証システム"
	@echo ""
	@echo "基本コマンド:"
	@echo "  make gen [SPEC=specs/xxx.yaml]        スケルトンコード生成"
	@echo "  make run [SPEC=specs/xxx.yaml]        DAG実行・検証"
	@echo "  make validate [SPEC=specs/xxx.yaml]   仕様と実装の整合性検証"
	@echo "  make clean                            生成されたコードを削除"
	@echo ""
	@echo "Config実行コマンド:"
	@echo "  make run-config [CONFIG=configs/xxx.yaml]  Config駆動でDAG実行"
	@echo "  make run-config-all                        全Configで実行"
	@echo ""
	@echo "開発コマンド:"
	@echo "  make format                           コードフォーマット"
	@echo "  make check                            コード品質チェック"
	@echo "  make test                             テスト実行"
	@echo ""
	@echo "一括実行コマンド:"
	@echo "  make gen-all                          全specでスケルトン生成"
	@echo "  make run-all                          全specでDAG実行"
	@echo "  make validate-all                     全specで整合性検証"
	@echo ""
	@echo "例:"
	@echo "  make gen                              デフォルト仕様でスケルトン生成"
	@echo "  make gen SPEC=specs/custom.yaml       カスタム仕様でスケルトン生成"
	@echo "  make run-config                       デフォルトConfigで実行"
	@echo "  make run-config CONFIG=configs/pipeline-config-robust-all.yaml"
	@echo ""

gen: ## スケルトンコード生成
	uv run python spec2code_cli.py gen $(SPEC)
	@make format

run: ## DAG実行・検証
	uv run python spec2code_cli.py run $(SPEC)

validate: ## 仕様と実装の整合性検証
	uv run python spec2code_cli.py validate $(SPEC)

run-config: ## Config駆動でDAG実行
	uv run python spec2code_cli.py run-config $(CONFIG)

run-config-all: ## 全てのconfigファイルでDAG実行
	@for config in configs/*.yaml; do \
		echo ""; \
		echo "�� 処理中: $$config"; \
		uv run python spec2code_cli.py run-config $$config || true; \
	done
	echo ""

clean: ## 生成されたコードを削除
	rm -rf apps/*

format: ## コードフォーマット
	uv run ruff format .

check: ## コード品質チェック
	uv run ruff check .

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
		uv run python spec2code_cli.py gen $$spec; \
	done
	uv run ruff format apps/ 2>/dev/null || true

# 複数のspecを一括実行
run-all: ## 全てのspecファイルでDAG実行
	@for spec in specs/*.yaml; do \
		echo ""; \
		echo "�� 処理中: $$spec"; \
		uv run python spec2code_cli.py run $$spec; \
	done
	echo ""

# 複数のspecを一括検証
validate-all: ## 全てのspecファイルで整合性検証
	@for spec in specs/*.yaml; do \
		echo ""; \
		echo "�� 処理中: $$spec"; \
		uv run python spec2code_cli.py validate $$spec; \
	done
	echo ""

# プロジェクト構造表示
tree: ## プロジェクト構造を表示
	@tree -L 3 -I '.venv|__pycache__|.git|.ruff_cache|output' || ls -la

# 開発環境セットアップ
setup: ## 開発環境セットアップ
	uv sync

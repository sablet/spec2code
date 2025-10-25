#!/usr/bin/env python
"""
Spec2Code Unified CLI - エントリーポイント統合版

Usage:
    python main.py gen <spec_file>
    python main.py run <spec_file>
    python main.py validate <spec_file>
    python main.py run_config <config_file>
    python main.py validate_config <config_file>
    python main.py export_cards <spec1> <spec2> ... --output=<dir>
"""

import sys
from pathlib import Path
from typing import Any

import fire

from packages.spec2code.engine import (
    Engine,
    generate_skeleton,
    load_spec,
)
from packages.spec2code.card_exporter import export_spec_to_cards


class Spec2CodeCLI:
    """Spec2Code統合CLI"""

    def gen(self, spec_file: str) -> None:
        """スケルトンコード生成

        Args:
            spec_file: 仕様ファイル (YAML/JSON)
        """
        try:
            spec = load_spec(spec_file)
            print(f"✅ Loaded spec: {spec.meta.name} (v{spec.version})")
            generate_skeleton(spec)
            print("✅ Skeleton generation completed")
        except Exception as exc:
            print(f"❌ Failed to generate skeleton: {exc}")
            sys.exit(1)

    def run(self, spec_file: str) -> None:
        """DAG実行・検証

        Args:
            spec_file: 仕様ファイル (YAML/JSON)
        """
        try:
            spec = load_spec(spec_file)
            print(f"✅ Loaded spec: {spec.meta.name} (v{spec.version})")

            engine = Engine(spec)
            engine.validate_schemas()
            engine.run_checks()
            engine.run_dag()
            results = engine.run_examples()
            print(f"📊 Example report: {results}")
            print("✅ Execution completed")
        except Exception as exc:
            print(f"❌ Failed to run: {exc}")
            sys.exit(1)

    def validate(self, spec_file: str) -> None:
        """仕様と実装の整合性を検証

        Args:
            spec_file: 仕様ファイル (YAML/JSON)
        """
        try:
            spec = load_spec(spec_file)
            print(f"✅ Loaded spec: {spec.meta.name} (v{spec.version})")

            engine = Engine(spec)
            errors = engine.validate_integrity()
            total_errors = sum(len(errs) for errs in errors.values())
            if total_errors > 0:
                sys.exit(1)
        except Exception as exc:
            print(f"❌ Failed to validate: {exc}")
            sys.exit(1)

    def run_config(self, config_file: str) -> None:
        """Config-based DAG実行

        Args:
            config_file: Config file (YAML)
        """
        from packages.spec2code.config_runner import ConfigRunner
        import pandas as pd

        try:
            runner = ConfigRunner(config_file)
            initial_data = pd.DataFrame(
                {
                    "timestamp": [
                        "2024-01-01",
                        "2024-01-02",
                        "2024-01-03",
                        "2024-01-04",
                        "2024-01-05",
                    ],
                    "value": [100, 150, 120, 180, 140],
                }
            )
            print("\n📊 Initial data:")
            print(initial_data)
            print()

            result = runner.run(initial_data)
            print("\n📊 Final result:")
            print(result)
        except Exception as exc:
            print(f"❌ Config execution failed: {exc}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    def validate_config(self, config_file: str) -> None:
        """Config整合性検証

        Args:
            config_file: Config file (YAML)
        """
        from packages.spec2code.config_runner import ConfigRunner
        from packages.spec2code.config_validator import ConfigValidationError

        try:
            print("🔍 Loading config...")
            runner = ConfigRunner(config_file)
            print(f"✅ Config loaded: {runner.config.meta.config_name}")
            print(f"📄 Base spec: {runner.config.meta.base_spec}")
            print()

            print("🔍 Validating config against spec...")
            validation_result = runner.validate(check_implementations=True)
            print("✅ Config validation passed!")
            print()

            execution_plan = validation_result["execution_plan"]
            print(f"📋 Execution plan: {len(execution_plan)} transform(s)")
            for idx, step in enumerate(execution_plan, start=1):
                print(f"  {idx}. Stage: {step['stage_id']}")
                print(f"     Transform: {step['transform_id']}")
                if step["params"]:
                    print(f"     Params: {step['params']}")
            print()
            print("✅ Config validation completed successfully")

        except ConfigValidationError as exc:
            print(f"❌ Config validation failed:\n{exc}")
            sys.exit(1)
        except Exception as exc:
            print(f"❌ Config validation error: {exc}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    def export_cards(self, *specs: str, output: str) -> None:
        """YAML仕様をJSONカードにエクスポート

        Args:
            *specs: YAML spec files
            output: Output directory
        """
        import json

        if not specs:
            print("❌ Error: No spec files provided")
            print("Usage: python main.py export_cards spec1.yaml spec2.yaml --output=output/cards")
            sys.exit(1)

        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)

        for spec_path_str in specs:
            spec_path = Path(spec_path_str)

            if not spec_path.exists():
                print(f"Warning: {spec_path} does not exist, skipping")
                continue

            print(f"Processing {spec_path}...")

            try:
                cards_data = export_spec_to_cards(spec_path)

                output_path = output_dir / f"{spec_path.stem}.json"
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(cards_data, f, indent=2, ensure_ascii=False)

                print(f"  → Exported {len(cards_data['cards'])} cards to {output_path}")

            except Exception as e:
                print(f"  ✗ Error: {e}")
                import traceback
                traceback.print_exc()


def main() -> None:
    """CLIエントリーポイント"""
    fire.Fire(Spec2CodeCLI)


if __name__ == "__main__":
    main()

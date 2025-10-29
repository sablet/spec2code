#!/usr/bin/env python
"""
Spec2Code Unified CLI - エントリーポイント統合版

Usage:
    python main.py gen <spec_file>
    python main.py run <spec_file>
    python main.py validate <spec_file>
    python main.py validate_spec <spec_file>
    python main.py run_config <config_file>
    python main.py validate_config <config_file>
    python main.py export_cards <spec1> <spec2> ... --output=<dir>
"""

import sys
from pathlib import Path

import fire
from pydantic import ValidationError

from packages.spec2code.engine import (
    Engine,
    generate_skeleton,
    load_spec,
)
from packages.spec2code.card_exporter import export_spec_to_cards
from packages.spec2code.config_model import load_extended_spec


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

    def _extract_validation_errors(self, exc: ValidationError | ValueError) -> list[str]:
        """Extract error messages from validation exception."""
        issues: list[str] = []
        if isinstance(exc, ValidationError):
            for error_dict in exc.errors():
                loc = " -> ".join(str(part) for part in error_dict.get("loc", ())) or "spec"
                msg = error_dict.get("msg", "Unknown validation error")
                issues.append(f"{loc}: {msg}")
        else:
            issues.append(str(exc))
        return issues

    def _load_and_check_extended_spec(self, spec_file: str) -> list[str]:
        """Load extended spec and collect validation issues."""
        try:
            extended_spec = load_extended_spec(spec_file)
            meta_name = extended_spec.meta.get("name") if isinstance(extended_spec.meta, dict) else None
            spec_name = meta_name or spec_file
            print(f"✅ Loaded spec metadata: {spec_name}")
            if extended_spec.dag_stages:
                print(f"  ✅ dag_stages connectivity verified ({len(extended_spec.dag_stages)} stage(s))")
            else:
                print("  ⚠️  No dag_stages defined")
            return []
        except (ValidationError, ValueError) as exc:
            print(f"❌ Spec structural validation failed: {spec_file}")
            issues = self._extract_validation_errors(exc)
            for message in issues:
                print(f"  ❌ {message}")
            return issues
        except Exception as exc:
            print(f"❌ Spec structural validation error: {exc}")
            sys.exit(1)

    def _print_unreachable_stages(self, issues: list[str]) -> None:
        """Print unreachable stage warnings."""
        if not issues:
            return
        print("\n⚠️  dag_stages connectivity issues detected above:")
        for issue_str in issues:
            if "到達できない" in issue_str:
                try:
                    unreachable_section = issue_str.split("到達できないステージがあります: ", 1)[1]
                    for stage_id in [item.strip() for item in unreachable_section.split(",") if item.strip()]:
                        print(f"  ⚠️  Stage '{stage_id}' is unreachable from final stage")
                except IndexError:
                    pass

    def validate_spec(self, spec_file: str) -> None:
        """仕様ファイルの構造のみを検証

        Args:
            spec_file: 仕様ファイル (YAML/JSON)
        """
        dag_stage_issues = self._load_and_check_extended_spec(spec_file)

        try:
            spec = load_spec(spec_file)
            engine = Engine(spec)
            errors = engine.validate_spec_structure(summarize=False)
            structural_errors: dict[str, list[str]] = {"dag_stage_flow": dag_stage_issues}
            for category, messages in errors.items():
                structural_errors.setdefault(category, []).extend(messages)

            total_errors = sum(len(msgs) for msgs in structural_errors.values())
            self._print_unreachable_stages(dag_stage_issues)
            engine._summarize_integrity(structural_errors)

            if total_errors > 0:
                sys.exit(1)
            print("✅ Spec structural validation completed successfully")
        except Exception as exc:
            print(f"❌ Spec structural validation error: {exc}")
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
        """YAML仕様をJSONカードにエクスポート（統合JSONのみ）

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

        all_cards = []
        all_specs_metadata = []
        all_dag_stage_groups = []
        all_referenced_keys = set()
        all_unlinked_keys = set()

        for spec_path_str in specs:
            spec_path = Path(spec_path_str)

            if not spec_path.exists():
                print(f"Warning: {spec_path} does not exist, skipping")
                continue

            print(f"Processing {spec_path}...")

            try:
                cards_data = export_spec_to_cards(spec_path)
                print(f"  → Processed {len(cards_data['cards'])} cards from {spec_path.name}")

                dag_groups = cards_data.get("dag_stage_groups", [])
                if dag_groups:
                    print(f"  → Found {len(dag_groups)} DAG stage groups")

                # Collect for unified JSON
                all_cards.extend(cards_data["cards"])
                all_specs_metadata.append(
                    {
                        "source_file": spec_path.name,
                        **cards_data["metadata"],
                    }
                )
                all_dag_stage_groups.extend(dag_groups)
                # Accumulate referenced/unlinked keys across specs
                for k in cards_data.get("referenced_card_keys", []):
                    all_referenced_keys.add(k)
                for k in cards_data.get("unlinked_card_keys", []):
                    all_unlinked_keys.add(k)

            except Exception as e:
                print(f"  ✗ Error: {e}")
                import traceback

                traceback.print_exc()

        # Export unified JSON only
        unified_output = output_dir / "all-cards.json"
        unified_data = {
            "specs": all_specs_metadata,
            "cards": all_cards,
            "dag_stage_groups": all_dag_stage_groups,
            "referenced_card_keys": sorted(all_referenced_keys),
            "unlinked_card_keys": sorted(all_unlinked_keys),
        }

        with open(unified_output, "w", encoding="utf-8") as f:
            json.dump(unified_data, f, indent=2, ensure_ascii=False)

        print(
            f"\n✅ Unified JSON: {len(all_cards)} cards, "
            f"{len(all_dag_stage_groups)} DAG stage groups from "
            f"{len(all_specs_metadata)} specs → {unified_output}"
        )


def main() -> None:
    """CLIエントリーポイント"""
    fire.Fire(Spec2CodeCLI)


if __name__ == "__main__":
    main()

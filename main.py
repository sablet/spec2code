#!/usr/bin/env python
"""
Spectool CLI - Spec2Code Next Generation Command Line Interface

Usage:
    python -m spectool validate <spec_file>
    python -m spectool gen <spec_file> [--output-dir DIR]
    python -m spectool validate-integrity <spec_file>
    python -m spectool --version
"""

import sys
from pathlib import Path

import fire

from spectool.spectool.core.base.ir import SpecIR
from spectool.spectool.core.engine.loader import load_spec
from spectool.spectool.core.engine.normalizer import normalize_ir
from spectool.spectool.core.engine.validate import validate_spec, format_validation_result
from spectool.spectool.core.engine.integrity import IntegrityValidator
from spectool.spectool.core.engine.dag_runner import DAGRunner
from spectool.spectool.core.engine.config_runner import ConfigRunner
from spectool.spectool.backends.py_skeleton import generate_skeleton
from spectool.spectool.core.export.card_exporter import export_spec_to_cards

__version__ = "2.0.0-alpha"


class SpectoolCLI:
    """Spectool - Spec2Code Next Generation CLI"""

    def validate(self, spec_file: str, debug: bool = False, verbose: bool = False) -> None:
        """Validate spec file for correctness.

        Args:
            spec_file: Path to spec YAML file
            debug: Enable debug output
            verbose: Show detailed validation results including successes
        """
        spec_path = Path(spec_file)
        if not spec_path.exists():
            print(f"❌ Error: Spec file not found: {spec_path}")
            sys.exit(1)

        try:
            # Load and validate spec with categorized results
            print(f"📖 Loading and validating spec: {spec_path}")
            result = validate_spec(str(spec_path), skip_impl_check=True, normalize=True)

            # Format and display results
            formatted = format_validation_result(result, verbose=verbose)
            print(formatted)

            # Exit with error if validation failed
            total_errors = sum(len(msgs) for msgs in result["errors"].values())
            if total_errors > 0:
                sys.exit(1)

        except Exception as e:
            print(f"❌ Error: {e}")
            if debug:
                import traceback

                traceback.print_exc()
            sys.exit(1)

    def gen(self, spec_file: str, output_dir: str | None = None, debug: bool = False, verbose: bool = False) -> None:
        """Generate skeleton code from spec file.

        Args:
            spec_file: Path to spec YAML file
            output_dir: Output directory (default: current directory, generates apps/<project-name>/)
            debug: Enable debug output
            verbose: Show detailed validation results including successes
        """
        spec_path = Path(spec_file)
        if not spec_path.exists():
            print(f"❌ Error: Spec file not found: {spec_path}")
            sys.exit(1)

        try:
            # Load and validate spec
            print(f"📖 Loading and validating spec: {spec_path}")
            ir = load_spec(str(spec_path))
            normalized = normalize_ir(ir)

            # Validate spec
            result = validate_spec(str(spec_path), skip_impl_check=True, normalize=True)

            # Format and display validation results
            formatted = format_validation_result(result, verbose=False)

            # エラーがある場合は表示して終了
            total_errors = sum(len(msgs) for msgs in result["errors"].values())
            if total_errors > 0:
                print(formatted)
                sys.exit(1)

            # 警告がある場合は表示して継続
            total_warnings = sum(len(msgs) for msgs in result["warnings"].values())
            if total_warnings > 0:
                print(formatted)
                print("Continuing with code generation...\n")
            else:
                print("✅ Validation passed\n")

            # Determine output directory
            out_path = Path(output_dir) if output_dir else Path(".")

            print(f"📁 Output directory: {out_path}")

            # Generate complete skeleton using generate_skeleton
            print("🔨 Generating skeleton code...")
            generate_skeleton(normalized, out_path)

            project_name = normalized.meta.name if normalized.meta else "generated-project"
            app_root = out_path / "apps" / project_name

            print("\n✅ Skeleton generation complete!")
            print(f"   Generated project in: {app_root}")
            print("   Structure:")
            print("     - checks/     (validation functions)")
            print("     - transforms/ (processing functions)")
            print("     - generators/ (data generator functions)")
            print("     - models/     (Pydantic models)")
            print("     - schemas/    (Pandera validation schemas)")

        except Exception as e:
            print(f"❌ Error: {e}")
            if debug:
                import traceback

                traceback.print_exc()
            sys.exit(1)

    def validate_integrity(self, spec_file: str, debug: bool = False) -> None:
        """Validate that implementation matches spec.

        Args:
            spec_file: Path to spec YAML file
            debug: Enable debug output
        """
        spec_path = Path(spec_file)
        if not spec_path.exists():
            print(f"❌ Error: Spec file not found: {spec_path}")
            sys.exit(1)

        try:
            normalized = self._load_and_normalize_spec(spec_path)
            app_root = self._check_generated_directory(normalized)
            self._check_directory_structure(app_root)
            # Pass project root (current directory) instead of app_root
            self._run_integrity_validation(normalized, Path("."))
        except Exception as e:
            print(f"❌ Error: {e}")
            if debug:
                import traceback

                traceback.print_exc()
            sys.exit(1)

    def _load_and_normalize_spec(self, spec_path: Path) -> SpecIR:
        """Load and normalize spec file."""
        print(f"📖 Loading spec: {spec_path}")
        ir = load_spec(str(spec_path))
        print(f"✅ Loaded {len(ir.frames)} DataFrames, {len(ir.transforms)} Transforms")

        print("🔄 Normalizing IR...")
        normalized = normalize_ir(ir)
        print("✅ Normalization complete")
        return normalized

    def _check_generated_directory(self, normalized: SpecIR) -> Path:
        """Check if generated directory exists."""
        project_name = normalized.meta.name if normalized.meta else "generated-project"
        app_root = Path("apps") / project_name

        print("🔍 Checking generated code...")
        print(f"  📁 Expected directory: {app_root}")

        if not app_root.exists():
            print("    ❌ Directory not found")
            print("\n❌ Error: Generated code directory not found")
            print("   Run 'spectool gen' first to generate code.")
            sys.exit(1)
        print("    ✅ Directory exists")
        return app_root

    def _check_directory_structure(self, app_root: Path) -> None:
        """Check for required directories."""
        print("  🔍 Checking generated structure...")
        required_dirs = ["checks", "transforms", "generators", "models", "schemas"]

        for dirname in required_dirs:
            dir_path = app_root / dirname
            if dir_path.exists():
                print(f"    ✅ {dirname}/")
            else:
                print(f"    ⚠️  {dirname}/ (missing, may not be needed)")

    def _run_integrity_validation(self, normalized: SpecIR, project_root: Path) -> None:
        """Run integrity validation.

        Args:
            normalized: Normalized SpecIR
            project_root: Project root directory (should be repository root, not apps/project_name)
        """
        print("  🔍 Validating implementation integrity...")
        validator = IntegrityValidator(normalized)
        result = validator.validate_integrity(project_root)

        total_errors = sum(len(errors) for errors in result.values())
        if total_errors > 0:
            print(f"\n❌ Integrity validation failed with {total_errors} error(s)")
            for category, errors in result.items():
                if errors:
                    print(f"\n  {category}:")
                    for error in errors:
                        print(f"    ⚠️  {error}")
            sys.exit(1)

        print("\n✅ All integrity checks passed")
        print("   All required files exist and match spec")

    def run(
        self,
        spec_file: str,
        config: str | None = None,
        initial_data: str | None = None,
        debug: bool = False,
    ) -> None:
        """Execute DAG pipeline defined in spec.

        Args:
            spec_file: Path to spec YAML file (required)
            config: Path to config YAML file (optional, for parameter override)
            initial_data: Path to initial data file (JSON format, optional)
            debug: Enable debug output
        """
        spec_path = Path(spec_file)
        if not spec_path.exists():
            print(f"❌ Error: Spec file not found: {spec_path}")
            sys.exit(1)

        try:
            if config:
                self._run_with_config(spec_path, config, initial_data)
            else:
                self._run_with_spec(spec_path, initial_data)
        except Exception as e:
            print(f"❌ Error: {e}")
            if debug:
                import traceback

                traceback.print_exc()
            sys.exit(1)

    def _run_with_config(self, spec_path: Path, config: str, initial_data: str | None) -> None:
        """Execute DAG with config-driven approach."""
        config_path = Path(config)
        if not config_path.exists():
            print(f"❌ Error: Config file not found: {config_path}")
            sys.exit(1)

        print(f"📖 Loading config: {config_path}")
        print(f"📖 Base spec: {spec_path}")

        runner = ConfigRunner(str(config_path))
        print(f"✅ Loaded config: {runner.config.meta.config_name}")

        # Validate config
        print("🔍 Validating config...")
        validation_result = runner.validate(check_implementations=True)
        print("✅ Config validation passed")

        # Show execution plan
        self._show_execution_plan(validation_result["execution_plan"])

        # Load and execute
        data = self._load_initial_data(initial_data)
        print("\n🚀 Executing DAG pipeline...")
        result = runner.run(data)
        print("\n✅ Execution complete!")
        print(f"📊 Result: {result}")

    def _run_with_spec(self, spec_path: Path, initial_data: str | None) -> None:
        """Execute DAG with spec-driven approach."""
        print(f"📖 Loading spec: {spec_path}")
        ir = load_spec(str(spec_path))
        print(f"✅ Loaded {len(ir.transforms)} Transforms, {len(ir.dag_stages)} DAG stages")

        print("🔄 Normalizing IR...")
        normalized = normalize_ir(ir)
        print("✅ Normalization complete")

        if not normalized.dag_stages:
            print("\n❌ Error: No dag_stages defined in spec")
            print("   Either define dag_stages in spec or use --config to specify execution")
            sys.exit(1)

        # Build DAG runner
        print("🔍 Building DAG execution plan...")
        runner = DAGRunner(normalized)
        execution_order = runner.get_execution_order()
        print(f"✅ Execution order: {[s.stage_id for s in execution_order]}")

        # Load and execute
        data = self._load_initial_data(initial_data)
        print("\n🚀 Executing DAG pipeline...")
        result = runner.run_dag(data)
        print("\n✅ Execution complete!")
        print(f"📊 Result: {result}")

    def _show_execution_plan(self, execution_plan: list) -> None:
        """Display execution plan."""
        print(f"\n📋 Execution plan ({len(execution_plan)} step(s)):")
        for idx, step in enumerate(execution_plan, start=1):
            print(f"  {idx}. Stage: {step['stage_id']}")
            print(f"     Transform: {step['transform_id']}")
            if step["params"]:
                print(f"     Params: {step['params']}")

    def _load_initial_data(self, initial_data: str | None) -> dict:
        """Load initial data from file or return empty dict."""
        if initial_data:
            import json

            initial_data_path = Path(initial_data)
            if not initial_data_path.exists():
                print(f"❌ Error: Initial data file not found: {initial_data_path}")
                sys.exit(1)

            with open(initial_data_path) as f:
                data = json.load(f)
            print(f"\n📊 Loaded initial data from: {initial_data_path}")
            return data

        print("\n⚠️  No initial data provided (use --initial-data to specify)")
        print("   Using empty dict as initial data")
        return {}

    def version(self) -> None:
        """Show version information."""
        print(f"spectool {__version__}")

    def _collect_referenced_card_keys(self, dag_stage_groups: list) -> set[str]:
        """DAGステージグループから参照されているカードキーを収集"""
        referenced_card_keys = set()

        for group in dag_stage_groups:
            related = group["related_cards"]

            # 単一カード
            for card_key in ["stage_card", "input_dtype_card", "output_dtype_card"]:
                if related.get(card_key):
                    card = related[card_key]
                    referenced_card_keys.add(f"{card['source_spec']}::{card['id']}")

            # リスト型カード
            for card_list_key in [
                "transform_cards",
                "generator_cards",
                "param_dtype_cards",
                "input_example_cards",
                "output_example_cards",
                "input_check_cards",
                "output_check_cards",
            ]:
                for card in related.get(card_list_key, []):
                    referenced_card_keys.add(f"{card['source_spec']}::{card['id']}")

        return referenced_card_keys

    def _process_spec_file(self, spec_file: str) -> dict | None:
        """単一のspecファイルを処理してカードデータを返す"""
        spec_path = Path(spec_file)
        if not spec_path.exists():
            print(f"⚠️  Skipped: {spec_file} (not found)")
            return None

        try:
            print(f"\n📖 Processing: {spec_path}")
            ir = load_spec(str(spec_path))
            normalized = normalize_ir(ir)
            cards_data = export_spec_to_cards(normalized, spec_file)

            num_cards = len(cards_data["cards"])
            num_groups = len(cards_data["dag_stage_groups"])
            print(f"✅ Exported {num_cards} cards, {num_groups} DAG stage groups from {spec_path.name}")

            return cards_data

        except Exception as e:
            print(f"⚠️  Skipped {spec_file}: {e}")
            return None

    def export_cards(self, *specs: str, output: str = "frontend/public/cards") -> None:
        """Export YAML specs to JSON cards for frontend display.

        Args:
            *specs: Spec YAML files (e.g., specs/*.yaml)
            output: Output directory (default: frontend/public/cards)

        Example:
            python -m spectool export-cards specs/*.yaml --output frontend/public/cards
        """
        import json

        if not specs:
            print("❌ Error: No spec files provided")
            print("   Usage: spectool export-cards specs/*.yaml [--output DIR]")
            sys.exit(1)

        # 出力ディレクトリ作成
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Output directory: {output_dir}")

        # 統合データを準備
        all_specs = []
        all_cards = []
        all_dag_stage_groups = []

        # 各specファイルを処理
        for spec_file in specs:
            cards_data = self._process_spec_file(spec_file)
            if cards_data:
                all_specs.append(cards_data["metadata"])
                all_cards.extend(cards_data["cards"])
                all_dag_stage_groups.extend(cards_data["dag_stage_groups"])

        # referenced_card_keysとunlinked_card_keysを計算
        all_card_keys = {f"{card['source_spec']}::{card['id']}" for card in all_cards}
        referenced_card_keys = self._collect_referenced_card_keys(all_dag_stage_groups)
        unlinked_card_keys = all_card_keys - referenced_card_keys

        # 統合JSONを構築
        output_data = {
            "specs": all_specs,
            "cards": all_cards,
            "dag_stage_groups": all_dag_stage_groups,
            "referenced_card_keys": sorted(list(referenced_card_keys)),
            "unlinked_card_keys": sorted(list(unlinked_card_keys)),
        }

        # all-cards.json に書き込み
        output_file = output_dir / "all-cards.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print("\n✅ Export complete!")
        print(f"   Total specs: {len(all_specs)}")
        print(f"   Total cards: {len(all_cards)}")
        print(f"   Total DAG stage groups: {len(all_dag_stage_groups)}")
        print(f"   Referenced cards: {len(referenced_card_keys)}")
        print(f"   Unlinked cards: {len(unlinked_card_keys)}")
        coverage_pct = 100 * len(referenced_card_keys) // len(all_cards)
        print(f"   Coverage: {len(referenced_card_keys)}/{len(all_cards)} ({coverage_pct}%)")
        print(f"   Output file: {output_file}")


def spectool_main() -> None:
    """Spectool CLI entry point (called from python -m spectool)."""
    fire.Fire(SpectoolCLI)


if __name__ == "__main__":
    spectool_main()

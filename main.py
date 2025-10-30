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

from spectool.spectool.core.engine.loader import load_spec
from spectool.spectool.core.engine.normalizer import normalize_ir
from spectool.spectool.core.engine.validate import validate_ir, validate_spec
from spectool.spectool.core.engine.integrity import IntegrityValidator
from spectool.spectool.core.engine.dag_runner import DAGRunner
from spectool.spectool.core.engine.config_runner import ConfigRunner
from spectool.spectool.backends.py_skeleton import generate_skeleton
from spectool.spectool.backends.py_code import (
    generate_dataframe_aliases,
    generate_models_file,
)
from spectool.spectool.backends.py_validators import generate_pandera_schemas

__version__ = "2.0.0-alpha"


class SpectoolCLI:
    """Spectool - Spec2Code Next Generation CLI"""

    def validate(self, spec_file: str, debug: bool = False) -> None:
        """Validate spec file for correctness.

        Args:
            spec_file: Path to spec YAML file
            debug: Enable debug output
        """
        spec_path = Path(spec_file)
        if not spec_path.exists():
            print(f"❌ Error: Spec file not found: {spec_path}")
            sys.exit(1)

        try:
            # Load spec
            print(f"📖 Loading spec: {spec_path}")
            ir = load_spec(str(spec_path))
            print(f"✅ Loaded {len(ir.frames)} DataFrames, {len(ir.transforms)} Transforms")

            # Normalize
            print("🔄 Normalizing IR...")
            normalized = normalize_ir(ir)
            print("✅ Normalization complete")

            # Validate IR
            print("🔍 Validating IR...")
            errors = validate_ir(normalized, skip_impl_check=True)

            if errors:
                print(f"\n❌ Validation failed with {len(errors)} error(s):")
                for error in errors:
                    print(f"  ⚠️  {error}")
                sys.exit(1)

            print("✅ All validations passed")

        except Exception as e:
            print(f"❌ Error: {e}")
            if debug:
                import traceback

                traceback.print_exc()
            sys.exit(1)

    def gen(self, spec_file: str, output_dir: str | None = None, debug: bool = False) -> None:
        """Generate skeleton code from spec file.

        Args:
            spec_file: Path to spec YAML file
            output_dir: Output directory (default: current directory, generates apps/<project-name>/)
            debug: Enable debug output
        """
        spec_path = Path(spec_file)
        if not spec_path.exists():
            print(f"❌ Error: Spec file not found: {spec_path}")
            sys.exit(1)

        try:
            # Load spec
            print(f"📖 Loading spec: {spec_path}")
            ir = load_spec(str(spec_path))
            print(f"✅ Loaded {len(ir.frames)} DataFrames, {len(ir.transforms)} Transforms, {len(ir.checks)} Checks")

            # Normalize
            print("🔄 Normalizing IR...")
            normalized = normalize_ir(ir)
            print("✅ Normalization complete")

            # Validate IR (skip implementation checks for gen)
            print("🔍 Validating IR...")
            errors = validate_ir(normalized, skip_impl_check=True)
            if errors:
                print(f"\n⚠️  Found {len(errors)} validation warnings:")
                for error in errors:
                    print(f"  ⚠️  {error}")
                print("Continuing with code generation...\n")
            else:
                print("✅ All validations passed")

            # Determine output directory
            if output_dir:
                out_path = Path(output_dir)
            else:
                # Default: current directory (will generate apps/<project-name>/)
                out_path = Path(".")

            print(f"📁 Output directory: {out_path}")

            # Generate complete skeleton using generate_skeleton
            print("🔨 Generating skeleton code...")
            generate_skeleton(normalized, out_path)

            project_name = normalized.meta.name if normalized.meta else "generated-project"
            app_root = out_path / "apps" / project_name

            print(f"\n✅ Skeleton generation complete!")
            print(f"   Generated project in: {app_root}")
            print(f"   Structure:")
            print(f"     - checks/     (validation functions)")
            print(f"     - transforms/ (processing functions)")
            print(f"     - generators/ (data generator functions)")
            print(f"     - models/     (Pydantic models)")
            print(f"     - schemas/    (Pandera validation schemas)")

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
            # Load spec
            print(f"📖 Loading spec: {spec_path}")
            ir = load_spec(str(spec_path))
            print(f"✅ Loaded {len(ir.frames)} DataFrames, {len(ir.transforms)} Transforms")

            # Normalize
            print("🔄 Normalizing IR...")
            normalized = normalize_ir(ir)
            print("✅ Normalization complete")

            # Check if generated directory exists
            project_name = normalized.meta.name if normalized.meta else "generated-project"
            app_root = Path("apps") / project_name

            print("🔍 Checking generated code...")
            print(f"  📁 Expected directory: {app_root}")

            if not app_root.exists():
                print(f"    ❌ Directory not found")
                print("\n❌ Error: Generated code directory not found")
                print("   Run 'spectool gen' first to generate code.")
                sys.exit(1)
            print(f"    ✅ Directory exists")

            # Check for required directories
            print("  🔍 Checking generated structure...")
            required_dirs = ["checks", "transforms", "generators", "models", "schemas"]
            missing_dirs = []

            for dirname in required_dirs:
                dir_path = app_root / dirname
                if dir_path.exists():
                    print(f"    ✅ {dirname}/")
                else:
                    print(f"    ⚠️  {dirname}/ (missing, may not be needed)")

            if missing_dirs:
                print(f"\n⚠️  Warning: Some directories are missing: {', '.join(missing_dirs)}")
                print("   This may be expected if your spec doesn't use all features.")

            # Validate against spec using IntegrityValidator
            print("  🔍 Validating implementation integrity...")
            validator = IntegrityValidator(normalized)
            result = validator.validate_integrity()

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

        except Exception as e:
            print(f"❌ Error: {e}")
            if debug:
                import traceback

                traceback.print_exc()
            sys.exit(1)

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
                # Config-driven execution
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
                execution_plan = validation_result["execution_plan"]
                print(f"\n📋 Execution plan ({len(execution_plan)} step(s)):")
                for idx, step in enumerate(execution_plan, start=1):
                    print(f"  {idx}. Stage: {step['stage_id']}")
                    print(f"     Transform: {step['transform_id']}")
                    if step["params"]:
                        print(f"     Params: {step['params']}")

                # Load initial data
                if initial_data:
                    import json

                    initial_data_path = Path(initial_data)
                    if not initial_data_path.exists():
                        print(f"❌ Error: Initial data file not found: {initial_data_path}")
                        sys.exit(1)

                    with open(initial_data_path) as f:
                        data = json.load(f)
                    print(f"\n📊 Loaded initial data from: {initial_data_path}")
                else:
                    print("\n⚠️  No initial data provided (use --initial-data to specify)")
                    print("   Using empty dict as initial data")
                    data = {}

                # Execute
                print("\n🚀 Executing DAG pipeline...")
                result = runner.run(data)
                print("\n✅ Execution complete!")
                print(f"📊 Result: {result}")

            else:
                # Spec-driven execution (using default_transform_id in dag_stages)
                print(f"📖 Loading spec: {spec_path}")
                ir = load_spec(str(spec_path))
                print(f"✅ Loaded {len(ir.transforms)} Transforms, {len(ir.dag_stages)} DAG stages")

                # Normalize
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

                # Load initial data
                if initial_data:
                    import json

                    initial_data_path = Path(initial_data)
                    if not initial_data_path.exists():
                        print(f"❌ Error: Initial data file not found: {initial_data_path}")
                        sys.exit(1)

                    with open(initial_data_path) as f:
                        data = json.load(f)
                    print(f"\n📊 Loaded initial data from: {initial_data_path}")
                else:
                    print("\n⚠️  No initial data provided (use --initial-data to specify)")
                    print("   Using empty dict as initial data")
                    data = {}

                # Execute
                print("\n🚀 Executing DAG pipeline...")
                result = runner.run_dag(data)
                print("\n✅ Execution complete!")
                print(f"📊 Result: {result}")

        except Exception as e:
            print(f"❌ Error: {e}")
            if debug:
                import traceback

                traceback.print_exc()
            sys.exit(1)

    def version(self) -> None:
        """Show version information."""
        print(f"spectool {__version__}")


def spectool_main() -> None:
    """Spectool CLI entry point (called from python -m spectool)."""
    fire.Fire(SpectoolCLI)


if __name__ == "__main__":
    spectool_main()

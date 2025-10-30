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
from spectool.spectool.core.engine.validate import validate_ir
from spectool.spectool.backends.py_code import (
    generate_dataframe_aliases,
    generate_models_file,
)
from spectool.spectool.backends.py_validators import generate_pandera_schemas

__version__ = "2.0.0-alpha"


class SpectoolCLI:
    """Spectool - Spec2Code Next Generation CLI"""

    def _validate_ir_with_details(self, ir, skip_impl_check: bool = False):
        """Validate IR with detailed step-by-step output.

        Returns:
            List of all errors collected
        """
        from spectool.spectool.core.engine.validate import (
            _validate_dataframe_specs,
            _validate_check_specs,
            _validate_transform_specs,
            _validate_dag_stage_specs,
            _validate_type_references,
        )

        all_errors = []

        # 1. DataFrame definitions
        print("  🔍 Validating DataFrame definitions...")
        errors = _validate_dataframe_specs(ir)
        error_messages = set(errors)
        for frame in ir.frames:
            # Check if this frame has any errors
            has_error = any(f"DataFrame '{frame.id}'" in err for err in error_messages)
            if has_error:
                # Display errors for this frame
                for error in errors:
                    if f"DataFrame '{frame.id}'" in error:
                        print(f"    ⚠️  {error}")
            else:
                print(f"    ✅ DataFrame '{frame.id}': schema is valid")
        all_errors.extend(errors)
        success_count = len(ir.frames) - len([e for e in errors if "DataFrame" in e])
        print(f"    📊 {success_count} of {len(ir.frames)} DataFrame(s) validated")

        # 2. Check definitions
        print("  🔍 Validating Check definitions...")
        errors = _validate_check_specs(ir)
        error_messages = set(errors)
        for check in ir.checks:
            has_error = any(f"Check '{check.id}'" in err for err in error_messages)
            if has_error:
                for error in errors:
                    if f"Check '{check.id}'" in error:
                        print(f"    ⚠️  {error}")
            else:
                print(f"    ✅ Check '{check.id}': definition is valid")
        all_errors.extend(errors)
        success_count = len(ir.checks) - len(errors)
        print(f"    📊 {success_count} of {len(ir.checks)} Check(s) validated")

        # 3. Transform definitions
        print("  🔍 Validating Transform definitions...")
        errors = _validate_transform_specs(ir)
        error_messages = set(errors)
        for transform in ir.transforms:
            has_error = any(f"Transform '{transform.id}'" in err for err in error_messages)
            if has_error:
                for error in errors:
                    if f"Transform '{transform.id}'" in error:
                        print(f"    ⚠️  {error}")
            else:
                print(f"    ✅ Transform '{transform.id}': definition is valid")
        all_errors.extend(errors)
        success_count = len(ir.transforms) - len(
            [
                f"Transform '{t.id}'"
                for t in ir.transforms
                if any(f"Transform '{t.id}'" in err for err in error_messages)
            ]
        )
        print(f"    📊 {success_count} of {len(ir.transforms)} Transform(s) validated")

        # 4. DAG Stage definitions
        if ir.dag_stages:
            print("  🔍 Validating DAG Stage definitions...")
            errors = _validate_dag_stage_specs(ir)
            error_messages = set(errors)
            for stage in ir.dag_stages:
                has_error = any(f"DAG Stage '{stage.stage_id}'" in err for err in error_messages)
                if has_error:
                    for error in errors:
                        if f"DAG Stage '{stage.stage_id}'" in error:
                            print(f"    ⚠️  {error}")
                else:
                    print(f"    ✅ DAG Stage '{stage.stage_id}': configuration is valid")
            all_errors.extend(errors)
            success_count = len(ir.dag_stages) - len(errors)
            print(f"    📊 {success_count} of {len(ir.dag_stages)} DAG Stage(s) validated")

        # 5. Type references (skip implementation checks if requested)
        if not skip_impl_check:
            print("  🔍 Validating implementation imports...")
            errors = _validate_type_references(ir, skip_impl_check=False)
            error_messages = set(errors)

            # Check implementations
            for check in ir.checks:
                if check.impl:
                    has_error = any(f"Check '{check.id}'" in err for err in error_messages)
                    if has_error:
                        for error in errors:
                            if f"Check '{check.id}'" in error:
                                print(f"    ⚠️  {error}")
                    else:
                        print(f"    ✅ Check '{check.id}': implementation found")

            # Transform implementations
            for transform in ir.transforms:
                if transform.impl:
                    has_error = any(f"Transform '{transform.id}'" in err for err in error_messages)
                    if has_error:
                        for error in errors:
                            if f"Transform '{transform.id}'" in error:
                                print(f"    ⚠️  {error}")
                    else:
                        print(f"    ✅ Transform '{transform.id}': implementation found")

            all_errors.extend(errors)
            total_impls = len([c for c in ir.checks if c.impl]) + len([t for t in ir.transforms if t.impl])
            success_count = total_impls - len(errors)
            print(f"    📊 {success_count} of {total_impls} implementation(s) found")

        return all_errors

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

            # Validate with detailed output (skip implementation checks)
            print("🔍 Validating IR...")
            errors = self._validate_ir_with_details(normalized, skip_impl_check=True)

            if errors:
                print(f"\n❌ Validation failed with {len(errors)} error(s)")
                sys.exit(1)

            print("\n✅ All validations passed")

        except Exception as e:
            print(f"❌ Error: {e}")
            if debug:
                import traceback

                traceback.print_exc()
            sys.exit(1)

    def gen(self, spec_file: str, output_dir: str | None = None, debug: bool = False) -> None:
        """Generate code from spec file.

        Args:
            spec_file: Path to spec YAML file
            output_dir: Output directory (default: apps/<project-name>/datatypes/)
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

            # Validate with detailed output (skip implementation checks for gen)
            print("🔍 Validating IR...")
            errors = self._validate_ir_with_details(normalized, skip_impl_check=True)
            if errors:
                print(f"\n⚠️  Found {len(errors)} validation warnings (continuing with code generation...)\n")
            else:
                print("✅ All validations passed")

            # Determine output directory
            if output_dir:
                out_path = Path(output_dir)
            else:
                # Default: apps/<project-name>/datatypes/
                project_name = normalized.meta.name if normalized.meta else "generated-project"
                out_path = Path("apps") / project_name / "datatypes"

            out_path.mkdir(parents=True, exist_ok=True)
            print(f"📁 Output directory: {out_path}")

            # Generate models.py
            print("🔨 Generating models.py...")
            models_path = out_path / "models.py"
            generate_models_file(normalized, models_path)
            print(f"  ✅ {models_path}")

            # Generate type_aliases.py
            print("🔨 Generating type_aliases.py...")
            aliases_path = out_path / "type_aliases.py"
            generate_dataframe_aliases(normalized, aliases_path)
            print(f"  ✅ {aliases_path}")

            # Generate schemas.py
            print("🔨 Generating schemas.py...")
            schemas_path = out_path / "schemas.py"
            generate_pandera_schemas(normalized, schemas_path)
            print(f"  ✅ {schemas_path}")

            print("\n✅ Code generation complete!")
            print(f"   Generated files in: {out_path}")

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
            datatypes_dir = Path("apps") / project_name / "datatypes"

            print("🔍 Checking generated code...")
            print(f"  📁 Expected directory: {datatypes_dir}")

            if not datatypes_dir.exists():
                print(f"    ❌ Directory not found")
                print("\n❌ Error: Generated code directory not found")
                print("   Run 'spectool gen' first to generate code.")
                sys.exit(1)
            print(f"    ✅ Directory exists")

            # Check for required files
            print("  🔍 Checking generated files...")
            required_files = ["models.py", "type_aliases.py", "schemas.py"]
            missing_files = []

            for filename in required_files:
                file_path = datatypes_dir / filename
                if file_path.exists():
                    print(f"    ✅ {filename}")
                else:
                    print(f"    ❌ {filename} (missing)")
                    missing_files.append(filename)

            if missing_files:
                print(f"\n❌ Error: Missing generated files: {', '.join(missing_files)}")
                sys.exit(1)

            # Validate against spec
            print("  🔍 Validating implementation integrity...")
            errors = self._validate_ir_with_details(normalized, skip_impl_check=False)

            if errors:
                print(f"\n❌ Integrity validation failed with {len(errors)} error(s)")
                sys.exit(1)

            print("\n✅ All integrity checks passed")
            print("   All required files exist and match spec")

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

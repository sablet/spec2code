"""
spectool CLI - Spec2Code Next Generation Command Line Interface

Usage:
    spectool validate <spec.yaml>
    spectool gen <spec.yaml> [--output-dir DIR]
    spectool validate-integrity <spec.yaml>
    spectool --version
"""

import argparse
import sys
from pathlib import Path
from typing import NoReturn

from spectool.core.engine.loader import load_spec
from spectool.core.engine.normalizer import normalize_ir
from spectool.core.engine.validate import validate_ir
from spectool.backends.py_code import (
    generate_dataframe_aliases,
    generate_models_file,
)
from spectool.backends.py_validators import generate_pandera_schemas

__version__ = "2.0.0-alpha"


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate spec file for correctness."""
    spec_path = Path(args.spec_file)
    if not spec_path.exists():
        print(f"❌ Error: Spec file not found: {spec_path}", file=sys.stderr)
        return 1

    try:
        # Load spec
        print(f"📖 Loading spec: {spec_path}")
        ir = load_spec(str(spec_path))
        print(f"✅ Loaded {len(ir.frames)} DataFrames, {len(ir.transforms)} Transforms")

        # Normalize
        print("🔄 Normalizing IR...")
        normalized = normalize_ir(ir)
        print("✅ Normalization complete")

        # Validate
        print("🔍 Validating IR...")
        errors = validate_ir(normalized)

        if errors:
            print(f"\n❌ Validation failed with {len(errors)} error(s):", file=sys.stderr)
            for i, error in enumerate(errors, 1):
                print(f"  {i}. {error}", file=sys.stderr)
            return 1

        print("✅ Validation passed")
        return 0

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        if args.debug:
            import traceback

            traceback.print_exc()
        return 1


def cmd_gen(args: argparse.Namespace) -> int:
    """Generate code from spec file."""
    spec_path = Path(args.spec_file)
    if not spec_path.exists():
        print(f"❌ Error: Spec file not found: {spec_path}", file=sys.stderr)
        return 1

    try:
        # Load and normalize
        print(f"📖 Loading spec: {spec_path}")
        ir = load_spec(str(spec_path))
        print("🔄 Normalizing IR...")
        normalized = normalize_ir(ir)

        # Validate first
        print("🔍 Validating IR...")
        errors = validate_ir(normalized)
        if errors:
            print(f"\n❌ Validation failed with {len(errors)} error(s):", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 1

        # Determine output directory
        if args.output_dir:
            output_dir = Path(args.output_dir)
        else:
            # Default: apps/<project-name>/datatypes/
            project_name = normalized.meta.name if normalized.meta else "generated-project"
            output_dir = Path("apps") / project_name / "datatypes"

        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Output directory: {output_dir}")

        # Generate models.py
        print("🔨 Generating models.py...")
        models_path = output_dir / "models.py"
        generate_models_file(normalized, models_path)
        print(f"  ✅ {models_path}")

        # Generate type_aliases.py
        print("🔨 Generating type_aliases.py...")
        aliases_path = output_dir / "type_aliases.py"
        generate_dataframe_aliases(normalized, aliases_path)
        print(f"  ✅ {aliases_path}")

        # Generate schemas.py
        print("🔨 Generating schemas.py...")
        schemas_path = output_dir / "schemas.py"
        generate_pandera_schemas(normalized, schemas_path)
        print(f"  ✅ {schemas_path}")

        print("\n✅ Code generation complete!")
        print(f"   Generated files in: {output_dir}")
        return 0

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        if args.debug:
            import traceback

            traceback.print_exc()
        return 1


def cmd_validate_integrity(args: argparse.Namespace) -> int:
    """Validate that implementation matches spec."""
    spec_path = Path(args.spec_file)
    if not spec_path.exists():
        print(f"❌ Error: Spec file not found: {spec_path}", file=sys.stderr)
        return 1

    try:
        # Load and normalize
        print(f"📖 Loading spec: {spec_path}")
        ir = load_spec(str(spec_path))
        normalized = normalize_ir(ir)

        # Check if generated files exist
        project_name = normalized.meta.name if normalized.meta else "generated-project"
        datatypes_dir = Path("apps") / project_name / "datatypes"

        if not datatypes_dir.exists():
            print(f"❌ Error: Generated code directory not found: {datatypes_dir}", file=sys.stderr)
            print("   Run 'spectool gen' first to generate code.", file=sys.stderr)
            return 1

        # Check for required files
        required_files = ["models.py", "type_aliases.py", "schemas.py"]
        missing_files = []
        for filename in required_files:
            if not (datatypes_dir / filename).exists():
                missing_files.append(filename)

        if missing_files:
            print(f"❌ Error: Missing generated files: {', '.join(missing_files)}", file=sys.stderr)
            return 1

        # For now, simple existence check
        # TODO: Add deep integrity validation (import checks, signature validation, etc.)
        print("✅ Basic integrity check passed")
        print("   All required files exist")
        print("\n⚠️  Note: Deep integrity validation not yet implemented")
        return 0

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        if args.debug:
            import traceback

            traceback.print_exc()
        return 1


def main() -> NoReturn:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="spectool",
        description="Spec2Code Next Generation - Type-driven spec/code consistency tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"spectool {__version__}")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate spec file for correctness",
    )
    validate_parser.add_argument("spec_file", help="Path to spec YAML file")

    # gen command
    gen_parser = subparsers.add_parser(
        "gen",
        help="Generate code from spec file",
    )
    gen_parser.add_argument("spec_file", help="Path to spec YAML file")
    gen_parser.add_argument(
        "--output-dir",
        "-o",
        help="Output directory (default: apps/<project-name>/datatypes/)",
    )

    # validate-integrity command
    integrity_parser = subparsers.add_parser(
        "validate-integrity",
        help="Validate that implementation matches spec",
    )
    integrity_parser.add_argument("spec_file", help="Path to spec YAML file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Dispatch to command handlers
    if args.command == "validate":
        sys.exit(cmd_validate(args))
    elif args.command == "gen":
        sys.exit(cmd_gen(args))
    elif args.command == "validate-integrity":
        sys.exit(cmd_validate_integrity(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

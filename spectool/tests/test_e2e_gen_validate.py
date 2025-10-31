"""E2E統合テスト: gen -> validate フロー

実際のspecファイルを使用して、コード生成からバリデーションまでの
完全なフローがエラーなく動作することを確認する。
"""

from pathlib import Path
import tempfile
import pytest
import shutil

from spectool.spectool.core.engine.loader import load_spec
from spectool.spectool.core.engine.normalizer import normalize_ir
from spectool.spectool.backends.py_skeleton import generate_skeleton
from spectool.spectool.core.engine.integrity import IntegrityValidator


@pytest.fixture
def temp_project_dir():
    """一時プロジェクトディレクトリ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def algo_trade_spec():
    """algo-trade-pipeline.yaml のパス"""
    spec_path = Path(__file__).parent.parent.parent / "specs" / "algo-trade-pipeline.yaml"
    if not spec_path.exists():
        pytest.skip(f"algo-trade-pipeline.yaml not found at {spec_path}")
    return spec_path


def test_algo_trade_pipeline_gen_validate_e2e(temp_project_dir, algo_trade_spec):
    """algo-trade-pipeline: gen -> validate が完全に成功すること

    このテストは以下を確認する：
    1. specがロード・正規化できる
    2. スケルトンコードが生成できる
    3. 生成されたコードに必要な型定義が全て含まれている
    4. integrityバリデーションで関数が全てimportできる（実装は不要）
    """
    # 1. Load and normalize spec
    print(f"\n📖 Loading spec: {algo_trade_spec}")
    ir = load_spec(str(algo_trade_spec))
    assert ir.meta.name == "algo_trade_pipeline", "Should load correct spec"

    normalized = normalize_ir(ir)
    assert len(normalized.transforms) > 0, "Should have transforms"
    assert len(normalized.checks) > 0, "Should have checks"
    assert len(normalized.generators) > 0, "Should have generators"

    # Check type_aliases and generics are loaded
    assert len(normalized.type_aliases) > 0, "Should load type_aliases"
    assert len(normalized.generics) > 0, "Should load generics"

    print(
        f"  ✅ Loaded: {len(normalized.transforms)} transforms, "
        f"{len(normalized.checks)} checks, {len(normalized.generators)} generators"
    )
    print(f"  ✅ Loaded: {len(normalized.type_aliases)} type_aliases, {len(normalized.generics)} generics")

    # 2. Generate skeleton
    print(f"\n🔨 Generating skeleton in: {temp_project_dir}")
    generate_skeleton(normalized, temp_project_dir)

    app_root = temp_project_dir / "apps" / "algo_trade_pipeline"
    assert app_root.exists(), "App directory should be created"

    # 3. Verify types.py contains all required type definitions
    types_file = app_root / "types.py"
    assert types_file.exists(), "types.py should be generated"

    types_content = types_file.read_text()

    # Check critical type_alias definitions are generated
    missing_types = []
    required_types = [
        "MultiAssetOHLCVFrame",  # type_alias: simple
        "AlignedFeatureTarget",  # type_alias: tuple
        "PredictionDataList",  # generic: list
    ]

    for type_name in required_types:
        if type_name not in types_content:
            missing_types.append(type_name)

    if missing_types:
        print(f"\n❌ Missing type definitions in types.py:")
        for mt in missing_types:
            print(f"  - {mt}")
        print(f"\nGenerated types.py preview:")
        print("=" * 80)
        lines = types_content.split("\n")
        for i, line in enumerate(lines[:50], 1):
            print(f"{i:3}: {line}")
        if len(lines) > 50:
            print(f"... ({len(lines) - 50} more lines)")
        print("=" * 80)

    assert len(missing_types) == 0, (
        f"types.py is missing required type definitions: {missing_types}. "
        f"type_alias and generic code generation is not implemented."
    )

    # 4. Verify transform files can import these types
    print(f"\n🔍 Checking transform files...")
    transform_files = list((app_root / "transforms").glob("*.py"))
    assert len(transform_files) > 0, "Should have generated transform files"

    for tf in transform_files:
        if tf.name == "__init__.py":
            continue
        content = tf.read_text()
        # Should import from types module
        assert "from apps.algo_trade_pipeline.types import" in content, f"{tf.name} should import from types module"

    # 5. Run integrity validation
    print(f"\n✅ Running integrity validation...")
    validator = IntegrityValidator(normalized)
    errors = validator.validate_integrity(temp_project_dir)

    # Count errors by category
    error_summary = {}
    for category, err_list in errors.items():
        if err_list:
            error_summary[category] = len(err_list)

    # Display errors if any
    if error_summary:
        print(f"\n❌ Integrity validation errors:")
        for category, count in error_summary.items():
            print(f"  - {category}: {count} error(s)")

        # Show first few errors for debugging
        for category, err_list in errors.items():
            if err_list:
                print(f"\n{category} (showing first 3):")
                for err in err_list[:3]:
                    print(f"  ⚠️  {err}")

    # Assert: All functions should be importable (skeletons exist)
    # We don't require implementations, just that modules can be imported
    total_errors = sum(len(err_list) for err_list in errors.values())

    assert total_errors == 0, (
        f"Integrity validation should pass for generated skeleton code. "
        f"Found {total_errors} errors across categories: {error_summary}. "
        f"This indicates missing type definitions or incorrect imports."
    )

    print(f"\n✅ E2E test passed: gen -> validate completed successfully")


def test_simple_spec_gen_validate_e2e(temp_project_dir):
    """シンプルなspecで gen -> validate が完全に成功すること"""
    spec_yaml = """
version: "1.0"
meta:
  name: simple_project
  description: "Simple E2E test spec"

checks:
  - id: check_value
    description: "Check value"
    impl: "apps.simple_project.checks.validators:check_value"
    file_path: "checks/validators.py"

datatypes:
  - id: DataModel
    description: "Simple data model"
    pydantic_model:
      fields:
        - name: value
          type:
            native: "builtins:float"
          required: true

transforms:
  - id: process_value
    description: "Process value"
    impl: "apps.simple_project.transforms.processors:process_value"
    file_path: "transforms/processors.py"
    parameters:
      - name: data
        datatype_ref: DataModel
    return_datatype_ref: DataModel
"""

    spec_path = temp_project_dir / "simple_spec.yaml"
    spec_path.write_text(spec_yaml)

    # Load and generate
    ir = load_spec(str(spec_path))
    normalized = normalize_ir(ir)
    generate_skeleton(normalized, temp_project_dir)

    # Validate
    validator = IntegrityValidator(normalized)
    errors = validator.validate_integrity(temp_project_dir)

    # Should detect missing implementations (but modules should be importable)
    # Since we don't implement the functions, we expect import errors
    total_errors = sum(len(err_list) for err_list in errors.values())

    # With skeleton only, functions exist as stubs with TODO
    # IntegrityValidator tries to import them, which should succeed
    assert total_errors == 0, f"Should be able to import skeleton functions. Found {total_errors} errors."


def test_type_alias_spec_gen_validate_e2e(temp_project_dir):
    """type_alias を含むspecで gen -> validate が成功すること

    これは現在失敗することが期待される（type_alias未実装）
    """
    spec_yaml = """
version: "1.0"
meta:
  name: test_alias_project
  description: "Test spec with type_alias"

checks:
  - id: check_frame
    description: "Check dataframe"
    impl: "apps.checks:check_frame"
    file_path: "apps/checks/validators.py"

datatypes:
  - id: BaseFrame
    description: "Base DataFrame"
    dataframe_schema:
      index:
        name: id
        dtype: int
        nullable: false
      columns:
        - name: value
          dtype: float
          nullable: false

  - id: AliasFrame
    description: "Aliased DataFrame"
    check_functions:
      - check_frame
    type_alias:
      type: simple
      target: "pandas:DataFrame"

transforms:
  - id: process_alias_frame
    description: "Process aliased frame"
    impl: "apps.transforms:process_alias_frame"
    file_path: "apps/transforms/processors.py"
    parameters:
      - name: data
        datatype_ref: AliasFrame
    return_datatype_ref: AliasFrame
"""

    spec_path = temp_project_dir / "alias_spec.yaml"
    spec_path.write_text(spec_yaml)

    # Load and generate
    ir = load_spec(str(spec_path))
    normalized = normalize_ir(ir)

    # Should load type_alias
    assert len(normalized.type_aliases) > 0, "Should load type_aliases"

    generate_skeleton(normalized, temp_project_dir)

    # Check types.py
    types_file = temp_project_dir / "apps" / "test_alias_project" / "types.py"
    assert types_file.exists(), "types.py should be generated"

    types_content = types_file.read_text()

    # AliasFrame should be in types.py
    assert "AliasFrame" in types_content, (
        "AliasFrame TypeAlias should be generated in types.py. type_alias code generation is not implemented."
    )

    # Validate
    validator = IntegrityValidator(normalized)
    errors = validator.validate_integrity(temp_project_dir)

    total_errors = sum(len(err_list) for err_list in errors.values())
    assert total_errors == 0, f"Should be able to validate after generating type_alias. Found {total_errors} errors."

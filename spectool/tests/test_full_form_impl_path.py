"""完全形式implパスのテスト

apps.project_name.module:func 形式のimplパスが正しく処理されることを確認する。
短縮形式 apps.module:func と混在していても正しく動作すること。
"""

from pathlib import Path
import tempfile
import pytest

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
def full_form_spec(temp_project_dir):
    """完全形式のimplパスを使用するspec"""
    spec_yaml = """
version: "1.0"
meta:
  name: test_project
  description: "Test spec with full-form impl paths"

checks:
  - id: check_positive
    description: "Check positive values"
    impl: "apps.test_project.checks.validators:check_positive"
    file_path: "checks/validators.py"

  - id: check_negative
    description: "Check negative values (short-form)"
    impl: "apps.checks:check_negative"
    file_path: "apps/checks/validators.py"

datatypes:
  - id: TestModel
    description: "Test Pydantic model"
    pydantic_model:
      fields:
        - name: value
          type:
            native: "builtins:float"
          required: true

transforms:
  - id: process_data
    description: "Process data"
    impl: "apps.test_project.transforms.processors:process_data"
    file_path: "transforms/processors.py"
    parameters:
      - name: value
        native: "builtins:float"
    return_native: "builtins:float"

generators:
  - id: gen_test_data
    description: "Generate test data"
    impl: "apps.test_project.generators.data_gen:generate_test_data"
    file_path: "generators/data_gen.py"
    parameters: []
"""
    spec_path = temp_project_dir / "test_spec.yaml"
    spec_path.write_text(spec_yaml)
    return spec_path


def test_full_form_impl_path_generation_and_validation(temp_project_dir, full_form_spec):
    """完全形式のimplパスでコード生成とバリデーションが成功する"""
    # Load and normalize spec
    ir = load_spec(str(full_form_spec))
    normalized = normalize_ir(ir)

    # Generate skeleton
    generate_skeleton(normalized, temp_project_dir)

    # Verify files were created
    app_root = temp_project_dir / "apps" / "test_project"
    assert (app_root / "checks" / "validators.py").exists()
    assert (app_root / "transforms" / "processors.py").exists()
    assert (app_root / "generators" / "data_gen.py").exists()

    # Implement the functions
    validators_code = """def check_positive(value: float) -> bool:
    return value > 0

def check_negative(value: float) -> bool:
    return value < 0
"""
    (app_root / "checks" / "validators.py").write_text(validators_code)

    processors_code = """def process_data(value: float) -> float:
    return value * 2
"""
    (app_root / "transforms" / "processors.py").write_text(processors_code)

    gen_code = """def generate_test_data():
    return 42.0
"""
    (app_root / "generators" / "data_gen.py").write_text(gen_code)

    # Validate integrity - should pass
    validator = IntegrityValidator(normalized)
    errors = validator.validate_integrity(temp_project_dir)

    # Assert no errors
    total_errors = sum(len(err_list) for err_list in errors.values())
    if total_errors > 0:
        print("Integrity validation errors:")
        for category, err_list in errors.items():
            if err_list:
                print(f"\n{category}:")
                for err in err_list:
                    print(f"  - {err}")
    assert total_errors == 0, "Should have no integrity errors with full-form impl paths"


def test_full_form_impl_path_mixed_with_short_form(temp_project_dir, full_form_spec):
    """完全形式と短縮形式が混在しても正しく処理される"""
    # Load spec
    ir = load_spec(str(full_form_spec))
    normalized = normalize_ir(ir)

    # Generate skeleton
    generate_skeleton(normalized, temp_project_dir)

    # Check that both forms are handled correctly
    validator = IntegrityValidator(normalized)

    # Before implementation, should report missing functions
    errors = validator.validate_integrity(temp_project_dir)

    # Should have errors for missing implementations
    assert len(errors["check_functions"]) > 0, "Should detect missing check functions"
    assert len(errors["transform_functions"]) > 0, "Should detect missing transform functions"
    assert len(errors["generator_functions"]) > 0, "Should detect missing generator functions"

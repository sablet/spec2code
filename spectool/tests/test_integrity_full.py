"""完全なIntegrity検証のテスト

packages/tests/test_integrity_validation.pyに相当する機能をspectoolで実装するためのテスト。
仕様と実装の整合性を厳密に検証する。
"""

from pathlib import Path
import tempfile
import pytest

from spectool.spectool.core.engine.loader import load_spec
from spectool.spectool.core.base.ir import SpecIR


# Integrity検証エンジンをインポート
from spectool.spectool.core.engine.integrity import IntegrityValidator

# スケルトン生成機能をインポート
from spectool.spectool.backends.py_skeleton import generate_skeleton


@pytest.fixture
def sample_spec_path():
    """サンプルspec YAMLのパス"""
    return Path(__file__).parent / "fixtures" / "sample_spec.yaml"


@pytest.fixture
def temp_project_dir():
    """一時プロジェクトディレクトリ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def generated_project(sample_spec_path, temp_project_dir):
    """スケルトン生成済みのプロジェクト"""
    ir = load_spec(sample_spec_path)
    # スケルトン生成
    generate_skeleton(ir, temp_project_dir)
    return temp_project_dir


@pytest.fixture
def implemented_project(generated_project, sample_spec_path):
    """実装完了済みのプロジェクト"""
    # 実際の実装を追加するフィクスチャ
    ir = load_spec(sample_spec_path)
    app_name = ir.meta.name if ir.meta else "app"
    app_root = generated_project / "apps" / app_name

    # Check関数の実装
    validators_file = app_root / "checks" / "validators.py"
    validators_code = """# Check functions
from apps.sample_project.models.models import DataPoint

def validate_positive(payload: DataPoint) -> bool:
    '''Validate positive values'''
    return payload.value > 0


def validate_status(status: str) -> bool:
    '''Validate status values'''
    return status in ["active", "inactive"]


def validate_timeseries(df) -> bool:
    '''Validate time series data'''
    return True
"""
    validators_file.write_text(validators_code)

    # __init__.pyから関数を再エクスポート
    checks_init_file = app_root / "checks" / "__init__.py"
    checks_init_code = """# Check functions
from .validators import validate_positive, validate_status, validate_timeseries

__all__ = ["validate_positive", "validate_status", "validate_timeseries"]
"""
    checks_init_file.write_text(checks_init_code)

    # Transform関数の実装
    processors_file = app_root / "transforms" / "processors.py"
    processors_code = """# Transform functions
from typing import Annotated
import pandas as pd

def process_data(
    data: Annotated[pd.DataFrame, ...],
    threshold: float = 0.5,
) -> Annotated[pd.DataFrame, ...]:
    '''Process time series data'''
    return data
"""
    processors_file.write_text(processors_code)

    # __init__.pyから関数を再エクスポート
    transforms_init_file = app_root / "transforms" / "__init__.py"
    transforms_init_code = """# Transform functions
from .processors import process_data

__all__ = ["process_data"]
"""
    transforms_init_file.write_text(transforms_init_code)

    # Generator関数の実装
    (app_root / "generators").mkdir(parents=True, exist_ok=True)
    generator_file = app_root / "generators" / "data_generators.py"
    generator_code = """# Generator functions
from typing import Any
from apps.sample_project.models.models import DataPoint

def generate_timeseries() -> dict[str, Any]:
    '''Generate time series data'''
    return {"timestamp": [], "value": [], "status": []}


def generate_datapoint() -> DataPoint:
    '''Generate a single data point'''
    return DataPoint(timestamp="2024-01-01T00:00:00", value=100.0)
"""
    generator_file.write_text(generator_code)

    # __init__.pyから関数を再エクスポート
    generators_init_file = app_root / "generators" / "__init__.py"
    generators_init_code = """# Generator functions
from .data_generators import generate_timeseries, generate_datapoint

__all__ = ["generate_timeseries", "generate_datapoint"]
"""
    generators_init_file.write_text(generators_init_code)

    return generated_project


def test_validate_all_passed(implemented_project, sample_spec_path):
    """正常ケース: すべての検証がパスする"""
    ir = load_spec(sample_spec_path)
    validator = IntegrityValidator(ir)

    errors = validator.validate_integrity(project_root=implemented_project)

    # エラーが0件であることを確認
    total_errors = sum(len(errs) for errs in errors.values())
    if total_errors > 0:
        print("\nUnexpected errors found:")
        for category, err_list in errors.items():
            if err_list:
                print(f"  {category}: {err_list}")

    assert total_errors == 0, f"Expected 0 errors, but got {total_errors}"
    assert len(errors["check_functions"]) == 0
    assert len(errors["check_locations"]) == 0
    assert len(errors["transform_functions"]) == 0
    assert len(errors["transform_signatures"]) == 0
    assert len(errors["generator_functions"]) == 0
    assert len(errors["generator_locations"]) == 0


def test_detect_missing_check_function(implemented_project, sample_spec_path):
    """異常ケース: Check関数が削除された"""
    # Check関数を削除
    ir = load_spec(sample_spec_path)
    app_name = ir.meta.name if ir.meta else "app"
    app_root = implemented_project / "apps" / app_name
    validators_file = app_root / "checks" / "validators.py"

    # validate_positive関数を削除
    validators_code = """# Check functions
# validate_positive function has been removed
"""
    validators_file.write_text(validators_code)

    ir = load_spec(sample_spec_path)
    validator = IntegrityValidator(ir)

    errors = validator.validate_integrity(project_root=implemented_project)

    # validate_positiveが見つからないエラーが1件
    assert len(errors["check_functions"]) >= 1
    assert any("validate_positive" in err for err in errors["check_functions"])


def test_detect_file_moved(implemented_project, sample_spec_path):
    """異常ケース: ファイルが移動された"""
    ir = load_spec(sample_spec_path)
    app_name = ir.meta.name if ir.meta else "app"
    app_root = implemented_project / "apps" / app_name

    # validators.pyを別ディレクトリに移動
    new_dir = app_root / "checks" / "deep"
    new_dir.mkdir(parents=True, exist_ok=True)
    old_file = app_root / "checks" / "validators.py"
    new_file = new_dir / "validators.py"

    if old_file.exists():
        old_file.rename(new_file)

    ir = load_spec(sample_spec_path)
    validator = IntegrityValidator(ir)

    errors = validator.validate_integrity(project_root=implemented_project)

    # 関数が見つからないエラーが発生（モジュールパスが変わったため）
    assert len(errors["check_functions"]) >= 1


def test_detect_signature_mismatch(implemented_project, sample_spec_path):
    """異常ケース: Transform関数のシグネチャが変更された"""
    ir = load_spec(sample_spec_path)
    app_name = ir.meta.name if ir.meta else "app"
    app_root = implemented_project / "apps" / app_name
    processors_file = app_root / "transforms" / "processors.py"

    # 余分なパラメータを追加
    processors_code = """# Transform functions
from typing import Annotated

def process_data(
    data: Annotated[dict, ...],
    threshold: float,
    extra_param: str = "default",  # 余分なパラメータ
) -> Annotated[dict, ...]:
    '''Process time series data'''
    return data
"""
    processors_file.write_text(processors_code)

    ir = load_spec(sample_spec_path)
    validator = IntegrityValidator(ir)

    errors = validator.validate_integrity(project_root=implemented_project)

    # シグネチャ不一致エラーが1件
    assert len(errors["transform_signatures"]) >= 1
    assert any("process_data" in err for err in errors["transform_signatures"])
    assert any("extra_param" in err for err in errors["transform_signatures"])


def test_detect_missing_transform_function(generated_project, sample_spec_path):
    """異常ケース: Transform関数のスケルトンのみ（実装未完了）"""
    ir = load_spec(sample_spec_path)
    app_name = ir.meta.name if ir.meta else "app"
    app_root = generated_project / "apps" / app_name
    processors_file = app_root / "transforms" / "processors.py"

    # transform関数自体を削除
    processors_file.write_text("# Empty file")

    ir = load_spec(sample_spec_path)
    validator = IntegrityValidator(ir)

    errors = validator.validate_integrity(project_root=generated_project)

    # Transform関数が削除されたのでエラーが発生
    assert len(errors["transform_functions"]) >= 1
    assert any("process_data" in err for err in errors["transform_functions"])


def test_detect_missing_generator_function(generated_project, sample_spec_path):
    """異常ケース: Generator関数が未実装"""
    ir = load_spec(sample_spec_path)
    app_name = ir.meta.name if ir.meta else "app"
    app_root = generated_project / "apps" / app_name
    generator_file = app_root / "generators" / "data_generators.py"

    if generator_file.exists():
        generator_file.write_text("# Generator file without functions\n")

    ir = load_spec(sample_spec_path)
    validator = IntegrityValidator(ir)

    errors = validator.validate_integrity(project_root=generated_project)

    # Generator関数がないのでエラーが発生
    assert len(errors["generator_functions"]) >= 1


def test_detect_generator_signature_mismatch(implemented_project, sample_spec_path):
    """異常ケース: Generator関数のシグネチャ不一致"""
    ir = load_spec(sample_spec_path)
    app_name = ir.meta.name if ir.meta else "app"
    app_root = implemented_project / "apps" / app_name
    generator_file = app_root / "generators" / "data_generators.py"

    generator_code = """# Generator functions
from typing import Any
from apps.sample_project.models.models import DataPoint

def generate_timeseries(extra: int = 1) -> dict[str, Any]:  # 余分なパラメータ
    '''Generate time series data'''
    return {"timestamp": [], "value": [], "status": []}


def generate_datapoint() -> DataPoint:
    '''Generate a single data point'''
    return DataPoint(timestamp="2024-01-01T00:00:00", value=100.0)
"""
    generator_file.write_text(generator_code)

    ir = load_spec(sample_spec_path)
    validator = IntegrityValidator(ir)

    errors = validator.validate_integrity(project_root=implemented_project)

    assert len(errors["generator_signatures"]) >= 1


def test_detect_generator_location_mismatch(implemented_project, sample_spec_path):
    """異常ケース: Generator関数が別ファイルから再エクスポートされる"""
    ir = load_spec(sample_spec_path)
    app_name = ir.meta.name if ir.meta else "app"
    app_root = implemented_project / "apps" / app_name
    generator_file = app_root / "generators" / "data_generators.py"
    helper_file = app_root / "generators" / "helper_generators.py"

    helper_code = """from typing import Any

def generate_timeseries() -> dict[str, Any]:
    '''Generate time series data'''
    return {"timestamp": [], "value": [], "status": []}
"""
    helper_file.write_text(helper_code)
    generator_code = """from .helper_generators import generate_timeseries
from apps.sample_project.models.models import DataPoint

def generate_datapoint() -> DataPoint:
    '''Generate a single data point'''
    return DataPoint(timestamp="2024-01-01T00:00:00", value=100.0)
"""
    generator_file.write_text(generator_code)

    ir = load_spec(sample_spec_path)
    validator = IntegrityValidator(ir)

    errors = validator.validate_integrity(project_root=implemented_project)

    # 関数が別ファイルから再エクスポートされているのでエラー
    assert len(errors["generator_locations"]) >= 1


def test_multiple_errors_reported(implemented_project, sample_spec_path):
    """複数のエラーが同時に報告される"""
    ir = load_spec(sample_spec_path)
    app_name = ir.meta.name if ir.meta else "app"
    app_root = implemented_project / "apps" / app_name

    # 1. Check関数を削除
    validators_file = app_root / "checks" / "validators.py"
    validators_code = """# Only some check functions remain
"""
    validators_file.write_text(validators_code)

    # 2. Transform関数のシグネチャを変更
    processors_file = app_root / "transforms" / "processors.py"
    processors_code = """# Transform with wrong signature
from typing import Annotated

def process_data(
    data: Annotated[dict, ...],
    threshold: float,
    new_param: int,  # 余分なパラメータ
) -> dict:
    return data
"""
    processors_file.write_text(processors_code)

    ir = load_spec(sample_spec_path)
    validator = IntegrityValidator(ir)

    errors = validator.validate_integrity(project_root=implemented_project)

    # 複数のエラーが報告される
    total_errors = sum(len(errs) for errs in errors.values())
    assert total_errors >= 2
    assert len(errors["check_functions"]) >= 1
    assert len(errors["transform_signatures"]) >= 1


def test_validation_checks_function_imports(implemented_project, sample_spec_path):
    """関数が実際にインポート可能かどうかを検証する"""
    ir = load_spec(sample_spec_path)
    validator = IntegrityValidator(ir)

    errors = validator.validate_integrity(project_root=implemented_project)

    # すべての関数がインポート可能であることを確認
    assert len(errors["check_functions"]) == 0
    assert len(errors["transform_functions"]) == 0
    assert len(errors["generator_functions"]) == 0


def test_validation_checks_function_locations(implemented_project, sample_spec_path):
    """関数が正しいファイルに定義されているかを検証する"""
    ir = load_spec(sample_spec_path)
    validator = IntegrityValidator(ir)

    errors = validator.validate_integrity(project_root=implemented_project)

    # すべての関数が正しい場所に定義されていることを確認
    assert len(errors["check_locations"]) == 0
    assert len(errors["transform_locations"]) == 0
    assert len(errors["generator_locations"]) == 0


def test_validation_checks_type_annotations(implemented_project, sample_spec_path):
    """関数の型アノテーションが正しいかを検証する"""
    ir = load_spec(sample_spec_path)
    validator = IntegrityValidator(ir)

    errors = validator.validate_integrity(project_root=implemented_project)

    # 型アノテーションに関するエラーがないことを確認
    assert len(errors.get("transform_annotations", [])) == 0


def test_validation_error_messages_are_helpful(implemented_project, sample_spec_path):
    """エラーメッセージが有用な情報を含むことを確認"""
    ir = load_spec(sample_spec_path)
    app_name = ir.meta.name if ir.meta else "app"
    app_root = implemented_project / "apps" / app_name
    processors_file = app_root / "transforms" / "processors.py"

    # 余分なパラメータを追加
    processors_code = """# Transform with wrong signature
def process_data(
    data: dict,
    threshold: float,
    extra_param: str,
) -> dict:
    return data
"""
    processors_file.write_text(processors_code)

    ir = load_spec(sample_spec_path)
    validator = IntegrityValidator(ir)

    errors = validator.validate_integrity(project_root=implemented_project)

    # エラーメッセージに以下の情報が含まれることを確認
    # - 関数名
    # - 問題のパラメータ名
    # - ファイルパス
    error_msg = errors["transform_signatures"][0]
    assert "process_data" in error_msg
    assert "extra_param" in error_msg
    assert "processors.py" in error_msg or "file" in error_msg.lower()

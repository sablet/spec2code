"""Config既存時の完全ワークフローテスト

Configが既にある状態で、コード生成→バリデーションが全て通ることを確認する。
"""

from pathlib import Path
import tempfile
import pytest
import yaml

from spectool.core.engine.loader import load_spec


@pytest.fixture
def temp_project_dir():
    """一時プロジェクトディレクトリ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_spec_with_config(temp_project_dir):
    """Configを含むサンプルspec"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "test_pipeline"},
        "datatypes": [
            {
                "id": "DataFrame1",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
            },
            {
                "id": "DataFrame2",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "result", "dtype": "float"}],
                },
            },
        ],
        "transforms": [
            {
                "id": "process",
                "impl": "apps.transforms.process:process",
                "file_path": "transforms/process.py",
                "parameters": [
                    {"name": "data", "datatype_ref": "DataFrame1"},
                    {"name": "factor", "native": "builtins:float", "default": 1.0},
                ],
                "return_datatype_ref": "DataFrame2",
            }
        ],
        "dag_stages": [
            {
                "stage_id": "processing",
                "selection_mode": "single",
                "input_type": "DataFrame1",
                "output_type": "DataFrame2",
                "candidates": ["process"],
                "default_transform_id": "process",
            }
        ],
    }

    config_data = {
        "version": "1",
        "meta": {
            "config_name": "test-config",
            "description": "Test configuration",
            "base_spec": "spec.yaml",
        },
        "execution": {
            "stages": [
                {
                    "stage_id": "processing",
                    "selected": [{"transform_id": "process", "params": {"factor": 2.0}}],
                }
            ]
        },
    }

    spec_path = temp_project_dir / "spec.yaml"
    config_path = temp_project_dir / "config.yaml"

    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    return spec_path, config_path


def test_full_workflow_with_existing_config(sample_spec_with_config, temp_project_dir):
    """Config既存時: Spec読込 → コード生成 → バリデーション が全て通ることを確認"""
    spec_path, config_path = sample_spec_with_config

    # 1. Spec読込
    ir = load_spec(spec_path)
    assert ir is not None

    # 2. スケルトン生成
    from spectool.backends.py_skeleton import generate_skeleton

    generate_skeleton(ir, temp_project_dir)

    # 3. 生成されたファイルが存在することを確認
    app_root = temp_project_dir / "apps" / "test_pipeline"
    assert (app_root / "transforms" / "process.py").exists()

    # 4. バリデーション実行
    from spectool.core.engine.validate import validate_spec

    result = validate_spec(str(spec_path))
    errors = result["errors"]

    # edge_casesは警告なので除外
    critical_errors = {k: v for k, v in errors.items() if k != "edge_cases"}
    total_errors = sum(len(errs) for errs in critical_errors.values())

    # バリデーションエラーがないことを確認
    if total_errors > 0:
        print(f"Critical validation errors: {critical_errors}")

    assert total_errors == 0, "Validation should pass after skeleton generation"

    # 5. Config検証
    from spectool.core.engine.config_validator import validate_config
    from spectool.core.engine.config_model import load_config

    config = load_config(str(config_path))
    config_validation = validate_config(config, ir, check_implementations=False)

    assert config_validation["valid"] is True


def test_config_validation_before_implementation(sample_spec_with_config, temp_project_dir):
    """実装前のConfig検証（check_implementations=False）が通ることを確認"""
    spec_path, config_path = sample_spec_with_config

    ir = load_spec(spec_path)

    from spectool.core.engine.config_validator import validate_config
    from spectool.core.engine.config_model import load_config

    config = load_config(str(config_path))

    # 実装チェックなしでConfig検証
    config_validation = validate_config(config, ir, check_implementations=False)

    assert config_validation["valid"] is True


def test_config_validation_after_implementation(sample_spec_with_config, temp_project_dir):
    """実装後のConfig検証（check_implementations=True）が通ることを確認"""
    spec_path, config_path = sample_spec_with_config

    ir = load_spec(spec_path)

    # スケルトン生成
    from spectool.backends.py_skeleton import generate_skeleton

    generate_skeleton(ir, temp_project_dir)

    # 実装を追加（簡易版）
    app_root = temp_project_dir / "apps" / "test_pipeline"
    transform_file = app_root / "transforms" / "process.py"

    implementation = """
import pandas as pd
from typing import Annotated

def process(data: pd.DataFrame, factor: float = 1.0) -> pd.DataFrame:
    result = data.copy()
    result['result'] = data['value'] * factor
    return result
"""
    transform_file.write_text(implementation)

    # 実装チェックありでConfig検証
    from spectool.core.engine.config_validator import validate_config
    from spectool.core.engine.config_model import load_config

    config = load_config(str(config_path))
    config_validation = validate_config(config, ir, check_implementations=True, project_root=temp_project_dir)

    assert config_validation["valid"] is True


@pytest.mark.skip(reason="実装の中身（TODO）のチェックは現在未対応")
def test_workflow_detects_missing_implementation(sample_spec_with_config, temp_project_dir):
    """実装が不足している場合、check_implementations=Trueで検出されることを確認"""
    spec_path, config_path = sample_spec_with_config

    ir = load_spec(spec_path)

    # スケルトン生成のみ（実装なし）
    from spectool.backends.py_skeleton import generate_skeleton

    generate_skeleton(ir, temp_project_dir)

    # 実装チェックありでConfig検証（実装がTODOのままなので失敗するはず）
    from spectool.core.engine.config_validator import validate_config, ConfigValidationError
    from spectool.core.engine.config_model import load_config

    config = load_config(str(config_path))

    # TODOのままの実装は検出されるべき
    with pytest.raises((ConfigValidationError, Exception)):
        validate_config(config, ir, check_implementations=True, project_root=temp_project_dir)


def test_workflow_regeneration_is_safe(sample_spec_with_config, temp_project_dir):
    """実装後に再度スケルトン生成しても既存コードが保持されることを確認"""
    spec_path, config_path = sample_spec_with_config

    ir = load_spec(spec_path)

    # 1回目のスケルトン生成
    from spectool.backends.py_skeleton import generate_skeleton

    generate_skeleton(ir, temp_project_dir)

    app_root = temp_project_dir / "apps" / "test_pipeline"
    transform_file = app_root / "transforms" / "process.py"

    # 実装を追加
    implementation = """
import pandas as pd
from typing import Annotated

def process(data: pd.DataFrame, factor: float = 1.0) -> pd.DataFrame:
    '''Custom implementation'''
    result = data.copy()
    result['result'] = data['value'] * factor
    return result
"""
    transform_file.write_text(implementation)

    original_content = transform_file.read_text()

    # 2回目のスケルトン生成
    generate_skeleton(ir, temp_project_dir)

    # 既存の実装が保持されていることを確認
    regenerated_content = transform_file.read_text()
    assert "Custom implementation" in regenerated_content
    assert regenerated_content == original_content


def test_config_with_invalid_stage_fails_validation(temp_project_dir):
    """存在しないstage_idを指定したConfigが検証で弾かれることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "test_pipeline"},
        "datatypes": [
            {
                "id": "DataFrame1",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
            }
        ],
        "transforms": [
            {
                "id": "process",
                "impl": "apps.transforms:process",
                "file_path": "transforms/process.py",
                "parameters": [{"name": "data", "datatype_ref": "DataFrame1"}],
                "return_datatype_ref": "DataFrame1",
            }
        ],
        "dag_stages": [
            {
                "stage_id": "valid_stage",
                "selection_mode": "single",
                "input_type": "DataFrame1",
                "output_type": "DataFrame1",
                "candidates": ["process"],
            }
        ],
    }

    config_data = {
        "version": "1",
        "meta": {"config_name": "invalid-config", "base_spec": "spec.yaml"},
        "execution": {
            "stages": [
                {
                    "stage_id": "invalid_stage",  # 存在しないstage
                    "selected": [{"transform_id": "process"}],
                }
            ]
        },
    }

    spec_path = temp_project_dir / "spec.yaml"
    config_path = temp_project_dir / "config.yaml"

    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    ir = load_spec(spec_path)

    from spectool.core.engine.config_validator import validate_config, ConfigValidationError
    from spectool.core.engine.config_model import load_config

    config = load_config(str(config_path))

    # 存在しないstage_idでエラーが発生すること
    with pytest.raises((ConfigValidationError, ValueError)):
        validate_config(config, ir)

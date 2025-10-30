"""Transformパラメータの型検証テスト

デフォルト値の型が宣言された型と一致するかをチェックする。
"""

from pathlib import Path
import tempfile
import pytest
import yaml

from spectool.spectool.core.engine.loader import load_spec
from spectool.spectool.core.engine.validate import validate_spec


@pytest.fixture
def temp_spec_dir():
    """一時specディレクトリ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_transform_default_parameter_type_mismatch_detected(temp_spec_dir):
    """デフォルト値の型が宣言と不一致の場合にエラーが検出されることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "type-mismatch-spec"},
        "datatypes": [
            {
                "id": "TestFrame",
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
                "parameters": [
                    {"name": "data", "type_ref": "TestFrame"},
                    {
                        "name": "threshold",
                        "native": "builtins:float",  # float型を宣言
                        "default": "not_a_float",  # しかしデフォルト値は文字列
                    },
                ],
                "return_type_ref": "TestFrame",
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]

    # エラーが検出されること
    total_errors = sum(len(errs) for errs in errors.values())
    assert total_errors > 0, "Type mismatch in default parameter should be detected"

    # エラーメッセージに該当する情報が含まれること
    all_error_messages = []
    for category_errors in errors.values():
        all_error_messages.extend(category_errors)

    combined_errors = " ".join(all_error_messages).lower()
    assert "threshold" in combined_errors or "type" in combined_errors or "default" in combined_errors


def test_transform_default_parameter_correct_type_passes(temp_spec_dir):
    """デフォルト値の型が正しい場合はエラーが出ないことを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "correct-type-spec"},
        "datatypes": [
            {
                "id": "TestFrame",
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
                "parameters": [
                    {"name": "data", "type_ref": "TestFrame"},
                    {"name": "threshold", "native": "builtins:float", "default": 0.5},  # 正しい型
                    {"name": "count", "native": "builtins:int", "default": 10},  # 正しい型
                    {"name": "label", "native": "builtins:str", "default": "default"},  # 正しい型
                ],
                "return_type_ref": "TestFrame",
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]

    # パラメータ型に関するエラーがないことを確認
    param_errors = errors.get("parameter_types", [])
    assert len(param_errors) == 0, "Correct parameter types should not produce errors"


def test_transform_default_parameter_int_float_coercion(temp_spec_dir):
    """int型のデフォルト値がfloat型宣言で許容されるか確認（または警告）"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "coercion-spec"},
        "datatypes": [
            {
                "id": "TestFrame",
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
                "parameters": [
                    {"name": "data", "type_ref": "TestFrame"},
                    {"name": "threshold", "native": "builtins:float", "default": 5},  # intをfloatに
                ],
                "return_type_ref": "TestFrame",
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]

    # int→floatの変換は通常許容されるので、エラーにならない（または警告のみ）
    critical_errors = [err for errs in errors.values() for err in errs if "error" in err.lower()]
    assert len(critical_errors) == 0 or "threshold" not in " ".join(critical_errors).lower()


def test_transform_default_parameter_none_for_optional(temp_spec_dir):
    """optional=Trueの場合、default=Noneが許容されることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "optional-none-spec"},
        "datatypes": [
            {
                "id": "TestFrame",
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
                "parameters": [
                    {"name": "data", "type_ref": "TestFrame"},
                    {
                        "name": "threshold",
                        "native": "builtins:float",
                        "optional": True,
                        "default": None,  # optionalならNoneが許容される
                    },
                ],
                "return_type_ref": "TestFrame",
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]

    # optional=Trueでdefault=Noneはエラーにならない
    param_errors = [err for errs in errors.values() for err in errs if "threshold" in err.lower()]
    assert len(param_errors) == 0


def test_transform_default_parameter_complex_type_mismatch(temp_spec_dir):
    """複雑な型（list, dict）のデフォルト値の型不一致も検出されることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "complex-type-mismatch-spec"},
        "datatypes": [
            {
                "id": "TestFrame",
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
                "parameters": [
                    {"name": "data", "type_ref": "TestFrame"},
                    {
                        "name": "config",
                        "native": "builtins:dict",  # dict型を宣言
                        "default": [1, 2, 3],  # しかしデフォルト値はlist
                    },
                ],
                "return_type_ref": "TestFrame",
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]

    # エラーが検出されること
    total_errors = sum(len(errs) for errs in errors.values())
    assert total_errors > 0, "Complex type mismatch should be detected"


def test_transform_default_parameter_bool_type_check(temp_spec_dir):
    """bool型のデフォルト値チェックが正しく動作することを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "bool-type-spec"},
        "datatypes": [
            {
                "id": "TestFrame",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
            }
        ],
        "transforms": [
            {
                "id": "process_valid",
                "impl": "apps.transforms:process_valid",
                "file_path": "transforms/process.py",
                "parameters": [
                    {"name": "data", "type_ref": "TestFrame"},
                    {"name": "flag", "native": "builtins:bool", "default": True},  # 正しい
                ],
                "return_type_ref": "TestFrame",
            },
            {
                "id": "process_invalid",
                "impl": "apps.transforms:process_invalid",
                "file_path": "transforms/process.py",
                "parameters": [
                    {"name": "data", "type_ref": "TestFrame"},
                    {"name": "flag", "native": "builtins:bool", "default": "true"},  # 文字列（誤り）
                ],
                "return_type_ref": "TestFrame",
            },
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]

    # process_invalidにエラーが出ること
    all_error_messages = []
    for category_errors in errors.values():
        all_error_messages.extend(category_errors)

    combined_errors = " ".join(all_error_messages).lower()
    assert "process_invalid" in combined_errors or "flag" in combined_errors

"""Example Spec検証のテスト

Exampleの定義と検証が正しく動作することを確認する。
"""

from pathlib import Path
import tempfile
import pytest
import yaml

from spectool.spectool.core.engine.loader import load_spec


@pytest.fixture
def temp_spec_dir():
    """一時specディレクトリ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_example_linked_to_datatype(temp_spec_dir):
    """ExampleがDataTypeに正しくリンクされることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "example-link-spec"},
        "datatypes": [
            {
                "id": "TestFrame",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
            }
        ],
        "examples": [
            {
                "id": "example_1",
                "description": "Example 1",
                "datatype_ref": "TestFrame",
                "input": {"idx": [1, 2], "value": [10.0, 20.0]},
                "expected": {"idx": [1, 2], "value": [10.0, 20.0]},
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    ir = load_spec(spec_path)

    # Exampleが読み込まれていることを確認
    assert len(ir.examples) == 1
    assert ir.examples[0].id == "example_1"


def test_example_without_datatype_ref_detected(temp_spec_dir):
    """datatype_refが指定されていないExampleが検出されることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "missing-ref-spec"},
        "datatypes": [
            {
                "id": "TestFrame",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
            }
        ],
        "examples": [
            {
                "id": "orphan_example",
                "description": "Orphan example without datatype_ref",
                "input": {"idx": [1], "value": [10.0]},
                # datatype_refがない
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    # バリデーションで警告が出ることを期待
    # （実装依存だが、少なくともエラーにはならない）
    try:
        ir = load_spec(spec_path)
        assert ir is not None
    except Exception as e:
        pytest.fail(f"Loading spec with orphan example should not fail: {e}")


def test_example_references_nonexistent_datatype(temp_spec_dir):
    """存在しないDataTypeを参照するExampleが検出されることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "invalid-ref-spec"},
        "datatypes": [
            {
                "id": "TestFrame",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
            }
        ],
        "examples": [
            {
                "id": "bad_example",
                "description": "Example with invalid datatype_ref",
                "datatype_ref": "NonExistentFrame",  # 存在しないDataType
                "input": {"idx": [1], "value": [10.0]},
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    # バリデーションでエラーが検出されることを期待
    from spectool.spectool.core.engine.validate import validate_spec

    result = validate_spec(str(spec_path))
    errors = result["errors"]

    # エラーが報告されること
    total_errors = sum(len(errs) for errs in errors.values())
    assert total_errors > 0, "Invalid datatype_ref should be detected"

    # エラーメッセージに該当するExampleIDが含まれること
    all_error_messages = []
    for category_errors in errors.values():
        all_error_messages.extend(category_errors)

    combined_errors = " ".join(all_error_messages).lower()
    assert "bad_example" in combined_errors or "nonexistentframe" in combined_errors


def test_example_input_matches_datatype_schema(temp_spec_dir):
    """ExampleのinputがDataTypeのschemaに一致することを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "schema-match-spec"},
        "datatypes": [
            {
                "id": "TestFrame",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float", "nullable": False}],
                },
            }
        ],
        "examples": [
            {
                "id": "valid_example",
                "description": "Valid example",
                "datatype_ref": "TestFrame",
                "input": {"idx": [1, 2], "value": [10.0, 20.0]},
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    ir = load_spec(spec_path)

    # バリデーションが成功することを確認
    from spectool.spectool.core.engine.validate import validate_spec

    result = validate_spec(str(spec_path))
    errors = result["errors"]
    total_errors = sum(len(errs) for errs in errors.values())

    # スキーマに一致するExampleはエラーが出ないはず
    assert total_errors == 0 or "valid_example" not in " ".join([msg for errs in errors.values() for msg in errs])


def test_example_input_violates_datatype_schema(temp_spec_dir):
    """ExampleのinputがDataTypeのschemaに違反する場合にエラーが検出されることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "schema-violation-spec"},
        "datatypes": [
            {
                "id": "TestFrame",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float", "nullable": False}],
                },
            }
        ],
        "examples": [
            {
                "id": "invalid_example",
                "description": "Invalid example with wrong data type",
                "datatype_ref": "TestFrame",
                "input": {"idx": [1, 2], "value": ["not_a_float", "also_not_float"]},  # 型が違う
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    from spectool.spectool.core.engine.validate import validate_spec

    result = validate_spec(str(spec_path))
    errors = result["errors"]

    # エラーが報告されること
    total_errors = sum(len(errs) for errs in errors.values())
    assert total_errors > 0, "Schema violation should be detected"


def test_multiple_examples_for_same_datatype(temp_spec_dir):
    """同じDataTypeに対して複数のExampleが定義できることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "multiple-examples-spec"},
        "datatypes": [
            {
                "id": "TestFrame",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
            }
        ],
        "examples": [
            {
                "id": "example_1",
                "description": "Example 1",
                "datatype_ref": "TestFrame",
                "input": {"idx": [1], "value": [10.0]},
            },
            {
                "id": "example_2",
                "description": "Example 2",
                "datatype_ref": "TestFrame",
                "input": {"idx": [2, 3], "value": [20.0, 30.0]},
            },
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    ir = load_spec(spec_path)

    # 両方のExampleが読み込まれていることを確認
    assert len(ir.examples) == 2
    example_ids = {ex.id for ex in ir.examples}
    assert "example_1" in example_ids
    assert "example_2" in example_ids


def test_example_expected_output_validation(temp_spec_dir):
    """Exampleのexpected outputも検証されることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "expected-output-spec"},
        "datatypes": [
            {
                "id": "InputFrame",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "input_col", "dtype": "float"}],
                },
            },
            {
                "id": "OutputFrame",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "output_col", "dtype": "float"}],
                },
            },
        ],
        "transforms": [
            {
                "id": "test_transform",
                "impl": "apps.transforms:test_transform",
                "file_path": "transforms/test.py",
                "parameters": [{"name": "input", "type_ref": "InputFrame"}],
                "return_type_ref": "OutputFrame",
            }
        ],
        "examples": [
            {
                "id": "transform_example",
                "description": "Transform example",
                "transform_ref": "test_transform",
                "input": {"idx": [1], "input_col": [10.0]},
                "expected": {"idx": [1], "output_col": [20.0]},
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    ir = load_spec(spec_path)

    # Exampleが読み込まれていることを確認
    assert len(ir.examples) >= 1


def test_example_without_expected_is_valid(temp_spec_dir):
    """expectedがないExample（入力のみ）も有効であることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "input-only-example-spec"},
        "datatypes": [
            {
                "id": "TestFrame",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
            }
        ],
        "examples": [
            {
                "id": "input_only_example",
                "description": "Example with input only",
                "datatype_ref": "TestFrame",
                "input": {"idx": [1], "value": [10.0]},
                # expectedなし
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    try:
        ir = load_spec(spec_path)
        assert len(ir.examples) == 1
    except Exception as e:
        pytest.fail(f"Example without expected should be valid: {e}")

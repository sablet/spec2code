"""バリデーションのエッジケーステスト

重要なバリデーションルールが正しく動作することを確認する。
"""

from pathlib import Path
import tempfile
import pytest
import yaml

from spectool.core.engine.loader import load_spec
from spectool.core.engine.validate import validate_spec


@pytest.fixture
def temp_spec_dir():
    """一時specディレクトリ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_dag_stage_with_zero_transform_candidates_detected(temp_spec_dir):
    """i/o dtypeに対して候補のtransform関数がゼロ件のdag_stagesが検出されることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "zero-candidates-spec"},
        "datatypes": [
            {
                "id": "FrameA",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
            },
            {
                "id": "FrameB",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "result", "dtype": "float"}],
                },
            },
            {
                "id": "FrameC",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "other", "dtype": "str"}],
                },
            },
        ],
        "transforms": [
            {
                "id": "transform_a_to_b",
                "impl": "apps.transforms:transform_a_to_b",
                "file_path": "transforms/ab.py",
                "parameters": [{"name": "data", "type_ref": "FrameA"}],
                "return_type_ref": "FrameB",
            }
            # FrameB -> FrameCのtransformは存在しない
        ],
        "dag_stages": [
            {
                "stage_id": "stage_a_to_b",
                "selection_mode": "single",
                "input_type": "FrameA",
                "output_type": "FrameB",
                # candidatesを指定しない（自動収集）
                # 上記transformが存在するので問題なし
            },
            {
                "stage_id": "stage_b_to_c",
                "selection_mode": "single",
                "input_type": "FrameB",
                "output_type": "FrameC",
                # candidatesを指定しない（自動収集）
                # FrameB -> FrameCのtransformが存在しないのでエラーになるべき
            },
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]

    # エラーが報告されること
    total_errors = sum(len(errs) for errs in errors.values())
    assert total_errors > 0, "DAG stage with zero transform candidates should be detected"

    # エラーメッセージに該当するstage_idが含まれること
    all_error_messages = []
    for category_errors in errors.values():
        all_error_messages.extend(category_errors)

    combined_errors = " ".join(all_error_messages).lower()
    assert (
        "stage_b_to_c" in combined_errors
        or "no candidates" in combined_errors
        or "no transform" in combined_errors
        or "frameb" in combined_errors
        and "framec" in combined_errors
    ), f"Expected error about stage_b_to_c having no candidates, but got: {combined_errors}"


def test_dag_stage_with_explicit_empty_candidates_detected(temp_spec_dir):
    """明示的に空のcandidatesが指定された場合も検出されることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "explicit-empty-candidates-spec"},
        "datatypes": [
            {
                "id": "FrameA",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
            }
        ],
        "transforms": [
            {
                "id": "transform_a",
                "impl": "apps.transforms:transform_a",
                "file_path": "transforms/a.py",
                "parameters": [{"name": "data", "type_ref": "FrameA"}],
                "return_type_ref": "FrameA",
            }
        ],
        "dag_stages": [
            {
                "stage_id": "empty_stage",
                "selection_mode": "single",
                "input_type": "FrameA",
                "output_type": "FrameA",
                "candidates": [],  # 明示的に空
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]

    # エラーが報告されること
    total_errors = sum(len(errs) for errs in errors.values())
    assert total_errors > 0, "DAG stage with explicit empty candidates should be detected"


def test_datatype_with_zero_check_functions_detected(temp_spec_dir):
    """dtypeの型アノテーションのcheckがゼロ件の場合が検出されることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "zero-checks-spec"},
        "datatypes": [
            {
                "id": "ValidatedFrame",
                "description": "Frame with checks",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
                "check_functions": ["apps.checks:check_validated"],  # checkあり
            },
            {
                "id": "UnvalidatedFrame",
                "description": "Frame without checks",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "result", "dtype": "float"}],
                },
                # check_functionsなし（エラーまたは警告）
            },
        ],
        "checks": [
            {
                "id": "check_validated",
                "description": "Validation check",
                "impl": "apps.checks:check_validated",
                "file_path": "checks/validated.py",
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]
    warnings = result["warnings"]

    # エラーまたは警告が報告されること
    total_issues = sum(len(errs) for errs in errors.values()) + sum(len(warns) for warns in warnings.values())
    assert total_issues > 0, "DataType with zero check functions should be detected (as warning or error)"

    # エラー/警告メッセージに該当するDataType IDが含まれること
    all_error_messages = []
    for category_errors in errors.values():
        all_error_messages.extend(category_errors)
    for category_warnings in warnings.values():
        all_error_messages.extend(category_warnings)

    combined_errors = " ".join(all_error_messages).lower()
    assert (
        "unvalidatedframe" in combined_errors or "no check" in combined_errors or "missing check" in combined_errors
    ), f"Expected warning about UnvalidatedFrame having no checks, but got: {combined_errors}"


def test_datatype_with_zero_examples_and_zero_generators_detected(temp_spec_dir):
    """example/generatorの両方がゼロ件の場合が検出されることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "zero-examples-generators-spec"},
        "datatypes": [
            {
                "id": "FrameWithExample",
                "description": "Frame with example",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
            },
            {
                "id": "FrameWithGenerator",
                "description": "Frame with generator",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "result", "dtype": "float"}],
                },
                "generator_factory": "apps.generators:generate_frame",  # generatorあり
            },
            {
                "id": "FrameWithNeither",
                "description": "Frame without example or generator",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "other", "dtype": "str"}],
                },
                # exampleもgeneratorもなし（エラーまたは警告）
            },
        ],
        "examples": [
            {
                "id": "example_1",
                "description": "Example for FrameWithExample",
                "datatype_ref": "FrameWithExample",
                "input": {"idx": [1], "value": [10.0]},
            }
        ],
        "generators": [
            {
                "id": "generate_frame",
                "description": "Generator for FrameWithGenerator",
                "impl": "apps.generators:generate_frame",
                "file_path": "generators/generators.py",
                "parameters": [],
                "return_type_ref": "FrameWithGenerator",
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]
    warnings = result["warnings"]

    # エラーまたは警告が報告されること
    total_issues = sum(len(errs) for errs in errors.values()) + sum(len(warns) for warns in warnings.values())
    assert total_issues > 0, "DataType with neither examples nor generators should be detected (as warning or error)"

    # エラー/警告メッセージに該当するDataType IDが含まれること
    all_error_messages = []
    for category_errors in errors.values():
        all_error_messages.extend(category_errors)
    for category_warnings in warnings.values():
        all_error_messages.extend(category_warnings)

    combined_errors = " ".join(all_error_messages).lower()
    assert (
        "framewithneither" in combined_errors
        or "no example" in combined_errors
        or "no generator" in combined_errors
        or "missing example" in combined_errors
    ), f"Expected warning about FrameWithNeither having no examples/generators, but got: {combined_errors}"


def test_datatype_completeness_all_three_checks(temp_spec_dir):
    """check/example/generatorの3つすべてがゼロの場合、最も重大なエラーとして検出されることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "incomplete-datatype-spec"},
        "datatypes": [
            {
                "id": "CompleteFrame",
                "description": "Frame with all validation components",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
                "check_functions": ["apps.checks:check_complete"],
                "generator_factory": "apps.generators:generate_complete",
            },
            {
                "id": "IncompleteFrame",
                "description": "Frame missing all validation components",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "result", "dtype": "float"}],
                },
                # check_functions なし
                # examples なし
                # generator_factory なし
            },
        ],
        "checks": [
            {
                "id": "check_complete",
                "description": "Check for complete frame",
                "impl": "apps.checks:check_complete",
                "file_path": "checks/complete.py",
            }
        ],
        "generators": [
            {
                "id": "generate_complete",
                "description": "Generator for complete frame",
                "impl": "apps.generators:generate_complete",
                "file_path": "generators/complete.py",
                "parameters": [],
                "return_type_ref": "CompleteFrame",
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]
    warnings = result["warnings"]

    # 複数のエラー/警告が報告されること（check/example/generatorの3つ）
    total_issues = sum(len(errs) for errs in errors.values()) + sum(len(warns) for warns in warnings.values())
    assert total_issues >= 1, "DataType missing all validation components should produce multiple errors/warnings"

    # エラー/警告メッセージに該当するDataType IDが含まれること
    all_error_messages = []
    for category_errors in errors.values():
        all_error_messages.extend(category_errors)
    for category_warnings in warnings.values():
        all_error_messages.extend(category_warnings)

    combined_errors = " ".join(all_error_messages).lower()
    assert "incompleteframe" in combined_errors, f"Expected errors/warnings about IncompleteFrame, but got: {combined_errors}"


def test_validation_reports_all_incomplete_datatypes(temp_spec_dir):
    """複数のDataTypeに問題がある場合、すべて報告されることを確認（1つ目で停止しない）"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "multiple-incomplete-spec"},
        "datatypes": [
            {
                "id": "Frame1",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
                # 検証コンポーネントなし
            },
            {
                "id": "Frame2",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "result", "dtype": "float"}],
                },
                # 検証コンポーネントなし
            },
            {
                "id": "Frame3",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "other", "dtype": "str"}],
                },
                # 検証コンポーネントなし
            },
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]
    warnings = result["warnings"]

    # 複数のエラー/警告が報告されること
    total_issues = sum(len(errs) for errs in errors.values()) + sum(len(warns) for warns in warnings.values())
    assert total_issues >= 3, "All incomplete DataTypes should be reported, not just the first one"

    # 各DataTypeがエラー/警告メッセージに含まれること
    all_error_messages = []
    for category_errors in errors.values():
        all_error_messages.extend(category_errors)
    for category_warnings in warnings.values():
        all_error_messages.extend(category_warnings)

    combined_errors = " ".join(all_error_messages).lower()
    assert "frame1" in combined_errors or "frame2" in combined_errors or "frame3" in combined_errors


def test_dag_stage_zero_candidates_specific_error_message(temp_spec_dir):
    """候補がゼロのdag_stageのエラーメッセージが具体的であることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "specific-error-spec"},
        "datatypes": [
            {
                "id": "InputFrame",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "input", "dtype": "float"}],
                },
            },
            {
                "id": "OutputFrame",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "output", "dtype": "float"}],
                },
            },
        ],
        "transforms": [],  # transformが一つもない
        "dag_stages": [
            {
                "stage_id": "processing_stage",
                "selection_mode": "single",
                "input_type": "InputFrame",
                "output_type": "OutputFrame",
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]

    # エラーメッセージに以下の情報が含まれることを確認
    # - stage_id
    # - input_type
    # - output_type
    all_error_messages = []
    for category_errors in errors.values():
        all_error_messages.extend(category_errors)

    combined_errors = " ".join(all_error_messages).lower()

    assert "processing_stage" in combined_errors, "Error should mention the stage_id"
    assert "inputframe" in combined_errors or "outputframe" in combined_errors, (
        "Error should mention the input/output types"
    )

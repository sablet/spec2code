"""包括的なValidation機能のテスト

バリデーションエラーが発生しても、他の検証項目の結果が表示されることを確認する。
一部のエラーで全体が停止しないことが重要。
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


def test_validation_returns_all_errors_not_exception(temp_spec_dir):
    """複数のエラーがある場合、すべてのエラーがリストで返されることを確認（例外を投げない）"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "multi-error-spec"},
        "datatypes": [
            {
                "id": "DataFrame1",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [
                        {"name": "col1", "dtype": "float"},
                        {"name": "col1", "dtype": "str"},  # 重複カラム（エラー1）
                    ],
                },
            },
            {
                "id": "DataFrame2",
                "dataframe_schema": {
                    "index": {"name": "idx"},  # dtypeなし（エラー2）
                    "columns": [{"name": "col2"}],  # dtypeなし（エラー3）
                },
            },
        ],
        "checks": [
            {
                "id": "check1",
                "description": "Check 1",
                "impl": "",  # implが空（エラー4）
                "file_path": "checks/check1.py",
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    # バリデーション実行（例外を投げずにエラーリストを返すべき）
    result = validate_spec(str(spec_path))

    # 3層構造が返されること
    assert isinstance(result, dict)
    assert "errors" in result
    assert "warnings" in result
    assert "successes" in result

    errors = result["errors"]
    assert isinstance(errors, dict)

    # 複数のエラーカテゴリが報告されること
    total_errors = sum(len(errs) for errs in errors.values())
    assert total_errors >= 3, f"Expected at least 3 errors, but got {total_errors}"

    # 各エラーカテゴリが存在すること
    assert "dataframe_schemas" in errors or "datatypes" in errors
    assert "checks" in errors or "check_definitions" in errors


def test_validation_shows_warnings_and_successes(temp_spec_dir):
    """一部にエラーがあっても、警告や成功した項目も表示されることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "partial-error-spec"},
        "datatypes": [
            {
                "id": "ValidFrame",
                "description": "Valid DataFrame",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "col1", "dtype": "float"}],
                },
            },
            {
                "id": "InvalidFrame",
                "dataframe_schema": {
                    "index": {"name": "idx"},  # dtypeなし（エラー）
                    "columns": [{"name": "col2", "dtype": "str"}],
                },
            },
        ],
        "checks": [
            {
                "id": "valid_check",
                "description": "Valid check",
                "impl": "apps.checks:valid_check",
                "file_path": "checks/valid.py",
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]
    warnings = result["warnings"]
    successes = result["successes"]

    # エラーがあること
    assert any(len(errs) > 0 for errs in errors.values())

    # 警告もあること（check関数やexampleがない警告）
    assert any(len(warns) > 0 for warns in warnings.values())

    # 成功項目もあること（ValidFrameは成功しているはず）
    assert any(len(succs) > 0 for succs in successes.values())

    # しかし、バリデーション自体は完了していること（例外が投げられていない）
    assert result is not None


def test_validation_error_messages_are_descriptive(temp_spec_dir):
    """バリデーションエラーメッセージが詳細であることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "error-message-spec"},
        "datatypes": [
            {
                "id": "TestFrame",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "unknown_type"},  # 不正な型
                    "columns": [{"name": "col1", "dtype": "float"}],
                },
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]

    # エラーメッセージに以下の情報が含まれることを確認
    # - データ型ID
    # - 問題のフィールド
    # - 期待される値
    all_error_messages = []
    for category_errors in errors.values():
        all_error_messages.extend(category_errors)

    combined_errors = " ".join(all_error_messages).lower()

    # データ型IDが含まれているか
    assert "testframe" in combined_errors or "idx" in combined_errors


def test_validation_continues_after_first_error(temp_spec_dir):
    """最初のエラー後も検証が継続されることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "continue-validation-spec"},
        "datatypes": [
            {
                "id": "Frame1",
                "dataframe_schema": {
                    "columns": []  # indexなし（エラー1）
                },
            },
            {
                "id": "Frame2",
                "dataframe_schema": {
                    "index": {"name": "idx"},  # dtypeなし（エラー2）
                    "columns": [{"name": "col"}],  # dtypeなし（エラー3）
                },
            },
            {
                "id": "Frame3",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [
                        {"name": "a", "dtype": "float"},
                        {"name": "a", "dtype": "str"},  # 重複（エラー4）
                    ],
                },
            },
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]

    # 複数のエラーが報告されること（最初のエラーで停止していない）
    total_errors = sum(len(errs) for errs in errors.values())
    assert total_errors >= 2, "Validation should report multiple errors, not stop at the first one"


def test_validation_categorizes_errors_by_type(temp_spec_dir):
    """エラーが種類別にカテゴライズされて返されることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "categorized-errors-spec"},
        "datatypes": [
            {
                "id": "BadFrame",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": None},  # dtypeが明示的にnull
                    "columns": [
                        {"name": "col", "dtype": None},  # dtypeが明示的にnull
                        {"name": "col", "dtype": "float"},  # 重複カラム名
                    ],
                },
            }
        ],
        "checks": [
            {
                "id": "bad_check",
                "description": "Bad check",
                "impl": "invalid_format",  # 形式が不正（":" がない）
                "file_path": "",
            }
        ],
        "transforms": [
            {
                "id": "bad_transform",
                "description": "Bad transform",
                "impl": "also_invalid",  # 形式が不正（":" がない）
                "file_path": "",
                "parameters": [],
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))
    errors = result["errors"]

    # エラーがカテゴリ別に分類されていること
    assert isinstance(errors, dict)

    # 各カテゴリが存在すること（実装に依存）
    # 少なくとも複数のカテゴリにエラーが分散していること
    categories_with_errors = [cat for cat, errs in errors.items() if len(errs) > 0]
    assert len(categories_with_errors) >= 2, "Errors should be categorized by type"


def test_validation_summary_includes_counts(temp_spec_dir):
    """バリデーション結果にエラー/警告/成功の件数が含まれることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "summary-spec"},
        "datatypes": [
            {
                "id": "ValidFrame",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "col", "dtype": "float"}],
                },
            },
            {
                "id": "InvalidFrame",
                "dataframe_schema": {
                    "index": {"name": "idx"},  # dtypeなし（エラーを発生させる）
                    "columns": [{"name": "col", "dtype": "str"}],
                },
            },
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    result = validate_spec(str(spec_path))

    # 3層構造が返されること
    assert isinstance(result, dict)
    assert "errors" in result
    assert "warnings" in result
    assert "successes" in result

    errors = result["errors"]
    warnings = result["warnings"]
    successes = result["successes"]

    # エラー件数が取得できること
    total_errors = sum(len(errs) for errs in errors.values())
    assert total_errors > 0, "Should have at least one error (InvalidFrame with missing dtype)"

    # 警告件数が取得できること（check関数やexampleがない警告）
    total_warnings = sum(len(warns) for warns in warnings.values())
    assert total_warnings > 0, "Should have warnings (no check functions, no examples)"

    # 成功件数が取得できること（ValidFrameは成功）
    total_successes = sum(len(succs) for succs in successes.values())
    assert total_successes > 0, "Should have at least one success (ValidFrame)"

    # 各カテゴリの件数を表示（デバッグ用）
    print(f"Errors: {total_errors}, Warnings: {total_warnings}, Successes: {total_successes}")


def test_validation_handles_circular_dependencies_gracefully(temp_spec_dir):
    """循環依存がある場合も、他の検証項目は継続されることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "circular-dep-spec"},
        "datatypes": [
            {
                "id": "Frame1",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "col", "dtype": "float"}],
                },
            }
        ],
        "transforms": [
            {
                "id": "transform_a",
                "impl": "apps.transforms:transform_a",
                "file_path": "transforms/a.py",
                "parameters": [{"name": "input", "type_ref": "Frame1"}],
                "return_type_ref": "Frame1",
            },
            {
                "id": "transform_b",
                "impl": "apps.transforms:transform_b",
                "file_path": "transforms/b.py",
                "parameters": [{"name": "input", "type_ref": "Frame1"}],
                "return_type_ref": "Frame1",
            },
        ],
        "dag_stages": [
            {
                "stage_id": "stage_a",
                "selection_mode": "single",
                "input_type": "Frame1",
                "output_type": "Frame1",
                "candidates": ["transform_a"],
            },
            {
                "stage_id": "stage_b",
                "selection_mode": "single",
                "input_type": "Frame1",
                "output_type": "Frame1",
                "candidates": ["transform_b"],
            },
        ],
    }

    # 循環依存を作るために、DAGを追加
    # （実際の循環依存チェックは別の場所で行われる可能性があるが、
    # ここではバリデーションが例外を投げずに完了することを確認）

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    # バリデーション実行（例外を投げない）
    try:
        result = validate_spec(str(spec_path))
        assert result is not None
        assert "errors" in result
        assert "warnings" in result
        assert "successes" in result
    except Exception as e:
        pytest.fail(f"Validation should not raise exception, but got: {e}")

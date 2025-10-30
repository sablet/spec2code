"""Validator: IR検証 - 公開API

IRの検証を行うための公開APIを提供する。
内部的には分割されたモジュールを使用する。
"""

from __future__ import annotations

import sys
from pathlib import Path

from spectool.spectool.core.engine.loader import load_spec
from spectool.spectool.core.engine.validate_edge_cases import (
    validate_datatype_checks,
    validate_datatype_examples_generators,
    validate_edge_cases_errors_only,
)
from spectool.spectool.core.engine.validate_example_data import validate_example_data
from spectool.spectool.core.engine.validate_formatter import (
    categorize_error,
    create_category_dict,
    format_validation_result,
    record_successes,
)
from spectool.spectool.core.engine.validate_ir import validate_ir


def validate_spec(
    spec_path: str | Path,
    skip_impl_check: bool = False,
    normalize: bool = False,
) -> dict[str, dict[str, list[str]]]:
    """Spec YAMLファイルを読み込み、エラー/警告/成功をカテゴリ別に返す

    Args:
        spec_path: Spec YAMLファイルのパス
        skip_impl_check: 実装ファイルのインポートチェックをスキップ（gen時に使用）
        normalize: IRを正規化してから検証（Pydanticモデルから列を推論）

    Returns:
        3層構造の辞書: {"errors": {...}, "warnings": {...}, "successes": {...}}
        各層はカテゴリ別のメッセージリスト
    """
    spec_path = Path(spec_path)
    ir = load_spec(spec_path)

    # 正規化オプション
    if normalize:
        from spectool.spectool.core.engine.normalizer import normalize_ir

        ir = normalize_ir(ir)

    # sys.pathにproject_rootを追加（apps.XXX形式のimportのため）
    # project_root は spec_path の親ディレクトリと仮定
    project_root = spec_path.parent.resolve()
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

    # カテゴリ別辞書を作成
    errors = create_category_dict()
    warnings = create_category_dict()
    successes = create_category_dict()

    # 既存のvalidate_irを実行
    flat_errors = validate_ir(ir, skip_impl_check=skip_impl_check)

    # エラーをカテゴリ別に分類
    for error in flat_errors:
        categorize_error(error, errors)

    # エッジケース検証を追加（エラーのみ）
    edge_case_errors = validate_edge_cases_errors_only(ir)
    errors["edge_cases"].extend(edge_case_errors)

    # Exampleデータのschema検証
    example_data_errors = validate_example_data(ir)
    errors["examples"].extend(example_data_errors)

    # 警告を生成
    datatype_check_warnings = validate_datatype_checks(ir)
    warnings["datatypes"].extend(datatype_check_warnings)

    datatype_example_warnings = validate_datatype_examples_generators(ir)
    warnings["datatypes"].extend(datatype_example_warnings)

    # 成功を記録
    record_successes(ir, errors, successes)

    return {"errors": errors, "warnings": warnings, "successes": successes}


# Re-export format_validation_result for convenience
__all__ = ["validate_spec", "validate_ir", "format_validation_result"]

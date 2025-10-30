"""Validator: 検証結果のフォーマット

カテゴリ別に分類された検証結果をフォーマットして出力する。
"""

from __future__ import annotations

from spectool.spectool.core.base.ir import SpecIR


def create_category_dict() -> dict[str, list[str]]:
    """カテゴリ別辞書を作成

    Returns:
        カテゴリ別のメッセージリスト辞書
    """
    return {
        "dataframe_schemas": [],
        "datatypes": [],
        "check_definitions": [],
        "checks": [],
        "transform_definitions": [],
        "transforms": [],
        "dag_stages": [],
        "examples": [],
        "parameter_types": [],
        "edge_cases": [],
    }


def _match_dataframe_schema_error(error: str) -> bool:
    """DataFrameスキーマエラーかチェック"""
    return "DataFrame" in error and ("duplicate column" in error.lower() or "dtype is not set" in error)


def _match_dataframe_error(error: str) -> bool:
    """DataFrameエラーかチェック"""
    return "DataFrame" in error


def _match_check_definition_error(error: str) -> bool:
    """Check定義エラーかチェック"""
    return "Check" in error and "impl" in error


def _match_check_error(error: str) -> bool:
    """Checkエラーかチェック"""
    return "Check" in error


def _match_transform_definition_error(error: str) -> bool:
    """Transform定義エラーかチェック"""
    return "Transform" in error and ("impl" in error or "type_ref" in error or "parameter" in error)


def _match_transform_error(error: str) -> bool:
    """Transformエラーかチェック"""
    return "Transform" in error


def _match_dag_stage_error(error: str) -> bool:
    """DAG Stageエラーかチェック"""
    return "DAG Stage" in error or "candidate" in error.lower()


def _match_example_error(error: str) -> bool:
    """Exampleエラーかチェック"""
    return "Example" in error


def _match_parameter_type_error(error: str) -> bool:
    """パラメータ型エラーかチェック"""
    return "parameter" in error.lower() and ("type" in error.lower() or "default" in error.lower())


def categorize_error(error: str, errors: dict[str, list[str]]) -> None:
    """エラーメッセージをカテゴリ別に分類

    Args:
        error: エラーメッセージ
        errors: カテゴリ別エラー辞書
    """
    # マッチング規則を順番に適用（優先度順）
    if _match_dataframe_schema_error(error):
        errors["dataframe_schemas"].append(error)
    elif _match_dataframe_error(error):
        errors["datatypes"].append(error)
    elif _match_check_definition_error(error):
        errors["check_definitions"].append(error)
    elif _match_check_error(error):
        errors["checks"].append(error)
    elif _match_transform_definition_error(error):
        errors["transform_definitions"].append(error)
    elif _match_transform_error(error):
        errors["transforms"].append(error)
    elif _match_dag_stage_error(error):
        errors["dag_stages"].append(error)
    elif _match_example_error(error):
        errors["examples"].append(error)
    elif _match_parameter_type_error(error):
        errors["parameter_types"].append(error)
    else:
        errors["edge_cases"].append(error)


def _record_success_if_no_error(
    item_id: str, item_type: str, all_errors: str, category: str, message: str, successes: dict[str, list[str]]
) -> None:
    """エラーがない項目を成功として記録

    Args:
        item_id: 項目ID
        item_type: 項目タイプ（"DataFrame", "Check", "Transform"など）
        all_errors: 全エラーメッセージの結合文字列
        category: 成功カテゴリ
        message: 成功メッセージ
        successes: 成功辞書
    """
    if f"{item_type} '{item_id}'" not in all_errors:
        successes[category].append(message)


def record_successes(ir: SpecIR, errors: dict[str, list[str]], successes: dict[str, list[str]]) -> None:
    """検証に成功した項目を記録する

    Args:
        ir: 検証対象のIR
        errors: エラー辞書（どの項目にエラーがあるか確認用）
        successes: 成功辞書（ここに成功メッセージを追加）
    """
    # すべてのエラーメッセージを結合（エラーチェック用）
    all_errors = " ".join([msg for msgs in errors.values() for msg in msgs])

    # DataFrame schemas の成功
    for frame in ir.frames:
        _record_success_if_no_error(
            frame.id,
            "DataFrame",
            all_errors,
            "dataframe_schemas",
            f"DataFrame '{frame.id}': schema is valid",
            successes,
        )

    # Check definitions の成功
    for check in ir.checks:
        _record_success_if_no_error(
            check.id, "Check", all_errors, "check_definitions", f"Check '{check.id}': definition is valid", successes
        )

    # Transform definitions の成功
    for transform in ir.transforms:
        _record_success_if_no_error(
            transform.id,
            "Transform",
            all_errors,
            "transform_definitions",
            f"Transform '{transform.id}': definition is valid",
            successes,
        )

    # DAG stages の成功
    for stage in ir.dag_stages:
        _record_success_if_no_error(
            stage.stage_id,
            "DAG Stage",
            all_errors,
            "dag_stages",
            f"DAG Stage '{stage.stage_id}': configuration is valid",
            successes,
        )

    # Examples の成功
    for example in ir.examples:
        _record_success_if_no_error(
            example.id,
            "Example",
            all_errors,
            "examples",
            f"Example '{example.id}': datatype_ref is valid",
            successes,
        )


_CATEGORY_LABELS = {
    "dataframe_schemas": "📊 DataFrame Schemas",
    "datatypes": "🔤 Data Types",
    "check_definitions": "✓ Check Definitions",
    "checks": "✓ Checks",
    "transform_definitions": "🔄 Transform Definitions",
    "transforms": "🔄 Transforms",
    "dag_stages": "📈 DAG Stages",
    "examples": "📝 Examples",
    "parameter_types": "⚙️  Parameter Types",
    "edge_cases": "⚠️  Edge Cases",
}


def _format_message_category(category: str, messages: list[str], message_type: str) -> list[str]:
    """メッセージカテゴリをフォーマット"""
    if not messages:
        return []

    lines = []
    label = _CATEGORY_LABELS.get(category, category)
    count = len(messages)
    suffix = "s" if count > 1 else ""

    if message_type == "passed":
        lines.append(f"{label} ({count} {message_type}):")
    else:
        lines.append(f"{label} ({count} {message_type}{suffix}):")

    for msg in messages:
        lines.append(f"  • {msg}")
    lines.append("")
    return lines


def _format_errors(errors: dict[str, list[str]]) -> list[str]:
    """エラーメッセージをフォーマット"""
    total_errors = sum(len(msgs) for msgs in errors.values())
    if total_errors == 0:
        return []

    lines = [f"\n❌ Validation failed with {total_errors} error(s):\n"]
    for category, messages in errors.items():
        lines.extend(_format_message_category(category, messages, "error"))
    return lines


def _format_warnings(warnings: dict[str, list[str]]) -> list[str]:
    """警告メッセージをフォーマット"""
    total_warnings = sum(len(msgs) for msgs in warnings.values())
    if total_warnings == 0:
        return []

    lines = [f"\n⚠️  Found {total_warnings} warning(s):\n"]
    for category, messages in warnings.items():
        lines.extend(_format_message_category(category, messages, "warning"))
    return lines


def _format_successes(successes: dict[str, list[str]], verbose: bool) -> list[str]:
    """成功メッセージをフォーマット（verboseモード）"""
    if not verbose:
        return []

    total_successes = sum(len(msgs) for msgs in successes.values())
    if total_successes == 0:
        return []

    lines = [f"\n✅ {total_successes} item(s) passed validation:\n"]
    for category, messages in successes.items():
        lines.extend(_format_message_category(category, messages, "passed"))
    return lines


def format_validation_result(result: dict[str, dict[str, list[str]]], verbose: bool = False) -> str:
    """検証結果をフォーマットして文字列に変換

    Args:
        result: validate_spec()の戻り値
        verbose: 詳細表示モード（成功も表示）

    Returns:
        フォーマットされた検証結果の文字列
    """
    lines = []
    errors = result["errors"]
    warnings = result["warnings"]
    successes = result["successes"]

    # エラー、警告、成功をフォーマット
    lines.extend(_format_errors(errors))
    lines.extend(_format_warnings(warnings))
    lines.extend(_format_successes(successes, verbose))

    # 成功メッセージ（エラーがなければ表示）
    total_errors = sum(len(msgs) for msgs in errors.values())
    if total_errors == 0:
        lines.append("✅ All validations passed")

    return "\n".join(lines)

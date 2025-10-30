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


def categorize_error(error: str, errors: dict[str, list[str]]) -> None:
    """エラーメッセージをカテゴリ別に分類

    Args:
        error: エラーメッセージ
        errors: カテゴリ別エラー辞書
    """
    categorized = False

    # DataFrame schema errors
    if "DataFrame" in error and ("duplicate column" in error.lower() or "dtype is not set" in error):
        errors["dataframe_schemas"].append(error)
        categorized = True
    # DataFrame datatype errors
    elif "DataFrame" in error:
        errors["datatypes"].append(error)
        categorized = True

    # Check definition errors (impl related)
    if "Check" in error and "impl" in error:
        errors["check_definitions"].append(error)
        categorized = True
    # Other check errors
    elif "Check" in error and not categorized:
        errors["checks"].append(error)
        categorized = True

    # Transform definition errors (impl, type_ref, parameter related)
    if "Transform" in error and ("impl" in error or "type_ref" in error or "parameter" in error):
        errors["transform_definitions"].append(error)
        categorized = True
    # Other transform errors
    elif "Transform" in error and not categorized:
        errors["transforms"].append(error)
        categorized = True

    # DAG stage errors
    if ("DAG Stage" in error or "candidate" in error.lower()) and not categorized:
        errors["dag_stages"].append(error)
        categorized = True

    # Example errors
    if "Example" in error and not categorized:
        errors["examples"].append(error)
        categorized = True

    # Parameter type errors
    if "parameter" in error.lower() and ("type" in error.lower() or "default" in error.lower()) and not categorized:
        errors["parameter_types"].append(error)
        categorized = True

    # Edge cases (uncategorized)
    if not categorized:
        errors["edge_cases"].append(error)


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
        if f"DataFrame '{frame.id}'" not in all_errors:
            successes["dataframe_schemas"].append(f"DataFrame '{frame.id}': schema is valid")

    # Check definitions の成功
    for check in ir.checks:
        if f"Check '{check.id}'" not in all_errors:
            successes["check_definitions"].append(f"Check '{check.id}': definition is valid")

    # Transform definitions の成功
    for transform in ir.transforms:
        if f"Transform '{transform.id}'" not in all_errors:
            successes["transform_definitions"].append(f"Transform '{transform.id}': definition is valid")

    # DAG stages の成功
    for stage in ir.dag_stages:
        if f"DAG Stage '{stage.stage_id}'" not in all_errors:
            successes["dag_stages"].append(f"DAG Stage '{stage.stage_id}': configuration is valid")

    # Examples の成功
    for example in ir.examples:
        if f"Example '{example.id}'" not in all_errors:
            successes["examples"].append(f"Example '{example.id}': datatype_ref is valid")


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

"""Config検証 - 型チェック

パラメータの型チェックを行うヘルパー関数。
"""

from __future__ import annotations

import inspect
from typing import Any


def expected_basic_type(annotation: object) -> type | None:
    """型アノテーションから基本型を抽出

    Args:
        annotation: 型アノテーション

    Returns:
        基本型 (int, float, str, bool) またはNone
    """
    basic_types: dict[str, type] = {
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "builtins.int": int,
        "builtins.float": float,
        "builtins.str": str,
        "builtins.bool": bool,
    }

    if annotation in {int, float, str, bool}:
        return annotation  # type: ignore

    as_str = str(annotation)
    if as_str.startswith("<class '") and as_str.endswith("'>"):
        return basic_types.get(as_str[8:-2])

    return basic_types.get(as_str)


def validate_parameter_type(
    transform_id: str,
    param_name: str,
    param_value: Any,  # noqa: ANN401
    param_spec: inspect.Parameter,
) -> list[str]:
    """パラメータ型を検証

    Args:
        transform_id: Transform ID
        param_name: パラメータ名
        param_value: パラメータ値
        param_spec: パラメータ仕様

    Returns:
        エラーメッセージリスト
    """
    if param_spec.annotation == inspect.Parameter.empty:
        return []

    expected_type = expected_basic_type(param_spec.annotation)
    if expected_type and not isinstance(param_value, expected_type):
        return [
            f"Transform '{transform_id}': parameter '{param_name}' expected type "
            f"{expected_type.__name__}, got {type(param_value).__name__}"
        ]

    return []


def validate_param_type_from_spec(
    transform_id: str,
    param_name: str,
    param_value: Any,  # noqa: ANN401
    param_def: Any,  # noqa: ANN401
) -> list[str]:
    """Spec定義からパラメータ型を検証

    Args:
        transform_id: Transform ID
        param_name: パラメータ名
        param_value: パラメータ値
        param_def: パラメータ定義

    Returns:
        エラーメッセージリスト
    """
    # nativeフィールドから型を取得
    native_type = getattr(param_def, "type_ref", None)
    if not native_type:
        return []

    # "builtins:type"形式から型名を抽出
    type_name = native_type.split(":")[-1] if ":" in native_type else native_type

    # 基本型のマッピング
    type_mapping = {
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
    }

    expected_type = type_mapping.get(type_name)
    if expected_type and not isinstance(param_value, expected_type):
        return [
            f"Transform '{transform_id}': parameter '{param_name}' expected type "
            f"{expected_type.__name__}, got {type(param_value).__name__}"
        ]

    return []

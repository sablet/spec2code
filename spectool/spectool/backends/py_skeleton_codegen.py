"""Python スケルトン生成 - コード生成ヘルパー

型アノテーション、パラメータシグネチャ、インポート文の生成を担当。
"""

from __future__ import annotations

from spectool.spectool.core.base.ir import ParameterSpec, SpecIR, TransformSpec


def extract_function_name(impl: str) -> str:
    """implから関数名を抽出

    Args:
        impl: "module.path:function_name" 形式の文字列

    Returns:
        関数名
    """
    if ":" in impl:
        return impl.split(":")[-1]
    return impl


def resolve_type_annotation(param: ParameterSpec, ir: SpecIR) -> str:
    """パラメータから型アノテーション文字列を生成

    Args:
        param: パラメータ定義
        ir: SpecIR（型参照解決用）

    Returns:
        型アノテーション文字列（例: "Annotated[pd.DataFrame, Check[...]]"）
    """
    type_ref = param.type_ref

    # ネイティブ型の場合
    if "builtins:" in type_ref:
        return type_ref.split(":")[-1]

    # DataFrame型の場合
    for frame in ir.frames:
        if frame.id == type_ref:
            # Check関数があればAnnotatedで包む
            if frame.check_functions:
                check_refs = ", ".join(f'Check["{cf}"]' for cf in frame.check_functions)
                return f"Annotated[pd.DataFrame, {check_refs}]"
            return "pd.DataFrame"

    # Enum型の場合
    for enum in ir.enums:
        if enum.id == type_ref:
            return enum.id

    # Pydanticモデルの場合
    for model in ir.pydantic_models:
        if model.id == type_ref:
            return model.id

    # 型が見つからない場合はそのまま返す
    return type_ref


def render_parameter_signature(param: ParameterSpec, ir: SpecIR) -> str:
    """パラメータのシグネチャ文字列を生成

    Args:
        param: パラメータ定義
        ir: SpecIR（型参照解決用）

    Returns:
        パラメータシグネチャ文字列（例: "data: Annotated[pd.DataFrame, ...]"）
    """
    type_annotation = resolve_type_annotation(param, ir)

    if param.optional and param.default is not None:
        # デフォルト値がある場合
        if isinstance(param.default, str):
            return f"{param.name}: {type_annotation} = '{param.default}'"
        return f"{param.name}: {type_annotation} = {param.default}"
    if param.optional:
        # Optionalだがデフォルト値がない場合
        return f"{param.name}: {type_annotation} | None = None"
    # 必須パラメータ
    return f"{param.name}: {type_annotation}"


def resolve_transform_return_type(transform: TransformSpec, ir: SpecIR) -> str:
    """Resolve return type for transform function."""
    if not transform.return_type_ref:
        return "Any"

    for frame in ir.frames:
        if frame.id == transform.return_type_ref:
            if frame.check_functions:
                check_refs = ", ".join(f'Check["{cf}"]' for cf in frame.check_functions)
                return f"Annotated[pd.DataFrame, {check_refs}]"
            return "pd.DataFrame"

    return transform.return_type_ref


def update_imports_for_transform(imports: set[str], return_type: str, params: list[str]) -> None:
    """Update imports based on return type and parameters."""
    if "Annotated" in return_type or any("Annotated" in p for p in params):
        imports.add("from typing import Annotated")
    if "pd.DataFrame" in return_type or any("pd.DataFrame" in p for p in params):
        imports.add("import pandas as pd")
    if "Check" in return_type or any("Check" in p for p in params):
        imports.add("from spectool.spectool.core.base.meta_types import Check")


def build_transform_function_signature(
    func_name: str, param_str: str, return_type: str, description: str | None
) -> list[str]:
    """Build function signature lines."""
    lines = []
    if description:
        lines.append(f"# {description}")

    lines.append(f"def {func_name}({param_str}) -> {return_type}:")
    lines.append(f'    """TODO: Implement {func_name}')
    lines.append("    ")
    if description:
        lines.append(f"    {description}")
    lines.append('    """')
    lines.append("    # TODO: Implement transformation logic")

    return lines


def build_function_body_placeholder(return_type: str) -> list[str]:
    """Build placeholder return statement."""
    if "pd.DataFrame" in return_type:
        return ["    return pd.DataFrame()"]
    return ["    raise NotImplementedError()"]


def render_imports(imports: set[str]) -> str:
    """インポート文を整形して返す"""
    if not imports:
        return ""
    return "\n".join(sorted(imports))

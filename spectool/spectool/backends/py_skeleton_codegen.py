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


def resolve_type_annotation(param: ParameterSpec, ir: SpecIR, imports: set[str] | None = None) -> str:
    """パラメータから型アノテーション文字列を生成

    Args:
        param: パラメータ定義
        ir: SpecIR（型参照解決用）
        imports: インポート文を蓄積するセット（指定時のみimportを追加）

    Returns:
        型アノテーション文字列（例: "Annotated[pd.DataFrame, Check[...]]"）
    """
    type_ref = param.type_ref
    app_name = ir.meta.name.replace("-", "_") if ir.meta else "app"

    # ネイティブ型の場合
    if "builtins:" in type_ref:
        return type_ref.split(":")[-1]

    # DataFrame型の場合
    for frame in ir.frames:
        if frame.id == type_ref:
            if imports is not None:
                imports.add("import pandas as pd")
            # Check関数があればAnnotatedで包む
            if frame.check_functions:
                if imports is not None:
                    imports.add("from typing import Annotated")
                    imports.add("from spectool.spectool.core.base.meta_types import Check")
                check_refs = ", ".join(f'Check["{cf}"]' for cf in frame.check_functions)
                return f"Annotated[pd.DataFrame, {check_refs}]"
            return "pd.DataFrame"

    # Enum型の場合
    for enum in ir.enums:
        if enum.id == type_ref:
            if imports is not None:
                imports.add(f"from apps.{app_name}.models.enums import {enum.id}")
            return enum.id

    # Pydanticモデルの場合
    for model in ir.pydantic_models:
        if model.id == type_ref:
            if imports is not None:
                imports.add(f"from apps.{app_name}.models.models import {model.id}")
            return model.id

    # TypeAliasの場合
    for type_alias in ir.type_aliases:
        if type_alias.id == type_ref:
            if imports is not None:
                imports.add(f"from apps.{app_name}.types import {type_alias.id}")
                # TypeAliasがpandas:DataFrameを参照している場合、pandasもimport
                target = type_alias.type_def.get("target", "")
                if target and "pandas:" in target:
                    imports.add("import pandas as pd")
            return type_alias.id

    # Genericの場合
    for generic in ir.generics:
        if generic.id == type_ref:
            if imports is not None:
                imports.add(f"from apps.{app_name}.types import {generic.id}")
            return generic.id

    # 型が見つからない場合はそのまま返す
    return type_ref


def render_parameter_signature(param: ParameterSpec, ir: SpecIR, imports: set[str] | None = None) -> str:
    """パラメータのシグネチャ文字列を生成

    Args:
        param: パラメータ定義
        ir: SpecIR（型参照解決用）
        imports: インポート文を蓄積するセット（指定時のみimportを追加）

    Returns:
        パラメータシグネチャ文字列（例: "data: Annotated[pd.DataFrame, ...]"）
    """
    type_annotation = resolve_type_annotation(param, ir, imports)

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


def resolve_transform_return_type(transform: TransformSpec, ir: SpecIR, imports: set[str] | None = None) -> str:
    """Resolve return type for transform function.

    Args:
        transform: Transform定義
        ir: SpecIR（型参照解決用）
        imports: インポート文を蓄積するセット（指定時のみimportを追加）

    Returns:
        戻り値の型アノテーション文字列
    """
    if not transform.return_type_ref:
        if imports is not None:
            imports.add("from typing import Any")
        return "Any"

    return_type_ref = transform.return_type_ref
    app_name = ir.meta.name.replace("-", "_") if ir.meta else "app"

    # DataFrame型の場合
    for frame in ir.frames:
        if frame.id == return_type_ref:
            if imports is not None:
                imports.add("import pandas as pd")
            if frame.check_functions:
                if imports is not None:
                    imports.add("from typing import Annotated")
                    imports.add("from spectool.spectool.core.base.meta_types import Check")
                check_refs = ", ".join(f'Check["{cf}"]' for cf in frame.check_functions)
                return f"Annotated[pd.DataFrame, {check_refs}]"
            return "pd.DataFrame"

    # Enum型の場合
    for enum in ir.enums:
        if enum.id == return_type_ref:
            if imports is not None:
                imports.add(f"from apps.{app_name}.models.enums import {enum.id}")
            return enum.id

    # Pydanticモデルの場合
    for model in ir.pydantic_models:
        if model.id == return_type_ref:
            if imports is not None:
                imports.add(f"from apps.{app_name}.models.models import {model.id}")
            return model.id

    # TypeAliasの場合
    for type_alias in ir.type_aliases:
        if type_alias.id == return_type_ref:
            if imports is not None:
                imports.add(f"from apps.{app_name}.types import {type_alias.id}")
                # TypeAliasがpandas:DataFrameを参照している場合、pandasもimport
                target = type_alias.type_def.get("target", "")
                if target and "pandas:" in target:
                    imports.add("import pandas as pd")
            return type_alias.id

    # Genericの場合
    for generic in ir.generics:
        if generic.id == return_type_ref:
            if imports is not None:
                imports.add(f"from apps.{app_name}.types import {generic.id}")
            return generic.id

    # 型が見つからない場合はそのまま返す
    return return_type_ref


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

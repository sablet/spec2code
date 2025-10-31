"""Python スケルトン生成 - コード生成ヘルパー

型アノテーション、パラメータシグネチャ、インポート文の生成を担当。
"""

from __future__ import annotations

from typing import Protocol

from spectool.spectool.core.base.ir import ParameterSpec, SpecIR, SpecMetadata


class HasReturnTypeRef(Protocol):
    """return_type_ref属性を持つオブジェクトのプロトコル"""

    return_type_ref: str | None


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


def _add_type_alias_imports(imports: set[str] | None, app_name: str, type_alias_id: str, target: str) -> None:
    """TypeAlias用のインポートを追加"""
    if imports is None:
        return
    imports.add(f"from apps.{app_name}.types import {type_alias_id}")
    if target and "pandas:" in target:
        imports.add("import pandas as pd")


def _add_generic_imports(imports: set[str] | None, app_name: str, generic_id: str) -> None:
    """Generic用のインポートを追加"""
    if imports is not None:
        imports.add(f"from apps.{app_name}.types import {generic_id}")


def _add_enum_imports(imports: set[str] | None, app_name: str, enum_id: str) -> None:
    """Enum用のインポートを追加"""
    if imports is not None:
        imports.add(f"from apps.{app_name}.models.enums import {enum_id}")


def _add_model_imports(imports: set[str] | None, app_name: str, model_id: str) -> None:
    """Pydanticモデル用のインポートを追加"""
    if imports is not None:
        imports.add(f"from apps.{app_name}.models.models import {model_id}")


def _search_in_type_aliases(type_ref: str, ir: SpecIR, app_name: str, imports: set[str] | None) -> str | None:
    """TypeAliasコレクションから検索"""
    for type_alias in ir.type_aliases:
        if type_alias.id == type_ref:
            target = type_alias.type_def.get("target", "")
            _add_type_alias_imports(imports, app_name, type_alias.id, target)
            return type_alias.id
    return None


def _search_in_generics(type_ref: str, ir: SpecIR, app_name: str, imports: set[str] | None) -> str | None:
    """Genericコレクションから検索"""
    for generic in ir.generics:
        if generic.id == type_ref:
            _add_generic_imports(imports, app_name, generic.id)
            return generic.id
    return None


def _search_in_enums(type_ref: str, ir: SpecIR, app_name: str, imports: set[str] | None) -> str | None:
    """Enumコレクションから検索"""
    for enum in ir.enums:
        if enum.id == type_ref:
            _add_enum_imports(imports, app_name, enum.id)
            return enum.id
    return None


def _search_in_models(type_ref: str, ir: SpecIR, app_name: str, imports: set[str] | None) -> str | None:
    """Pydanticモデルコレクションから検索"""
    for model in ir.pydantic_models:
        if model.id == type_ref:
            _add_model_imports(imports, app_name, model.id)
            return model.id
    return None


def _search_in_frames(type_ref: str, ir: SpecIR, app_name: str, imports: set[str] | None) -> str | None:
    """DataFrameコレクションから検索してTypeAliasを返す

    Frameが見つかった場合、types.pyで定義されているTypeAliasを使用する。
    """
    for frame in ir.frames:
        if frame.id == type_ref:
            # types.pyで定義されているTypeAliasを使用
            _add_type_alias_imports(imports, app_name, frame.id, "pandas:DataFrame")
            return frame.id
    return None


def _find_type_in_collections(type_ref: str, ir: SpecIR, app_name: str, imports: set[str] | None) -> str | None:
    """型参照をコレクション内で検索して解決

    Returns:
        解決された型文字列、または見つからない場合はNone
    """
    # 優先順位に従って検索
    return (
        _search_in_type_aliases(type_ref, ir, app_name, imports)
        or _search_in_generics(type_ref, ir, app_name, imports)
        or _search_in_enums(type_ref, ir, app_name, imports)
        or _search_in_models(type_ref, ir, app_name, imports)
        or _search_in_frames(type_ref, ir, app_name, imports)
    )


def _resolve_type_ref(type_ref: str, ir: SpecIR, imports: set[str] | None = None) -> str:
    """型参照を解決して型アノテーション文字列を生成

    Args:
        type_ref: 型参照（datatype_ref または native）
        ir: SpecIR（型参照解決用）
        imports: インポート文を蓄積するセット（指定時のみimportを追加）

    Returns:
        型アノテーション文字列
    """
    # ネイティブ型の場合
    if "builtins:" in type_ref:
        return type_ref.split(":")[-1]

    app_name = ir.meta.name.replace("-", "_") if ir.meta else "app"

    # 各種型コレクションから検索
    resolved = _find_type_in_collections(type_ref, ir, app_name, imports)
    if resolved:
        return resolved

    # 型が見つからない場合はそのまま返す
    return type_ref


def resolve_type_annotation(param: ParameterSpec, ir: SpecIR, imports: set[str] | None = None) -> str:
    """パラメータから型アノテーション文字列を生成

    Args:
        param: パラメータ定義
        ir: SpecIR（型参照解決用）
        imports: インポート文を蓄積するセット（指定時のみimportを追加）

    Returns:
        型アノテーション文字列（例: "Annotated[pd.DataFrame, Check[...]]"）
    """
    return _resolve_type_ref(param.type_ref, ir, imports)


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

    # デフォルト値がある場合は、optionalフラグに関わらず生成
    if param.default is not None:
        if isinstance(param.default, str):
            return f"{param.name}: {type_annotation} = '{param.default}'"
        return f"{param.name}: {type_annotation} = {param.default}"
    if param.optional:
        # Optionalだがデフォルト値がない場合
        return f"{param.name}: {type_annotation} | None = None"
    # 必須パラメータ
    return f"{param.name}: {type_annotation}"


def resolve_transform_return_type(transform: HasReturnTypeRef, ir: SpecIR, imports: set[str] | None = None) -> str:
    """Resolve return type for transform function.

    Args:
        transform: return_type_ref属性を持つオブジェクト（TransformSpec, GeneratorDefなど）
        ir: SpecIR（型参照解決用）
        imports: インポート文を蓄積するセット（指定時のみimportを追加）

    Returns:
        戻り値の型アノテーション文字列
    """
    if not transform.return_type_ref:
        if imports is not None:
            imports.add("from typing import Any")
        return "Any"

    return _resolve_type_ref(transform.return_type_ref, ir, imports)


def build_transform_function_signature(
    func_name: str,
    param_str: str,
    return_type: str,
    description: str | None,
    spec_metadata: SpecMetadata | None = None,
) -> list[str]:
    """Build function signature lines with optional metadata.

    Args:
        func_name: 関数名
        param_str: パラメータ文字列
        return_type: 戻り値型
        description: 関数の説明
        spec_metadata: 実装者向けメタデータ（docstring生成用）

    Returns:
        関数定義の行リスト
    """
    lines = []
    lines.append(f"def {func_name}({param_str}) -> {return_type}:")
    lines.append('    """')
    if description:
        lines.append(f"    {description}")

    # SpecMetadataセクションを追加
    if spec_metadata:
        if description:
            lines.append("    ")

        # Implementation policy or Explicit checks
        if not spec_metadata.explicit_checks:
            # 空リスト or 省略の場合: 素朴な実装ポリシー
            lines.append(
                "    Policy: Implement straightforwardly without defensive checks or custom exception handling"
            )
            lines.append("    ")
        else:
            # explicit_checksがある場合
            lines.append("    Explicit checks (validate only these):")
            for check in spec_metadata.explicit_checks:
                lines.append(f"    - {check}")
            lines.append("    ")
            lines.append("    Do NOT add other defensive checks beyond what is explicitly listed above.")
            lines.append("    ")

        # Logic steps
        if spec_metadata.logic_steps:
            lines.append("    Logic steps:")
            for step in spec_metadata.logic_steps:
                lines.append(f"    - {step}")
            lines.append("    ")

        # Implementation hints
        if spec_metadata.implementation_hints:
            lines.append("    Implementation hints:")
            for hint in spec_metadata.implementation_hints:
                lines.append(f"    - {hint}")

    lines.append('    """')

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

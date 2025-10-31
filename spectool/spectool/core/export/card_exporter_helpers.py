"""Card Exporter Helper Functions - 型収集とカテゴリ判定のヘルパー関数"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from spectool.spectool.core.base.ir import PydanticModelSpec

from spectool.spectool.core.base.ir import SpecIR


def _process_pydantic_field_type_ref(spec_ir: SpecIR, field_type: str, visited: set[str]) -> None:
    """Pydanticフィールドのtype_refを処理"""
    if "[" in field_type and "]" in field_type:
        inner_type = field_type[field_type.index("[") + 1 : field_type.rindex("]")]
        if ":" in inner_type:
            inner_type = inner_type.split(":")[-1]
        collect_nested_types(spec_ir, inner_type, visited)
    else:
        collect_nested_types(spec_ir, field_type, visited)


def _process_pydantic_field_type_dict(spec_ir: SpecIR, type_field: dict[str, Any], visited: set[str]) -> None:
    """Pydanticフィールドのtype辞書を処理"""
    # type.datatype_refをチェック
    datatype_ref = type_field.get("datatype_ref", "")
    if datatype_ref and not datatype_ref.startswith("builtins:"):
        collect_nested_types(spec_ir, datatype_ref, visited)

    # type.generic.element_type.datatype_refをチェック
    generic_field = type_field.get("generic", {})
    if isinstance(generic_field, dict):
        element_type = generic_field.get("element_type", {})
        if isinstance(element_type, dict):
            elem_datatype_ref = element_type.get("datatype_ref", "")
            if elem_datatype_ref and not elem_datatype_ref.startswith("builtins:"):
                collect_nested_types(spec_ir, elem_datatype_ref, visited)


def _process_pydantic_fields(spec_ir: SpecIR, pydantic: PydanticModelSpec, visited: set[str]) -> None:
    """Pydanticモデルのフィールドを処理"""
    for field in pydantic.fields:
        field_type = field.get("type_ref", "")
        if field_type and not field_type.startswith("builtins:"):
            _process_pydantic_field_type_ref(spec_ir, field_type, visited)

        type_field = field.get("type", {})
        if isinstance(type_field, dict):
            _process_pydantic_field_type_dict(spec_ir, type_field, visited)


def _handle_pydantic_type(spec_ir: SpecIR, type_ref: str, visited: set[str]) -> bool:
    """Pydanticモデルの処理"""
    pydantic = next((p for p in spec_ir.pydantic_models if p.id == type_ref), None)
    if pydantic:
        _process_pydantic_fields(spec_ir, pydantic, visited)
        return True
    return False


def _handle_generic_type(spec_ir: SpecIR, type_ref: str, visited: set[str]) -> bool:
    """Generic型の処理"""
    generic = next((g for g in spec_ir.generics if g.id == type_ref), None)
    if generic and generic.element_type:
        elem_type_ref = generic.element_type.get("datatype_ref", "")
        if elem_type_ref and not elem_type_ref.startswith("builtins:"):
            collect_nested_types(spec_ir, elem_type_ref, visited)
        return True
    return False


def _handle_alias_type(spec_ir: SpecIR, type_ref: str, visited: set[str]) -> bool:
    """TypeAliasの処理"""
    alias = next((a for a in spec_ir.type_aliases if a.id == type_ref), None)
    if alias and alias.type_def:
        alias_type_ref = alias.type_def.get("datatype_ref", "")
        if alias_type_ref and not alias_type_ref.startswith("builtins:"):
            collect_nested_types(spec_ir, alias_type_ref, visited)
        return True
    return False


def collect_nested_types(spec_ir: SpecIR, type_ref: str, visited: set[str]) -> None:
    """型参照から再帰的にネストされた型を収集"""
    if not type_ref or type_ref in visited or type_ref.startswith("builtins:"):
        return
    visited.add(type_ref)

    # 型ハンドラーを順番に実行
    handlers = [_handle_pydantic_type, _handle_generic_type, _handle_alias_type]
    for handler in handlers:
        if handler(spec_ir, type_ref, visited):
            return


def determine_dtype_category(spec_ir: SpecIR, type_ref: str) -> tuple[str, str]:
    """型参照からカテゴリと説明を判定

    Returns:
        (category, description)のタプル
    """
    # 型種別とカテゴリのマッピング
    type_mappings: Sequence[tuple[Sequence[Any], str]] = [
        (spec_ir.frames, "dtype_frame"),
        (spec_ir.enums, "dtype_enum"),
        (spec_ir.pydantic_models, "dtype_pydantic"),
        (spec_ir.type_aliases, "dtype_alias"),
        (spec_ir.generics, "dtype_generic"),
    ]

    for type_list, category in type_mappings:
        found = next((t for t in type_list if t.id == type_ref), None)
        if found:
            return category, found.description

    return "dtype", ""

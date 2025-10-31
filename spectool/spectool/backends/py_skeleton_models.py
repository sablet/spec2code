"""Python スケルトン生成 - モデル生成

Enum、Pydanticモデルのスケルトンを生成。
"""

from __future__ import annotations

from spectool.spectool.core.base.ir import EnumSpec, PydanticModelSpec


def _resolve_generic_type(generic_def: dict, imports: set[str] | None = None) -> str:
    """Generic型定義から型アノテーション文字列を生成

    Args:
        generic_def: Generic型定義（container, element_type, key_type, value_typeなど）
        imports: インポート文を蓄積するセット（指定時のみimportを追加）

    Returns:
        型アノテーション文字列（例: "list[str]", "dict[str, float]"）
    """
    container = generic_def.get("container", "list")

    if container == "list":
        element_type = generic_def.get("element_type", {})
        element_str = _resolve_type_from_def(element_type, imports)
        return f"list[{element_str}]"

    if container == "dict":
        key_type = generic_def.get("key_type", {})
        value_type = generic_def.get("value_type", {})
        key_str = _resolve_type_from_def(key_type, imports)
        value_str = _resolve_type_from_def(value_type, imports)
        return f"dict[{key_str}, {value_str}]"

    if container == "set":
        element_type = generic_def.get("element_type", {})
        element_str = _resolve_type_from_def(element_type, imports)
        return f"set[{element_str}]"

    if container == "tuple":
        elements = generic_def.get("elements", [])
        if elements:
            element_strs = [_resolve_type_from_def(elem, imports) for elem in elements]
            return f"tuple[{', '.join(element_strs)}]"
        return "tuple"

    if imports is not None:
        imports.add("from typing import Any")
    return "Any"


def _resolve_type_from_def(type_def: dict, imports: set[str] | None = None) -> str:
    """型定義dictから型文字列を解決

    Args:
        type_def: 型定義（native, datatype_ref, genericなど）
        imports: インポート文を蓄積するセット（指定時のみimportを追加）

    Returns:
        型文字列
    """
    if "native" in type_def:
        native_full = type_def["native"]  # "module:type"形式
        native_type = native_full.split(":")[-1]

        # 必要なimportを追加
        if imports is not None:
            if native_type == "Any":
                imports.add("from typing import Any")
            elif ":" in native_full:
                module = native_full.split(":")[0]
                # builtinsとtypingは特別扱い
                if module not in {"builtins", "typing"}:
                    imports.add(f"from {module} import {native_type}")

        return native_type
    if "datatype_ref" in type_def:
        return type_def["datatype_ref"]
    if "generic" in type_def:
        return _resolve_generic_type(type_def["generic"], imports)
    if imports is not None:
        imports.add("from typing import Any")
    return "Any"


def generate_enum_class(enum: EnumSpec) -> str:
    """Enumクラスを生成

    Args:
        enum: Enum定義

    Returns:
        Enumクラス定義文字列
    """
    lines = []
    if enum.description:
        lines.append(f"# {enum.description}")

    lines.append(f"class {enum.id}(str, Enum):")
    if enum.description:
        lines.append(f'    """{enum.description}"""')

    if enum.members:
        for member in enum.members:
            if member.description:
                lines.append(f"    # {member.description}")
            lines.append(f'    {member.name} = "{member.value}"')
    else:
        lines.append("    pass")

    return "\n".join(lines)


def _resolve_field_type_and_imports(field_type: dict, imports: set[str] | None) -> str:
    """フィールドの型を解決し、必要なインポートを追加する

    Args:
        field_type: 型定義
        imports: インポート文を蓄積するセット（指定時のみimportを追加）

    Returns:
        型文字列
    """
    # 型を解決
    if "native" in field_type:
        native_full = field_type["native"]  # "module:type"形式
        native_type = native_full.split(":")[-1]
        type_str = native_type

        # 必要なimportを追加
        if imports is not None:
            if native_type == "Any":
                imports.add("from typing import Any")
            elif ":" in native_full:
                module = native_full.split(":")[0]
                if module not in {"builtins", "typing"}:
                    imports.add(f"from {module} import {native_type}")
    elif "datatype_ref" in field_type:
        type_str = field_type["datatype_ref"]
    elif "generic" in field_type:
        # Generic型の処理
        type_str = _resolve_generic_type(field_type["generic"], imports)
    else:
        type_str = "Any"
        if imports is not None:
            imports.add("from typing import Any")

    return type_str


def generate_pydantic_model(model: PydanticModelSpec, imports: set[str] | None = None) -> str:
    """Pydanticモデルを生成

    Args:
        model: Pydanticモデル定義
        imports: インポート文を蓄積するセット（指定時のみimportを追加）

    Returns:
        Pydanticモデルクラス定義文字列
    """
    lines = []
    if model.description:
        lines.append(f"# {model.description}")

    lines.append(f"class {model.id}(BaseModel):")
    if model.description:
        lines.append(f'    """{model.description}"""')

    # Check if model needs arbitrary_types_allowed (for DataFrame, Series, etc.)
    needs_arbitrary_types = _check_needs_arbitrary_types(model.fields)
    if needs_arbitrary_types:
        if imports is not None:
            imports.add("from pydantic import ConfigDict")
        lines.append("    model_config = ConfigDict(arbitrary_types_allowed=True)")
        lines.append("")

    if model.fields:
        for field in model.fields:
            field_name = field["name"]
            field_type = field.get("type", {})

            # 型を解決
            type_str = _resolve_field_type_and_imports(field_type, imports)

            # オプショナルフィールドの処理
            required = field.get("required", True)
            if not required:
                type_str = f"{type_str} | None"

            lines.append(f"    {field_name}: {type_str}")
    else:
        lines.append("    pass")

    return "\n".join(lines)


def _check_needs_arbitrary_types(fields: list[dict]) -> bool:
    """フィールドの型が arbitrary_types_allowed を必要とするかチェック

    Args:
        fields: フィールド定義のリスト

    Returns:
        arbitrary_types_allowed が必要な場合 True
    """
    arbitrary_type_modules = {"pandas", "numpy", "polars"}

    for field in fields:
        field_type = field.get("type", {})
        if _type_needs_arbitrary_types(field_type, arbitrary_type_modules):
            return True
    return False


def _check_generic_arbitrary_types(generic_def: dict, arbitrary_type_modules: set[str]) -> bool:
    """Generic型定義が arbitrary_types_allowed を必要とするかチェック（再帰的）

    Args:
        generic_def: Generic型定義
        arbitrary_type_modules: arbitrary_types が必要なモジュール名のセット

    Returns:
        arbitrary_types_allowed が必要な場合 True
    """
    if "element_type" in generic_def and _type_needs_arbitrary_types(
        generic_def["element_type"], arbitrary_type_modules
    ):
        return True
    if "key_type" in generic_def and _type_needs_arbitrary_types(generic_def["key_type"], arbitrary_type_modules):
        return True
    if "value_type" in generic_def and _type_needs_arbitrary_types(generic_def["value_type"], arbitrary_type_modules):
        return True
    if "elements" in generic_def:
        for elem in generic_def["elements"]:
            if _type_needs_arbitrary_types(elem, arbitrary_type_modules):
                return True
    return False


def _type_needs_arbitrary_types(field_type: dict, arbitrary_type_modules: set[str]) -> bool:
    """型定義が arbitrary_types_allowed を必要とするかチェック（再帰的）

    Args:
        field_type: 型定義
        arbitrary_type_modules: arbitrary_types が必要なモジュール名のセット

    Returns:
        arbitrary_types_allowed が必要な場合 True
    """
    # native型のチェック
    if "native" in field_type:
        native_full = field_type["native"]
        if ":" in native_full:
            module = native_full.split(":")[0]
            if module in arbitrary_type_modules:
                return True

    # datatype_refは TypeAlias の可能性があるので、その名前から判定
    # (MultiAssetOHLCVFrame などは既に別の場所で DataFrame に解決されている)
    if "datatype_ref" in field_type:
        ref = field_type["datatype_ref"]
        # DataFrame や Series という名前が含まれている場合
        if "DataFrame" in ref or "Series" in ref or "Frame" in ref:
            return True

    # generic型の再帰的チェック
    if "generic" in field_type:
        return _check_generic_arbitrary_types(field_type["generic"], arbitrary_type_modules)

    return False

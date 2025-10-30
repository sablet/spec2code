"""Python スケルトン生成 - モデル生成

Enum、Pydanticモデルのスケルトンを生成。
"""

from __future__ import annotations

from spectool.spectool.core.base.ir import EnumSpec, PydanticModelSpec


def _resolve_generic_type(generic_def: dict) -> str:
    """Generic型定義から型アノテーション文字列を生成

    Args:
        generic_def: Generic型定義（container, element_type, key_type, value_typeなど）

    Returns:
        型アノテーション文字列（例: "list[str]", "dict[str, float]"）
    """
    container = generic_def.get("container", "list")

    if container == "list":
        element_type = generic_def.get("element_type", {})
        element_str = _resolve_type_from_def(element_type)
        return f"list[{element_str}]"

    if container == "dict":
        key_type = generic_def.get("key_type", {})
        value_type = generic_def.get("value_type", {})
        key_str = _resolve_type_from_def(key_type)
        value_str = _resolve_type_from_def(value_type)
        return f"dict[{key_str}, {value_str}]"

    if container == "set":
        element_type = generic_def.get("element_type", {})
        element_str = _resolve_type_from_def(element_type)
        return f"set[{element_str}]"

    if container == "tuple":
        elements = generic_def.get("elements", [])
        if elements:
            element_strs = [_resolve_type_from_def(elem) for elem in elements]
            return f"tuple[{', '.join(element_strs)}]"
        return "tuple"

    return "Any"


def _resolve_type_from_def(type_def: dict) -> str:
    """型定義dictから型文字列を解決

    Args:
        type_def: 型定義（native, datatype_ref, genericなど）

    Returns:
        型文字列
    """
    if "native" in type_def:
        return type_def["native"].split(":")[-1]
    if "datatype_ref" in type_def:
        return type_def["datatype_ref"]
    if "generic" in type_def:
        return _resolve_generic_type(type_def["generic"])
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


def generate_pydantic_model(model: PydanticModelSpec) -> str:
    """Pydanticモデルを生成

    Args:
        model: Pydanticモデル定義

    Returns:
        Pydanticモデルクラス定義文字列
    """
    lines = []
    if model.description:
        lines.append(f"# {model.description}")

    lines.append(f"class {model.id}(BaseModel):")
    if model.description:
        lines.append(f'    """{model.description}"""')

    if model.fields:
        for field in model.fields:
            field_name = field["name"]
            field_type = field.get("type", {})

            # 型を解決
            if "native" in field_type:
                native_type = field_type["native"].split(":")[-1]
                type_str = native_type
            elif "datatype_ref" in field_type:
                type_str = field_type["datatype_ref"]
            elif "generic" in field_type:
                # Generic型の処理
                type_str = _resolve_generic_type(field_type["generic"])
            else:
                type_str = "Any"

            required = field.get("required", True)
            if not required:
                type_str = f"{type_str} | None"

            lines.append(f"    {field_name}: {type_str}")
    else:
        lines.append("    pass")

    return "\n".join(lines)

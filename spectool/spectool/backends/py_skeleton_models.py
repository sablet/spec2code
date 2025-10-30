"""Python スケルトン生成 - モデル生成

Enum、Pydanticモデルのスケルトンを生成。
"""

from __future__ import annotations

from spectool.spectool.core.base.ir import EnumSpec, PydanticModelSpec


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
            else:
                type_str = "Any"

            required = field.get("required", True)
            if not required:
                type_str = f"{type_str} | None"

            lines.append(f"    {field_name}: {type_str}")
    else:
        lines.append("    pass")

    return "\n".join(lines)

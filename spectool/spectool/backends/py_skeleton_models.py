"""Python スケルトン生成 - モデル生成

Enum、Pydanticモデルのスケルトンを生成。
"""

from __future__ import annotations

from spectool.spectool.core.base.ir import EnumSpec, PydanticModelSpec, SpecIR


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

    Note:
        datatype_refがTypeAlias/Frameの場合、循環インポートを避けるため
        models.py内ではIDをそのまま使用（他のPydanticモデルやEnumを参照）。
        TypeAlias/Frameは関数シグネチャで使われるべきで、Pydanticモデル内では使用しない。
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
        # datatype_refはPydanticモデルやEnumのIDをそのまま返す
        # TypeAlias/Frameの場合も、models.py内では他のモデルと同様に扱う
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
        # datattype_refはそのままIDを返す（Pydanticモデル/Enum参照）
        # 注: TypeAlias/Frameの展開はgenerate_pydantic_model()側で行う
        type_str = field_type["datatype_ref"]
    elif "generic" in field_type:
        # Generic型の処理
        type_str = _resolve_generic_type(field_type["generic"], imports)
    else:
        type_str = "Any"
        if imports is not None:
            imports.add("from typing import Any")

    return type_str


def _add_pandas_import(type_name: str, imports: set[str] | None) -> None:
    """pandasの型に応じたimportを追加

    Args:
        type_name: 型名（DataFrame/Series）
        imports: インポート文を蓄積するセット
    """
    if imports is None:
        return
    imports.add(f"from pandas import {type_name}")


def _resolve_type_alias_target(target: str, imports: set[str] | None) -> str | None:
    """TypeAliasのtargetを解決

    Args:
        target: type_defのtarget（例: "pandas:DataFrame"）
        imports: インポート文を蓄積するセット

    Returns:
        解決された型文字列、解決できない場合はNone
    """
    if target == "pandas:DataFrame":
        _add_pandas_import("DataFrame", imports)
        return "DataFrame"
    if target == "pandas:Series":
        _add_pandas_import("Series", imports)
        return "Series"
    return None


def _resolve_type_alias_or_frame(ref_id: str, ir: SpecIR | None, imports: set[str] | None) -> str | None:
    """TypeAliasまたはFrameを解決してDataFrame/Series型文字列を返す

    Args:
        ref_id: datatype_refのID
        ir: SpecIR（TypeAlias/Frame解決用）
        imports: インポート文を蓄積するセット

    Returns:
        解決された型文字列（DataFrame/Series）、解決できない場合はNone
    """
    if not ir:
        return None

    # TypeAliasチェック
    for type_alias in ir.type_aliases:
        if type_alias.id != ref_id:
            continue
        type_def = type_alias.type_def
        if type_def.get("type") != "simple":
            return None
        target = type_def.get("target", "")
        return _resolve_type_alias_target(target, imports)

    # Frameチェック
    for frame in ir.frames:
        if frame.id == ref_id:
            _add_pandas_import("DataFrame", imports)
            return "DataFrame"

    return None


def _generate_field_type(field: dict, ir: SpecIR | None, imports: set[str] | None) -> str:
    """フィールドの型文字列を生成

    Args:
        field: フィールド定義
        ir: SpecIR（TypeAlias/Frame解決用）
        imports: インポート文を蓄積するセット

    Returns:
        型文字列（オプショナル処理を含む）
    """
    field_type = field.get("type", {})
    type_str = _resolve_field_type_and_imports(field_type, imports)

    # IRがある場合、TypeAlias/Frameを展開
    if "datatype_ref" in field_type:
        resolved = _resolve_type_alias_or_frame(field_type["datatype_ref"], ir, imports)
        if resolved:
            type_str = resolved

    # オプショナルフィールドの処理
    if not field.get("required", True):
        type_str = f"{type_str} | None"

    return type_str


def generate_pydantic_model(model: PydanticModelSpec, imports: set[str] | None = None, ir: SpecIR | None = None) -> str:
    """Pydanticモデルを生成

    Args:
        model: Pydanticモデル定義
        imports: インポート文を蓄積するセット（指定時のみimportを追加）
        ir: SpecIR（TypeAlias/Frame解決用、Noneの場合は従来の動作）

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
            field_type_str = _generate_field_type(field, ir, imports)
            lines.append(f"    {field['name']}: {field_type_str}")
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

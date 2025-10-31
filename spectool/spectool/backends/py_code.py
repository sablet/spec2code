"""TypeAlias生成バックエンド

IRからDataFrame/Enum/PydanticモデルのTypeAlias（Annotatedメタ付き）を生成。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from spectool.spectool.core.base.ir import (
    EnumSpec,
    FrameSpec,
    GenericSpec,
    PydanticModelSpec,
    SpecIR,
    TypeAliasSpec,
)
from spectool.spectool.backends.py_skeleton_codegen import _resolve_type_ref


def render_imports(imports: set[str]) -> str:
    """インポート文を整形して返す"""
    if not imports:
        return ""
    return "\n".join(sorted(imports))


def build_file_content(imports: set[str], sections: list[str]) -> str:
    """ファイルコンテンツを構築

    Args:
        imports: インポート文のセット
        sections: コードセクションのリスト

    Returns:
        完成したファイルコンテンツ
    """
    header = [
        '"""生成されたTypeAlias（AnnotatedメタデータでExampleSpec/CheckedSpecを付与）',
        "",
        "このファイルは spectool が spec.yaml から自動生成します。",
        "新アーキテクチャでは、全ての型にAnnotatedメタ型でメタデータを付与します。",
        '"""',
        "",
    ]
    return "\n".join(header) + render_imports(imports) + "\n\n" + "\n".join(sections)


def _build_pydantic_row_ref(frame: FrameSpec) -> str | None:
    """PydanticRowRefメタデータを生成"""
    if not frame.row_model:
        return None
    # row_modelは "module.path:ClassName" 形式
    return f"PydanticRowRef(model={frame.row_model.split(':')[-1]})"


def _build_generator_spec_from_frame(frame: FrameSpec) -> str | None:
    """GeneratorSpecメタデータを生成（frame.generator_factoryから）"""
    if not frame.generator_factory:
        return None
    return f'GeneratorSpec(factory="{frame.generator_factory}")'


def _build_generator_spec_from_ids(generator_ids: list[str]) -> str | None:
    """GeneratorSpecメタデータを生成（generator IDリストから）"""
    if not generator_ids:
        return None
    generators_str = ", ".join(f'"{gid}"' for gid in generator_ids)
    return f"GeneratorSpec(generators=[{generators_str}])"


def _build_checked_spec(check_functions: list[str]) -> str | None:
    """CheckedSpecメタデータを生成"""
    if not check_functions:
        return None
    funcs_str = ", ".join(f'"{f}"' for f in check_functions)
    return f"CheckedSpec(functions=[{funcs_str}])"


def _build_example_spec(examples: list[Any]) -> str | None:
    """ExampleSpecメタデータを生成"""
    if not examples:
        return None
    # 例示データを適切にフォーマット
    examples_str = ", ".join(repr(ex) for ex in examples)
    return f"ExampleSpec(examples=[{examples_str}])"


def _build_dataframe_meta_parts(
    frame: FrameSpec, app_name: str, imports: set[str], generator_ids: list[str] | None = None
) -> list[str]:
    """DataFrameのメタデータパーツを構築

    Args:
        frame: DataFrame定義
        app_name: アプリ名
        imports: インポート文のセット
        generator_ids: Generator IDリスト（指定時のみGeneratorSpecを追加）

    Returns:
        メタデータパーツのリスト
    """
    meta_parts = []

    # PydanticRowRef（存在する場合）
    if frame.row_model:
        row_ref = _build_pydantic_row_ref(frame)
        if row_ref:
            meta_parts.append(f"    {row_ref},")
            # row_modelからクラス名を抽出してインポート
            model_class = frame.row_model.split(":")[-1]
            imports.add(f"from apps.{app_name}.models.models import {model_class}")

    # GeneratorSpec（generatorsから）を追加
    if generator_ids:
        gen_spec_from_generators = _build_generator_spec_from_ids(generator_ids)
        if gen_spec_from_generators:
            meta_parts.append(f"    {gen_spec_from_generators},")

    # 従来のGeneratorSpec（frame.generator_factory）も維持
    gen_spec_legacy = _build_generator_spec_from_frame(frame)
    if gen_spec_legacy:
        meta_parts.append(f"    {gen_spec_legacy},")

    # CheckedSpec（存在する場合）
    checked_spec = _build_checked_spec(frame.check_functions)
    if checked_spec:
        meta_parts.append(f"    {checked_spec},")

    return meta_parts


def _build_dataframe_type_alias_lines(frame: FrameSpec, meta_parts: list[str], imports: set[str]) -> list[str]:
    """DataFrame TypeAliasのコード行を構築

    Args:
        frame: DataFrame定義
        meta_parts: メタデータパーツのリスト
        imports: インポート文のセット

    Returns:
        TypeAliasコード行のリスト
    """
    lines = []
    if frame.description:
        lines.append(f"# {frame.description}")

    if meta_parts:
        imports.add("from typing import Annotated")
        imports.add("import pandas as pd")
        imports.add("from spectool.spectool.core.base.meta_types import PydanticRowRef, GeneratorSpec, CheckedSpec")

        lines.append(f"{frame.id}: TypeAlias = Annotated[")
        lines.append("    pd.DataFrame,")
        lines.extend(meta_parts)
        lines.append("]")
    else:
        imports.add("import pandas as pd")
        lines.append(f"{frame.id}: TypeAlias = pd.DataFrame")

    return lines


def generate_dataframe_type_alias(frame: FrameSpec, imports: set[str], app_name: str) -> str:
    """DataFrame TypeAliasコードブロックを生成"""
    meta_parts = _build_dataframe_meta_parts(frame, app_name, imports)
    lines = _build_dataframe_type_alias_lines(frame, meta_parts, imports)
    return "\n".join(lines)


def generate_dataframe_type_alias_with_generators(
    frame: FrameSpec, imports: set[str], app_name: str, generator_ids: list[str]
) -> str:
    """DataFrame TypeAliasコードブロックを生成（GeneratorSpec付き）"""
    meta_parts = _build_dataframe_meta_parts(frame, app_name, imports, generator_ids)
    lines = _build_dataframe_type_alias_lines(frame, meta_parts, imports)
    return "\n".join(lines)


def _build_common_meta_parts(examples: list[Any], check_functions: list[str]) -> list[str]:
    """ExampleSpecとCheckedSpecのメタデータパーツを構築

    Args:
        examples: 例示データのリスト
        check_functions: チェック関数のリスト

    Returns:
        メタデータパーツのリスト
    """
    meta_parts = []

    # ExampleSpec（存在する場合）
    example_spec = _build_example_spec(examples)
    if example_spec:
        meta_parts.append(f"    {example_spec},")

    # CheckedSpec（存在する場合）
    checked_spec = _build_checked_spec(check_functions)
    if checked_spec:
        meta_parts.append(f"    {checked_spec},")

    return meta_parts


def generate_enum_type_alias(enum: EnumSpec, imports: set[str], app_name: str) -> str:
    """Enum TypeAliasコードブロックを生成"""
    meta_parts = _build_common_meta_parts(enum.examples, enum.check_functions)

    # Enumクラスをインポートするためのパスをビルド
    enum_class_name = enum.id
    imports.add(f"from apps.{app_name}.models.enums import {enum_class_name}")

    # TypeAlias構築
    lines = []
    if enum.description:
        lines.append(f"# {enum.description}")

    if meta_parts:
        imports.add("from typing import Annotated")
        imports.add("from spectool.spectool.core.base.meta_types import ExampleSpec, CheckedSpec")

        lines.append(f"{enum.id}Type: TypeAlias = Annotated[")
        lines.append(f"    {enum_class_name},")
        lines.extend(meta_parts)
        lines.append("]")
    else:
        lines.append(f"{enum.id}Type: TypeAlias = {enum_class_name}")

    return "\n".join(lines)


def generate_enum_type_alias_with_generators(
    enum: EnumSpec, imports: set[str], app_name: str, generator_ids: list[str]
) -> str:
    """Enum TypeAliasコードブロックを生成（GeneratorSpec付き）"""
    meta_parts = _build_common_meta_parts(enum.examples, enum.check_functions)

    # GeneratorSpecを追加
    gen_spec = _build_generator_spec_from_ids(generator_ids)
    if gen_spec:
        meta_parts.append(f"    {gen_spec},")

    # Enumクラスをインポートするためのパスをビルド
    enum_class_name = enum.id
    imports.add(f"from apps.{app_name}.models.enums import {enum_class_name}")

    # TypeAlias構築
    lines = []
    if enum.description:
        lines.append(f"# {enum.description}")

    if meta_parts:
        imports.add("from typing import Annotated")
        imports.add("from spectool.spectool.core.base.meta_types import ExampleSpec, CheckedSpec, GeneratorSpec")

        lines.append(f"{enum.id}Type: TypeAlias = Annotated[")
        lines.append(f"    {enum_class_name},")
        lines.extend(meta_parts)
        lines.append("]")
    else:
        lines.append(f"{enum.id}Type: TypeAlias = {enum_class_name}")

    return "\n".join(lines)


def generate_pydantic_type_alias(model: PydanticModelSpec, imports: set[str], app_name: str) -> str:
    """Pydanticモデル TypeAliasコードブロックを生成"""
    meta_parts = _build_common_meta_parts(model.examples, model.check_functions)

    # Pydanticモデルをインポート
    model_class_name = model.id
    imports.add(f"from apps.{app_name}.models.models import {model_class_name}")

    # TypeAlias構築
    lines = []
    if model.description:
        lines.append(f"# {model.description}")

    if meta_parts:
        imports.add("from typing import Annotated")
        imports.add("from spectool.spectool.core.base.meta_types import ExampleSpec, CheckedSpec")

        lines.append(f"{model.id}Type: TypeAlias = Annotated[")
        lines.append(f"    {model_class_name},")
        lines.extend(meta_parts)
        lines.append("]")
    else:
        lines.append(f"{model.id}Type: TypeAlias = {model_class_name}")

    return "\n".join(lines)


def generate_pydantic_type_alias_with_generators(
    model: PydanticModelSpec, imports: set[str], app_name: str, generator_ids: list[str]
) -> str:
    """Pydanticモデル TypeAliasコードブロックを生成（GeneratorSpec付き）"""
    meta_parts = _build_common_meta_parts(model.examples, model.check_functions)

    # GeneratorSpecを追加
    gen_spec = _build_generator_spec_from_ids(generator_ids)
    if gen_spec:
        meta_parts.append(f"    {gen_spec},")

    # Pydanticモデルをインポート
    model_class_name = model.id
    imports.add(f"from apps.{app_name}.models.models import {model_class_name}")

    # TypeAlias構築
    lines = []
    if model.description:
        lines.append(f"# {model.description}")

    if meta_parts:
        imports.add("from typing import Annotated")
        imports.add("from spectool.spectool.core.base.meta_types import ExampleSpec, CheckedSpec, GeneratorSpec")

        lines.append(f"{model.id}Type: TypeAlias = Annotated[")
        lines.append(f"    {model_class_name},")
        lines.extend(meta_parts)
        lines.append("]")
    else:
        lines.append(f"{model.id}Type: TypeAlias = {model_class_name}")

    return "\n".join(lines)


def generate_type_alias_code(type_alias: TypeAliasSpec, imports: set[str], app_name: str, ir: SpecIR) -> str:
    """TypeAlias（simple/tuple）コードブロックを生成

    Args:
        type_alias: TypeAlias定義
        imports: インポート文のセット
        app_name: アプリケーション名
        ir: SpecIR（型参照解決用）

    Returns:
        生成されたTypeAliasコード
    """
    type_def = type_alias.type_def
    alias_type = type_def.get("type", "simple")

    # メタデータパーツを構築
    meta_parts = _build_common_meta_parts(type_alias.examples, type_alias.check_functions)

    # TypeAlias構築
    lines = []
    if type_alias.description:
        lines.append(f"# {type_alias.description}")

    # ターゲット型を解決
    if alias_type == "simple":
        target = type_def.get("target", "")
        if "pandas:" in target:
            imports.add("import pandas as pd")
            target_type = "pd.DataFrame"
        elif ":" in target:
            target_type = target.split(":")[-1]
        else:
            target_type = target
    elif alias_type == "tuple":
        # tuple要素を解決（types.py内では循環インポートを避けるため、importsにNoneを渡す）
        elements = type_def.get("elements", [])
        element_types = []
        for elem in elements:
            if "datatype_ref" in elem:
                # types.py内での参照なので、インポートなしで型名のみ取得
                elem_type = _resolve_type_ref(elem["datatype_ref"], ir, None)
                element_types.append(elem_type)
            elif "native" in elem:
                elem_type = process_native_type(elem["native"])
                element_types.append(elem_type)

        imports.add("from typing import Tuple")
        target_type = f"tuple[{', '.join(element_types)}]"
    else:
        # Unsupported type
        target_type = "Any"
        imports.add("from typing import Any")

    if meta_parts:
        imports.add("from typing import Annotated")
        imports.add("from spectool.spectool.core.base.meta_types import ExampleSpec, CheckedSpec")

        lines.append(f"{type_alias.id}: TypeAlias = Annotated[")
        lines.append(f"    {target_type},")
        lines.extend(meta_parts)
        lines.append("]")
    else:
        lines.append(f"{type_alias.id}: TypeAlias = {target_type}")

    return "\n".join(lines)


def generate_type_alias_code_with_generators(
    type_alias: TypeAliasSpec, imports: set[str], app_name: str, ir: SpecIR, generator_ids: list[str]
) -> str:
    """TypeAlias（simple/tuple）コードブロックを生成（GeneratorSpec付き）

    Args:
        type_alias: TypeAlias定義
        imports: インポート文のセット
        app_name: アプリケーション名
        ir: SpecIR（型参照解決用）
        generator_ids: Generator IDリスト

    Returns:
        生成されたTypeAliasコード
    """
    type_def = type_alias.type_def
    alias_type = type_def.get("type", "simple")

    # メタデータパーツを構築
    meta_parts = _build_common_meta_parts(type_alias.examples, type_alias.check_functions)

    # GeneratorSpecを追加
    gen_spec = _build_generator_spec_from_ids(generator_ids)
    if gen_spec:
        meta_parts.append(f"    {gen_spec},")

    # TypeAlias構築
    lines = []
    if type_alias.description:
        lines.append(f"# {type_alias.description}")

    # ターゲット型を解決
    if alias_type == "simple":
        target = type_def.get("target", "")
        if "pandas:" in target:
            imports.add("import pandas as pd")
            target_type = "pd.DataFrame"
        elif ":" in target:
            target_type = target.split(":")[-1]
        else:
            target_type = target
    elif alias_type == "tuple":
        # tuple要素を解決（types.py内では循環インポートを避けるため、importsにNoneを渡す）
        elements = type_def.get("elements", [])
        element_types = []
        for elem in elements:
            if "datatype_ref" in elem:
                # types.py内での参照なので、インポートなしで型名のみ取得
                elem_type = _resolve_type_ref(elem["datatype_ref"], ir, None)
                element_types.append(elem_type)
            elif "native" in elem:
                elem_type = process_native_type(elem["native"])
                element_types.append(elem_type)

        imports.add("from typing import Tuple")
        target_type = f"tuple[{', '.join(element_types)}]"
    else:
        # Unsupported type
        target_type = "Any"
        imports.add("from typing import Any")

    if meta_parts:
        imports.add("from typing import Annotated")
        imports.add("from spectool.spectool.core.base.meta_types import ExampleSpec, CheckedSpec, GeneratorSpec")

        lines.append(f"{type_alias.id}: TypeAlias = Annotated[")
        lines.append(f"    {target_type},")
        lines.extend(meta_parts)
        lines.append("]")
    else:
        lines.append(f"{type_alias.id}: TypeAlias = {target_type}")

    return "\n".join(lines)


def generate_generic_code(generic: GenericSpec, imports: set[str], app_name: str, ir: SpecIR) -> str:
    """Generic（list/dict/set/tuple）コードブロックを生成

    Args:
        generic: Generic定義
        imports: インポート文のセット
        app_name: アプリケーション名
        ir: SpecIR（型参照解決用）

    Returns:
        生成されたGenericコード
    """
    # メタデータパーツを構築
    meta_parts = _build_common_meta_parts(generic.examples, generic.check_functions)

    # TypeAlias構築
    lines = []
    if generic.description:
        lines.append(f"# {generic.description}")

    # Helper function to process native types and add necessary imports
    def process_native_type(native_str: str) -> str:
        if ":" in native_str:
            module, typename = native_str.split(":", 1)
            if module == "typing":
                imports.add(f"from typing import {typename}")
            return typename
        return native_str

    # Generic型を構築
    container = generic.container

    if container == "list":
        if generic.element_type:
            if "datatype_ref" in generic.element_type:
                # types.py内での参照なので、インポートなしで型名のみ取得
                elem_type = _resolve_type_ref(generic.element_type["datatype_ref"], ir, None)
            elif "native" in generic.element_type:
                elem_type = process_native_type(generic.element_type["native"])
            else:
                elem_type = "Any"
                imports.add("from typing import Any")
        else:
            elem_type = "Any"
            imports.add("from typing import Any")
        target_type = f"list[{elem_type}]"

    elif container == "dict":
        if generic.key_type:
            if "datatype_ref" in generic.key_type:
                # types.py内での参照なので、インポートなしで型名のみ取得
                key_type = _resolve_type_ref(generic.key_type["datatype_ref"], ir, None)
            elif "native" in generic.key_type:
                key_type = process_native_type(generic.key_type["native"])
            else:
                key_type = "Any"
                imports.add("from typing import Any")
        else:
            key_type = "Any"
            imports.add("from typing import Any")

        if generic.value_type:
            if "datatype_ref" in generic.value_type:
                # types.py内での参照なので、インポートなしで型名のみ取得
                value_type = _resolve_type_ref(generic.value_type["datatype_ref"], ir, None)
            elif "native" in generic.value_type:
                value_type = process_native_type(generic.value_type["native"])
            else:
                value_type = "Any"
                imports.add("from typing import Any")
        else:
            value_type = "Any"
            imports.add("from typing import Any")

        target_type = f"dict[{key_type}, {value_type}]"

    elif container == "set":
        if generic.element_type:
            if "datatype_ref" in generic.element_type:
                # types.py内での参照なので、インポートなしで型名のみ取得
                elem_type = _resolve_type_ref(generic.element_type["datatype_ref"], ir, None)
            elif "native" in generic.element_type:
                elem_type = process_native_type(generic.element_type["native"])
            else:
                elem_type = "Any"
                imports.add("from typing import Any")
        else:
            elem_type = "Any"
            imports.add("from typing import Any")
        target_type = f"set[{elem_type}]"

    elif container == "tuple":
        element_types = []
        for elem in generic.elements:
            if "datatype_ref" in elem:
                # types.py内での参照なので、インポートなしで型名のみ取得
                elem_type = _resolve_type_ref(elem["datatype_ref"], ir, None)
                element_types.append(elem_type)
            elif "native" in elem:
                elem_type = process_native_type(elem["native"])
                element_types.append(elem_type)
        target_type = f"tuple[{', '.join(element_types)}]"

    else:
        # Unsupported container
        target_type = "Any"
        imports.add("from typing import Any")

    if meta_parts:
        imports.add("from typing import Annotated")
        imports.add("from spectool.spectool.core.base.meta_types import ExampleSpec, CheckedSpec")

        lines.append(f"{generic.id}: TypeAlias = Annotated[")
        lines.append(f"    {target_type},")
        lines.extend(meta_parts)
        lines.append("]")
    else:
        lines.append(f"{generic.id}: TypeAlias = {target_type}")

    return "\n".join(lines)


def generate_generic_code_with_generators(
    generic: GenericSpec, imports: set[str], app_name: str, ir: SpecIR, generator_ids: list[str]
) -> str:
    """Generic（list/dict/set/tuple）コードブロックを生成（GeneratorSpec付き）

    Args:
        generic: Generic定義
        imports: インポート文のセット
        app_name: アプリケーション名
        ir: SpecIR（型参照解決用）
        generator_ids: Generator IDリスト

    Returns:
        生成されたGenericコード
    """
    # メタデータパーツを構築
    meta_parts = _build_common_meta_parts(generic.examples, generic.check_functions)

    # GeneratorSpecを追加
    gen_spec = _build_generator_spec_from_ids(generator_ids)
    if gen_spec:
        meta_parts.append(f"    {gen_spec},")

    # TypeAlias構築
    lines = []
    if generic.description:
        lines.append(f"# {generic.description}")

    # Helper function to process native types and add necessary imports
    def process_native_type(native_str: str) -> str:
        if ":" in native_str:
            module, typename = native_str.split(":", 1)
            if module == "typing":
                imports.add(f"from typing import {typename}")
            return typename
        return native_str

    # Generic型を構築
    container = generic.container

    if container == "list":
        if generic.element_type:
            if "datatype_ref" in generic.element_type:
                # types.py内での参照なので、インポートなしで型名のみ取得
                elem_type = _resolve_type_ref(generic.element_type["datatype_ref"], ir, None)
            elif "native" in generic.element_type:
                elem_type = process_native_type(generic.element_type["native"])
            else:
                elem_type = "Any"
                imports.add("from typing import Any")
        else:
            elem_type = "Any"
            imports.add("from typing import Any")
        target_type = f"list[{elem_type}]"

    elif container == "dict":
        if generic.key_type:
            if "datatype_ref" in generic.key_type:
                # types.py内での参照なので、インポートなしで型名のみ取得
                key_type = _resolve_type_ref(generic.key_type["datatype_ref"], ir, None)
            elif "native" in generic.key_type:
                key_type = process_native_type(generic.key_type["native"])
            else:
                key_type = "Any"
                imports.add("from typing import Any")
        else:
            key_type = "Any"
            imports.add("from typing import Any")

        if generic.value_type:
            if "datatype_ref" in generic.value_type:
                # types.py内での参照なので、インポートなしで型名のみ取得
                value_type = _resolve_type_ref(generic.value_type["datatype_ref"], ir, None)
            elif "native" in generic.value_type:
                value_type = process_native_type(generic.value_type["native"])
            else:
                value_type = "Any"
                imports.add("from typing import Any")
        else:
            value_type = "Any"
            imports.add("from typing import Any")

        target_type = f"dict[{key_type}, {value_type}]"

    elif container == "set":
        if generic.element_type:
            if "datatype_ref" in generic.element_type:
                # types.py内での参照なので、インポートなしで型名のみ取得
                elem_type = _resolve_type_ref(generic.element_type["datatype_ref"], ir, None)
            elif "native" in generic.element_type:
                elem_type = process_native_type(generic.element_type["native"])
            else:
                elem_type = "Any"
                imports.add("from typing import Any")
        else:
            elem_type = "Any"
            imports.add("from typing import Any")
        target_type = f"set[{elem_type}]"

    elif container == "tuple":
        element_types = []
        for elem in generic.elements:
            if "datatype_ref" in elem:
                # types.py内での参照なので、インポートなしで型名のみ取得
                elem_type = _resolve_type_ref(elem["datatype_ref"], ir, None)
                element_types.append(elem_type)
            elif "native" in elem:
                elem_type = process_native_type(elem["native"])
                element_types.append(elem_type)
        target_type = f"tuple[{', '.join(element_types)}]"

    else:
        # Unsupported container
        target_type = "Any"
        imports.add("from typing import Any")

    if meta_parts:
        imports.add("from typing import Annotated")
        imports.add("from spectool.spectool.core.base.meta_types import ExampleSpec, CheckedSpec, GeneratorSpec")

        lines.append(f"{generic.id}: TypeAlias = Annotated[")
        lines.append(f"    {target_type},")
        lines.extend(meta_parts)
        lines.append("]")
    else:
        lines.append(f"{generic.id}: TypeAlias = {target_type}")

    return "\n".join(lines)


def _build_generator_refs_map(ir: SpecIR) -> dict[str, list[str]]:
    """generatorsのreturn_type_refからDatatype IDへのマップを構築

    Args:
        ir: 統合IR

    Returns:
        {datatype_id: [generator_id, ...]} のマップ
    """
    generator_map: dict[str, list[str]] = {}
    for gen in ir.generators:
        if gen.return_type_ref:
            if gen.return_type_ref not in generator_map:
                generator_map[gen.return_type_ref] = []
            generator_map[gen.return_type_ref].append(gen.id)
    return generator_map


def _generate_type_alias_section(
    items: list[Any],
    header: str,
    generator_map: dict[str, list[str]],
    imports: set[str],
    app_name: str,
    gen_func_with_generators: Callable[[Any, set[str], str, list[str]], str],
    gen_func_without_generators: Callable[[Any, set[str], str], str],
) -> list[str]:
    """型エイリアスセクションを生成する共通処理

    Args:
        items: 処理対象のアイテムリスト
        header: セクションヘッダー
        generator_map: Datatype IDからgenerator IDsへのマップ
        imports: インポート文を蓄積するセット
        app_name: アプリケーション名
        gen_func_with_generators: Generatorありの生成関数
        gen_func_without_generators: Generatorなしの生成関数

    Returns:
        生成されたセクションの文字列リスト
    """
    section: list[str] = [header]
    for item in items:
        if item.id in generator_map:
            if hasattr(item, "check_functions"):
                item.check_functions = item.check_functions or []
            alias = gen_func_with_generators(item, imports, app_name, generator_map[item.id])
        else:
            alias = gen_func_without_generators(item, imports, app_name)
        section.append(alias)
        section.append("")
    return section


def generate_all_type_aliases(ir: SpecIR, output_path: Path) -> None:
    """全てのTypeAlias（DataFrame/Enum/Pydantic）を1ファイルに統合生成

    Args:
        ir: 統合IR
        output_path: 出力ファイルパス
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    app_name = ir.meta.name.replace("-", "_") if ir.meta else "app"
    generator_map = _build_generator_refs_map(ir)
    imports: set[str] = {"from typing import TypeAlias"}
    sections: list[str] = []

    # Pydanticモデル TypeAliases
    if ir.pydantic_models:
        sections.extend(
            _generate_type_alias_section(
                ir.pydantic_models,
                "# === Pydantic Model TypeAliases ===\n",
                generator_map,
                imports,
                app_name,
                generate_pydantic_type_alias_with_generators,
                generate_pydantic_type_alias,
            )
        )

    # Enum TypeAliases
    if ir.enums:
        sections.extend(
            _generate_type_alias_section(
                ir.enums,
                "# === Enum TypeAliases ===\n",
                generator_map,
                imports,
                app_name,
                generate_enum_type_alias_with_generators,
                generate_enum_type_alias,
            )
        )

    # DataFrame TypeAliases
    if ir.frames:
        sections.extend(
            _generate_type_alias_section(
                ir.frames,
                "# === DataFrame TypeAliases ===\n",
                generator_map,
                imports,
                app_name,
                generate_dataframe_type_alias_with_generators,
                generate_dataframe_type_alias,
            )
        )

    # TypeAlias (simple/tuple) TypeAliases
    if ir.type_aliases:
        section = ["# === Custom TypeAliases ===\n"]
        for type_alias in ir.type_aliases:
            if type_alias.id in generator_map:
                # Ensure check_functions is not None
                if not type_alias.check_functions:
                    type_alias.check_functions = []

                # ラッパー関数でirを渡す
                def gen_with_gen(ta, imp, an, gids):
                    return generate_type_alias_code_with_generators(ta, imp, an, ir, gids)

                alias = gen_with_gen(type_alias, imports, app_name, generator_map[type_alias.id])
            else:
                alias = generate_type_alias_code(type_alias, imports, app_name, ir)
            section.append(alias)
            section.append("")
        sections.extend(section)

    # Generic (list/dict/set/tuple) TypeAliases
    if ir.generics:
        section = ["# === Generic TypeAliases ===\n"]
        for generic in ir.generics:
            if generic.id in generator_map:
                # Ensure check_functions is not None
                if not generic.check_functions:
                    generic.check_functions = []

                # ラッパー関数でirを渡す
                def gen_with_gen(g, imp, an, gids):
                    return generate_generic_code_with_generators(g, imp, an, ir, gids)

                alias = gen_with_gen(generic, imports, app_name, generator_map[generic.id])
            else:
                alias = generate_generic_code(generic, imports, app_name, ir)
            section.append(alias)
            section.append("")
        sections.extend(section)

    if not sections:
        print("  ⏭️  Skip (no type aliases to generate)")
        return

    content = build_file_content(imports, sections)
    output_path.write_text(content)
    print(f"  ✅ Generated: {output_path}")

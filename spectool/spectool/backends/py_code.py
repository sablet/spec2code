"""TypeAlias生成バックエンド

IRからDataFrame/Enum/PydanticモデルのTypeAlias（Annotatedメタ付き）を生成。
"""

from __future__ import annotations

from pathlib import Path

from spectool.spectool.core.base.ir import (
    EnumSpec,
    FrameSpec,
    GenericSpec,
    PydanticModelSpec,
    SpecIR,
    TypeAliasSpec,
)
from spectool.spectool.backends.py_code_base import (
    _build_common_meta_parts,
    _build_dataframe_meta_parts,
    _build_dataframe_type_alias_lines,
    _build_generic_target_type,
    _build_generator_spec_from_ids,
    _resolve_target_type,
    build_file_content,
    build_generator_refs_map,
    generate_type_alias_section,
)


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
    # メタデータパーツを構築
    meta_parts = _build_common_meta_parts(type_alias.examples, type_alias.check_functions)

    # TypeAlias構築
    lines = []
    if type_alias.description:
        lines.append(f"# {type_alias.description}")

    # ターゲット型を解決
    target_type = _resolve_target_type(type_alias.type_def, imports, ir)

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
    target_type = _resolve_target_type(type_alias.type_def, imports, ir)

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

    # Generic型を構築
    target_type = _build_generic_target_type(generic, imports, ir)

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

    # Generic型を構築
    target_type = _build_generic_target_type(generic, imports, ir)

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


def _process_type_aliases(
    type_aliases: list[TypeAliasSpec],
    section: list[str],
    generator_map: dict[str, list[str]],
    imports: set[str],
    app_name: str,
    ir: SpecIR,
) -> None:
    """TypeAliasの処理"""
    for type_alias in type_aliases:
        if type_alias.id in generator_map:
            if not type_alias.check_functions:
                type_alias.check_functions = []
            alias = generate_type_alias_code_with_generators(
                type_alias, imports, app_name, ir, generator_map[type_alias.id]
            )
        else:
            alias = generate_type_alias_code(type_alias, imports, app_name, ir)
        section.append(alias)
        section.append("")


def _process_generics(
    generics: list[GenericSpec],
    section: list[str],
    generator_map: dict[str, list[str]],
    imports: set[str],
    app_name: str,
    ir: SpecIR,
) -> None:
    """Genericの処理"""
    for generic in generics:
        if generic.id in generator_map:
            if not generic.check_functions:
                generic.check_functions = []
            alias = generate_generic_code_with_generators(generic, imports, app_name, ir, generator_map[generic.id])
        else:
            alias = generate_generic_code(generic, imports, app_name, ir)
        section.append(alias)
        section.append("")


def generate_all_type_aliases(ir: SpecIR, output_path: Path) -> None:
    """全てのTypeAlias（DataFrame/Enum/Pydantic）を1ファイルに統合生成

    Args:
        ir: 統合IR
        output_path: 出力ファイルパス
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    app_name = ir.meta.name.replace("-", "_") if ir.meta else "app"
    generator_map = build_generator_refs_map(ir)
    imports: set[str] = {"from typing import TypeAlias"}
    sections: list[str] = []

    # Pydanticモデル TypeAliases
    if ir.pydantic_models:
        sections.extend(
            generate_type_alias_section(
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
            generate_type_alias_section(
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
            generate_type_alias_section(
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
        _process_type_aliases(ir.type_aliases, section, generator_map, imports, app_name, ir)
        sections.extend(section)

    # Generic (list/dict/set/tuple) TypeAliases
    if ir.generics:
        section = ["# === Generic TypeAliases ===\n"]
        _process_generics(ir.generics, section, generator_map, imports, app_name, ir)
        sections.extend(section)

    if not sections:
        print("  ⏭️  Skip (no type aliases to generate)")
        return

    content = build_file_content(imports, sections)
    output_path.write_text(content)
    print(f"  ✅ Generated: {output_path}")

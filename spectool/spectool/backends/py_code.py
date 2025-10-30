"""TypeAlias生成バックエンド

IRからDataFrame/Enum/PydanticモデルのTypeAlias（Annotatedメタ付き）を生成。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spectool.spectool.core.base.ir import EnumSpec, FrameSpec, PydanticModelSpec, SpecIR


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


def _build_generator_spec(frame: FrameSpec) -> str | None:
    """GeneratorSpecメタデータを生成"""
    if not frame.generator_factory:
        return None
    return f'GeneratorSpec(factory="{frame.generator_factory}")'


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


def generate_dataframe_type_alias(frame: FrameSpec, imports: set[str], app_name: str) -> str:
    """DataFrame TypeAliasコードブロックを生成"""
    meta_parts = []

    # PydanticRowRef（存在する場合）
    if frame.row_model:
        row_ref = _build_pydantic_row_ref(frame)
        if row_ref:
            meta_parts.append(f"    {row_ref},")
            # row_modelからクラス名を抽出してインポート
            model_class = frame.row_model.split(":")[-1]
            imports.add(f"from apps.{app_name}.models.models import {model_class}")

    # GeneratorSpec（存在する場合）
    gen_spec = _build_generator_spec(frame)
    if gen_spec:
        meta_parts.append(f"    {gen_spec},")

    # CheckedSpec（存在する場合）
    checked_spec = _build_checked_spec(frame.check_functions)
    if checked_spec:
        meta_parts.append(f"    {checked_spec},")

    # TypeAlias構築
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


def generate_all_type_aliases(ir: SpecIR, output_path: Path) -> None:
    """全てのTypeAlias（DataFrame/Enum/Pydantic）を1ファイルに統合生成

    Args:
        ir: 統合IR
        output_path: 出力ファイルパス
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # アプリ名を取得（ハイフンをアンダースコアに変換）
    app_name = ir.meta.name.replace("-", "_") if ir.meta else "app"

    imports: set[str] = {"from typing import TypeAlias"}
    sections: list[str] = []

    # Pydanticモデル TypeAliases
    if ir.pydantic_models:
        sections.append("# === Pydantic Model TypeAliases ===\n")
        for model in ir.pydantic_models:
            model_alias = generate_pydantic_type_alias(model, imports, app_name)
            sections.append(model_alias)
            sections.append("")

    # Enum TypeAliases
    if ir.enums:
        sections.append("# === Enum TypeAliases ===\n")
        for enum in ir.enums:
            enum_alias = generate_enum_type_alias(enum, imports, app_name)
            sections.append(enum_alias)
            sections.append("")

    # DataFrame TypeAliases
    if ir.frames:
        sections.append("# === DataFrame TypeAliases ===\n")
        for frame in ir.frames:
            frame_alias = generate_dataframe_type_alias(frame, imports, app_name)
            sections.append(frame_alias)
            sections.append("")

    if not sections:
        print("  ⏭️  Skip (no type aliases to generate)")
        return

    # ファイル構築
    content = build_file_content(imports, sections)

    output_path.write_text(content)
    print(f"  ✅ Generated: {output_path}")

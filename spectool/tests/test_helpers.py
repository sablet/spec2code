"""テスト用ヘルパー関数

本番コードでは使用されないが、テストで必要な補助関数を定義。
"""

from pathlib import Path
from spectool.spectool.core.base.ir import SpecIR
from spectool.spectool.backends.py_code import (
    build_file_content,
    generate_dataframe_type_alias,
    generate_enum_type_alias,
    generate_pydantic_type_alias,
    render_imports,
)


def generate_dataframe_aliases(ir: SpecIR, output_path: Path) -> None:
    """DataFrame TypeAlias（Annotatedメタ付き）を生成（テスト用）

    Args:
        ir: 統合IR
        output_path: 出力ファイルパス
    """
    if not ir.frames:
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # アプリ名を取得
    app_name = ir.meta.name.replace("-", "_") if ir.meta else "app"

    imports: set[str] = {"from typing import TypeAlias"}
    sections: list[str] = []

    # DataFrame TypeAliasを生成
    sections.append("# === DataFrame TypeAliases ===\n")
    for frame in ir.frames:
        frame_alias = generate_dataframe_type_alias(frame, imports, app_name)
        sections.append(frame_alias)
        sections.append("")  # 空行

    # ファイル構築
    content = build_file_content(imports, sections)

    output_path.write_text(content)
    print(f"  ✅ Generated: {output_path}")


def generate_enum_aliases(ir: SpecIR, output_path: Path) -> None:
    """Enum TypeAlias（Annotatedメタ付き）を生成（テスト用）

    Args:
        ir: 統合IR
        output_path: 出力ファイルパス
    """
    if not ir.enums:
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # アプリ名を取得
    app_name = ir.meta.name.replace("-", "_") if ir.meta else "app"

    imports: set[str] = {"from typing import TypeAlias"}
    sections: list[str] = []

    # Enum TypeAliasを生成
    sections.append("# === Enum TypeAliases ===\n")
    for enum in ir.enums:
        enum_alias = generate_enum_type_alias(enum, imports, app_name)
        sections.append(enum_alias)
        sections.append("")  # 空行

    # ファイル構築
    header = [
        '"""生成されたEnum TypeAlias（AnnotatedメタデータでExampleSpec/CheckedSpecを付与）',
        "",
        "このファイルは spectool が spec.yaml から自動生成します。",
        '"""',
        "",
    ]

    content = "\n".join(header) + render_imports(imports) + "\n\n" + "\n".join(sections)

    output_path.write_text(content)
    print(f"  ✅ Generated: {output_path}")


def generate_pydantic_aliases(ir: SpecIR, output_path: Path) -> None:
    """Pydanticモデル TypeAlias（Annotatedメタ付き）を生成（テスト用）

    Args:
        ir: 統合IR
        output_path: 出力ファイルパス
    """
    if not ir.pydantic_models:
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # アプリ名を取得
    app_name = ir.meta.name.replace("-", "_") if ir.meta else "app"

    imports: set[str] = {"from typing import TypeAlias"}
    sections: list[str] = []

    # Pydanticモデル TypeAliasを生成
    sections.append("# === Pydantic Model TypeAliases ===\n")
    for model in ir.pydantic_models:
        model_alias = generate_pydantic_type_alias(model, imports, app_name)
        sections.append(model_alias)
        sections.append("")  # 空行

    # ファイル構築
    header = [
        '"""生成されたPydanticモデル TypeAlias（AnnotatedメタデータでExampleSpec/CheckedSpecを付与）',
        "",
        "このファイルは spectool が spec.yaml から自動生成します。",
        '"""',
        "",
    ]

    content = "\n".join(header) + render_imports(imports) + "\n\n" + "\n".join(sections)

    output_path.write_text(content)
    print(f"  ✅ Generated: {output_path}")


def generate_models_file(ir: SpecIR, output_path: str | Path) -> None:
    """Pydanticモデル・Enum定義を生成（テスト用スタブ実装）

    Args:
        ir: 統合IR
        output_path: 出力ファイルパス
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        '"""Pydanticモデル・Enum定義',
        "",
        "このファイルは spectool が spec.yaml から自動生成します。",
        "新アーキテクチャでは、既存のPython型を参照する想定です。",
        '"""',
        "",
        "from enum import Enum",
        "from pydantic import BaseModel",
        "",
    ]

    sections: list[str] = []

    # Enum生成
    if ir.enums:
        sections.append("# === Enums ===\n")
        for enum in ir.enums:
            if enum.description:
                sections.append(f"# {enum.description}")
            sections.append(f"class {enum.id}(str, Enum):")
            if enum.members:
                for member in enum.members:
                    sections.append(f'    {member} = "{member}"')
            else:
                sections.append("    pass")
            sections.append("")

    # Pydanticモデル生成（スタブ）
    if ir.pydantic_models:
        sections.append("# === Pydantic Models ===\n")
        for model in ir.pydantic_models:
            if model.description:
                sections.append(f"# {model.description}")
            sections.append(f"class {model.id}(BaseModel):")
            sections.append('    """TODO: Implement Pydantic model fields"""')
            sections.append("    pass")
            sections.append("")

    if not sections:
        # 空のファイルを生成
        sections.append("# No models or enums defined\n")

    content = "\n".join(header) + "\n".join(sections)
    output_path.write_text(content)
    print(f"  ✅ Generated: {output_path}")

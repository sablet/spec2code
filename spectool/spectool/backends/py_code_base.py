"""TypeAlias生成の基盤関数群

ユーティリティ、型解決、メタデータ構築などの基本的な関数を提供。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from spectool.spectool.core.base.ir import FrameSpec, GenericSpec, SpecIR
from spectool.spectool.backends.py_skeleton_codegen import _resolve_type_ref


def process_native_type(native_str: str, imports: set[str]) -> str:
    """ネイティブ型文字列を処理し、必要なインポートを追加

    Args:
        native_str: "module:typename" 形式の型文字列
        imports: インポート文のセット

    Returns:
        型名
    """
    if ":" in native_str:
        module, typename = native_str.split(":", 1)
        if module == "typing":
            imports.add(f"from typing import {typename}")
        return typename
    return native_str


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


def _resolve_target_type(type_def: dict[str, Any], imports: set[str], ir: SpecIR) -> str:
    """TypeAliasのターゲット型を解決

    Args:
        type_def: 型定義辞書
        imports: インポート文のセット
        ir: SpecIR（型参照解決用）

    Returns:
        解決された型文字列
    """
    alias_type = type_def.get("type", "simple")

    if alias_type == "simple":
        target = type_def.get("target", "")
        if "pandas:" in target:
            imports.add("import pandas as pd")
            return "pd.DataFrame"
        if ":" in target:
            return target.split(":")[-1]
        return target

    if alias_type == "tuple":
        # tuple要素を解決（types.py内では循環インポートを避けるため、importsにNoneを渡す）
        elements = type_def.get("elements", [])
        element_types = []
        for elem in elements:
            if "datatype_ref" in elem:
                # types.py内での参照なので、インポートなしで型名のみ取得
                elem_type = _resolve_type_ref(elem["datatype_ref"], ir, None)
                element_types.append(elem_type)
            elif "native" in elem:
                elem_type = process_native_type(elem["native"], imports)
                element_types.append(elem_type)

        imports.add("from typing import Tuple")
        return f"tuple[{', '.join(element_types)}]"

    # Unsupported type
    imports.add("from typing import Any")
    return "Any"


def _resolve_element_type(element_type_spec: dict[str, Any] | None, imports: set[str], ir: SpecIR) -> str:
    """要素型を解決

    Args:
        element_type_spec: 要素型定義（datatype_ref/native等を含む辞書）
        imports: インポート文のセット
        ir: SpecIR（型参照解決用）

    Returns:
        解決された型文字列
    """
    if element_type_spec:
        if "datatype_ref" in element_type_spec:
            return _resolve_type_ref(element_type_spec["datatype_ref"], ir, None)
        if "native" in element_type_spec:
            return process_native_type(element_type_spec["native"], imports)
    imports.add("from typing import Any")
    return "Any"


def _build_generic_target_type(generic: GenericSpec, imports: set[str], ir: SpecIR) -> str:
    """Generic型のターゲット型を構築

    Args:
        generic: Generic定義
        imports: インポート文のセット
        ir: SpecIR（型参照解決用）

    Returns:
        構築されたGeneric型文字列
    """
    container = generic.container

    if container == "list":
        elem_type = _resolve_element_type(generic.element_type, imports, ir)
        return f"list[{elem_type}]"

    if container == "dict":
        key_type = _resolve_element_type(generic.key_type, imports, ir)
        value_type = _resolve_element_type(generic.value_type, imports, ir)
        return f"dict[{key_type}, {value_type}]"

    if container == "set":
        elem_type = _resolve_element_type(generic.element_type, imports, ir)
        return f"set[{elem_type}]"

    if container == "tuple":
        element_types = []
        for elem in generic.elements:
            if "datatype_ref" in elem:
                elem_type = _resolve_type_ref(elem["datatype_ref"], ir, None)
                element_types.append(elem_type)
            elif "native" in elem:
                elem_type = process_native_type(elem["native"], imports)
                element_types.append(elem_type)
        return f"tuple[{', '.join(element_types)}]"

    # Unsupported container
    imports.add("from typing import Any")
    return "Any"


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


def build_generator_refs_map(ir: SpecIR) -> dict[str, list[str]]:
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


def generate_type_alias_section(
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

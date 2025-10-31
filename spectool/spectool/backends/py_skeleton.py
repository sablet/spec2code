"""Python スケルトン生成バックエンド

IRから関数スケルトンコードを生成する。
Check関数、Transform関数、Generator関数、Enum、Pydanticモデル、Pandera Schemaを生成。
"""

from __future__ import annotations

from pathlib import Path

from spectool.spectool.core.base.ir import SpecIR, TypeAliasSpec
from spectool.spectool.backends.py_validators import generate_pandera_schemas
from spectool.spectool.backends.py_code import generate_all_type_aliases
from spectool.spectool.backends.py_skeleton_codegen import render_imports
from spectool.spectool.backends.py_skeleton_functions import (
    generate_check_function,
    generate_generator_function,
    generate_transform_function,
)
from spectool.spectool.backends.py_skeleton_models import generate_enum_class, generate_pydantic_model


def _write_module_file(output_path: Path, header_comment: str, imports: set[str], content_sections: list[str]) -> None:
    """モジュールファイルを書き込む（既存ファイルは上書きしない）

    Args:
        output_path: 出力ファイルパス
        header_comment: ファイルヘッダーコメント
        imports: インポート文のセット
        content_sections: コンテンツセクションのリスト
    """
    if output_path.exists():
        # 既存ファイルは上書きしない
        print(f"  ⏭️  Skip (file exists): {output_path}")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ファイル内容を構築
    lines = [f'"""{header_comment}"""', ""]

    if imports:
        lines.append(render_imports(imports))
        lines.append("")
        lines.append("")

    for section in content_sections:
        lines.append(section)
        lines.append("")
        lines.append("")

    content = "\n".join(lines)
    output_path.write_text(content)
    print(f"  ✅ Generated: {output_path}")


def generate_skeleton(ir: SpecIR, output_dir: Path) -> None:
    """スケルトンコードを生成

    IRからCheck/Transform/Generator関数、Enum、Pydanticモデル、Pandera Schemaを生成。

    Args:
        ir: 統合IR
        output_dir: 出力ディレクトリ
    """
    app_name = ir.meta.name if ir.meta else "app"
    app_name = app_name.replace("-", "_")
    app_root = output_dir / "apps" / app_name

    _create_directory_structure(app_root)
    _generate_check_modules(ir, app_root)
    _generate_transform_modules(ir, app_root)
    _generate_generator_modules(ir, app_root)
    _generate_enum_module(ir, app_root)
    _generate_pydantic_model_module(ir, app_root)
    _generate_pandera_schemas(ir, app_root)
    _generate_type_aliases(ir, app_root)


def _create_directory_structure(app_root: Path) -> None:
    """Create directory structure for the generated app."""
    directories = [
        app_root / "checks",
        app_root / "transforms",
        app_root / "generators",
        app_root / "models",
        app_root / "schemas",
    ]

    for dir_path in directories:
        dir_path.mkdir(parents=True, exist_ok=True)
        init_file = dir_path / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""Auto-generated module"""\n')


def _generate_check_modules(ir: SpecIR, app_root: Path) -> None:
    """Generate check function modules."""
    if not ir.checks:
        return

    check_functions_by_file: dict[str, list[str]] = {}
    for check in ir.checks:
        file_path = check.file_path or "checks/validators.py"
        # Normalize file_path to remove "apps/" prefix for grouping
        normalized_path = str(_strip_apps_prefix(Path(file_path)))
        imports_check: set[str] = set()
        func_code = generate_check_function(check, imports_check)

        if normalized_path not in check_functions_by_file:
            check_functions_by_file[normalized_path] = []
        check_functions_by_file[normalized_path].append(func_code)

    for file_path, functions in check_functions_by_file.items():
        relative_path = _strip_apps_prefix(Path(file_path))
        output_path = app_root / relative_path
        imports_check_global: set[str] = set()
        _write_module_file(
            output_path,
            "Check functions\n\nこのファイルは spectool が自動生成しました。",
            imports_check_global,
            functions,
        )


def _generate_transform_modules(ir: SpecIR, app_root: Path) -> None:
    """Generate transform function modules."""
    if not ir.transforms:
        return

    transform_functions_by_file: dict[str, list[tuple[str, set[str]]]] = {}
    for transform in ir.transforms:
        file_path = transform.file_path or "transforms/processors.py"
        # Normalize file_path to remove "apps/" prefix for grouping
        normalized_path = str(_strip_apps_prefix(Path(file_path)))
        imports_transform: set[str] = set()
        func_code = generate_transform_function(transform, ir, imports_transform)

        if normalized_path not in transform_functions_by_file:
            transform_functions_by_file[normalized_path] = []
        transform_functions_by_file[normalized_path].append((func_code, imports_transform))

    for file_path, functions_with_imports in transform_functions_by_file.items():
        relative_path = _strip_apps_prefix(Path(file_path))
        output_path = app_root / relative_path

        imports_transform_global: set[str] = set()
        function_codes = []
        for func_code, imports_local in functions_with_imports:
            imports_transform_global.update(imports_local)
            function_codes.append(func_code)

        _write_module_file(
            output_path,
            "Transform functions\n\nこのファイルは spectool が自動生成しました。",
            imports_transform_global,
            function_codes,
        )


def _generate_generator_modules(ir: SpecIR, app_root: Path) -> None:
    """Generate generator function modules."""
    if not ir.generators:
        return

    generator_functions_by_file: dict[str, list[tuple[str, set[str]]]] = {}
    for generator in ir.generators:
        file_path = generator.file_path or "generators/data_generators.py"
        # Normalize file_path to remove "apps/" prefix for grouping
        normalized_path = str(_strip_apps_prefix(Path(file_path)))
        imports_generator: set[str] = set()
        func_code = generate_generator_function(generator, ir, imports_generator)

        if normalized_path not in generator_functions_by_file:
            generator_functions_by_file[normalized_path] = []
        generator_functions_by_file[normalized_path].append((func_code, imports_generator))

    for file_path, functions_with_imports in generator_functions_by_file.items():
        relative_path = _strip_apps_prefix(Path(file_path))
        output_path = app_root / relative_path

        imports_generator_global: set[str] = set()
        function_codes = []
        for func_code, imports_local in functions_with_imports:
            imports_generator_global.update(imports_local)
            function_codes.append(func_code)

        _write_module_file(
            output_path,
            "Generator functions\n\nこのファイルは spectool が自動生成しました。",
            imports_generator_global,
            function_codes,
        )


def _generate_enum_module(ir: SpecIR, app_root: Path) -> None:
    """Generate enum module."""
    if not ir.enums:
        return

    imports_enums: set[str] = {"from enum import Enum"}
    enum_sections = []

    for enum in ir.enums:
        enum_code = generate_enum_class(enum)
        enum_sections.append(enum_code)

    enums_path = app_root / "models" / "enums.py"
    _write_module_file(
        enums_path,
        "Enum definitions\n\nこのファイルは spectool が自動生成しました。",
        imports_enums,
        enum_sections,
    )


def _collect_used_datatype_refs(ir: SpecIR) -> set[str]:
    """Collect all datatype_refs used in Pydantic models.

    Args:
        ir: Spec IR

    Returns:
        Set of datatype_ref IDs used in Pydantic models
    """
    used_datatype_refs: set[str] = set()
    for model in ir.pydantic_models:
        for field in model.fields:
            field_type = field.get("type", {})
            _collect_datatype_refs(field_type, used_datatype_refs)
    return used_datatype_refs


def _add_enum_imports(ir: SpecIR, used_datatype_refs: set[str], imports_models: set[str]) -> None:
    """Add imports for Enums that are referenced in models.

    Args:
        ir: Spec IR
        used_datatype_refs: Set of datatype_ref IDs used in models
        imports_models: Import set to add enum imports to
    """
    enum_ids = {enum.id for enum in ir.enums}
    for ref in used_datatype_refs:
        if ref in enum_ids:
            imports_models.add(f"from apps.{ir.meta.name.replace('-', '_')}.models.enums import {ref}")


def _generate_type_alias_sections(ir: SpecIR, used_datatype_refs: set[str], imports_models: set[str]) -> list[str]:
    """Generate TypeAlias sections for used type aliases.

    Args:
        ir: Spec IR
        used_datatype_refs: Set of datatype_ref IDs used in models
        imports_models: Import set to add type alias imports to

    Returns:
        List of TypeAlias code sections
    """
    type_alias_sections = []
    if ir.type_aliases:
        for type_alias in ir.type_aliases:
            if type_alias.id in used_datatype_refs:
                # Generate simple TypeAlias
                type_alias_sections.append(_generate_simple_type_alias(type_alias, imports_models))
    return type_alias_sections


def _generate_pydantic_model_module(ir: SpecIR, app_root: Path) -> None:
    """Generate Pydantic model module."""
    if not ir.pydantic_models:
        return

    imports_models: set[str] = {"from pydantic import BaseModel"}

    # Collect all datatype_refs used in Pydantic models
    used_datatype_refs = _collect_used_datatype_refs(ir)

    # Add imports for Enums
    _add_enum_imports(ir, used_datatype_refs, imports_models)

    # Add TypeAliases as direct definitions for simple type aliases
    type_alias_sections = _generate_type_alias_sections(ir, used_datatype_refs, imports_models)

    # Generate model code sections
    model_sections = []
    for model in ir.pydantic_models:
        model_code = generate_pydantic_model(model, imports_models)
        model_sections.append(model_code)

    # Combine type aliases and models
    all_sections = type_alias_sections + model_sections

    models_path = app_root / "models" / "models.py"
    _write_module_file(
        models_path,
        "Pydantic Model definitions\n\nこのファイルは spectool が自動生成しました。",
        imports_models,
        all_sections,
    )


def _collect_datatype_refs(field_type: dict, refs: set[str]) -> None:
    """Recursively collect all datatype_ref references from a field type definition."""
    if "datatype_ref" in field_type:
        refs.add(field_type["datatype_ref"])
    elif "generic" in field_type:
        generic_def = field_type["generic"]
        if "element_type" in generic_def:
            _collect_datatype_refs(generic_def["element_type"], refs)
        if "key_type" in generic_def:
            _collect_datatype_refs(generic_def["key_type"], refs)
        if "value_type" in generic_def:
            _collect_datatype_refs(generic_def["value_type"], refs)


def _generate_simple_type_alias(type_alias: TypeAliasSpec, imports: set[str]) -> str:
    """Generate a simple TypeAlias definition for use in models.py."""
    if not isinstance(type_alias, TypeAliasSpec):
        return ""

    # type_def contains {"type": "simple", "target": "pandas:DataFrame"}
    type_def = type_alias.type_def
    if not type_def:
        return ""

    # Handle simple type aliases (e.g., MultiAssetOHLCVFrame = pd.DataFrame)
    if type_def.get("type") == "simple":
        target = type_def.get("target", "")
        if target == "pandas:DataFrame":
            imports.add("from pandas import DataFrame")
            return f"{type_alias.id} = DataFrame"
        if target == "pandas:Series":
            imports.add("from pandas import Series")
            return f"{type_alias.id} = Series"
        # Generic target handling
        module, type_name = target.split(":") if ":" in target else ("", target)
        if module and module not in {"builtins", "typing"}:
            imports.add(f"from {module} import {type_name}")
        return f"{type_alias.id} = {type_name}"

    return ""


def _generate_pandera_schemas(ir: SpecIR, app_root: Path) -> None:
    """Generate Pandera schema module."""
    if not ir.frames:
        return

    schema_path = app_root / "schemas" / "dataframe_schemas.py"
    generate_pandera_schemas(ir, schema_path)


def _generate_type_aliases(ir: SpecIR, app_root: Path) -> None:
    """Generate TypeAlias module with Annotated metadata."""
    if not (ir.frames or ir.enums or ir.pydantic_models):
        return

    type_aliases_path = app_root / "types.py"
    generate_all_type_aliases(ir, type_aliases_path)


def _strip_apps_prefix(file_path: Path) -> Path:
    """Remove 'apps/' prefix from file path if present."""
    if file_path.parts and file_path.parts[0] == "apps":
        return Path(*file_path.parts[1:])
    return file_path

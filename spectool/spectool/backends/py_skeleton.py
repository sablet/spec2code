"""Python スケルトン生成バックエンド

IRから関数スケルトンコードを生成する。
Check関数、Transform関数、Generator関数、Enum、Pydanticモデル、Pandera Schemaを生成。
"""

from __future__ import annotations

from pathlib import Path

from spectool.spectool.core.base.ir import (
    CheckSpec,
    EnumSpec,
    GeneratorDef,
    ParameterSpec,
    PydanticModelSpec,
    SpecIR,
    TransformSpec,
)
from spectool.spectool.backends.py_validators import generate_pandera_schemas
from spectool.spectool.backends.py_code import generate_all_type_aliases


def _extract_function_name(impl: str) -> str:
    """implから関数名を抽出

    Args:
        impl: "module.path:function_name" 形式の文字列

    Returns:
        関数名
    """
    if ":" in impl:
        return impl.split(":")[-1]
    return impl


def _extract_module_path(impl: str) -> str:
    """implからモジュールパスを抽出

    Args:
        impl: "module.path:function_name" 形式の文字列

    Returns:
        モジュールパス
    """
    if ":" in impl:
        return impl.split(":")[0]
    return ""


def _resolve_type_annotation(param: ParameterSpec, ir: SpecIR) -> str:
    """パラメータから型アノテーション文字列を生成

    Args:
        param: パラメータ定義
        ir: SpecIR（型参照解決用）

    Returns:
        型アノテーション文字列（例: "Annotated[pd.DataFrame, Check[...]]"）
    """
    type_ref = param.type_ref

    # ネイティブ型の場合
    if "builtins:" in type_ref:
        return type_ref.split(":")[-1]

    # DataFrame型の場合
    for frame in ir.frames:
        if frame.id == type_ref:
            # Check関数があればAnnotatedで包む
            if frame.check_functions:
                check_refs = ", ".join(f'Check["{cf}"]' for cf in frame.check_functions)
                return f"Annotated[pd.DataFrame, {check_refs}]"
            return "pd.DataFrame"

    # Enum型の場合
    for enum in ir.enums:
        if enum.id == type_ref:
            return enum.id

    # Pydanticモデルの場合
    for model in ir.pydantic_models:
        if model.id == type_ref:
            return model.id

    # 型が見つからない場合はそのまま返す
    return type_ref


def _render_parameter_signature(param: ParameterSpec, ir: SpecIR) -> str:
    """パラメータのシグネチャ文字列を生成

    Args:
        param: パラメータ定義
        ir: SpecIR（型参照解決用）

    Returns:
        パラメータシグネチャ文字列（例: "data: Annotated[pd.DataFrame, ...]"）
    """
    type_annotation = _resolve_type_annotation(param, ir)

    if param.optional and param.default is not None:
        # デフォルト値がある場合
        if isinstance(param.default, str):
            return f"{param.name}: {type_annotation} = '{param.default}'"
        return f"{param.name}: {type_annotation} = {param.default}"
    if param.optional:
        # Optionalだがデフォルト値がない場合
        return f"{param.name}: {type_annotation} | None = None"
    # 必須パラメータ
    return f"{param.name}: {type_annotation}"


def _generate_check_function(check: CheckSpec, imports: set[str]) -> str:
    """Check関数のスケルトンを生成

    Args:
        check: Check関数定義
        imports: インポート文を蓄積するセット

    Returns:
        関数定義文字列
    """
    func_name = _extract_function_name(check.impl)

    lines = []
    if check.description:
        lines.append(f"# {check.description}")

    lines.append(f"def {func_name}(payload: dict) -> bool:")
    lines.append(f'    """TODO: Implement {func_name}')
    lines.append("    ")
    if check.description:
        lines.append(f"    {check.description}")
    lines.append('    """')
    lines.append("    # TODO: Implement validation logic")
    lines.append("    return True")

    return "\n".join(lines)


def _generate_transform_function(transform: TransformSpec, ir: SpecIR, imports: set[str]) -> str:
    """Transform関数のスケルトンを生成

    Args:
        transform: Transform関数定義
        ir: SpecIR（型参照解決用）
        imports: インポート文を蓄積するセット

    Returns:
        関数定義文字列
    """
    func_name = _extract_function_name(transform.impl)

    # パラメータリストを生成
    params = [_render_parameter_signature(p, ir) for p in transform.parameters]
    param_str = ", ".join(params)

    # 戻り値型を解決
    return_type = "Any"
    if transform.return_type_ref:
        # DataFrame型の場合
        for frame in ir.frames:
            if frame.id == transform.return_type_ref:
                if frame.check_functions:
                    check_refs = ", ".join(f'Check["{cf}"]' for cf in frame.check_functions)
                    return_type = f"Annotated[pd.DataFrame, {check_refs}]"
                else:
                    return_type = "pd.DataFrame"
                break
        else:
            # Enum/Pydantic/その他の型
            return_type = transform.return_type_ref

    # インポートを追加
    if "Annotated" in return_type or any("Annotated" in p for p in params):
        imports.add("from typing import Annotated")
    if "pd.DataFrame" in return_type or any("pd.DataFrame" in p for p in params):
        imports.add("import pandas as pd")
    if "Check" in return_type or any("Check" in p for p in params):
        imports.add("from spectool.spectool.core.base.meta_types import Check")

    lines = []
    if transform.description:
        lines.append(f"# {transform.description}")

    lines.append(f"def {func_name}({param_str}) -> {return_type}:")
    lines.append(f'    """TODO: Implement {func_name}')
    lines.append("    ")
    if transform.description:
        lines.append(f"    {transform.description}")
    lines.append('    """')
    lines.append("    # TODO: Implement transformation logic")

    # 戻り値のプレースホルダー
    if "pd.DataFrame" in return_type:
        lines.append("    return pd.DataFrame()")
    else:
        lines.append("    raise NotImplementedError()")

    return "\n".join(lines)


def _generate_generator_function(generator: GeneratorDef, ir: SpecIR, imports: set[str]) -> str:
    """Generator関数のスケルトンを生成

    Args:
        generator: Generator関数定義
        ir: SpecIR（型参照解決用）
        imports: インポート文を蓄積するセット

    Returns:
        関数定義文字列
    """
    func_name = _extract_function_name(generator.impl)

    # パラメータリストを生成
    params = [_render_parameter_signature(p, ir) for p in generator.parameters]
    param_str = ", ".join(params) if params else ""

    # Generator関数は常にpd.DataFrameを返すと仮定
    return_type = "pd.DataFrame"
    imports.add("import pandas as pd")

    lines = []
    if generator.description:
        lines.append(f"# {generator.description}")

    lines.append(f"def {func_name}({param_str}) -> {return_type}:")
    lines.append(f'    """TODO: Implement {func_name}')
    lines.append("    ")
    if generator.description:
        lines.append(f"    {generator.description}")
    lines.append('    """')
    lines.append("    # TODO: Implement data generation logic")
    lines.append("    return pd.DataFrame()")

    return "\n".join(lines)


def _generate_enum_class(enum: EnumSpec) -> str:
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


def _generate_pydantic_model(model: PydanticModelSpec) -> str:
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


def _render_imports(imports: set[str]) -> str:
    """インポート文を整形して返す"""
    if not imports:
        return ""
    return "\n".join(sorted(imports))


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
        lines.append(_render_imports(imports))
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
    app_name = app_name.replace("-", "_")  # Pythonモジュール名としてハイフンは無効
    app_root = output_dir / "apps" / app_name

    # ディレクトリ構造を作成
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

    # Check関数を生成
    if ir.checks:
        check_functions_by_file: dict[str, list[str]] = {}
        for check in ir.checks:
            file_path = check.file_path or "checks/validators.py"
            imports_check: set[str] = set()
            func_code = _generate_check_function(check, imports_check)

            if file_path not in check_functions_by_file:
                check_functions_by_file[file_path] = []
            check_functions_by_file[file_path].append(func_code)

        for file_path, functions in check_functions_by_file.items():
            # file_pathから "apps/" プレフィックスを除去
            relative_path = Path(file_path)
            if relative_path.parts and relative_path.parts[0] == "apps":
                relative_path = Path(*relative_path.parts[1:])
            output_path = app_root / relative_path

            imports_check_global: set[str] = set()
            _write_module_file(
                output_path,
                "Check functions\n\nこのファイルは spectool が自動生成しました。",
                imports_check_global,
                functions,
            )

    # Transform関数を生成
    if ir.transforms:
        transform_functions_by_file: dict[str, list[tuple[str, set[str]]]] = {}
        for transform in ir.transforms:
            file_path = transform.file_path or "transforms/processors.py"
            imports_transform: set[str] = set()
            func_code = _generate_transform_function(transform, ir, imports_transform)

            if file_path not in transform_functions_by_file:
                transform_functions_by_file[file_path] = []
            transform_functions_by_file[file_path].append((func_code, imports_transform))

        for file_path, functions_with_imports in transform_functions_by_file.items():
            # file_pathから "apps/" プレフィックスを除去
            relative_path = Path(file_path)
            if relative_path.parts and relative_path.parts[0] == "apps":
                relative_path = Path(*relative_path.parts[1:])
            output_path = app_root / relative_path

            # 全てのインポートを統合
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

    # Generator関数を生成
    if ir.generators:
        generator_functions_by_file: dict[str, list[tuple[str, set[str]]]] = {}
        for generator in ir.generators:
            file_path = generator.file_path or "generators/data_generators.py"
            imports_generator: set[str] = set()
            func_code = _generate_generator_function(generator, ir, imports_generator)

            if file_path not in generator_functions_by_file:
                generator_functions_by_file[file_path] = []
            generator_functions_by_file[file_path].append((func_code, imports_generator))

        for file_path, functions_with_imports in generator_functions_by_file.items():
            # file_pathから "apps/" プレフィックスを除去
            relative_path = Path(file_path)
            if relative_path.parts and relative_path.parts[0] == "apps":
                relative_path = Path(*relative_path.parts[1:])
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

    # Enumを生成（enums.py）
    if ir.enums:
        imports_enums: set[str] = {"from enum import Enum"}
        enum_sections = []

        for enum in ir.enums:
            enum_code = _generate_enum_class(enum)
            enum_sections.append(enum_code)

        enums_path = app_root / "models" / "enums.py"
        _write_module_file(
            enums_path,
            "Enum definitions\n\nこのファイルは spectool が自動生成しました。",
            imports_enums,
            enum_sections,
        )

    # Pydanticモデルを生成（models.py）
    if ir.pydantic_models:
        imports_models: set[str] = {"from pydantic import BaseModel"}
        model_sections = []

        for model in ir.pydantic_models:
            model_code = _generate_pydantic_model(model)
            model_sections.append(model_code)

        models_path = app_root / "models" / "models.py"
        _write_module_file(
            models_path,
            "Pydantic Model definitions\n\nこのファイルは spectool が自動生成しました。",
            imports_models,
            model_sections,
        )

    # Pandera Schemaを生成（既存の py_validators を活用）
    if ir.frames:
        schema_path = app_root / "schemas" / "dataframe_schemas.py"
        generate_pandera_schemas(ir, schema_path)

    # TypeAlias生成（Annotatedメタデータ付き）
    if ir.frames or ir.enums or ir.pydantic_models:
        type_aliases_path = app_root / "types.py"
        generate_all_type_aliases(ir, type_aliases_path)

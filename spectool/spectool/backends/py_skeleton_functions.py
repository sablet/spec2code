"""Python スケルトン生成 - 関数生成

Check関数、Transform関数、Generator関数のスケルトンを生成。
"""

from __future__ import annotations

from spectool.spectool.core.base.ir import CheckSpec, GeneratorDef, SpecIR, TransformSpec
from spectool.spectool.backends.py_skeleton_codegen import (
    build_function_body_placeholder,
    build_transform_function_signature,
    extract_function_name,
    render_parameter_signature,
    resolve_transform_return_type,
    _resolve_type_ref,
)


def generate_check_function(check: CheckSpec, ir: SpecIR, imports: set[str]) -> str:
    """Check関数のスケルトンを生成

    Args:
        check: Check関数定義
        ir: SpecIR（型参照解決用）
        imports: インポート文を蓄積するセット

    Returns:
        関数定義文字列
    """
    func_name = extract_function_name(check.impl)

    # input_type_refがある場合は型解決、ない場合はdictをデフォルトとする
    input_type = _resolve_type_ref(check.input_type_ref, ir, imports) if check.input_type_ref else "dict"

    lines = []
    if check.description:
        lines.append(f"# {check.description}")

    lines.append(f"def {func_name}(payload: {input_type}) -> bool:")
    lines.append(f'    """TODO: Implement {func_name}')
    lines.append("    ")
    if check.description:
        lines.append(f"    {check.description}")
    lines.append('    """')
    lines.append("    # TODO: Implement validation logic")
    lines.append("    return True")

    return "\n".join(lines)


def generate_transform_function(transform: TransformSpec, ir: SpecIR, imports: set[str]) -> str:
    """Transform関数のスケルトンを生成

    Args:
        transform: Transform関数定義
        ir: SpecIR（型参照解決用）
        imports: インポート文を蓄積するセット

    Returns:
        関数定義文字列
    """
    func_name = extract_function_name(transform.impl)
    # パラメータ生成時にimportsを渡す
    params = [render_parameter_signature(p, ir, imports) for p in transform.parameters]
    param_str = ", ".join(params)
    # 戻り値型解決時にimportsを渡す
    return_type = resolve_transform_return_type(transform, ir, imports)

    lines = build_transform_function_signature(
        func_name,
        param_str,
        return_type,
        transform.description,
        spec_metadata=transform.spec_metadata,  # メタデータを渡す
    )
    lines.extend(build_function_body_placeholder(return_type))

    return "\n".join(lines)


def generate_generator_function(generator: GeneratorDef, ir: SpecIR, imports: set[str]) -> str:
    """Generator関数のスケルトンを生成

    Args:
        generator: Generator関数定義
        ir: SpecIR（型参照解決用）
        imports: インポート文を蓄積するセット

    Returns:
        関数定義文字列
    """
    func_name = extract_function_name(generator.impl)

    # パラメータリストを生成
    params = [render_parameter_signature(p, ir, imports) for p in generator.parameters]
    param_str = ", ".join(params) if params else ""

    # return_type_refを解決（Transform関数と同じロジックを使用）
    # GeneratorDefをTransformSpecのように扱うために、return_type_refを持つオブジェクトとして渡す
    # resolve_transform_return_typeは、.return_type_refを持つオブジェクトを受け取る
    return_type = resolve_transform_return_type(generator, ir, imports)

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

    # プレースホルダーの返り値を生成
    placeholder_lines = build_function_body_placeholder(return_type)
    lines.extend(placeholder_lines)

    return "\n".join(lines)

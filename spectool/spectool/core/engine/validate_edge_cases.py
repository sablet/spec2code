"""Validator: エッジケース検証

エッジケース（候補ゼロ、checkゼロ、exampleゼロ等）を検証する。
"""

from __future__ import annotations

from spectool.spectool.core.base.ir import (
    EnumSpec,
    FrameSpec,
    GenericSpec,
    PydanticModelSpec,
    SpecIR,
    TypeAliasSpec,
)
from spectool.spectool.core.engine.validate_ir import _collect_all_datatype_ids


def validate_edge_cases_errors_only(ir: SpecIR) -> list[str]:
    """エッジケース検証（エラーのみ、警告は除く）

    検証項目:
    1. DAG stageで候補transform関数がゼロ件
    2. Exampleのdatatype_ref妥当性
    3. Transformパラメータのデフォルト値型チェック

    Args:
        ir: 検証対象のIR

    Returns:
        エラーメッセージのリスト
    """
    errors: list[str] = []

    # 全datatype IDを収集
    all_datatype_ids = _collect_all_datatype_ids(ir)

    # 1. DAG stageの候補ゼロチェック
    errors.extend(_validate_dag_stage_candidates(ir, all_datatype_ids))

    # 2. Exampleのdatatype_ref妥当性チェック
    errors.extend(_validate_example_refs(ir, all_datatype_ids))

    # 3. Transformパラメータのデフォルト値型チェック
    errors.extend(_validate_parameter_defaults(ir))

    return errors


def _find_matching_transforms(ir: SpecIR, input_type: str, output_type: str) -> list[str]:
    """指定された入出力型に一致するtransform関数を探す

    Args:
        ir: SpecIR
        input_type: 入力型
        output_type: 出力型

    Returns:
        一致するtransform IDのリスト
    """
    matching_transforms = []
    for transform in ir.transforms:
        # 第1パラメータの型がinput_typeで、return_type_refがoutput_typeのものを探す
        if transform.parameters and transform.return_type_ref == output_type:
            first_param = transform.parameters[0]
            if first_param.type_ref == input_type:
                matching_transforms.append(transform.id)
    return matching_transforms


def _validate_dag_stage_candidates(ir: SpecIR, all_datatype_ids: set[str]) -> list[str]:
    """DAG stageの候補transform関数がゼロ件でないかチェック

    Args:
        ir: 検証対象のIR
        all_datatype_ids: 全datatype IDのセット

    Returns:
        エラーメッセージのリスト
    """
    errors: list[str] = []

    for stage in ir.dag_stages:
        # 候補が空の場合
        if not stage.candidates:
            # 自動収集を試みる（input_type → output_type の変換を行うtransformを探す）
            if stage.input_type and stage.output_type:
                matching_transforms = _find_matching_transforms(ir, stage.input_type, stage.output_type)

                if not matching_transforms:
                    errors.append(
                        f"DAG Stage '{stage.stage_id}': no transform candidates found for "
                        f"input_type '{stage.input_type}' → output_type '{stage.output_type}'. "
                        f"Please define a transform or specify candidates explicitly."
                    )
            else:
                errors.append(
                    f"DAG Stage '{stage.stage_id}': candidates list is empty and "
                    f"input_type/output_type are not specified for auto-collection."
                )

    return errors


def _check_datatype_has_check_functions(datatype: Any) -> str | None:  # noqa: ANN401
    """データタイプにcheck関数が定義されているかチェック

    Args:
        datatype: データタイプ（Frame/Enum/PydanticModel/TypeAlias/Generic）

    Returns:
        警告メッセージ、または None
    """
    if not datatype.check_functions:
        return (
            f"DataType '{datatype.id}': no check functions defined. "
            f"Consider adding check_functions for data validation."
        )
    return None


def validate_datatype_checks(ir: SpecIR) -> list[str]:
    """DataTypeのcheck関数がゼロ件でないかチェック（警告）

    Args:
        ir: 検証対象のIR

    Returns:
        警告メッセージのリスト
    """
    warnings: list[str] = []

    # 全てのデータタイプをまとめてチェック
    all_datatypes = [
        *ir.frames,
        *ir.enums,
        *ir.pydantic_models,
        *ir.type_aliases,
        *ir.generics,
    ]

    for datatype in all_datatypes:
        warning = _check_datatype_has_check_functions(datatype)
        if warning:
            warnings.append(warning)

    return warnings


def _collect_example_datatypes(ir: SpecIR) -> set[str]:
    """Exampleから参照されているdatatype_refを収集"""
    example_datatypes = set()
    for example in ir.examples:
        if example.datatype_ref and example.datatype_ref.strip():
            example_datatypes.add(example.datatype_ref)
    return example_datatypes


def _collect_generator_datatypes(ir: SpecIR) -> set[str]:
    """Generatorとgenerator_factoryから参照されているデータタイプを収集"""
    generator_datatypes = set()
    for generator in ir.generators:
        if generator.return_type_ref and generator.return_type_ref.strip():
            generator_datatypes.add(generator.return_type_ref)

    # FrameSpecのgenerator_factoryもチェック
    for frame in ir.frames:
        if frame.generator_factory:
            generator_datatypes.add(frame.id)

    return generator_datatypes


def _check_datatype_has_examples_or_generators(
    datatype_id: str, example_datatypes: set[str], generator_datatypes: set[str]
) -> str | None:
    """データタイプにexampleまたはgeneratorが存在するかチェック"""
    if datatype_id not in example_datatypes and datatype_id not in generator_datatypes:
        return (
            f"DataType '{datatype_id}': neither examples nor generators are defined. "
            f"Consider adding examples or a generator for testing."
        )
    return None


def validate_datatype_examples_generators(ir: SpecIR) -> list[str]:
    """DataTypeのexample/generatorの両方がゼロ件でないかチェック（警告）

    Args:
        ir: 検証対象のIR

    Returns:
        警告メッセージのリスト
    """
    warnings: list[str] = []

    example_datatypes = _collect_example_datatypes(ir)
    generator_datatypes = _collect_generator_datatypes(ir)

    # 各DataTypeでexampleもgeneratorも存在しないものを警告
    all_datatypes: list[FrameSpec | EnumSpec | PydanticModelSpec | TypeAliasSpec | GenericSpec] = [
        *ir.frames,
        *ir.enums,
        *ir.pydantic_models,
        *ir.type_aliases,
        *ir.generics,
    ]

    for datatype in all_datatypes:
        warning = _check_datatype_has_examples_or_generators(datatype.id, example_datatypes, generator_datatypes)
        if warning:
            warnings.append(warning)

    return warnings


def _validate_example_refs(ir: SpecIR, all_datatype_ids: set[str]) -> list[str]:
    """Exampleのdatatype_ref妥当性チェック

    Args:
        ir: 検証対象のIR
        all_datatype_ids: 全datatype IDのセット

    Returns:
        エラーメッセージのリスト
    """
    errors: list[str] = []

    for example in ir.examples:
        # datatype_refが指定されている場合（空文字列でない）
        if example.datatype_ref and example.datatype_ref.strip() and example.datatype_ref not in all_datatype_ids:
            errors.append(
                f"Example '{example.id}': datatype_ref '{example.datatype_ref}' not found in defined datatypes."
            )

    return errors


def _check_param_default_type(
    transform_id: str, param_name: str, default: object, type_ref: str, optional: bool
) -> str | None:
    """パラメータのデフォルト値の型をチェック

    Args:
        transform_id: Transform ID
        param_name: パラメータ名
        default: デフォルト値
        type_ref: 型参照
        optional: オプショナルフラグ

    Returns:
        エラーメッセージ、またはNone
    """
    type_name = type_ref.split(":", 1)[1]
    expected_type = _get_builtin_type(type_name)

    if expected_type is None:
        return None

    # optional=Trueの場合はNoneを許容
    if optional and default is None:
        return None

    # int→floatの変換は許容
    if expected_type is float and isinstance(default, int):
        return None

    # 型が一致しない場合
    if not isinstance(default, expected_type):
        return (
            f"Transform '{transform_id}', parameter '{param_name}': "
            f"default value type mismatch. Expected {type_name}, "
            f"but got {type(default).__name__}."
        )

    return None


def _validate_parameter_defaults(ir: SpecIR) -> list[str]:
    """Transformパラメータのデフォルト値型チェック

    Args:
        ir: 検証対象のIR

    Returns:
        エラーメッセージのリスト
    """
    errors: list[str] = []

    for transform in ir.transforms:
        for param in transform.parameters:
            # デフォルト値が設定されている場合
            if param.default is not None and param.type_ref.startswith("builtins:"):
                error = _check_param_default_type(
                    transform.id, param.name, param.default, param.type_ref, param.optional
                )
                if error:
                    errors.append(error)

    return errors


def _get_builtin_type(type_name: str) -> type | None:
    """builtins型名から対応するPython型オブジェクトを取得

    Args:
        type_name: 型名（"int", "str", "float", "bool", "list", "dict"等）

    Returns:
        対応するPython型オブジェクト、または None
    """
    builtin_types = {
        "int": int,
        "str": str,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "set": set,
    }
    return builtin_types.get(type_name)

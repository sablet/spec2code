"""Loader: YAML→IR変換

YAMLを読み込み、IRに変換する。
Python型参照解決機構を含む。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from spectool.spectool.core.base.ir import (
    CheckSpec,
    ColumnRule,
    DAGStageSpec,
    EnumMemberSpec,
    EnumSpec,
    ExampleCase,
    FrameSpec,
    GeneratorDef,
    GenericSpec,
    IndexRule,
    MetaSpec,
    MultiIndexLevel,
    ParameterSpec,
    PydanticModelSpec,
    SpecIR,
    TransformSpec,
    TypeAliasSpec,
)


def load_spec(spec_path: str | Path) -> SpecIR:
    """YAML/JSON仕様を読み込み、IRに変換

    Args:
        spec_path: 仕様ファイルのパス

    Returns:
        SpecIR: 統合IR

    Raises:
        ValueError: 未対応のファイル形式
    """
    spec_path = Path(spec_path)
    with open(spec_path) as f:
        if spec_path.suffix in {".yaml", ".yml"}:
            data = yaml.safe_load(f)
        elif spec_path.suffix == ".json":
            data = json.load(f)
        else:
            raise ValueError(f"未対応のファイル形式: {spec_path.suffix}")

    # メタデータ
    meta = _load_meta(data.get("meta", {}), data.get("version", "1.0"))

    # 各セクションを変換
    frames = _load_dataframe_specs(data.get("datatypes", []))
    enums = _load_enum_specs(data.get("datatypes", []))
    pydantic_models = _load_pydantic_model_specs(data.get("datatypes", []))
    type_aliases = _load_type_alias_specs(data.get("datatypes", []))
    generics = _load_generic_specs(data.get("datatypes", []))
    transforms = _load_transform_specs(data.get("transforms", []))
    dag_stages = _load_dag_stage_specs(data.get("dag_stages", []))
    checks = _load_check_specs(data.get("checks", []))
    examples = _load_example_specs(data.get("examples", []))
    generators = _load_generator_specs(data.get("generators", {}))

    return SpecIR(
        meta=meta,
        frames=frames,
        enums=enums,
        pydantic_models=pydantic_models,
        type_aliases=type_aliases,
        generics=generics,
        transforms=transforms,
        dag_stages=dag_stages,
        checks=checks,
        examples=examples,
        generators=generators,
    )


def _load_meta(meta_data: dict[str, Any], version: str) -> MetaSpec:
    """メタデータを読み込み"""
    return MetaSpec(
        name=meta_data.get("name", "unknown"),
        description=meta_data.get("description", ""),
        version=version,
    )


def _load_dataframe_specs(datatypes: list[dict[str, Any]]) -> list[FrameSpec]:
    """DataFrame定義をFrameSpecに変換"""
    frames = []
    for datatype in datatypes:
        if "dataframe_schema" not in datatype:
            continue

        schema = datatype["dataframe_schema"]
        frame = FrameSpec(
            id=datatype["id"],
            description=datatype.get("description", ""),
            index=_load_index(schema.get("index")) if "index" in schema else None,
            multi_index=_load_multi_index(schema.get("multi_index", [])),
            columns=_load_columns(schema.get("columns", [])),
            checks=schema.get("dataframe_checks", []),
            row_model=datatype.get("row_model"),
            generator_factory=datatype.get("generator_factory"),
            check_functions=datatype.get("check_functions", []),
            strict=schema.get("strict", False),
            coerce=schema.get("coerce", True),
            ordered=schema.get("ordered", False),
            examples=datatype.get("examples", []),
        )
        frames.append(frame)
    return frames


def _load_index(index_data: dict[str, Any] | list[dict[str, Any]]) -> IndexRule | None:
    """Index定義を読み込み"""
    if isinstance(index_data, list):
        # MultiIndexの場合はNoneを返す（multi_indexで処理）
        return None

    # dtypeが明示的にキーとして存在する場合はその値を使用、存在しない場合は空文字列
    # デフォルト値は設定しない（バリデーションでエラーを検出するため）
    dtype_value = index_data.get("dtype", "") or ""  # Noneまたは未設定は""に統一

    return IndexRule(
        name=index_data.get("name", "index"),
        dtype=dtype_value,
        nullable=index_data.get("nullable", False),
        unique=index_data.get("unique", False),
        monotonic=index_data.get("monotonic", ""),
        coerce=index_data.get("coerce", True),
        description=index_data.get("description", ""),
    )


def _load_multi_index(multi_index_data: list[dict[str, Any]]) -> list[MultiIndexLevel]:
    """MultiIndex定義を読み込み"""
    levels = []
    for level_data in multi_index_data:
        # dtypeが明示的にキーとして存在する場合はその値を使用、存在しない場合は空文字列
        # デフォルト値は設定しない（バリデーションでエラーを検出するため）
        dtype_value = level_data.get("dtype", "") or ""  # Noneまたは未設定は""に統一

        level = MultiIndexLevel(
            name=level_data.get("name", ""),
            dtype=dtype_value,
            enum=level_data.get("enum", []),
            description=level_data.get("description", ""),
        )
        levels.append(level)
    return levels


def _load_columns(columns_data: list[dict[str, Any]]) -> list[ColumnRule]:
    """Column定義を読み込み"""
    columns = []
    for col_data in columns_data:
        # dtypeが明示的にキーとして存在する場合はその値を使用、存在しない場合は空文字列
        # デフォルト値は設定しない（バリデーションでエラーを検出するため）
        dtype_value = col_data.get("dtype", "") or ""  # Noneまたは未設定は""に統一

        column = ColumnRule(
            name=col_data.get("name", ""),
            dtype=dtype_value,
            nullable=col_data.get("nullable", False),
            unique=col_data.get("unique", False),
            coerce=col_data.get("coerce", True),
            checks=col_data.get("checks", []),
            description=col_data.get("description", ""),
        )
        columns.append(column)
    return columns


def _load_enum_specs(datatypes: list[dict[str, Any]]) -> list[EnumSpec]:
    """Enum定義をEnumSpecに変換"""
    enums = []
    for datatype in datatypes:
        if "enum" not in datatype:
            continue

        enum_config = datatype["enum"]
        members = []
        for member_data in enum_config.get("members", []):
            member = EnumMemberSpec(
                name=member_data.get("name", ""),
                value=member_data.get("value", ""),
                description=member_data.get("description", ""),
            )
            members.append(member)

        enum = EnumSpec(
            id=datatype["id"],
            description=datatype.get("description", ""),
            base_type=enum_config.get("base_type", "str"),
            members=members,
            examples=datatype.get("examples", []),
            check_functions=datatype.get("check_functions", []),
        )
        enums.append(enum)
    return enums


def _load_pydantic_model_specs(datatypes: list[dict[str, Any]]) -> list[PydanticModelSpec]:
    """Pydanticモデル定義をPydanticModelSpecに変換"""
    models = []
    for datatype in datatypes:
        if "pydantic_model" not in datatype:
            continue

        pydantic_config = datatype["pydantic_model"]
        model = PydanticModelSpec(
            id=datatype["id"],
            description=datatype.get("description", ""),
            fields=pydantic_config.get("fields", []),
            base_class=pydantic_config.get("base_class", "BaseModel"),
            examples=datatype.get("examples", []),
            check_functions=datatype.get("check_functions", []),
        )
        models.append(model)
    return models


def _load_type_alias_specs(datatypes: list[dict[str, Any]]) -> list[TypeAliasSpec]:
    """型エイリアス定義をTypeAliasSpecに変換

    Note: dataframe_schemaが存在する場合、type_aliasがあっても
          FrameSpecとして扱うため、TypeAliasSpecには登録しない（重複回避）
    """
    aliases = []
    for datatype in datatypes:
        if "type_alias" not in datatype:
            continue

        # dataframe_schemaが存在する場合はFrameSpecとして扱うためスキップ
        if "dataframe_schema" in datatype:
            continue

        alias = TypeAliasSpec(
            id=datatype["id"],
            description=datatype.get("description", ""),
            type_def=datatype["type_alias"],
            examples=datatype.get("examples", []),
            check_functions=datatype.get("check_functions", []),
        )
        aliases.append(alias)
    return aliases


def _load_generic_specs(datatypes: list[dict[str, Any]]) -> list[GenericSpec]:
    """Generic型定義をGenericSpecに変換"""
    generics = []
    for datatype in datatypes:
        if "generic" not in datatype:
            continue

        generic_config = datatype["generic"]
        generic = GenericSpec(
            id=datatype["id"],
            description=datatype.get("description", ""),
            container=generic_config.get("container", "list"),
            element_type=generic_config.get("element_type"),
            key_type=generic_config.get("key_type"),
            value_type=generic_config.get("value_type"),
            elements=generic_config.get("elements", []),
            examples=datatype.get("examples", []),
            check_functions=datatype.get("check_functions", []),
        )
        generics.append(generic)
    return generics


def _load_parameters(params_data: list[dict[str, Any]]) -> list[ParameterSpec]:
    """パラメータ定義をParameterSpecに変換

    Args:
        params_data: パラメータデータのリスト

    Returns:
        ParameterSpecのリスト
    """
    parameters = []
    for param_data in params_data:
        param = ParameterSpec(
            name=param_data.get("name", ""),
            type_ref=param_data.get("datatype_ref") or param_data.get("native", ""),
            optional=param_data.get("optional", False),
            default=param_data.get("default"),
            description=param_data.get("description", ""),
        )
        parameters.append(param)
    return parameters


def _load_transform_specs(transforms_data: list[dict[str, Any]]) -> list[TransformSpec]:
    """Transform定義をTransformSpecに変換"""
    transforms = []
    for transform_data in transforms_data:
        parameters = _load_parameters(transform_data.get("parameters", []))

        transform = TransformSpec(
            id=transform_data.get("id", ""),
            description=transform_data.get("description", ""),
            impl=transform_data.get("impl", ""),
            file_path=transform_data.get("file_path", ""),
            parameters=parameters,
            return_type_ref=(
                transform_data.get("return_type_ref")
                or transform_data.get("return_datatype_ref")
                or transform_data.get("return_native")
            ),
            default_args=transform_data.get("default_args", {}),
            spec_metadata=transform_data.get("spec_metadata"),  # メタデータをパース
        )
        transforms.append(transform)
    return transforms


def _load_dag_stage_specs(dag_stages_data: list[dict[str, Any]]) -> list[DAGStageSpec]:
    """DAG Stage定義をDAGStageSpecに変換"""
    stages = []
    for stage_data in dag_stages_data:
        stage = DAGStageSpec(
            stage_id=stage_data.get("stage_id", ""),
            description=stage_data.get("description", ""),
            selection_mode=stage_data.get("selection_mode", "single"),
            max_select=stage_data.get("max_select"),
            input_type=stage_data.get("input_type", ""),
            output_type=stage_data.get("output_type", ""),
            candidates=stage_data.get("candidates", []),
            default_transform_id=stage_data.get("default_transform_id"),
            publish_output=stage_data.get("publish_output", False),
            collect_output=stage_data.get("collect_output", False),
        )
        stages.append(stage)
    return stages


def _load_check_specs(checks_data: list[dict[str, Any]]) -> list[CheckSpec]:
    """Check定義をCheckSpecに変換"""
    checks = []
    for check_data in checks_data:
        check = CheckSpec(
            id=check_data.get("id", ""),
            description=check_data.get("description", ""),
            impl=check_data.get("impl", ""),
            file_path=check_data.get("file_path", ""),
            input_type_ref=check_data.get("input_type_ref"),
        )
        checks.append(check)
    return checks


def _load_example_specs(examples_data: list[dict[str, Any]]) -> list[ExampleCase]:
    """Example定義をExampleCaseに変換"""
    examples = []
    for example_data in examples_data:
        example = ExampleCase(
            id=example_data.get("id", ""),
            description=example_data.get("description", ""),
            datatype_ref=example_data.get("datatype_ref", ""),
            transform_ref=example_data.get("transform_ref", ""),
            input=example_data.get("input", {}),
            expected=example_data.get("expected", {}),
        )
        examples.append(example)
    return examples


def _load_generator_specs(generators_data: dict[str, Any] | list[dict[str, Any]]) -> list[GeneratorDef]:
    """Generator定義をGeneratorDefに変換"""
    generators = []

    # dictまたはlistの両方をサポート
    items = generators_data.values() if isinstance(generators_data, dict) else generators_data

    for gen_data in items:
        if not isinstance(gen_data, dict):
            continue

        parameters = _load_parameters(gen_data.get("parameters", []))

        generator = GeneratorDef(
            id=gen_data.get("id", ""),
            description=gen_data.get("description", ""),
            impl=gen_data.get("impl", ""),
            file_path=gen_data.get("file_path", ""),
            parameters=parameters,
            return_type_ref=gen_data.get("return_type_ref", ""),
        )
        generators.append(generator)
    return generators

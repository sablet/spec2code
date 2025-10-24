"""
構造仕様ベースのコードスケルトン生成・検証システム - コアエンジン
"""

from __future__ import annotations

import argparse
import ast
import builtins
import importlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any, Callable, Generic, Iterable, Literal, TypeVar
from types import ModuleType

import jsonschema
import networkx as nx
import yaml
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from pydantic.fields import FieldInfo


# ==================== 型アノテーション用マーカー ====================

T = TypeVar("T")
AnnotationSource = TypeVar("AnnotationSource")
TypeContext = Literal["transform", "type_alias", "pydantic_model", "default"]

APP_MODULE_MIN_PARTS = 2


class Check(Generic[T]):
    """型アノテーション用のCheck参照マーカー

    Usage:
        Annotated[Out, Check["module.path.check_function"]]
    """

    def __class_getitem__(cls: type["Check"], item: str) -> type:
        """文字列でチェック関数を参照"""
        return type(f"Check[{item}]", (), {"__check_ref__": item})


class ExampleValue(Generic[T]):
    """型アノテーション用のExample値マーカー

    Usage:
        Annotated[In, ExampleValue[{"text": "hello world"}]]
    """

    def __class_getitem__(cls: type["ExampleValue"], item: dict[str, Any]) -> type:
        """辞書で例示値を参照"""
        return type(f"ExampleValue[{item}]", (), {"__example_value__": item})


# ==================== データモデル定義 ====================


class CheckDef(BaseModel):
    """チェック関数定義"""

    id: str
    description: str
    impl: str  # "module:function"形式
    file_path: str


class Example(BaseModel):
    """検証用入力・期待値定義"""

    id: str
    description: str
    input: dict[str, Any]
    expected: dict[str, Any]


class TypeAliasConfig(BaseModel):
    """型エイリアス定義"""

    type: Literal["simple", "tuple", "dict"]
    target: str | None = None
    elements: list[dict[str, Any]] = Field(default_factory=list)
    key_type: dict[str, Any] | None = None
    value_type: dict[str, Any] | None = None


class EnumMember(BaseModel):
    """Enumメンバー定義"""

    name: str
    value: Any
    description: str = ""


class EnumConfig(BaseModel):
    """Enum定義"""

    base_type: Literal["int", "str", "float"] = "str"
    members: list[EnumMember] = Field(default_factory=list)


class GenericConfig(BaseModel):
    """Generic型定義"""

    container: Literal["list", "dict", "set", "tuple"]
    element_type: dict[str, Any] | None = None  # list/set 用
    key_type: dict[str, Any] | None = None  # dict 用
    value_type: dict[str, Any] | None = None  # dict 用
    elements: list[dict[str, Any]] = Field(default_factory=list)  # tuple 用


class PandasMultiIndexLevel(BaseModel):
    """MultiIndexのレベル定義"""

    name: str
    type: str
    enum: list[str] = Field(default_factory=list)
    description: str = ""


class PandasMultiIndexConfig(BaseModel):
    """pandas MultiIndex構造定義"""

    axis: Literal[0, 1] = 0
    levels: list[PandasMultiIndexLevel]
    index_type: str = "default"


class PydanticFieldConfig(BaseModel):
    """Pydanticモデルのフィールド定義"""

    name: str
    type: dict[str, Any]
    required: bool = True
    optional: bool = False
    default: Any = None
    description: str = ""


class PydanticModelConfig(BaseModel):
    """Pydanticモデル定義"""

    fields: list[PydanticFieldConfig] = Field(default_factory=list)
    base_class: str = "BaseModel"


class DataType(BaseModel):
    """データ構造定義"""

    model_config = {"protected_namespaces": (), "populate_by_name": True}

    id: str
    description: str
    check_ids: list[str] = Field(default_factory=list)
    example_ids: list[str] = Field(default_factory=list)
    schema_def: dict[str, Any] | None = Field(default=None, alias="schema")  # JSON Schema
    type_alias: TypeAliasConfig | None = None
    enum: EnumConfig | None = None
    generic: GenericConfig | None = None
    pandas_multiindex: PandasMultiIndexConfig | None = None
    pydantic_model: PydanticModelConfig | None = None

    @model_validator(mode="after")
    def _validate_type_definition(self: "DataType") -> "DataType":
        type_fields = {
            "schema_def": self.schema_def,
            "type_alias": self.type_alias,
            "enum": self.enum,
            "generic": self.generic,
            "pandas_multiindex": self.pandas_multiindex,
            "pydantic_model": self.pydantic_model,
        }
        defined = [name for name, value in type_fields.items() if value]
        if not defined:
            message = (
                f"DataType '{self.id}' must define exactly one type "
                "(schema/type_alias/enum/generic/pandas_multiindex/pydantic_model)"
            )
            raise ValueError(message)
        if len(defined) > 1:
            message = f"DataType '{self.id}' must define exactly one type, got multiple: " f"{defined}"
            raise ValueError(message)
        return self


class Parameter(BaseModel):
    """関数パラメータ定義"""

    name: str
    datatype_ref: str | None = None
    native: str | None = None  # "builtins:type"形式
    optional: bool = False
    literal: list[str] = Field(default_factory=list)
    union: list[dict[str, Any]] = Field(default_factory=list)
    default: Any = None

    @model_validator(mode="after")
    def _validate_type_spec(self: "Parameter") -> "Parameter":
        type_fields = []
        if self.datatype_ref:
            type_fields.append("datatype_ref")
        if self.native:
            type_fields.append("native")
        if self.literal:
            type_fields.append("literal")
        if self.union:
            type_fields.append("union")
        if not type_fields:
            message = (
                f"Parameter '{self.name}' must specify at least one type definition "
                "(datatype_ref, native, literal, union)"
            )
            raise ValueError(message)
        return self


class Transform(BaseModel):
    """処理関数定義"""

    id: str
    description: str
    impl: str  # "module:function"形式
    file_path: str
    parameters: list[Parameter]
    return_datatype_ref: str | None = None
    return_native: str | None = None  # "module:type"形式（戻り値の型指定）
    default_args: dict[str, Any] = Field(default_factory=dict)


class DAGEdge(BaseModel):
    """DAGエッジ定義"""

    model_config = {"populate_by_name": True}

    from_: str = Field(alias="from")
    to: str | None


class Meta(BaseModel):
    """メタデータ"""

    name: str
    description: str


class DAGStage(BaseModel):
    """DAG stage definition (for unified dag_stages representation)"""

    stage_id: str
    description: str
    selection_mode: str = "single"  # single, exclusive, multiple
    max_select: int | None = None
    input_type: str
    output_type: str
    candidates: list[str] = Field(default_factory=list)  # transform_ids
    default_transform_id: str | None = None


class Spec(BaseModel):
    """仕様全体のルートモデル"""

    version: str
    meta: Meta
    checks: list[CheckDef] = Field(default_factory=list)
    examples: list[Example] = Field(default_factory=list)
    datatypes: list[DataType] = Field(default_factory=list)
    transforms: list[Transform] = Field(default_factory=list)
    dag: list[DAGEdge] = Field(default_factory=list)
    dag_stages: list[DAGStage] = Field(default_factory=list)


# ==================== 仕様読み込み・検証 ====================


def load_spec(spec_path: str | Path) -> Spec:
    """YAML/JSON仕様を読み込み、Pydanticで検証"""
    spec_path = Path(spec_path)
    with open(spec_path) as f:
        if spec_path.suffix in [".yaml", ".yml"]:
            data = yaml.safe_load(f)
        elif spec_path.suffix == ".json":
            data = json.load(f)
        else:
            raise ValueError(f"未対応のファイル形式: {spec_path.suffix}")

    spec = Spec(**data)
    _convert_dag_to_stages(spec)
    return spec


def _convert_dag_to_stages(spec: Spec) -> None:
    """Convert legacy dag format to dag_stages format

    If dag_stages is empty but dag exists, generate dag_stages from DAG topology.
    Each transform becomes a single-mode stage with one candidate.
    """
    if spec.dag_stages or not spec.dag:
        return

    transform_by_id = {transform.id: transform for transform in spec.transforms}
    ordered_transforms = _topologically_order_transforms(spec.dag)

    spec.dag_stages = [
        _stage_from_transform(transform_by_id[transform_id], index)
        for index, transform_id in enumerate(ordered_transforms, start=1)
        if transform_id in transform_by_id
    ]


def _topologically_order_transforms(dag_edges: list[DAGEdge]) -> list[str]:
    """Return transforms in topological order, falling back to input order."""
    import networkx as nx

    graph: nx.DiGraph = nx.DiGraph()
    for edge in dag_edges:
        if edge.to is not None:
            graph.add_edge(edge.from_, edge.to)
        else:
            graph.add_node(edge.from_)

    try:
        return list(nx.topological_sort(graph))
    except nx.NetworkXError:
        return [edge.from_ for edge in dag_edges]


def _infer_input_type(transform: Transform) -> str:
    """Infer input type from the first parameter."""
    if not transform.parameters:
        return "Any"
    first_param = transform.parameters[0]
    return first_param.datatype_ref or first_param.native or "Any"


def _infer_output_type(transform: Transform) -> str:
    """Infer output type from transform definition."""
    return transform.return_datatype_ref or transform.return_native or "Any"


def _stage_from_transform(transform: Transform, index: int) -> DAGStage:
    """Build a single-selection stage from a transform definition."""
    stage_id = f"stage_{index}_{transform.id}"
    description = transform.description or f"Stage {index}: {transform.id}"
    return DAGStage(
        stage_id=stage_id,
        description=description,
        selection_mode="single",
        input_type=_infer_input_type(transform),
        output_type=_infer_output_type(transform),
        candidates=[transform.id],
        default_transform_id=transform.id,
    )


# ==================== デフォルトConfig生成 ====================


def _infer_default_value_for_param(param: Parameter) -> Any:  # noqa: ANN401
    """Infer a reasonable default value for a parameter based on its type."""
    if param.native:
        type_name = param.native.split(":")[-1]
        if type_name == "int":
            if param.name in {"window", "n_lags", "size", "length", "count"}:
                return 2
            return 0
        if type_name == "float":
            return 0.0
        if type_name == "str":
            return ""
        if type_name == "bool":
            return False
    return None


def _build_default_stage_config(spec: Spec, stage: DAGStage) -> dict[str, Any] | None:
    """Build default config for a single DAG stage."""
    if stage.selection_mode == "single":
        return None

    if not stage.default_transform_id:
        return None

    transform = next((t for t in spec.transforms if t.id == stage.default_transform_id), None)
    if not transform:
        return None

    params: dict[str, Any] = {}
    for idx, param in enumerate(transform.parameters):
        if idx == 0:
            continue

        has_default = "default" in getattr(param, "model_fields_set", set())
        if has_default and param.default is not None:
            params[param.name] = param.default
        elif param.optional:
            continue
        else:
            inferred_value = _infer_default_value_for_param(param)
            if inferred_value is not None:
                params[param.name] = inferred_value

    selection = {"transform_id": transform.id}
    if params:
        selection["params"] = params

    return {"stage_id": stage.stage_id, "selected": [selection]}


def _auto_collect_stage_candidates(spec: Spec) -> None:
    """Auto-collect candidates for DAG stages based on input_type/output_type."""
    for stage in spec.dag_stages:
        if stage.candidates:
            continue

        matched_transforms = []
        for transform in spec.transforms:
            if not transform.parameters:
                continue

            first_param = transform.parameters[0]
            param_type = first_param.datatype_ref
            return_type = transform.return_datatype_ref

            if param_type == stage.input_type and return_type == stage.output_type:
                matched_transforms.append(transform.id)

        if matched_transforms:
            stage.candidates = matched_transforms

        if not stage.default_transform_id and stage.candidates:
            stage.default_transform_id = stage.candidates[0]


def generate_default_config(spec: Spec, project_root: Path = Path(".")) -> None:
    """Generate default config file from spec with dag_stages."""
    print("📝 Generating default config...")

    if not spec.dag_stages:
        print("  ⏭️  No dag_stages defined in spec (skipped)")
        return

    _auto_collect_stage_candidates(spec)

    app_package = _infer_app_package(spec)
    config_dir = project_root / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_filename = f"{app_package}-default-config.yaml"
    config_path = config_dir / config_filename

    stages = []
    for stage in spec.dag_stages:
        stage_config = _build_default_stage_config(spec, stage)
        if stage_config:
            stages.append(stage_config)

    config_data = {
        "version": spec.version,
        "meta": {
            "config_name": f"{app_package}-default",
            "description": f"Default configuration for {spec.meta.name}",
            "base_spec": f"specs/{spec.meta.name}.yaml",
        },
        "execution": {"stages": stages},
    }

    config_path.write_text(yaml.dump(config_data, default_flow_style=False, sort_keys=False))
    print(f"  ✅ Generated: {config_path}")


# ==================== スケルトンコード生成 ====================


def _resolve_native_type(native: str | None) -> tuple[str, set[str]]:
    """Return base type string and required imports for native notation."""
    if not native:
        return "dict", set()

    module, type_name = native.split(":")
    if module == "builtins":
        return type_name, set()
    if module == "pandas":
        return f"pd.{type_name}", {"import pandas as pd"}
    if module == "typing":
        return type_name, {f"from typing import {type_name}"}
    return f"{module}.{type_name}", {f"import {module}"}


def _normalize_module_name(name: str) -> str:
    """Normalize spec meta name to a valid Python module segment."""
    return name.replace("-", "_")


def _infer_app_package(spec: "Spec") -> str:
    """Infer the app package name from implementation paths."""

    def _candidate_from_impl(impl: str | None) -> str | None:
        module_path, _, _ = (impl or "").partition(":")
        if not module_path.startswith("apps."):
            return None
        parts = module_path.split(".")
        return parts[1] if len(parts) >= APP_MODULE_MIN_PARTS else None

    def _collect_candidates(impls: Iterable[str | None]) -> set[str]:
        return {candidate for candidate in (_candidate_from_impl(impl) for impl in impls) if candidate}

    candidates = _collect_candidates(transform.impl for transform in spec.transforms)
    if not candidates:
        candidates = _collect_candidates(check.impl for check in spec.checks)

    if not candidates:
        return spec.meta.name

    if len(candidates) > 1:
        sorted_candidates = ", ".join(sorted(candidates))
        raise ValueError(f"Spec references multiple app packages: {sorted_candidates}")

    return next(iter(candidates))


def _resolve_datatype_reference(
    spec: "Spec", datatype_ref: str, context: TypeContext = "default"
) -> tuple[str, set[str]]:
    """Resolve datatype reference to concrete type string and imports."""
    datatype = next((dt for dt in spec.datatypes if dt.id == datatype_ref), None)
    if not datatype:
        return datatype_ref, set()

    normalized_app = _normalize_module_name(spec.meta.name)
    resolved_type = datatype.id
    imports: set[str] = set()

    if datatype.generic:
        resolved_type, imports = _build_generic_type(spec, datatype.generic, context)
    elif datatype.pandas_multiindex:
        # MultiIndex構造はDataFrameで表現
        resolved_type = "pd.DataFrame"
        imports = {"import pandas as pd"}
    elif datatype.schema_def:
        # JSON Schema定義はdictとして扱う
        resolved_type = "dict"
        imports = set()
    else:
        imports = _imports_for_datatype(datatype, context, normalized_app)

    return resolved_type, imports


def _import_line_for_datatype(datatype: DataType, suffix: str, context: TypeContext, normalized_app: str) -> str | None:
    """Return import line for a datatype based on context."""
    if context == "transform":
        return f"from ..datatypes.{suffix} import {datatype.id}"
    if context == "type_alias":
        if suffix == "type_aliases":
            # Avoid self-import within type_aliases.py
            return None
        return f"from .{suffix} import {datatype.id}"
    if context == "pydantic_model":
        return f"from .{suffix} import {datatype.id}"
    return f"from apps.{normalized_app}.datatypes.{suffix} import {datatype.id}"


def _imports_for_datatype(datatype: DataType, context: TypeContext, normalized_app: str) -> set[str]:
    """Determine required imports for enum/pydantic/type alias datatypes."""
    suffix_priority = [
        ("enum", "enums"),
        ("pydantic_model", "models"),
        ("type_alias", "type_aliases"),
    ]
    for attr, suffix in suffix_priority:
        if getattr(datatype, attr):
            line = _import_line_for_datatype(datatype, suffix, context, normalized_app)
            return {line} if line else set()
    return set()


def _build_generic_type(spec: "Spec", config: GenericConfig, context: TypeContext) -> tuple[str, set[str]]:
    """Build a generic type string (list, dict, set, tuple)."""

    def _list_type() -> tuple[str, set[str]]:
        element_type, element_imports = _build_type_string(spec, config.element_type or {}, Path("."), context=context)
        return f"list[{element_type}]", element_imports

    def _set_type() -> tuple[str, set[str]]:
        element_type, element_imports = _build_type_string(spec, config.element_type or {}, Path("."), context=context)
        return f"set[{element_type}]", element_imports

    def _tuple_type() -> tuple[str, set[str]]:
        parts: list[str] = []
        imports: set[str] = set()
        for element in config.elements:
            part, part_imports = _build_type_string(spec, element, Path("."), context=context)
            parts.append(part)
            imports.update(part_imports)
        joined = ", ".join(parts) if parts else "Any"
        return f"tuple[{joined}]", imports

    def _dict_type() -> tuple[str, set[str]]:
        key_type_config = config.key_type or {"native": "builtins:str"}
        value_type_config = config.value_type or {"native": "typing:Any"}
        key_type, key_imports = _build_type_string(spec, key_type_config, Path("."), context=context)
        value_type, value_imports = _build_type_string(spec, value_type_config, Path("."), context=context)
        imports = set(key_imports)
        imports.update(value_imports)
        return f"dict[{key_type}, {value_type}]", imports

    builders: dict[str, Callable[[], tuple[str, set[str]]]] = {
        "list": _list_type,
        "set": _set_type,
        "tuple": _tuple_type,
        "dict": _dict_type,
    }
    builder = builders.get(config.container)
    if builder is None:
        return "dict", set()
    return builder()


def _type_string_from_literal(values: list[Any]) -> tuple[str, set[str]]:
    rendered = ", ".join(repr(v) for v in values)
    return f"Literal[{rendered}]", {"from typing import Literal"}


def _type_string_from_union(
    spec: "Spec",
    union_items: list[dict[str, Any]],
    app_root: Path | None,
    context: TypeContext,
) -> tuple[str, set[str]]:
    parts: list[str] = []
    imports: set[str] = set()
    for union_item in union_items:
        part_str, part_imports = _build_type_string(spec, union_item, app_root or Path("."), context=context)
        parts.append(part_str)
        imports.update(part_imports)
    joined = " | ".join(parts) if parts else "dict"
    return joined, imports


def _type_string_from_native(native: str) -> tuple[str, set[str]]:
    return _resolve_native_type(native)


def _type_string_from_ref(spec: "Spec", ref: str, context: TypeContext) -> tuple[str, set[str]]:
    return _resolve_datatype_reference(spec, ref, context)


def _type_string_from_generic(
    spec: "Spec", generic_config: dict[str, Any], context: TypeContext
) -> tuple[str, set[str]]:
    config = GenericConfig(**generic_config)
    return _build_generic_type(spec, config, context=context)


def _resolve_type_from_config(
    spec: "Spec",
    type_config: dict[str, Any],
    app_root: Path | None,
    context: TypeContext,
) -> tuple[str, set[str]]:
    handlers: list[tuple[str, Callable[[Any], tuple[str, set[str]]]]] = [
        ("literal", lambda value: _type_string_from_literal(value)),
        (
            "union",
            lambda value: _type_string_from_union(spec, value, app_root, context),
        ),
        ("native", lambda value: _type_string_from_native(value)),
        ("datatype_ref", lambda value: _type_string_from_ref(spec, value, context)),
        ("generic", lambda value: _type_string_from_generic(spec, value, context)),
    ]
    for key, handler in handlers:
        value = type_config.get(key)
        if value:
            return handler(value)
    return "dict", set()


def _append_optional(type_str: str, is_optional: bool) -> str:
    if not is_optional:
        return type_str
    parts = [part.strip() for part in type_str.split("|")]
    return type_str if "None" in parts else f"{type_str} | None"


def _build_type_string(
    spec: "Spec",
    type_config: dict[str, Any] | None,
    app_root: Path | None = None,
    *,
    context: TypeContext = "default",
) -> tuple[str, set[str]]:
    """Unified type string builder handling native, datatype_ref, literal, union."""
    if type_config is None:
        return "dict", set()

    base_type, imports = _resolve_type_from_config(spec, type_config, app_root, context)
    type_str = _append_optional(base_type, type_config.get("optional", False))
    return type_str, imports


def _parameter_type_config(param: Parameter) -> dict[str, Any]:
    """Build a type configuration dictionary from a Parameter instance."""
    config: dict[str, Any] = {}
    if param.literal:
        config["literal"] = param.literal
    elif param.union:
        config["union"] = param.union
    elif param.native:
        config["native"] = param.native
    elif param.datatype_ref:
        config["datatype_ref"] = param.datatype_ref
    else:
        config["native"] = "builtins:dict"

    if param.optional:
        config["optional"] = True

    return config


def _return_type_config(transform: Transform) -> dict[str, Any]:
    """Build a type configuration dictionary for a transform return value."""
    config: dict[str, Any] = {}
    if transform.return_native:
        config["native"] = transform.return_native
    if transform.return_datatype_ref and "native" not in config:
        config["datatype_ref"] = transform.return_datatype_ref
    if not config and transform.return_datatype_ref:
        config["datatype_ref"] = transform.return_datatype_ref
    if not config:
        config["native"] = "builtins:dict"
    return config


def _collect_datatype_annotations(
    spec: Spec,
    datatype_ref: str | None,
    id_iter: Callable[[DataType], Iterable[str]],
    fetch: Callable[[str], AnnotationSource | None],
    formatter: Callable[[AnnotationSource], str],
    import_statement: str,
) -> tuple[list[str], set[str]]:
    if not datatype_ref:
        return [], set()

    datatype = next((dt for dt in spec.datatypes if dt.id == datatype_ref), None)
    if not datatype:
        return [], set()

    annotations: list[str] = []
    for item_id in id_iter(datatype):
        item = fetch(item_id)
        if item is not None:
            annotations.append(formatter(item))

    imports = {import_statement} if annotations else set()
    return annotations, imports


def _find_example(spec: Spec, example_id: str) -> Example | None:
    return next(
        (example for example in spec.examples if example.id == example_id),
        None,
    )


def _find_check(spec: Spec, check_id: str) -> CheckDef | None:
    return next((check for check in spec.checks if check.id == check_id), None)


def _collect_example_annotations(spec: Spec, datatype_ref: str | None) -> tuple[list[str], set[str]]:
    return _collect_datatype_annotations(
        spec,
        datatype_ref,
        lambda datatype: datatype.example_ids,
        lambda example_id: _find_example(spec, example_id),
        lambda example: f"ExampleValue[{example.input}]",
        "from spec2code.engine import ExampleValue",
    )


def _collect_check_annotations(spec: Spec, datatype_ref: str | None) -> tuple[list[str], set[str]]:
    return _collect_datatype_annotations(
        spec,
        datatype_ref,
        lambda datatype: datatype.check_ids,
        lambda check_id: _find_check(spec, check_id),
        lambda check_def: f'Check["{check_def.impl}"]',
        "from spec2code.engine import Check",
    )


def _build_type_annotation(spec: Spec, param: Parameter, app_root: Path) -> tuple[str, set[str]]:
    """パラメータの型アノテーションを構築（Inputパラメータ用：Exampleのみ適用）"""
    type_config = _parameter_type_config(param)
    base_type, imports = _build_type_string(spec, type_config, app_root, context="transform")
    annotations, annotation_imports = _collect_example_annotations(spec, param.datatype_ref)
    imports.update(annotation_imports)

    if annotations:
        imports.add("from typing import Annotated")
        joined = ", ".join(annotations)
        return f"Annotated[{base_type}, {joined}]", imports

    return base_type, imports


def _build_return_annotation(spec: Spec, transform: Transform, app_root: Path) -> tuple[str, set[str]]:
    """戻り値の型アノテーションを構築（Outputパラメータ用：Checkのみ適用）"""
    type_config = _return_type_config(transform)
    base_type, imports = _build_type_string(spec, type_config, app_root, context="transform")
    annotations, annotation_imports = _collect_check_annotations(spec, transform.return_datatype_ref)
    imports.update(annotation_imports)

    if annotations:
        imports.add("from typing import Annotated")
        joined = ", ".join(annotations)
        return f"Annotated[{base_type}, {joined}]", imports

    return base_type, imports


def _generate_check_skeletons(spec: Spec, app_root: Path) -> None:
    """Generate skeleton files for checks grouped by file path."""
    grouped_checks: dict[Path, list[CheckDef]] = {}
    for check in spec.checks:
        file_path = app_root / check.file_path
        grouped_checks.setdefault(file_path, []).append(check)

    for file_path, checks in grouped_checks.items():
        if file_path.exists():
            print(f"  ⏭️  Skip (exists): {file_path}")
            continue

        file_path.parent.mkdir(parents=True, exist_ok=True)
        functions = []
        for check in checks:
            func_name = check.impl.split(":")[-1]
            functions.append(
                f'''def {func_name}(payload: dict) -> bool:
    """{check.description}"""
    # TODO: implement validation logic
    return True
'''
            )

        code = "# Auto-generated skeleton for Check functions\n" f"{chr(10).join(functions)}\n"
        file_path.write_text(code)
        print(f"  ✅ Generated: {file_path}")


def _render_imports(imports: set[str]) -> str:
    """Build import section for generated transform skeletons."""
    if not imports:
        return ""

    spec2code_imports = set()
    other_imports = set()
    for imp in imports:
        if imp.startswith("from spec2code.engine import"):
            parts = imp.split("import", 1)[1].strip()
            spec2code_imports.add(parts)
        else:
            other_imports.add(imp)

    rendered_lines: list[str] = []
    if spec2code_imports:
        rendered_lines.append("from spec2code.engine import " f"{', '.join(sorted(spec2code_imports))}")
    rendered_lines.extend(sorted(other_imports))
    return "\n".join(rendered_lines)


def _render_sorted_imports(imports: set[str]) -> str:
    """Render imports as sorted lines."""
    return "\n".join(sorted(imports)) if imports else ""


def _type_alias_target_string(spec: Spec, datatype: DataType, app_root: Path) -> tuple[str, set[str]]:
    """Build the target type string for a TypeAlias datatype."""
    config = datatype.type_alias
    if not config:
        return "dict", set()

    def _simple_target() -> tuple[str, set[str]]:
        target_config: dict[str, Any]
        if config.target and ":" in config.target:
            target_config = {"native": config.target}
        elif config.target:
            target_config = {"datatype_ref": config.target}
        else:
            target_config = {"native": "builtins:dict"}
        return _build_type_string(spec, target_config, app_root, context="type_alias")

    def _tuple_target() -> tuple[str, set[str]]:
        parts: list[str] = []
        imports: set[str] = set()
        for element in config.elements:
            part, part_imports = _build_type_string(spec, element, app_root, context="type_alias")
            parts.append(part)
            imports.update(part_imports)
        if not parts:
            imports.add("from typing import Any")
            return "tuple[Any, ...]", imports
        return f"tuple[{', '.join(parts)}]", imports

    def _dict_target() -> tuple[str, set[str]]:
        key_type_config = config.key_type or {"native": "builtins:str"}
        value_type_config = config.value_type or {"native": "typing:Any"}
        key_type, key_imports = _build_type_string(spec, key_type_config, app_root, context="type_alias")
        value_type, value_imports = _build_type_string(spec, value_type_config, app_root, context="type_alias")
        imports = set(key_imports)
        imports.update(value_imports)
        return f"dict[{key_type}, {value_type}]", imports

    builders: dict[str, Callable[[], tuple[str, set[str]]]] = {
        "simple": _simple_target,
        "tuple": _tuple_target,
        "dict": _dict_target,
    }
    builder = builders.get(config.type)
    if builder is None:
        return "dict", set()
    return builder()


def _generate_type_aliases(spec: Spec, datatypes: list[DataType], app_root: Path) -> None:
    """Generate type alias definitions file."""
    file_path = app_root / "datatypes" / "type_aliases.py"
    if file_path.exists():
        print(f"  ⏭️  Skip (exists): {file_path}")
        return

    file_path.parent.mkdir(parents=True, exist_ok=True)
    imports: set[str] = {"from typing import TypeAlias"}
    alias_blocks: list[str] = []

    for datatype in datatypes:
        alias_type, alias_imports = _type_alias_target_string(spec, datatype, app_root)
        imports.update(alias_imports)
        description_comment = f"# {datatype.description}" if datatype.description else ""
        block_lines = []
        if description_comment:
            block_lines.append(description_comment)
        block_lines.append(f"{datatype.id}: TypeAlias = {alias_type}")
        alias_blocks.append("\n".join(block_lines))

    lines = [
        "# Auto-generated Type Alias definitions",
        "from __future__ import annotations",
        "",
    ]
    import_block = _render_sorted_imports(imports)
    if import_block:
        lines.append(import_block)
        lines.append("")
    lines.extend("\n\n".join(alias_blocks).split("\n"))
    lines.append("")
    file_path.write_text("\n".join(lines))
    print(f"  ✅ Generated: {file_path}")


def _generate_enum_file(spec: Spec, datatypes: list[DataType], app_root: Path) -> None:
    """Generate Enum definitions file."""
    file_path = app_root / "datatypes" / "enums.py"
    if file_path.exists():
        print(f"  ⏭️  Skip (exists): {file_path}")
        return

    file_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Auto-generated Enum definitions",
        "from __future__ import annotations",
        "from enum import Enum",
        "",
    ]

    for datatype in datatypes:
        lines.append(f"class {datatype.id}(Enum):")
        description = datatype.description or ""
        if description:
            lines.append(f'    """{description}"""')
        members = datatype.enum.members if datatype.enum else []
        if not members:
            lines.append("    pass")
        else:
            for member in members:
                lines.append(f"    {member.name} = {repr(member.value)}")
        lines.append("")

    file_path.write_text("\n".join(lines))
    print(f"  ✅ Generated: {file_path}")


def _generate_pydantic_models(spec: Spec, datatypes: list[DataType], app_root: Path) -> None:
    """Generate Pydantic model definitions file."""
    file_path = app_root / "datatypes" / "models.py"
    if file_path.exists():
        print(f"  ⏭️  Skip (exists): {file_path}")
        return

    file_path.parent.mkdir(parents=True, exist_ok=True)
    imports: set[str] = {"from pydantic import BaseModel"}
    body_lines: list[str] = []

    for datatype in datatypes:
        class_lines, model_imports = _collect_pydantic_model_lines(spec, datatype, app_root)
        if not class_lines:
            continue
        imports.update(model_imports)
        body_lines.extend(class_lines)
        body_lines.append("")

    if not body_lines:
        # No models to generate
        print(f"  ⏭️  Skip (no models): {file_path}")
        return

    header_lines = [
        "# Auto-generated Pydantic models",
        "from __future__ import annotations",
    ]
    import_block = _render_sorted_imports(imports)
    if import_block:
        header_lines.append(import_block)
    header_lines.append("")

    header_lines.extend(body_lines)
    file_path.write_text("\n".join(header_lines))
    print(f"  ✅ Generated: {file_path}")


def _collect_pydantic_model_lines(spec: Spec, datatype: DataType, app_root: Path) -> tuple[list[str], set[str]]:
    """Build class definition lines for a Pydantic model datatype."""
    model_config = datatype.pydantic_model
    if not model_config:
        return [], set()

    imports: set[str] = set()
    lines = [f"class {datatype.id}({model_config.base_class}):"]

    description = datatype.description or ""
    if description:
        lines.append(f'    """{description}"""')

    fields = model_config.fields
    if not fields:
        lines.append("    pass")
        return lines, imports

    for field in fields:
        type_str, type_imports = _build_type_string(spec, field.type, app_root, context="pydantic_model")
        imports.update(type_imports)
        field_line = f"    {field.name}: {type_str}"
        has_default = "default" in field.model_fields_set
        if has_default:
            field_line += f" = {repr(field.default)}"
        elif field.optional or not field.required:
            field_line += " = None"
        lines.append(field_line)

    return lines, imports


def _render_transform_function(spec: Spec, transform: Transform, app_root: Path) -> tuple[str, set[str]]:
    """Render transform function skeleton and required imports."""
    func_name = transform.impl.split(":")[-1]

    param_strs = []
    all_imports: set[str] = set()
    for param in transform.parameters:
        type_str, imports = _build_type_annotation(spec, param, app_root)
        all_imports.update(imports)
        has_explicit_default = "default" in getattr(param, "model_fields_set", set())
        default_value = None
        if has_explicit_default:
            default_value = param.default
        elif param.optional:
            default_value = None

        if has_explicit_default or param.optional:
            param_strs.append(f"{param.name}: {type_str} = {repr(default_value)}")
        else:
            param_strs.append(f"{param.name}: {type_str}")

    return_type, return_imports = _build_return_annotation(spec, transform, app_root)
    all_imports.update(return_imports)

    params = ", ".join(param_strs)
    code = f'''# Auto-generated skeleton for Transform: {transform.id}
def {func_name}({params}) -> {return_type}:
    """{transform.description}"""
    # TODO: implement transform logic
    return {{}}
'''
    return code, all_imports


def _extract_existing_function_names(source: str) -> set[str]:
    """Extract function names defined in existing Python source."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}


def _ensure_trailing_newline(text: str) -> str:
    """Ensure text ends with a newline."""
    return text if text.endswith("\n") else f"{text}\n"


def _find_import_block_range(lines: list[str]) -> tuple[int | None, int | None]:
    """Find the range of existing import statements."""
    first_import_idx: int | None = None
    last_import_idx: int | None = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("import ", "from ")):
            if first_import_idx is None:
                first_import_idx = idx
            last_import_idx = idx
        elif first_import_idx is not None:
            break
    return first_import_idx, last_import_idx


def _extract_existing_imports(lines: list[str], start_idx: int, end_idx: int) -> set[str]:
    """Extract existing import statements from a line range."""
    existing_imports: set[str] = set()
    for idx in range(start_idx, end_idx + 1):
        stripped = lines[idx].strip()
        if stripped.startswith(("import ", "from ")):
            existing_imports.add(stripped)
    return existing_imports


def _find_insertion_point(lines: list[str]) -> int:
    """Find the appropriate position to insert import statements."""
    insertion_idx = 0
    while insertion_idx < len(lines):
        stripped = lines[insertion_idx].strip()
        if not stripped or stripped.startswith("#"):
            insertion_idx += 1
            continue
        if stripped.startswith(("'''", '"""')):
            insertion_idx = _skip_docstring(lines, insertion_idx, stripped[:3])
            continue
        break
    return insertion_idx


def _skip_docstring(lines: list[str], start_idx: int, quote: str) -> int:
    """Skip over a docstring block and return the index after it."""
    idx = start_idx + 1
    while idx < len(lines):
        if quote in lines[idx]:
            return idx + 1
        idx += 1
    return idx


def _merge_with_existing_imports(lines: list[str], first_idx: int, last_idx: int, new_imports: set[str]) -> str:
    """Merge new imports with existing import block."""
    existing_imports = _extract_existing_imports(lines, first_idx, last_idx)
    combined_imports = existing_imports | new_imports
    rendered = _render_imports(combined_imports)
    prefix = lines[:first_idx]
    suffix = lines[last_idx + 1 :]
    rendered_lines = rendered.splitlines()
    if suffix and suffix[0].strip():
        rendered_lines.append("")
    merged = prefix + rendered_lines + suffix
    return _ensure_trailing_newline("\n".join(merged))


def _insert_imports_at_top(lines: list[str], new_imports: set[str]) -> str:
    """Insert new imports at the appropriate position at the top of the file."""
    rendered = _render_imports(new_imports)
    if not rendered:
        return _ensure_trailing_newline("\n".join(lines))

    insertion_idx = _find_insertion_point(lines)
    new_lines = lines[:insertion_idx] + rendered.splitlines()
    remaining = lines[insertion_idx:]
    if remaining and (not remaining[0].strip()):
        new_lines += remaining
    else:
        new_lines += [""] + remaining
    return _ensure_trailing_newline("\n".join(new_lines))


def _merge_imports_into_code(source: str, new_imports: set[str]) -> str:
    """Insert or update import statements in the existing source."""
    if not new_imports:
        return _ensure_trailing_newline(source)

    lines = source.splitlines()
    first_import_idx, last_import_idx = _find_import_block_range(lines)

    if first_import_idx is not None and last_import_idx is not None:
        return _merge_with_existing_imports(lines, first_import_idx, last_import_idx, new_imports)

    return _insert_imports_at_top(lines, new_imports)


def _write_transform_file(spec: Spec, transforms: list[Transform], app_root: Path) -> None:
    """Create or update a transform module with the provided transforms."""
    relative_path = transforms[0].file_path
    file_path = app_root / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)

    existing_code = ""
    existing_functions: set[str] = set()
    if file_path.exists():
        existing_code = file_path.read_text()
        existing_functions = _extract_existing_function_names(existing_code)

    new_blocks: list[str] = []
    required_imports: set[str] = set()
    for transform in transforms:
        func_name = transform.impl.split(":")[-1]
        if func_name in existing_functions:
            print(f"  ⏭️  Skip (exists): {file_path}::{func_name}")
            continue
        block, imports = _render_transform_function(spec, transform, app_root)
        new_blocks.append(block)
        required_imports.update(imports)

    if not file_path.exists():
        if not new_blocks:
            print(f"  ⏭️  Skip (exists): {file_path}")
            return
        header = "# Auto-generated skeleton for Transform functions\n"
        imports_block = _render_imports(required_imports)
        sections = [header]
        if imports_block:
            sections.append(f"{imports_block}\n")
        sections.append("\n\n".join(new_blocks))
        content = "\n".join(sections)
        if not content.endswith("\n"):
            content += "\n"
        file_path.write_text(content)
        print(f"  ✅ Generated: {file_path}")
        return

    if not new_blocks:
        print(f"  ⏭️  Skip (up-to-date): {file_path}")
        return

    updated_code = _merge_imports_into_code(existing_code, required_imports)
    append_block = "\n\n".join(new_blocks)
    updated_code = updated_code.rstrip("\n")
    updated_code = f"{updated_code}\n\n{append_block}\n"
    file_path.write_text(updated_code)
    print(f"  ✏️  Appended {len(new_blocks)} transform(s): {file_path}")


def _generate_transform_skeletons(spec: Spec, app_root: Path) -> None:
    """Generate skeleton files for all transforms, grouping by file path."""
    grouped: dict[str, list[Transform]] = {}
    for transform in spec.transforms:
        grouped.setdefault(transform.file_path, []).append(transform)

    for transforms in grouped.values():
        _write_transform_file(spec, transforms, app_root)


def _ensure_package_inits(app_root: Path) -> None:
    """Ensure __init__.py files exist for generated packages."""
    for directory in ["checks", "transforms", "datatypes"]:
        init_path = app_root / directory / "__init__.py"
        if init_path.exists():
            continue
        init_path.parent.mkdir(parents=True, exist_ok=True)
        init_path.write_text("# Auto-generated\n")
        print(f"  ✅ Generated: {init_path}")


def generate_skeleton(spec: Spec, project_root: Path = Path(".")) -> None:
    """未実装ファイルを自動生成"""
    print("🔨 Generating skeleton code...")
    app_package = _infer_app_package(spec)
    app_root = project_root / "apps" / app_package
    print(f"  📁 Target directory: {app_root}")
    enum_datatypes = [dt for dt in spec.datatypes if dt.enum]
    if enum_datatypes:
        _generate_enum_file(spec, enum_datatypes, app_root)
    model_datatypes = [dt for dt in spec.datatypes if dt.pydantic_model]
    if model_datatypes:
        _generate_pydantic_models(spec, model_datatypes, app_root)
    alias_datatypes = [dt for dt in spec.datatypes if dt.type_alias]
    if alias_datatypes:
        _generate_type_aliases(spec, alias_datatypes, app_root)
    _generate_check_skeletons(spec, app_root)
    _generate_transform_skeletons(spec, app_root)
    _ensure_package_inits(app_root)
    generate_default_config(spec, project_root)


# ==================== DAG検証・実行エンジン ====================


class Engine:
    """コア実行・検証・生成エンジン"""

    def __init__(self: "Engine", spec: Spec):
        self.spec = spec
        self.app_package = _infer_app_package(spec)
        self.graph = self._build_dag()

    def _build_dag(self: "Engine") -> nx.DiGraph:
        """DAGを構築"""
        g: nx.DiGraph = nx.DiGraph()

        # Transformをノードとして追加
        for transform in self.spec.transforms:
            g.add_node(transform.id)

        # エッジを追加
        for edge in self.spec.dag:
            if edge.to is None:
                # 終端ノード
                continue
            g.add_edge(edge.from_, edge.to)

        # DAG検証（サイクルがないか）
        if not nx.is_directed_acyclic_graph(g):
            raise ValueError("❌ DAGにサイクルが存在します")

        return g

    def validate_schemas(self: "Engine") -> None:
        """JSON Schema検証"""
        print("🔍 Validating schemas...")
        for datatype in self.spec.datatypes:
            if not datatype.schema_def:
                print(f"  ⏭️  {datatype.id}: no JSON schema defined (skipped)")
                continue
            try:
                # スキーマ自体の妥当性チェック
                jsonschema.Draft7Validator.check_schema(datatype.schema_def)
                print(f"  ✅ {datatype.id}: schema valid")
            except jsonschema.SchemaError as e:
                print(f"  ❌ {datatype.id}: schema invalid - {e}")

    def validate_integrity(self: "Engine", project_root: Path = Path(".")) -> dict[str, list[str]]:
        """仕様と実装の整合性を検証

        Returns:
            エラーマップ {category: [error_messages]}
        """
        print("🔍 Validating spec-implementation integrity...")
        errors: dict[str, list[str]] = {
            "check_functions": [],
            "check_locations": [],
            "transform_functions": [],
            "transform_signatures": [],
            "example_schemas": [],
            "datatype_definitions": [],
        }

        packages_dir = str((project_root / "packages").resolve())
        if packages_dir not in sys.path:
            sys.path.insert(0, packages_dir)

        app_root = project_root / "apps" / self.app_package

        self._validate_datatypes(app_root, errors)
        self._validate_checks(app_root, errors)
        self._validate_transforms(app_root, errors)
        self._validate_examples(errors)
        self._summarize_integrity(errors)
        return errors

    def _validate_datatypes(self: "Engine", app_root: Path, errors: dict[str, list[str]]) -> None:
        """Validate generated datatype definitions against spec."""
        module_cache: dict[str, ModuleType | None] = {}
        for datatype in self.spec.datatypes:
            if datatype.enum:
                self._validate_enum_datatype(datatype, module_cache, errors)
            elif datatype.pydantic_model:
                self._validate_pydantic_model_datatype(datatype, app_root, module_cache, errors)
            elif datatype.type_alias:
                self._validate_type_alias_datatype(datatype, module_cache, errors)

    def _record_datatype_error(self: "Engine", errors: dict[str, list[str]], message: str) -> None:
        errors["datatype_definitions"].append(message)
        print(f"  ❌ {message}")

    def _get_datatype_module(
        self: "Engine",
        suffix: str,
        module_cache: dict[str, ModuleType | None],
        errors: dict[str, list[str]],
    ) -> ModuleType | None:
        if suffix in module_cache:
            return module_cache[suffix]
        module_path = f"apps.{self.app_package}.datatypes.{suffix}"
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            self._record_datatype_error(errors, f"Failed to import datatype module '{module_path}': {exc}")
            module = None
        module_cache[suffix] = module
        return module

    @staticmethod
    def _import_native_type(native: str) -> object | None:
        module_name, type_name = native.split(":")
        if module_name == "builtins":
            return getattr(builtins, type_name, None)
        if module_name == "typing":
            return getattr(importlib.import_module("typing"), type_name, None)
        if module_name == "pandas":
            import pandas as pd

            return getattr(pd, type_name, None)
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            return None
        return getattr(module, type_name, None)

    @staticmethod
    def _normalize_annotation(value: object) -> str:
        text = value if isinstance(value, str) else str(value)
        return text.replace("typing.", "").replace("builtins.", "")

    def _validate_enum_datatype(
        self: "Engine",
        datatype: DataType,
        module_cache: dict[str, ModuleType | None],
        errors: dict[str, list[str]],
    ) -> None:
        module = self._get_datatype_module("enums", module_cache, errors)
        if not module:
            return
        enum_cls = getattr(module, datatype.id, None)
        if enum_cls is None:
            self._record_datatype_error(errors, f"DataType '{datatype.id}' enum class not found in enums module")
            return
        if not inspect.isclass(enum_cls) or not issubclass(enum_cls, Enum):
            self._record_datatype_error(
                errors,
                f"DataType '{datatype.id}' expected Enum subclass, got {type(enum_cls).__name__}",
            )
            return
        expected_members = [(member.name, member.value) for member in datatype.enum.members]  # type: ignore[union-attr]
        actual_members = [(member.name, member.value) for member in enum_cls]
        if actual_members != expected_members:
            self._record_datatype_error(
                errors,
                (
                    f"DataType '{datatype.id}' enum members mismatch:\n"
                    f"    Expected: {expected_members}\n"
                    f"    Actual:   {actual_members}"
                ),
            )
            return
        print(f"  ✅ DataType {datatype.id}: enum matches spec")

    def _validate_pydantic_model_datatype(
        self: "Engine",
        datatype: DataType,
        app_root: Path,
        module_cache: dict[str, ModuleType | None],
        errors: dict[str, list[str]],
    ) -> None:
        error_count_before = len(errors["datatype_definitions"])
        module = self._get_datatype_module("models", module_cache, errors)
        if not module:
            return
        model_cls = getattr(module, datatype.id, None)
        if model_cls is None:
            self._record_datatype_error(errors, f"DataType '{datatype.id}' model class not found in models module")
            return
        if not inspect.isclass(model_cls) or not issubclass(model_cls, BaseModel):
            self._record_datatype_error(
                errors,
                f"DataType '{datatype.id}' expected BaseModel subclass, got {type(model_cls).__name__}",
            )
            return

        expected_fields = {field.name: field for field in datatype.pydantic_model.fields}  # type: ignore[union-attr]
        actual_fields: dict[str, FieldInfo] = getattr(model_cls, "model_fields", {})
        self._check_field_membership(datatype, expected_fields, actual_fields, errors)

        annotations: dict[str, object] = getattr(model_cls, "__annotations__", {})
        for field_name, field_config in expected_fields.items():
            field_info = actual_fields.get(field_name)
            if field_info is None:
                continue
            self._validate_pydantic_field(
                datatype,
                field_name,
                field_config,
                field_info,
                annotations.get(field_name),
                app_root,
                errors,
            )

        if len(errors["datatype_definitions"]) == error_count_before:
            print(f"  ✅ DataType {datatype.id}: model matches spec")

    def _check_field_membership(
        self: "Engine",
        datatype: DataType,
        expected_fields: dict[str, PydanticFieldConfig],
        actual_fields: dict[str, FieldInfo],
        errors: dict[str, list[str]],
    ) -> None:
        missing = sorted(set(expected_fields) - set(actual_fields))
        if missing:
            self._record_datatype_error(errors, f"DataType '{datatype.id}' missing fields: {missing}")
        extra = sorted(set(actual_fields) - set(expected_fields))
        if extra:
            self._record_datatype_error(errors, f"DataType '{datatype.id}' has extra fields not in spec: {extra}")

    def _validate_pydantic_field(
        self: "Engine",
        datatype: DataType,
        field_name: str,
        field_config: PydanticFieldConfig,
        field_info: FieldInfo,
        annotation: object | None,
        app_root: Path,
        errors: dict[str, list[str]],
    ) -> None:
        expected_type, _ = _build_type_string(self.spec, field_config.type, app_root, context="pydantic_model")
        if annotation is None:
            self._record_datatype_error(
                errors,
                f"DataType '{datatype.id}' field '{field_name}' missing type annotation",
            )
        elif self._normalize_annotation(annotation) != self._normalize_annotation(expected_type):
            self._record_datatype_error(
                errors,
                (
                    f"DataType '{datatype.id}' field '{field_name}' type mismatch:\n"
                    f"    Expected: {expected_type}\n"
                    f"    Actual:   {annotation}"
                ),
            )

        self._validate_pydantic_field_default(datatype, field_name, field_config, field_info, errors)

    def _validate_pydantic_field_default(
        self: "Engine",
        datatype: DataType,
        field_name: str,
        field_config: PydanticFieldConfig,
        field_info: FieldInfo,
        errors: dict[str, list[str]],
    ) -> None:
        has_default = "default" in field_config.model_fields_set
        is_optional = field_config.optional or not field_config.required
        if has_default:
            if field_info.is_required():
                self._record_datatype_error(
                    errors,
                    (
                        f"DataType '{datatype.id}' field '{field_name}' expected default "
                        f"{field_config.default}, but is required"
                    ),
                )
            elif field_info.default != field_config.default:
                self._record_datatype_error(
                    errors,
                    (
                        f"DataType '{datatype.id}' field '{field_name}' default mismatch:\n"
                        f"    Expected: {field_config.default}\n"
                        f"    Actual:   {field_info.default}"
                    ),
                )
        elif is_optional:
            if field_info.is_required():
                self._record_datatype_error(
                    errors,
                    f"DataType '{datatype.id}' field '{field_name}' expected to be optional",
                )
            elif field_info.default is not None:
                self._record_datatype_error(
                    errors,
                    (
                        f"DataType '{datatype.id}' field '{field_name}' expected default None, "
                        f"got {field_info.default}"
                    ),
                )
        elif not field_info.is_required():
            self._record_datatype_error(
                errors,
                f"DataType '{datatype.id}' field '{field_name}' should be required",
            )

    def _validate_type_alias_datatype(
        self: "Engine",
        datatype: DataType,
        module_cache: dict[str, ModuleType | None],
        errors: dict[str, list[str]],
    ) -> None:
        module = self._get_datatype_module("type_aliases", module_cache, errors)
        if not module:
            return
        alias_value = getattr(module, datatype.id, None)
        if alias_value is None:
            self._record_datatype_error(
                errors,
                f"DataType '{datatype.id}' type alias not found in type_aliases module",
            )
            return
        alias_config = datatype.type_alias
        if alias_config and alias_config.type == "simple" and alias_config.target:
            expected = self._import_native_type(alias_config.target)
            if expected is not None and alias_value is not expected:
                self._record_datatype_error(
                    errors,
                    f"DataType '{datatype.id}' alias expected {alias_config.target}, got {alias_value}",
                )
                return
        print(f"  ✅ DataType {datatype.id}: type alias exists")

    def _validate_checks(self: "Engine", app_root: Path, errors: dict[str, list[str]]) -> None:
        """Validate existence and location of check implementations."""
        for check in self.spec.checks:
            module_path, func_name = check.impl.split(":")
            expected_file = app_root / check.file_path
            try:
                module = importlib.import_module(module_path)
                func = getattr(module, func_name)
                print(f"  ✅ Check {check.id}: function exists")
                actual_file = Path(inspect.getfile(func)).resolve()
                expected_file_resolved = expected_file.resolve()
                if actual_file != expected_file_resolved:
                    message = (
                        f"Check '{check.id}' location mismatch:\n"
                        f"    Expected: {expected_file}\n"
                        f"    Actual:   {actual_file}"
                    )
                    errors["check_locations"].append(message)
                    print(f"  ⚠️  {message}")
            except (ImportError, AttributeError) as exc:
                message = f"Check '{check.id}' not found: {exc}"
                errors["check_functions"].append(message)
                print(f"  ❌ {message}")

    def _validate_transforms(self: "Engine", app_root: Path, errors: dict[str, list[str]]) -> None:
        """Validate transform implementations and signatures."""
        for transform in self.spec.transforms:
            module_path, func_name = transform.impl.split(":")
            expected_file = app_root / transform.file_path
            try:
                module = importlib.import_module(module_path)
                func = getattr(module, func_name)
                print(f"  ✅ Transform {transform.id}: function exists")
                actual_file = Path(inspect.getfile(func)).resolve()
                expected_file_resolved = expected_file.resolve()
                if actual_file != expected_file_resolved:
                    message = (
                        f"Transform '{transform.id}' location mismatch:\n"
                        f"    Expected: {expected_file}\n"
                        f"    Actual:   {actual_file}"
                    )
                    errors["transform_functions"].append(message)
                    print(f"  ⚠️  {message}")

                signature = inspect.signature(func)
                expected_params = {p.name for p in transform.parameters}
                actual_params = set(signature.parameters.keys())
                if expected_params != actual_params:
                    message = (
                        f"Transform '{transform.id}' signature mismatch:\n"
                        f"    Expected params: {sorted(expected_params)}\n"
                        f"    Actual params:   {sorted(actual_params)}"
                    )
                    errors["transform_signatures"].append(message)
                    print(f"  ⚠️  {message}")
            except (ImportError, AttributeError) as exc:
                message = f"Transform '{transform.id}' not found: {exc}"
                errors["transform_functions"].append(message)
                print(f"  ❌ {message}")

    def _validate_examples(self: "Engine", errors: dict[str, list[str]]) -> None:
        """Validate that example payloads satisfy their referenced schemas."""
        for example in self.spec.examples:
            for datatype in self.spec.datatypes:
                if example.id not in datatype.example_ids:
                    continue
                if not datatype.schema_def:
                    message = f"  ⏭️  Example {example.id}: " f"no schema to validate for {datatype.id}"
                    print(message)
                    continue
                try:
                    jsonschema.validate(example.input, datatype.schema_def)
                    print(f"  ✅ Example {example.id}: schema valid for {datatype.id}")
                except jsonschema.ValidationError as exc:
                    details = "\n".join(
                        [
                            f"Example {example.id} invalid for DataType {datatype.id}:",
                            f"    {exc.message}",
                        ]
                    )
                    errors["example_schemas"].append(details)
                    print(f"  ❌ {details}")

    def _summarize_integrity(self: "Engine", errors: dict[str, list[str]]) -> None:
        """Print a short summary for integrity validation."""
        total_errors = sum(len(errs) for errs in errors.values())
        if total_errors == 0:
            print("\n✅ All integrity checks passed!")
            return
        print(f"\n⚠️  Found {total_errors} integrity issue(s)")

    def run_checks(self: "Engine") -> None:
        """Check関数を実行"""
        print("🔍 Running checks...")
        for check in self.spec.checks:
            module_path, func_name = check.impl.split(":")
            try:
                module = importlib.import_module(module_path)
                getattr(module, func_name)
                print(f"  ✅ {check.id}: loaded")
            except (ImportError, AttributeError) as e:
                print(f"  ❌ {check.id}: {e}")

    def run_examples(self: "Engine") -> dict[str, bool]:
        """Example検証を実行"""
        print("🧪 Running examples...")
        results = {}

        for example in self.spec.examples:
            # 簡易実装: Transformを実行して期待値と比較
            # 実際にはDAGを辿って実行する必要がある
            print(f"  🔬 {example.id}: {example.description}")
            results[example.id] = True  # TODO: 実際の検証ロジック実装

        return results

    def run_dag(self: "Engine") -> None:
        """DAGを実行"""
        print("🚀 Running DAG...")

        if len(self.graph.nodes) == 0:
            print("  ℹ️  No transforms to execute")
            return

        # トポロジカルソートで実行順序を決定
        try:
            execution_order = list(nx.topological_sort(self.graph))
        except nx.NetworkXError:
            print("  ❌ Cannot determine execution order (cycle detected)")
            return

        for transform_id in execution_order:
            # Transform定義を取得
            transform = next((t for t in self.spec.transforms if t.id == transform_id), None)
            if not transform:
                print(f"  ❌ {transform_id}: not found in spec")
                continue

            # モジュール・関数をロード
            module_path, func_name = transform.impl.split(":")
            try:
                module = importlib.import_module(module_path)
                func = getattr(module, func_name)

                # 簡易実行（引数は仮）
                # 実際にはデータフローを実装する必要がある
                result = func(**transform.default_args)
                print(f"  ✅ {transform_id} -> {result}")
            except (ImportError, AttributeError) as e:
                print(f"  ❌ {transform_id}: {e}")
            except Exception as e:
                print(f"  ❌ {transform_id}: execution error - {e}")


# ==================== CLI ====================


def _create_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    parser = argparse.ArgumentParser(description="Spec-to-Code Engine")
    subparsers = parser.add_subparsers(dest="command", help="サブコマンド")

    gen_parser = subparsers.add_parser("gen", help="スケルトンコード生成")
    gen_parser.add_argument("spec_file", help="仕様ファイル (YAML/JSON)")

    run_parser = subparsers.add_parser("run", help="DAG実行・検証")
    run_parser.add_argument("spec_file", help="仕様ファイル (YAML/JSON)")

    validate_parser = subparsers.add_parser("validate", help="仕様と実装の整合性を検証")
    validate_parser.add_argument("spec_file", help="仕様ファイル (YAML/JSON)")

    run_config_parser = subparsers.add_parser("run-config", help="Config-based DAG execution")
    run_config_parser.add_argument("config_file", help="Config file (YAML)")

    validate_config_parser = subparsers.add_parser("validate-config", help="Config整合性検証")
    validate_config_parser.add_argument("config_file", help="Config file (YAML)")

    return parser


def _handle_run_config(config_file: str) -> None:
    """Execute config-driven pipeline run."""
    from packages.spec2code.config_runner import ConfigRunner

    import pandas as pd

    try:
        runner = ConfigRunner(config_file)
        initial_data = pd.DataFrame(
            {
                "timestamp": [
                    "2024-01-01",
                    "2024-01-02",
                    "2024-01-03",
                    "2024-01-04",
                    "2024-01-05",
                ],
                "value": [100, 150, 120, 180, 140],
            }
        )
        print("\n📊 Initial data:")
        print(initial_data)
        print()

        result = runner.run(initial_data)
        print("\n📊 Final result:")
        print(result)
    except Exception as exc:  # noqa: BLE001 - surface full error details
        print(f"❌ Config execution failed: {exc}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def _handle_validate_config(config_file: str) -> None:
    """Validate config file against spec."""
    from packages.spec2code.config_runner import ConfigRunner
    from packages.spec2code.config_validator import ConfigValidationError

    try:
        print("🔍 Loading config...")
        runner = ConfigRunner(config_file)
        print(f"✅ Config loaded: {runner.config.meta.config_name}")
        print(f"📄 Base spec: {runner.config.meta.base_spec}")
        print()

        print("🔍 Validating config against spec...")
        validation_result = runner.validate(check_implementations=True)
        print("✅ Config validation passed!")
        print()

        execution_plan = validation_result["execution_plan"]
        print(f"📋 Execution plan: {len(execution_plan)} transform(s)")
        for idx, step in enumerate(execution_plan, start=1):
            print(f"  {idx}. Stage: {step['stage_id']}")
            print(f"     Transform: {step['transform_id']}")
            if step["params"]:
                print(f"     Params: {step['params']}")
        print()
        print("✅ Config validation completed successfully")

    except ConfigValidationError as exc:
        print(f"❌ Config validation failed:\n{exc}")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 - surface full error details
        print(f"❌ Config validation error: {exc}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def _run_engine_command(command: str, spec: Spec) -> None:
    """Run engine command from parsed arguments."""
    if command == "gen":
        generate_skeleton(spec)
        print("✅ Skeleton generation completed")
        return

    engine = Engine(spec)
    if command == "run":
        engine.validate_schemas()
        engine.run_checks()
        engine.run_dag()
        results = engine.run_examples()
        print(f"📊 Example report: {results}")
        print("✅ Execution completed")
        return

    if command == "validate":
        errors = engine.validate_integrity()
        total_errors = sum(len(errs) for errs in errors.values())
        if total_errors > 0:
            sys.exit(1)
        return

    raise ValueError(f"Unknown command: {command}")


def main() -> None:
    """CLIエントリーポイント"""
    parser = _create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "run-config":
        _handle_run_config(args.config_file)
        return

    if args.command == "validate-config":
        _handle_validate_config(args.config_file)
        return

    try:
        spec = load_spec(args.spec_file)
        print(f"✅ Loaded spec: {spec.meta.name} (v{spec.version})")
    except Exception as exc:  # noqa: BLE001 - command-line surface
        print(f"❌ Failed to load spec: {exc}")
        sys.exit(1)

    _run_engine_command(args.command, spec)


if __name__ == "__main__":
    main()

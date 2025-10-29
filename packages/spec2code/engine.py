"""
構造仕様ベースのコードスケルトン生成・検証システム - コアエンジン
"""

from __future__ import annotations

import ast
import builtins
import importlib
import inspect
import json
import sys
from pathlib import Path
from typing import Annotated, Any, Callable, Generic, Iterable, Literal, TypeVar, get_args, get_origin, get_type_hints
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
UNLINKED_INFO_SUFFIX = " (紐付いているデータ型がステージIO対象外: check がない・Unlinked、でも問題ない)"


class Check(Generic[T]):
    """型アノテーション用のCheck参照マーカー

    Usage:
        Annotated[Out, Check["module.path.check_function"]]
    """

    def __class_getitem__(_cls: type["Check"], item: str) -> type:
        """文字列でチェック関数を参照"""
        return type(f"Check[{item}]", (), {"__check_ref__": item})


class ExampleValue(Generic[T]):
    """型アノテーション用のExample値マーカー

    Usage:
        Annotated[
            In,
            ExampleValue[{"__example_id__": "ex_hello", "__example_value__": {"text": "hello"}}],
        ]
    """

    def __class_getitem__(_cls: type["ExampleValue"], item: dict[str, Any]) -> type:
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
    example_refs: list[str] = Field(default_factory=list, alias="example_ids")
    generator_refs: list[str] = Field(default_factory=list, alias="generator_ids")
    schema_def: dict[str, Any] | None = Field(default=None, alias="schema")  # JSON Schema
    type_alias: TypeAliasConfig | None = None
    enum: EnumConfig | None = None
    generic: GenericConfig | None = None
    pandas_multiindex: PandasMultiIndexConfig | None = None
    pydantic_model: PydanticModelConfig | None = None

    @model_validator(mode="after")
    def _validate_type_definition(self: "DataType") -> "DataType":
        # schema_defはexampleバリデーション用として他の型定義と併用可能
        type_fields = {
            "type_alias": self.type_alias,
            "enum": self.enum,
            "generic": self.generic,
            "pandas_multiindex": self.pandas_multiindex,
            "pydantic_model": self.pydantic_model,
        }
        defined = [name for name, value in type_fields.items() if value]

        # schema_defのみの場合も許可（既存の動作）
        if not defined and not self.schema_def:
            message = (
                f"DataType '{self.id}' must define at least one type "
                "(schema/type_alias/enum/generic/pandas_multiindex/pydantic_model)"
            )
            raise ValueError(message)

        # 主要な型定義は1つまで（schema_defは併用可能）
        if len(defined) > 1:
            message = f"DataType '{self.id}' can define only one primary type, got multiple: {defined}"
            raise ValueError(message)

        # example/generatorの有無は validate_integrity() で詳細チェック
        return self

    @property
    def example_ids(self) -> list[str]:
        """後方互換性のためのエイリアス"""
        return self.example_refs

    @property
    def generator_ids(self) -> list[str]:
        """後方互換性のためのエイリアス"""
        return self.generator_refs


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


class GeneratorSpec(BaseModel):
    """データ生成関数定義"""

    id: str
    description: str
    impl: str  # "module:function"形式
    file_path: str
    parameters: list[Parameter] = Field(default_factory=list)


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
    publish_output: bool = False
    collect_output: bool = False


class Spec(BaseModel):
    """仕様全体のルートモデル"""

    version: str
    meta: Meta
    checks: list[CheckDef] = Field(default_factory=list)
    examples: list[Example] = Field(default_factory=list)
    generators: dict[str, GeneratorSpec] = Field(default_factory=dict)
    datatypes: list[DataType] = Field(default_factory=list)
    transforms: list[Transform] = Field(default_factory=list)
    dag: list[DAGEdge] = Field(default_factory=list)
    dag_stages: list[DAGStage] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_generators(_: type["Spec"], data: dict[str, Any]) -> dict[str, Any]:
        generators = data.get("generators")
        if generators is None:
            return data

        if isinstance(generators, dict):
            normalized = {}
            for gen_id, payload in generators.items():
                if isinstance(payload, dict):
                    payload.setdefault("id", gen_id)
                normalized[gen_id] = payload
        elif isinstance(generators, list):
            normalized = {}
            for item in generators:
                if not isinstance(item, dict):
                    continue
                gen_id = item.get("id")
                if not gen_id:
                    continue
                normalized[gen_id] = item
        else:
            normalized = {}
        data["generators"] = normalized
        return data


# ==================== 仕様読み込み・検証 ====================


def load_spec(spec_path: str | Path) -> Spec:
    """YAML/JSON仕様を読み込み、Pydanticで検証"""
    spec_path = Path(spec_path)
    with open(spec_path) as f:
        if spec_path.suffix in {".yaml", ".yml"}:
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
        publish_output=False,
        collect_output=False,
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


def _collect_transform_params(transform: Transform) -> dict[str, Any]:
    """Collect default or inferred parameters for a transform (excluding first param)."""
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

    return params


def _build_default_stage_config(spec: Spec, stage: DAGStage) -> dict[str, Any] | None:
    """Build default config for a single DAG stage."""
    if stage.selection_mode == "single" or not stage.default_transform_id:
        return None

    transform = next((t for t in spec.transforms if t.id == stage.default_transform_id), None)
    if not transform:
        return None

    params = _collect_transform_params(transform)

    selection: dict[str, Any] = {"transform_id": transform.id}
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
    formatter: Callable[[AnnotationSource], str | None],
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
        if item is None:
            continue
        annotation = formatter(item)
        if annotation:
            annotations.append(annotation)

    imports = {import_statement} if annotations else set()
    return annotations, imports


def _find_example(spec: Spec, example_id: str) -> Example | None:
    return next(
        (example for example in spec.examples if example.id == example_id),
        None,
    )


def _find_check(spec: Spec, check_id: str) -> CheckDef | None:
    return next((check for check in spec.checks if check.id == check_id), None)


def _collect_example_annotations(
    spec: Spec,
    datatype_ref: str | None,
    value_getter: Callable[[Example], dict[str, Any] | None] | None = None,
) -> tuple[list[str], set[str]]:
    if value_getter is None:

        def value_getter(example: Example) -> dict[str, Any] | None:
            return example.input

    def _format_example(example: Example) -> str | None:
        value = value_getter(example)
        if value is None:
            return None
        payload = repr(value)
        return f"ExampleValue[{{'__example_id__': '{example.id}', '__example_value__': {payload}}}]"

    return _collect_datatype_annotations(
        spec,
        datatype_ref,
        lambda datatype: datatype.example_ids,
        lambda example_id: _find_example(spec, example_id),
        _format_example,
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
    check_annotations, check_imports = _collect_check_annotations(spec, transform.return_datatype_ref)
    example_annotations, example_imports = _collect_example_annotations(
        spec,
        transform.return_datatype_ref,
        lambda example: example.expected,
    )
    annotations = check_annotations + example_annotations
    imports.update(check_imports)
    imports.update(example_imports)

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

        code = f"# Auto-generated skeleton for Check functions\n{chr(10).join(functions)}\n"
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
        rendered_lines.append(f"from spec2code.engine import {', '.join(sorted(spec2code_imports))}")
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
    lines.append("")
    lines.append('    model_config = {"arbitrary_types_allowed": True}')

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


def _render_generator_function(spec: Spec, generator: GeneratorSpec, app_root: Path) -> tuple[str, set[str]]:
    """Render generator function skeleton and required imports."""
    func_name = generator.impl.split(":")[-1]

    param_strs: list[str] = []
    all_imports: set[str] = set()
    for param in generator.parameters:
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

    signature = ", ".join(param_strs)
    all_imports.add("from typing import Any")

    description = generator.description or ""
    code = f'''# Auto-generated skeleton for Generator: {generator.id}
def {func_name}({signature}) -> dict[str, Any]:
    """{description}"""
    # TODO: implement data generation logic
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


def _write_generator_file(spec: Spec, generators: list[GeneratorSpec], app_root: Path) -> None:
    """Create or update a generator module with the provided generator functions."""
    relative_path = generators[0].file_path
    file_path = app_root / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)

    existing_code = ""
    existing_functions: set[str] = set()
    if file_path.exists():
        existing_code = file_path.read_text()
        existing_functions = _extract_existing_function_names(existing_code)

    new_blocks: list[str] = []
    required_imports: set[str] = set()
    for generator in generators:
        func_name = generator.impl.split(":")[-1]
        if func_name in existing_functions:
            print(f"  ⏭️  Skip (exists): {file_path}::{func_name}")
            continue
        block, imports = _render_generator_function(spec, generator, app_root)
        new_blocks.append(block)
        required_imports.update(imports)

    if not file_path.exists():
        if not new_blocks:
            print(f"  ⏭️  Skip (exists): {file_path}")
            return
        header = "# Auto-generated skeleton for Generator functions\n"
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
    print(f"  ✏️  Appended {len(new_blocks)} generator(s): {file_path}")


def _generate_transform_skeletons(spec: Spec, app_root: Path) -> None:
    """Generate skeleton files for all transforms, grouping by file path."""
    grouped: dict[str, list[Transform]] = {}
    for transform in spec.transforms:
        grouped.setdefault(transform.file_path, []).append(transform)

    for transforms in grouped.values():
        _write_transform_file(spec, transforms, app_root)


def _generate_generator_skeletons(spec: Spec, app_root: Path) -> None:
    """Generate skeleton files for generator functions, grouped by file path."""
    if not spec.generators:
        return

    grouped: dict[str, list[GeneratorSpec]] = {}
    for generator in spec.generators.values():
        grouped.setdefault(generator.file_path, []).append(generator)

    for generators in grouped.values():
        _write_generator_file(spec, generators, app_root)


def _ensure_package_inits(app_root: Path) -> None:
    """Ensure __init__.py files exist for generated packages."""
    for directory in ["checks", "transforms", "datatypes", "generators"]:
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
    _generate_generator_skeletons(spec, app_root)
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
            "transform_annotations": [],
            "generator_functions": [],
            "generator_locations": [],
            "generator_signatures": [],
            "example_schemas": [],
            "datatype_definitions": [],
            "datatype_completeness": [],
        }

        packages_dir = str((project_root / "packages").resolve())
        if packages_dir not in sys.path:
            sys.path.insert(0, packages_dir)

        app_root = project_root / "apps" / self.app_package

        # DataType完全性チェック（check/example必須要件）
        self._validate_datatype_completeness(errors)
        self._validate_datatypes(app_root, errors)
        self._validate_checks(app_root, errors)
        self._validate_transforms(app_root, errors)
        self._validate_generators(app_root, errors)
        self._validate_examples(app_root, errors)
        # 未紐付け要素の警告を表示（バリデーション失敗にはしない）
        self._warn_unlinked_items()
        self._summarize_integrity(errors)
        return errors

    def validate_spec_structure(self: "Engine", *, summarize: bool = True) -> dict[str, list[str]]:
        """Implementation-free spec validation focusing on metadata completeness."""
        print("🔍 Validating spec structure and references...")
        errors: dict[str, list[str]] = {
            "datatype_completeness": [],
            "example_links": [],
            "check_links": [],
            "generator_links": [],
        }

        self._validate_datatype_completeness(errors)
        self._validate_example_attachments(errors)
        self._validate_check_attachments(errors)
        self._validate_generator_attachments(errors)
        self._report_stage_publication()
        self._warn_unlinked_items()
        if summarize:
            self._summarize_integrity(errors)
        return errors

    @staticmethod
    def _format_datatype_status(
        datatype: DataType,
        has_checks: bool,
        has_sample_source: bool,
        *,
        is_stage_io: bool,
    ) -> None:
        """Print formatted datatype status line."""
        check_status = f"✓ ({len(datatype.check_ids)})" if has_checks else "✗ (0)"
        example_status = f"✓ ({len(datatype.example_refs)})" if datatype.example_refs else "✗ (0)"
        generator_status = f"✓ ({len(datatype.generator_refs)})" if datatype.generator_refs else "✗ (0)"
        scope_label = "ステージIO対象" if is_stage_io else "ステージIO対象外"
        if is_stage_io:
            icon = "✅" if has_checks and has_sample_source else "⚠️ "
        else:
            icon = "✅" if has_checks and has_sample_source else "ℹ️ "
        print(
            f"  {icon} {datatype.id:30s} | Scope: {scope_label:12s} | Checks: {check_status:8s} | "
            f"Examples: {example_status:8s} | Generators: {generator_status:8s}"
        )

    @staticmethod
    def _check_single_datatype_completeness(
        datatype: DataType,
        errors: dict[str, list[str]],
        *,
        stage_io_datatypes: set[str],
    ) -> bool:
        """Check single datatype completeness and return True if has issues."""
        has_checks = bool(datatype.check_ids)
        has_sample_source = bool(datatype.example_refs or datatype.generator_refs)
        is_stage_io = datatype.id in stage_io_datatypes

        Engine._format_datatype_status(
            datatype,
            has_checks,
            has_sample_source,
            is_stage_io=is_stage_io,
        )

        if has_checks and has_sample_source:
            return False

        if not is_stage_io:
            return False

        issues = []
        if not has_checks:
            issues.append("missing checks")
        if not has_sample_source:
            issues.append("missing examples/generators")
        errors["datatype_completeness"].append(f"DataType '{datatype.id}' is incomplete: {', '.join(issues)}")
        return True

    def _validate_datatype_completeness(self: "Engine", errors: dict[str, list[str]]) -> None:
        """DataTypeのcheck/example完全性を検証"""
        print("\n📋 DataType Completeness Check:")
        print("=" * 80)

        # Check all datatypes without short-circuiting
        stage_io_datatypes = self._collect_stage_io_datatypes()
        issue_flags = [
            self._check_single_datatype_completeness(
                dt,
                errors,
                stage_io_datatypes=stage_io_datatypes,
            )
            for dt in self.spec.datatypes
        ]
        has_issues = any(issue_flags)

        summary = (
            "\n  ⚠️  Some datatypes are missing checks or sample sources"
            if has_issues
            else "\n  ✅ All datatypes have checks and sample sources (examples/generators)!"
        )
        print(summary)
        print("=" * 80)

    def _report_stage_publication(self: "Engine") -> None:
        """Report which stages are marked to collect outputs."""
        if not self.spec.dag_stages:
            return

        print("\n📋 DAG Stage Output Collection:")
        print("=" * 80)
        collect_count = 0
        for stage in self.spec.dag_stages:
            if stage.collect_output or stage.publish_output:
                collect_count += 1
                flag = "collect_output" if stage.collect_output else "publish_output"
                print(f"  ✅ Stage {stage.stage_id}: {flag}=True (allowed terminal)")
        if collect_count == 0:
            print("  ⏭️  No stages marked with collect_output=True")
        print("=" * 80)

    def _validate_example_attachments(self: "Engine", errors: dict[str, list[str]]) -> None:
        """Validate that examples are referenced by datatypes."""
        print("\n📋 Example Attachments:")
        print("=" * 80)
        example_map = {example.id: example for example in self.spec.examples}
        usage: dict[str, list[str]] = {example_id: [] for example_id in example_map}

        for datatype in self.spec.datatypes:
            for example_id in datatype.example_refs:
                if example_id in example_map:
                    usage.setdefault(example_id, []).append(datatype.id)
                else:
                    message = f"DataType '{datatype.id}' references unknown example '{example_id}'"
                    errors["example_links"].append(message)
                    print(f"  ❌ {message}")

        if not example_map:
            print("  ⚠️  No examples defined in spec")
        else:
            for example_id in sorted(example_map):
                dtype_ids = sorted(usage.get(example_id, []))
                if dtype_ids:
                    dtype_list = ", ".join(dtype_ids)
                    print(f"  ✅ Example {example_id}: linked to datatypes [{dtype_list}]")
                else:
                    message = f"Example '{example_id}' is not referenced by any datatype"
                    errors["example_links"].append(message)
                    print(f"  ⚠️  {message}")
        print("=" * 80)

    def _validate_check_attachments(self: "Engine", errors: dict[str, list[str]]) -> None:
        """Validate that checks are referenced by datatypes."""
        print("\n📋 Check Attachments:")
        print("=" * 80)
        check_map = {check.id: check for check in self.spec.checks}
        usage: dict[str, list[str]] = {check_id: [] for check_id in check_map}

        for datatype in self.spec.datatypes:
            for check_id in datatype.check_ids:
                if check_id in check_map:
                    usage.setdefault(check_id, []).append(datatype.id)
                else:
                    message = f"DataType '{datatype.id}' references unknown check '{check_id}'"
                    errors["check_links"].append(message)
                    print(f"  ❌ {message}")

        if not check_map:
            print("  ⚠️  No checks defined in spec")
        else:
            for check_id in sorted(check_map):
                dtype_ids = sorted(usage.get(check_id, []))
                if dtype_ids:
                    dtype_list = ", ".join(dtype_ids)
                    print(f"  ✅ Check {check_id}: linked to datatypes [{dtype_list}]")
                else:
                    message = f"Check '{check_id}' is not referenced by any datatype"
                    errors["check_links"].append(message)
                    print(f"  ⚠️  {message}")
        print("=" * 80)

    def _validate_generator_attachments(self: "Engine", errors: dict[str, list[str]]) -> None:
        """Validate that generators are referenced by datatypes."""
        print("\n📋 Generator Attachments:")
        print("=" * 80)
        generator_specs = self.spec.generators or {}
        generator_map = {gen.id: gen for gen in generator_specs.values()}
        usage: dict[str, list[str]] = {gen_id: [] for gen_id in generator_map}

        for datatype in self.spec.datatypes:
            for generator_id in datatype.generator_refs:
                if generator_id in generator_map:
                    usage.setdefault(generator_id, []).append(datatype.id)
                else:
                    message = f"DataType '{datatype.id}' references unknown generator '{generator_id}'"
                    errors["generator_links"].append(message)
                    print(f"  ❌ {message}")

        if not generator_map:
            print("  ⚠️  No generators defined in spec")
        else:
            for generator_id in sorted(generator_map):
                dtype_ids = sorted(usage.get(generator_id, []))
                if dtype_ids:
                    dtype_list = ", ".join(dtype_ids)
                    print(f"  ✅ Generator {generator_id}: linked to datatypes [{dtype_list}]")
                else:
                    message = f"Generator '{generator_id}' is not referenced by any datatype"
                    errors["generator_links"].append(message)
                    print(f"  ⚠️  {message}")
        print("=" * 80)

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

    @staticmethod
    def _record_datatype_error(errors: dict[str, list[str]], message: str) -> None:
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
                    (f"DataType '{datatype.id}' field '{field_name}' expected default None, got {field_info.default}"),
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

                try:
                    type_hints = get_type_hints(
                        func,
                        globalns=getattr(module, "__dict__", {}),
                        include_extras=True,
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    message = f"Transform '{transform.id}' annotations could not be resolved: {exc}"
                    errors["transform_annotations"].append(message)
                    print(f"  ⚠️  {message}")
                else:
                    self._validate_transform_example_markers(transform, type_hints, errors)
            except (ImportError, AttributeError) as exc:
                message = f"Transform '{transform.id}' not found: {exc}"
                errors["transform_functions"].append(message)
                print(f"  ❌ {message}")

    @staticmethod
    def _extract_example_marker(annotation: object) -> dict[str, Any] | None:
        """Annotated型からExampleValueマーカー辞書を抽出"""
        if annotation is None:
            return None

        origin = get_origin(annotation)
        if origin is Annotated:
            args = get_args(annotation)
            extras = args[1:]
            for extra in extras:
                marker = getattr(extra, "__example_value__", None)
                if isinstance(marker, dict):
                    return marker
            return None

        marker = getattr(annotation, "__example_value__", None)
        return marker if isinstance(marker, dict) else None

    def _validate_transform_example_markers(
        self: "Engine",
        transform: Transform,
        type_hints: dict[str, object],
        errors: dict[str, list[str]],
    ) -> None:
        """Transform関数のExampleValueアノテーションを検証"""
        datatype_map = {datatype.id: datatype for datatype in self.spec.datatypes}
        example_map = {example.id: example for example in self.spec.examples}

        for param in transform.parameters:
            if not param.datatype_ref:
                continue
            datatype = datatype_map.get(param.datatype_ref)
            if not datatype or not datatype.example_refs:
                continue
            annotation = type_hints.get(param.name)
            self._check_example_marker(
                transform.id,
                f"parameter '{param.name}'",
                annotation,
                datatype,
                example_map,
                errors,
                use_expected=False,
            )

        if transform.return_datatype_ref:
            datatype = datatype_map.get(transform.return_datatype_ref)
            if datatype and datatype.example_refs:
                annotation = type_hints.get("return")
                self._check_example_marker(
                    transform.id,
                    "return value",
                    annotation,
                    datatype,
                    example_map,
                    errors,
                    use_expected=True,
                )

    @staticmethod
    def _report_example_error(errors: dict[str, list[str]], message: str) -> None:
        """Helper to report example validation errors."""
        errors["transform_annotations"].append(message)
        print(f"  ⚠️  {message}")

    def _check_example_marker(
        self: "Engine",
        transform_id: str,
        context: str,
        annotation: object | None,
        datatype: DataType,
        example_map: dict[str, Example],
        errors: dict[str, list[str]],
        *,
        use_expected: bool,
    ) -> None:
        """ExampleValueマーカー内容の詳細検証"""
        expected_ids = datatype.example_ids
        if not expected_ids:
            return

        error_msg = self._validate_example_annotation(
            transform_id, context, annotation, expected_ids, example_map, use_expected
        )
        if error_msg:
            self._report_example_error(errors, error_msg)

    @staticmethod
    def _validate_marker_content(
        marker: dict[str, Any], expected_ids: list[str], example_map: dict[str, Example], use_expected: bool
    ) -> tuple[str | None, Example | None]:
        """Validate marker content and return error message if any, otherwise return example."""
        example_id = marker.get("__example_id__")
        if not example_id or example_id not in expected_ids:
            id_desc = "missing" if not example_id else f"unknown '{example_id}'"
            return f"ExampleValue has {id_desc} example_id (expected one of {expected_ids})", None

        if "__example_value__" not in marker:
            return "missing '__example_value__'", None

        example = example_map.get(example_id)
        if example is None:
            return f"Example '{example_id}' not found", None

        expected_payload = example.expected if use_expected else example.input
        if marker["__example_value__"] != expected_payload:
            return f"ExampleValue payload mismatch for example '{example_id}'", None

        return None, example

    def _validate_example_annotation(
        self,
        transform_id: str,
        context: str,
        annotation: object | None,
        expected_ids: list[str],
        example_map: dict[str, Example],
        use_expected: bool,
    ) -> str | None:
        """Validate example annotation and return error message if any."""
        if annotation is None or (marker := self._extract_example_marker(annotation)) is None:
            return f"Transform '{transform_id}' {context} missing ExampleValue marker (expected one of {expected_ids})"

        error_msg, _ = self._validate_marker_content(marker, expected_ids, example_map, use_expected)
        return f"Transform '{transform_id}' {context}: {error_msg}" if error_msg else None

    def _validate_generator_refs(self, errors: dict[str, list[str]]) -> None:
        """Validate that all generator references are defined."""
        defined_generators = self.spec.generators
        for datatype in self.spec.datatypes:
            for generator_id in datatype.generator_refs:
                if generator_id not in defined_generators:
                    message = (
                        f"Generator '{generator_id}' referenced by DataType '{datatype.id}' is not defined in spec"
                    )
                    errors["generator_functions"].append(message)
                    print(f"  ❌ {message}")

    def _validate_single_generator(
        self, generator: GeneratorSpec, app_root: Path, errors: dict[str, list[str]]
    ) -> None:
        """Validate a single generator's implementation and signature."""
        module_path, func_name = generator.impl.split(":")
        expected_file = app_root / generator.file_path

        try:
            module = importlib.import_module(module_path)
            func = getattr(module, func_name)
            print(f"  ✅ Generator {generator.id}: function exists")
        except (ImportError, AttributeError) as exc:
            message = f"Generator '{generator.id}' not found: {exc}"
            errors["generator_functions"].append(message)
            print(f"  ❌ {message}")
            return

        self._check_generator_location(generator, func, expected_file, errors)
        self._check_generator_signature(generator, func, errors)

    @staticmethod
    def _check_generator_location(
        generator: GeneratorSpec, func: object, expected_file: Path, errors: dict[str, list[str]]
    ) -> None:
        """Check if generator is in the expected file location."""
        try:
            actual_file = Path(inspect.getfile(func)).resolve()  # type: ignore[arg-type]
            expected_file_resolved = expected_file.resolve()
            if actual_file != expected_file_resolved:
                message = (
                    f"Generator '{generator.id}' location mismatch:\n"
                    f"    Expected: {expected_file}\n"
                    f"    Actual:   {actual_file}"
                )
                errors["generator_locations"].append(message)
                print(f"  ⚠️  {message}")
        except (TypeError, OSError) as exc:
            message = f"Generator '{generator.id}' location could not be determined: {exc}"
            errors["generator_locations"].append(message)
            print(f"  ⚠️  {message}")

    @staticmethod
    def _check_generator_signature(generator: GeneratorSpec, func: object, errors: dict[str, list[str]]) -> None:
        """Check if generator signature matches specification."""
        signature = inspect.signature(func)  # type: ignore[arg-type]
        expected_params = {p.name for p in generator.parameters}
        actual_params = set(signature.parameters.keys())
        if expected_params != actual_params:
            message = (
                f"Generator '{generator.id}' signature mismatch:\n"
                f"    Expected params: {sorted(expected_params)}\n"
                f"    Actual params:   {sorted(actual_params)}"
            )
            errors["generator_signatures"].append(message)
            print(f"  ⚠️  {message}")

    def _validate_generators(self: "Engine", app_root: Path, errors: dict[str, list[str]]) -> None:
        """Validate generator implementations and signatures."""
        if not self.spec.generators:
            return

        self._validate_generator_refs(errors)
        for generator in self.spec.generators.values():
            self._validate_single_generator(generator, app_root, errors)

    def _validate_examples(self: "Engine", app_root: Path, errors: dict[str, list[str]]) -> None:
        """Validate that example payloads satisfy their referenced schemas."""
        module_cache: dict[str, ModuleType | None] = {}
        for example in self.spec.examples:
            for datatype in self.spec.datatypes:
                if example.id not in datatype.example_ids:
                    continue

                # JSON Schema validation
                if datatype.schema_def:
                    Engine._validate_example_with_schema(example, datatype, errors)
                # Pydantic model validation
                elif datatype.pydantic_model:
                    self._validate_example_with_pydantic(example, datatype, module_cache, errors)
                # No validation available
                else:
                    print(f"  ⏭️  Example {example.id}: no schema to validate for {datatype.id}")

    @staticmethod
    def _validate_example_with_schema(example: Example, datatype: DataType, errors: dict[str, list[str]]) -> None:
        """Validate example using JSON Schema."""
        if not datatype.schema_def:
            return
        try:
            jsonschema.validate(example.input, datatype.schema_def)
            print(f"  ✅ Example {example.id}: schema valid for {datatype.id}")
        except jsonschema.ValidationError as exc:
            details = f"Example {example.id} invalid for DataType {datatype.id}: {exc.message}"
            errors["example_schemas"].append(details)
            print(f"  ❌ {details}")

    def _validate_example_with_pydantic(
        self: "Engine",
        example: Example,
        datatype: DataType,
        module_cache: dict[str, ModuleType | None],
        errors: dict[str, list[str]],
    ) -> None:
        """Validate example using Pydantic model."""
        module = self._get_datatype_module("models", module_cache, errors)
        if not module:
            return
        model_cls = getattr(module, datatype.id, None)
        if not model_cls:
            message = f"Example {example.id}: model class {datatype.id} not found"
            errors["example_schemas"].append(message)
            print(f"  ❌ {message}")
            return
        try:
            model_cls(**example.input)
            print(f"  ✅ Example {example.id}: pydantic validation passed for {datatype.id}")
        except Exception as exc:
            details = f"Example {example.id} invalid for DataType {datatype.id}: {exc}"
            errors["example_schemas"].append(details)
            print(f"  ❌ {details}")

    @staticmethod
    def _summarize_integrity(errors: dict[str, list[str]]) -> None:
        """Print a short summary for integrity validation."""
        total_errors = sum(len(errs) for errs in errors.values())
        if total_errors == 0:
            print("\n✅ All integrity checks passed!")
            return
        print(f"\n⚠️  Found {total_errors} integrity issue(s)")

    # ==================== Unlinked item detection (warning only) ====================

    def _collect_stage_io_datatypes(self: "Engine") -> set[str]:
        """Collect datatypes directly referenced by dag_stages input/output."""
        stage_io_dtypes: set[str] = set()
        for stage in self.spec.dag_stages:
            if stage.input_type:
                stage_io_dtypes.add(stage.input_type)
            if stage.output_type:
                stage_io_dtypes.add(stage.output_type)
        return stage_io_dtypes

    def _collect_stage_references(self: "Engine") -> tuple[set[str], set[str]]:
        """Collect transforms and datatypes directly referenced by stages (including nested refs)."""
        referenced_transforms: set[str] = set()
        referenced_dtypes: set[str] = set(self._collect_stage_io_datatypes())

        for stage in self.spec.dag_stages:
            for tid in stage.candidates:
                if tid:
                    referenced_transforms.add(tid)

        return referenced_transforms, referenced_dtypes

    def _collect_nested_datatype_refs(
        self: "Engine",
        dtype_id: str,
        visited: set[str] | None = None,
        dtype_by_id: dict[str, "DataType"] | None = None,
    ) -> set[str]:
        """Recursively collect all datatype references within a datatype definition.

        This includes:
        - datatype_ref in type_alias tuple elements
        - datatype_ref in generic element_type/key_type/value_type
        - datatype_ref in pydantic_model field types
        """
        if visited is None:
            visited = set()

        # Avoid infinite recursion
        if dtype_id in visited:
            return set()
        visited.add(dtype_id)

        if dtype_by_id is None:
            dtype_by_id = {dt.id: dt for dt in self.spec.datatypes}

        dtype = dtype_by_id.get(dtype_id)
        if not dtype:
            return set()

        nested_refs: set[str] = set()
        nested_refs.update(self._collect_refs_from_type_alias(dtype, visited, dtype_by_id))
        nested_refs.update(self._collect_refs_from_generic(dtype, visited, dtype_by_id))
        nested_refs.update(self._collect_refs_from_pydantic_model(dtype, visited, dtype_by_id))
        return nested_refs

    def _collect_refs_from_type_alias(
        self: "Engine",
        dtype: "DataType",
        visited: set[str],
        dtype_by_id: dict[str, "DataType"],
    ) -> set[str]:
        if not dtype.type_alias or not dtype.type_alias.elements:
            return set()
        nested_refs: set[str] = set()
        for element in dtype.type_alias.elements:
            nested_refs.update(self._collect_refs_from_node(element, visited, dtype_by_id))
        return nested_refs

    def _collect_refs_from_generic(
        self: "Engine",
        dtype: "DataType",
        visited: set[str],
        dtype_by_id: dict[str, "DataType"],
    ) -> set[str]:
        generic = dtype.generic
        if not generic:
            return set()
        nested_refs: set[str] = set()
        for node in (generic.element_type, generic.key_type, generic.value_type):
            nested_refs.update(self._collect_refs_from_node(node, visited, dtype_by_id))
        for element in generic.elements:
            nested_refs.update(self._collect_refs_from_node(element, visited, dtype_by_id))
        return nested_refs

    def _collect_refs_from_pydantic_model(
        self: "Engine",
        dtype: "DataType",
        visited: set[str],
        dtype_by_id: dict[str, "DataType"],
    ) -> set[str]:
        model = dtype.pydantic_model
        if not model or not model.fields:
            return set()
        nested_refs: set[str] = set()
        for field in model.fields:
            nested_refs.update(self._collect_refs_from_node(field.type, visited, dtype_by_id))
        return nested_refs

    def _collect_refs_from_node(
        self: "Engine",
        node: object,
        visited: set[str],
        dtype_by_id: dict[str, "DataType"],
    ) -> set[str]:
        if node is None:
            return set()
        nested_refs: set[str] = set()
        ref = self._extract_datatype_ref(node)
        if ref:
            nested_refs.add(ref)
            nested_refs.update(self._collect_nested_datatype_refs(ref, visited, dtype_by_id))
            return nested_refs
        if isinstance(node, dict):
            generic_section = node.get("generic")
            if isinstance(generic_section, dict):
                nested_refs.update(self._collect_refs_from_generic_dict(generic_section, visited, dtype_by_id))
        return nested_refs

    def _collect_refs_from_generic_dict(
        self: "Engine",
        generic_config: dict[str, object],
        visited: set[str],
        dtype_by_id: dict[str, "DataType"],
    ) -> set[str]:
        nested_refs: set[str] = set()
        for key in ("element_type", "key_type", "value_type"):
            nested_refs.update(self._collect_refs_from_node(generic_config.get(key), visited, dtype_by_id))
        elements = generic_config.get("elements", [])
        if isinstance(elements, list):
            for element in elements:
                nested_refs.update(self._collect_refs_from_node(element, visited, dtype_by_id))
        return nested_refs

    @staticmethod
    def _extract_datatype_ref(candidate: object) -> str | None:
        if isinstance(candidate, dict):
            ref = candidate.get("datatype_ref")
            if isinstance(ref, str):
                return ref
        return None

    def _collect_transform_datatypes(self: "Engine", transform_ids: set[str]) -> set[str]:
        """Collect datatypes referenced by transforms (input/return types and nested references)"""
        transform_by_id = {t.id: t for t in self.spec.transforms}
        referenced_dtypes: set[str] = set()

        for tid in transform_ids:
            transform = transform_by_id.get(tid)
            if not transform:
                continue

            # Collect datatype_ref from ALL parameters (not just first one)
            for param in transform.parameters:
                if param.datatype_ref:
                    referenced_dtypes.add(param.datatype_ref)
                    # Also collect nested references from this datatype
                    referenced_dtypes.update(self._collect_nested_datatype_refs(param.datatype_ref))

            # Return datatype
            if transform.return_datatype_ref:
                referenced_dtypes.add(transform.return_datatype_ref)
                # Also collect nested references from return type
                referenced_dtypes.update(self._collect_nested_datatype_refs(transform.return_datatype_ref))

        return referenced_dtypes

    def _collect_datatype_references(self: "Engine", dtype_ids: set[str]) -> tuple[set[str], set[str]]:
        """Collect examples and checks attached to datatypes"""
        dtype_by_id = {dt.id: dt for dt in self.spec.datatypes}
        referenced_examples: set[str] = set()
        referenced_checks: set[str] = set()

        for dtype_id in dtype_ids:
            dtype = dtype_by_id.get(dtype_id)
            if not dtype:
                continue
            referenced_examples.update(dtype.example_ids)
            referenced_checks.update(dtype.check_ids)

        return referenced_examples, referenced_checks

    def _detect_unlinked_items(self: "Engine") -> dict[str, set[str]]:
        """Detect unlinked items similar to frontend CardLibrary 'ungrouped' view.

        The detection is based on dag_stages:
          - referenced transforms: any transform listed in stage.candidates
            (candidates are auto-populated when missing)
          - referenced datatypes: stage.input_type/output_type, plus input/return
            datatype of referenced transforms
          - referenced examples/checks/generators: those attached to referenced datatypes

        Returns a mapping of category to unlinked id set.
        """
        # Ensure candidates are available to mirror frontend grouping
        _auto_collect_stage_candidates(self.spec)

        # Collect all items
        all_transforms = {t.id for t in self.spec.transforms}
        all_dtypes = {dt.id for dt in self.spec.datatypes}
        all_examples = {ex.id for ex in self.spec.examples}
        all_checks = {ck.id for ck in self.spec.checks}
        all_generators = set(self.spec.generators.keys())
        dtype_by_id = {dt.id: dt for dt in self.spec.datatypes}

        # Collect referenced items
        referenced_transforms, referenced_dtypes = self._collect_stage_references()
        referenced_dtypes.update(self._collect_transform_datatypes(referenced_transforms))
        referenced_examples, referenced_checks = self._collect_datatype_references(referenced_dtypes)
        referenced_generators: set[str] = set()
        if all_generators:
            for dtype_id in referenced_dtypes:
                dtype = dtype_by_id.get(dtype_id)
                if not dtype:
                    continue
                referenced_generators.update(dtype.generator_refs)

        return {
            "transforms": all_transforms - referenced_transforms,
            "datatypes": all_dtypes - referenced_dtypes,
            "examples": all_examples - referenced_examples,
            "checks": all_checks - referenced_checks,
            "generators": all_generators - referenced_generators,
        }

    @staticmethod
    def _collect_example_usage_map(datatypes: Iterable[DataType]) -> dict[str, list[str]]:
        """Build a mapping from example id to datatypes referencing it."""
        usage: dict[str, list[str]] = {}
        for datatype in datatypes:
            for example_id in datatype.example_ids:
                usage.setdefault(example_id, []).append(datatype.id)
        return usage

    @staticmethod
    def _collect_generator_usage_map(datatypes: Iterable[DataType]) -> dict[str, list[str]]:
        """Build a mapping from generator id to datatypes referencing it."""
        usage: dict[str, list[str]] = {}
        for datatype in datatypes:
            for generator_id in datatype.generator_refs:
                usage.setdefault(generator_id, []).append(datatype.id)
        return usage

    @staticmethod
    def _print_transform_unlinked(item_id: str) -> None:
        print(f"  ⚠️  Unlinked transform: '{item_id}' is not referenced by any stage candidates")

    @staticmethod
    def _print_datatype_unlinked(item_id: str, stage_io_datatypes: set[str]) -> None:
        if item_id in stage_io_datatypes:
            print(f"  ⚠️  Unlinked datatype: '{item_id}' is not used in stages or transforms")
        else:
            print(f"  ℹ️  Unlinked datatype: '{item_id}'{UNLINKED_INFO_SUFFIX}")

    @staticmethod
    def _print_example_unlinked(
        item_id: str,
        stage_io_datatypes: set[str],
        example_usage: dict[str, list[str]],
    ) -> None:
        linked_dtypes = example_usage.get(item_id, [])
        if linked_dtypes and all(dtype not in stage_io_datatypes for dtype in linked_dtypes):
            print(f"  ℹ️  Unlinked example: '{item_id}'{UNLINKED_INFO_SUFFIX}")
        else:
            print(f"  ⚠️  Unlinked example: '{item_id}' is not attached to any used datatype")

    @staticmethod
    def _print_check_unlinked(item_id: str) -> None:
        print(f"  ⚠️  Unlinked check: '{item_id}' is not attached to any used datatype")

    @staticmethod
    def _print_generator_unlinked(
        item_id: str,
        stage_io_datatypes: set[str],
        generator_usage: dict[str, list[str]],
    ) -> None:
        linked_dtypes = generator_usage.get(item_id, [])
        if linked_dtypes and all(dtype not in stage_io_datatypes for dtype in linked_dtypes):
            print(f"  ℹ️  Unlinked generator: '{item_id}'{UNLINKED_INFO_SUFFIX}")
            return
        if linked_dtypes:
            joined = ", ".join(linked_dtypes)
            print(f"  ⚠️  Unlinked generator: '{item_id}' is only referenced by unused datatype(s): {joined}")
            return
        print(f"  ⚠️  Unlinked generator: '{item_id}' is not referenced by any datatype")

    @staticmethod
    def _print_generic_unlinked(category: str, item_id: str) -> None:
        print(f"  ⚠️  Unlinked {category[:-1]}: '{item_id}'")

    def _build_unlinked_handlers(
        self: "Engine",
        stage_io_datatypes: set[str],
        example_usage: dict[str, list[str]],
        generator_usage: dict[str, list[str]],
    ) -> dict[str, Callable[[str], None]]:
        """Prepare warning handler functions per category."""
        handlers: dict[str, Callable[[str], None]] = {
            "transforms": self._print_transform_unlinked,
            "datatypes": lambda item_id: self._print_datatype_unlinked(item_id, stage_io_datatypes),
            "examples": lambda item_id: self._print_example_unlinked(item_id, stage_io_datatypes, example_usage),
            "checks": self._print_check_unlinked,
            "generators": lambda item_id: self._print_generator_unlinked(
                item_id,
                stage_io_datatypes,
                generator_usage,
            ),
        }
        return handlers

    def _warn_unlinked_items(self: "Engine") -> None:
        """Print warnings for unlinked items without failing validation."""
        unlinked = self._detect_unlinked_items()
        stage_io_datatypes = self._collect_stage_io_datatypes()
        example_usage = self._collect_example_usage_map(self.spec.datatypes)
        generator_usage = self._collect_generator_usage_map(self.spec.datatypes)
        handlers = self._build_unlinked_handlers(stage_io_datatypes, example_usage, generator_usage)

        has_items = False
        for category, ids in unlinked.items():
            handler = handlers.get(category)
            for item_id in sorted(ids):
                has_items = True
                if handler:
                    handler(item_id)
                else:
                    self._print_generic_unlinked(category, item_id)
        if not has_items:
            print("  ✅ No unlinked items detected")

    def build_stage_groups(self: "Engine") -> list[dict[str, Any]]:
        """Build DAG stage groups with related card IDs.

        This is the single source of truth for stage-card relationships.
        card_exporter should call this method and simply convert the result to JSON.

        Returns:
            List of stage groups, each containing:
            - stage metadata (stage_id, input_type, output_type, etc.)
            - related_card_ids: dict with keys:
                - stage_id: str (the stage itself)
                - input_dtype_id: str | None
                - output_dtype_id: str | None
                - transform_ids: list[str]
                - datatype_ids: list[str] (all related datatypes including nested)
                - example_ids: list[str]
                - check_ids: list[str]
                - generator_ids: list[str]
        """
        # Ensure candidates are populated
        _auto_collect_stage_candidates(self.spec)

        stage_groups = []
        dtype_by_id = {dt.id: dt for dt in self.spec.datatypes}

        for stage in self.spec.dag_stages:
            stage_id = stage.stage_id
            input_type = stage.input_type
            output_type = stage.output_type

            # Collect transform IDs (handle both str and DAGStageCandidate)
            transform_ids = [c.transform_id if hasattr(c, "transform_id") else c for c in stage.candidates]

            # Collect all related datatypes
            all_dtype_ids: set[str] = set()

            # Add input/output types
            if input_type:
                all_dtype_ids.add(input_type)
                all_dtype_ids.update(self._collect_nested_datatype_refs(input_type))
            if output_type:
                all_dtype_ids.add(output_type)
                all_dtype_ids.update(self._collect_nested_datatype_refs(output_type))

            # Add datatypes from transform parameters
            all_dtype_ids.update(self._collect_transform_datatypes(set(transform_ids)))

            # Collect examples and checks from all related datatypes
            example_ids, check_ids = self._collect_datatype_references(all_dtype_ids)
            generator_ids: set[str] = set()
            for dtype_id in all_dtype_ids:
                dtype = dtype_by_id.get(dtype_id)
                if not dtype:
                    continue
                generator_ids.update(dtype.generator_refs)

            stage_groups.append(
                {
                    "stage_id": stage_id,
                    "description": stage.description,
                    "input_type": input_type,
                    "output_type": output_type,
                    "selection_mode": stage.selection_mode,
                    "max_select": stage.max_select,
                    "related_card_ids": {
                        "stage_id": stage_id,
                        "input_dtype_id": input_type,
                        "output_dtype_id": output_type,
                        "transform_ids": transform_ids,
                        "datatype_ids": sorted(all_dtype_ids),
                        "example_ids": sorted(example_ids),
                        "check_ids": sorted(check_ids),
                        "generator_ids": sorted(generator_ids),
                    },
                }
            )

        return stage_groups

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

"""spectool.core.base: IR（中間表現）とメタ型定義

純粋なデータ定義（最下層）
"""

from .ir import (
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
from .meta_types import (
    CheckedSpec,
    ExampleSpec,
    GeneratorSpec,
    PydanticRowRef,
    SchemaSpec,
)

__all__ = [
    # IR data classes
    "CheckSpec",
    "ColumnRule",
    "DAGStageSpec",
    "EnumMemberSpec",
    "EnumSpec",
    "ExampleCase",
    "FrameSpec",
    "GeneratorDef",
    "GenericSpec",
    "IndexRule",
    "MetaSpec",
    "MultiIndexLevel",
    "ParameterSpec",
    "PydanticModelSpec",
    "SpecIR",
    "TransformSpec",
    "TypeAliasSpec",
    # Meta types
    "CheckedSpec",
    "ExampleSpec",
    "GeneratorSpec",
    "PydanticRowRef",
    "SchemaSpec",
]

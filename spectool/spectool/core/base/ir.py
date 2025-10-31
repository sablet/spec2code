"""中間表現（IR）データ構造定義

Spec→IR→各バックエンドの一貫性を保つための中間表現。
DataFrame中心のIR設計（Pydantic/Enum/GenericはPython型参照で解決）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IndexRule:
    """DataFrame Index定義"""

    name: str
    dtype: str  # "datetime", "int", "str" など
    nullable: bool = False
    unique: bool = False
    monotonic: str = ""  # "increasing", "decreasing", ""
    coerce: bool = True
    description: str = ""


@dataclass
class MultiIndexLevel:
    """MultiIndex レベル定義"""

    name: str
    dtype: str
    enum: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ColumnRule:
    """DataFrame Column定義"""

    name: str
    dtype: str  # "float", "int", "str", "datetime" など
    nullable: bool = False
    unique: bool = False
    coerce: bool = True
    checks: list[dict[str, Any]] = field(default_factory=list)
    description: str = ""


@dataclass
class FrameSpec:
    """DataFrame制約定義

    Attributes:
        id: DataFrame型のID
        description: 説明
        index: Index定義（単一）
        multi_index: MultiIndex定義
        columns: Column定義リスト
        checks: DataFrameレベルチェック
        row_model: Python型参照（"pkg.mod:OHLCVRowModel"形式）
        generator_factory: 生成関数参照（"apps.gen:func"形式）
        check_functions: Check関数リスト（"apps.checks:check_ohlcv"形式）
        strict: 定義されていないカラムを許可しない
        coerce: 型強制
        ordered: カラム順序を強制
        examples: 例示データ
    """

    id: str
    description: str = ""
    index: IndexRule | None = None
    multi_index: list[MultiIndexLevel] = field(default_factory=list)
    columns: list[ColumnRule] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    row_model: str | None = None
    generator_factory: str | None = None
    check_functions: list[str] = field(default_factory=list)
    strict: bool = False
    coerce: bool = True
    ordered: bool = False
    examples: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EnumMemberSpec:
    """Enumメンバー定義"""

    name: str
    value: Any
    description: str = ""


@dataclass
class EnumSpec:
    """Enum定義（メタデータ付き）

    Attributes:
        id: Enum型のID
        description: 説明
        base_type: 基底型（"int", "str", "float"）
        members: メンバーリスト
        examples: 例示データ
        check_functions: Check関数リスト
    """

    id: str
    description: str = ""
    base_type: str = "str"
    members: list[EnumMemberSpec] = field(default_factory=list)
    examples: list[Any] = field(default_factory=list)
    check_functions: list[str] = field(default_factory=list)


@dataclass
class ParameterSpec:
    """関数パラメータ定義"""

    name: str
    type_ref: str  # datatype_ref または native
    optional: bool = False
    default: Any = None
    description: str = ""


@dataclass
class TransformSpec:
    """Transform定義

    Attributes:
        id: Transform ID
        description: 説明
        impl: 実装関数参照（"module:function"形式）
        file_path: ファイルパス
        parameters: パラメータリスト
        return_type_ref: 戻り値型参照
        default_args: デフォルト引数
        spec_metadata: 追加のメタデータ（docstring生成用、任意の構造）
    """

    id: str
    description: str = ""
    impl: str = ""
    file_path: str = ""
    parameters: list[ParameterSpec] = field(default_factory=list)
    return_type_ref: str | None = None
    default_args: dict[str, Any] = field(default_factory=dict)
    spec_metadata: dict[str, Any] | None = None


@dataclass
class DAGStageSpec:
    """DAG Stage定義

    Attributes:
        stage_id: ステージID
        description: 説明
        selection_mode: 選択モード（"single", "exclusive", "multiple"）
        max_select: 最大選択数
        input_type: 入力型参照
        output_type: 出力型参照
        candidates: Transform IDリスト
        default_transform_id: デフォルトTransform ID
        publish_output: 出力を公開するか
        collect_output: 出力を収集するか
    """

    stage_id: str
    description: str = ""
    selection_mode: str = "single"
    max_select: int | None = None
    input_type: str = ""
    output_type: str = ""
    candidates: list[str] = field(default_factory=list)
    default_transform_id: str | None = None
    publish_output: bool = False
    collect_output: bool = False


@dataclass
class CheckSpec:
    """Check関数定義

    Attributes:
        id: Check ID
        description: 説明
        impl: 実装関数参照（"module:function"形式）
        file_path: ファイルパス
        input_type_ref: 入力型参照
        spec_metadata: 追加のメタデータ（docstring生成用、任意の構造）
    """

    id: str
    description: str = ""
    impl: str = ""
    file_path: str = ""
    input_type_ref: str | None = None
    spec_metadata: dict[str, Any] | None = None


@dataclass
class ExampleCase:
    """検証用入力・期待値定義"""

    id: str
    description: str = ""
    datatype_ref: str = ""
    transform_ref: str = ""
    input: dict[str, Any] = field(default_factory=dict)
    expected: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratorDef:
    """データ生成関数定義

    Attributes:
        id: Generator ID
        description: 説明
        impl: 実装関数参照（"module:function"形式）
        file_path: ファイルパス
        parameters: パラメータリスト
        return_type_ref: 戻り値型参照
        spec_metadata: 追加のメタデータ（docstring生成用、任意の構造）
    """

    id: str
    description: str = ""
    impl: str = ""
    file_path: str = ""
    parameters: list[ParameterSpec] = field(default_factory=list)
    return_type_ref: str | None = None
    spec_metadata: dict[str, Any] | None = None


@dataclass
class PydanticModelSpec:
    """Pydanticモデル定義

    Attributes:
        id: モデルID
        description: 説明
        fields: フィールド定義リスト
        base_class: 基底クラス
        examples: 例示データ
        check_functions: Check関数リスト
    """

    id: str
    description: str = ""
    fields: list[dict[str, Any]] = field(default_factory=list)
    base_class: str = "BaseModel"
    examples: list[dict[str, Any]] = field(default_factory=list)
    check_functions: list[str] = field(default_factory=list)


@dataclass
class TypeAliasSpec:
    """型エイリアス定義"""

    id: str
    description: str = ""
    type_def: dict[str, Any] = field(default_factory=dict)
    examples: list[Any] = field(default_factory=list)
    check_functions: list[str] = field(default_factory=list)


@dataclass
class GenericSpec:
    """Generic型定義"""

    id: str
    description: str = ""
    container: str = "list"  # "list", "dict", "set", "tuple"
    element_type: dict[str, Any] | None = None
    key_type: dict[str, Any] | None = None
    value_type: dict[str, Any] | None = None
    elements: list[dict[str, Any]] = field(default_factory=list)
    examples: list[Any] = field(default_factory=list)
    check_functions: list[str] = field(default_factory=list)


@dataclass
class MetaSpec:
    """メタデータ"""

    name: str
    description: str = ""
    version: str = "1.0"


@dataclass
class SpecIR:
    """統合IR（中間表現）

    全てのSpec要素を統合した中間表現。
    Loader→Normalizer→Validator→Backendの各段階で使用される。

    Attributes:
        meta: メタデータ
        frames: DataFrame定義リスト
        enums: Enum定義リスト
        pydantic_models: Pydanticモデル定義リスト
        type_aliases: 型エイリアス定義リスト
        generics: Generic型定義リスト
        transforms: Transform定義リスト
        dag_stages: DAG Stage定義リスト
        checks: Check関数定義リスト
        examples: Example定義リスト
        generators: Generator関数定義リスト
    """

    meta: MetaSpec
    frames: list[FrameSpec] = field(default_factory=list)
    enums: list[EnumSpec] = field(default_factory=list)
    pydantic_models: list[PydanticModelSpec] = field(default_factory=list)
    type_aliases: list[TypeAliasSpec] = field(default_factory=list)
    generics: list[GenericSpec] = field(default_factory=list)
    transforms: list[TransformSpec] = field(default_factory=list)
    dag_stages: list[DAGStageSpec] = field(default_factory=list)
    checks: list[CheckSpec] = field(default_factory=list)
    examples: list[ExampleCase] = field(default_factory=list)
    generators: list[GeneratorDef] = field(default_factory=list)

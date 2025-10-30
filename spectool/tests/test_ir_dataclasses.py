"""IRデータクラスの単体テスト"""

import pytest
from spectool.spectool.core.base import (
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


def test_frame_spec_creation():
    """FrameSpecの作成テスト"""
    frame = FrameSpec(
        id="TestFrame",
        description="Test DataFrame",
        index=IndexRule(name="idx", dtype="int"),
        columns=[
            ColumnRule(name="col1", dtype="float"),
            ColumnRule(name="col2", dtype="str"),
        ],
    )
    assert frame.id == "TestFrame"
    assert frame.description == "Test DataFrame"
    assert frame.index is not None
    assert frame.index.name == "idx"
    assert len(frame.columns) == 2


def test_frame_spec_with_row_model():
    """FrameSpec with row_model テスト"""
    frame = FrameSpec(
        id="OHLCVFrame",
        description="OHLCV DataFrame",
        row_model="apps.models:OHLCVRowModel",
        generator_factory="apps.generators:generate_ohlcv",
        check_functions=["apps.checks:check_ohlcv"],
    )
    assert frame.row_model == "apps.models:OHLCVRowModel"
    assert frame.generator_factory == "apps.generators:generate_ohlcv"
    assert len(frame.check_functions) == 1


def test_enum_spec_creation():
    """EnumSpecの作成テスト"""
    enum = EnumSpec(
        id="AssetClass",
        description="Asset class enumeration",
        base_type="str",
        members=[
            EnumMemberSpec(name="EQUITY", value="equity", description="Equity assets"),
            EnumMemberSpec(name="CRYPTO", value="crypto", description="Cryptocurrency"),
        ],
        examples=["EQUITY", "CRYPTO"],
    )
    assert enum.id == "AssetClass"
    assert enum.base_type == "str"
    assert len(enum.members) == 2
    assert len(enum.examples) == 2


def test_transform_spec_creation():
    """TransformSpecの作成テスト"""
    transform = TransformSpec(
        id="process_data",
        description="Process data",
        impl="apps.transforms:process",
        file_path="apps/transforms/data_ops.py",
        parameters=[
            ParameterSpec(name="data", type_ref="DataFrame"),
            ParameterSpec(name="threshold", type_ref="builtins:float", optional=True, default=0.5),
        ],
        return_type_ref="ProcessedData",
    )
    assert transform.id == "process_data"
    assert len(transform.parameters) == 2
    assert transform.parameters[1].optional is True


def test_dag_stage_spec_creation():
    """DAGStageSpecの作成テスト"""
    stage = DAGStageSpec(
        stage_id="stage_1",
        description="First stage",
        selection_mode="single",
        input_type="RawData",
        output_type="ProcessedData",
        candidates=["transform_a", "transform_b"],
        default_transform_id="transform_a",
    )
    assert stage.stage_id == "stage_1"
    assert stage.selection_mode == "single"
    assert len(stage.candidates) == 2


def test_spec_ir_creation():
    """SpecIRの作成テスト"""
    ir = SpecIR(
        meta=MetaSpec(name="test_project", description="Test project", version="1.0"),
        frames=[
            FrameSpec(
                id="TestFrame",
                columns=[ColumnRule(name="col1", dtype="float")],
            )
        ],
        enums=[
            EnumSpec(
                id="Status",
                members=[EnumMemberSpec(name="ACTIVE", value="active")],
            )
        ],
    )
    assert ir.meta.name == "test_project"
    assert len(ir.frames) == 1
    assert len(ir.enums) == 1


def test_check_spec_creation():
    """CheckSpecの作成テスト"""
    check = CheckSpec(
        id="validate_positive",
        description="Validate positive values",
        impl="apps.checks:validate_positive",
        file_path="apps/checks/validators.py",
    )
    assert check.id == "validate_positive"
    assert check.impl == "apps.checks:validate_positive"


def test_example_case_creation():
    """ExampleCaseの作成テスト"""
    example = ExampleCase(
        id="example_1",
        description="Example test case",
        input={"value": 10},
        expected={"result": 20},
    )
    assert example.id == "example_1"
    assert example.input["value"] == 10
    assert example.expected["result"] == 20


def test_generator_def_creation():
    """GeneratorDefの作成テスト"""
    generator = GeneratorDef(
        id="generate_sample",
        description="Generate sample data",
        impl="apps.generators:generate_sample",
        file_path="apps/generators/data_gen.py",
        parameters=[ParameterSpec(name="size", type_ref="builtins:int")],
    )
    assert generator.id == "generate_sample"
    assert len(generator.parameters) == 1


def test_pydantic_model_spec_creation():
    """PydanticModelSpecの作成テスト"""
    model = PydanticModelSpec(
        id="UserModel",
        description="User data model",
        fields=[
            {"name": "name", "type": {"native": "builtins:str"}, "required": True},
            {"name": "age", "type": {"native": "builtins:int"}, "required": True},
        ],
        base_class="BaseModel",
    )
    assert model.id == "UserModel"
    assert len(model.fields) == 2


def test_type_alias_spec_creation():
    """TypeAliasSpecの作成テスト"""
    alias = TypeAliasSpec(
        id="UserId",
        description="User ID type",
        type_def={"native": "builtins:str"},
        examples=["user_123", "user_456"],
    )
    assert alias.id == "UserId"
    assert len(alias.examples) == 2


def test_generic_spec_creation():
    """GenericSpecの作成テスト"""
    generic = GenericSpec(
        id="StringList",
        description="List of strings",
        container="list",
        element_type={"native": "builtins:str"},
        examples=[["a", "b", "c"]],
    )
    assert generic.id == "StringList"
    assert generic.container == "list"


def test_multi_index_level():
    """MultiIndexLevelの作成テスト"""
    level = MultiIndexLevel(
        name="date",
        dtype="datetime",
        enum=[],
        description="Date level",
    )
    assert level.name == "date"
    assert level.dtype == "datetime"


def test_column_rule_with_checks():
    """ColumnRule with checksテスト"""
    column = ColumnRule(
        name="price",
        dtype="float",
        nullable=False,
        checks=[
            {"type": "ge", "value": 0},
            {"type": "le", "value": 1000000},
        ],
    )
    assert column.name == "price"
    assert len(column.checks) == 2


def test_parameter_spec_optional():
    """ParameterSpec optionalテスト"""
    param = ParameterSpec(
        name="threshold",
        type_ref="builtins:float",
        optional=True,
        default=0.5,
    )
    assert param.optional is True
    assert param.default == 0.5

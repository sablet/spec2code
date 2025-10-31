"""Card Exporter テストコード

SpecIRからJSONカード形式への変換をテスト。
"""

from __future__ import annotations

from spectool.spectool.core.base.ir import (
    CheckSpec,
    DAGStageSpec,
    EnumMemberSpec,
    EnumSpec,
    ExampleCase,
    FrameSpec,
    GeneratorDef,
    GenericSpec,
    IndexRule,
    MetaSpec,
    ParameterSpec,
    PydanticModelSpec,
    SpecIR,
    TransformSpec,
    TypeAliasSpec,
    ColumnRule,
    SpecMetadata,
)
from spectool.spectool.core.export.card_exporter import export_spec_to_cards, spec_to_card


def test_spec_to_card_basic():
    """基本的なカード変換をテスト"""
    check = CheckSpec(
        id="test_check",
        description="Test check function",
        impl="apps.test:check_func",
        file_path="checks/test.py",
        input_type_ref="TestFrame",
    )

    card = spec_to_card(check, "check", "test-spec")

    assert card["id"] == "test_check"
    assert card["category"] == "check"
    assert card["name"] == "test_check"
    assert card["description"] == "Test check function"
    assert card["source_spec"] == "test-spec"
    assert "data" in card
    assert card["data"]["impl"] == "apps.test:check_func"
    assert card["data"]["file_path"] == "checks/test.py"
    assert card["data"]["input_type_ref"] == "TestFrame"


def test_export_checks():
    """checkカードの変換をテスト"""
    spec_ir = SpecIR(
        meta=MetaSpec(name="test-spec", version="1.0"),
        checks=[
            CheckSpec(
                id="check_frame",
                description="Validate frame",
                impl="apps.test:check_frame",
                file_path="checks/checks.py",
                input_type_ref="DataFrame",
            )
        ],
    )

    result = export_spec_to_cards(spec_ir, "specs/test.yaml")

    assert len(result["cards"]) == 1
    card = result["cards"][0]
    assert card["category"] == "check"
    assert card["id"] == "check_frame"


def test_export_generators():
    """generatorカードの変換をテスト"""
    spec_ir = SpecIR(
        meta=MetaSpec(name="test-spec", version="1.0"),
        generators=[
            GeneratorDef(
                id="gen_data",
                description="Generate test data",
                impl="apps.test:gen_data",
                file_path="generators/gen.py",
                return_type_ref="TestFrame",
                parameters=[ParameterSpec(name="count", type_ref="builtins:int", optional=False)],
            )
        ],
    )

    result = export_spec_to_cards(spec_ir, "specs/test.yaml")

    assert len(result["cards"]) == 1
    card = result["cards"][0]
    assert card["category"] == "generator"
    assert card["id"] == "gen_data"
    assert "parameters" in card["data"]


def test_export_frames():
    """dtype_frameカードの変換をテスト"""
    spec_ir = SpecIR(
        meta=MetaSpec(name="test-spec", version="1.0"),
        frames=[
            FrameSpec(
                id="TestFrame",
                description="Test DataFrame",
                index=IndexRule(name="timestamp", dtype="datetime"),
                columns=[
                    ColumnRule(name="value", dtype="float", nullable=False),
                ],
                strict=True,
            )
        ],
    )

    result = export_spec_to_cards(spec_ir, "specs/test.yaml")

    assert len(result["cards"]) == 1
    card = result["cards"][0]
    assert card["category"] == "dtype_frame"
    assert card["id"] == "TestFrame"
    assert "index" in card["data"]
    assert "columns" in card["data"]


def test_export_enums():
    """dtype_enumカードの変換をテスト"""
    spec_ir = SpecIR(
        meta=MetaSpec(name="test-spec", version="1.0"),
        enums=[
            EnumSpec(
                id="Status",
                description="Status enum",
                base_type="str",
                members=[
                    EnumMemberSpec(name="ACTIVE", value="active"),
                    EnumMemberSpec(name="INACTIVE", value="inactive"),
                ],
            )
        ],
    )

    result = export_spec_to_cards(spec_ir, "specs/test.yaml")

    assert len(result["cards"]) == 1
    card = result["cards"][0]
    assert card["category"] == "dtype_enum"
    assert card["id"] == "Status"
    assert "members" in card["data"]
    assert len(card["data"]["members"]) == 2


def test_export_pydantic_models():
    """dtype_pydanticカードの変換をテスト"""
    spec_ir = SpecIR(
        meta=MetaSpec(name="test-spec", version="1.0"),
        pydantic_models=[
            PydanticModelSpec(
                id="Config",
                description="Configuration model",
                fields=[{"name": "api_key", "type_ref": "builtins:str", "optional": False}],
            )
        ],
    )

    result = export_spec_to_cards(spec_ir, "specs/test.yaml")

    assert len(result["cards"]) == 1
    card = result["cards"][0]
    assert card["category"] == "dtype_pydantic"
    assert card["id"] == "Config"
    assert "fields" in card["data"]


def test_export_type_aliases():
    """dtype_aliasカードの変換をテスト"""
    spec_ir = SpecIR(
        meta=MetaSpec(name="test-spec", version="1.0"),
        type_aliases=[
            TypeAliasSpec(
                id="DataPair",
                description="Pair of data",
                type_def={"alias_type": "tuple", "elements": [{"datatype_ref": "Data"}, {"datatype_ref": "Data"}]},
            )
        ],
    )

    result = export_spec_to_cards(spec_ir, "specs/test.yaml")

    assert len(result["cards"]) == 1
    card = result["cards"][0]
    assert card["category"] == "dtype_alias"
    assert card["id"] == "DataPair"
    assert "type_def" in card["data"]


def test_export_generics():
    """dtype_genericカードの変換をテスト"""
    spec_ir = SpecIR(
        meta=MetaSpec(name="test-spec", version="1.0"),
        generics=[
            GenericSpec(
                id="DataList", description="List of data", container="list", element_type={"datatype_ref": "Data"}
            )
        ],
    )

    result = export_spec_to_cards(spec_ir, "specs/test.yaml")

    assert len(result["cards"]) == 1
    card = result["cards"][0]
    assert card["category"] == "dtype_generic"
    assert card["id"] == "DataList"
    assert card["data"]["container"] == "list"


def test_export_examples():
    """exampleカードの変換をテスト"""
    spec_ir = SpecIR(
        meta=MetaSpec(name="test-spec", version="1.0"),
        examples=[
            ExampleCase(
                id="ex_data",
                description="Example data",
                datatype_ref="Data",
                input={"value": 42},
                expected={"valid": True},
            )
        ],
    )

    result = export_spec_to_cards(spec_ir, "specs/test.yaml")

    assert len(result["cards"]) == 1
    card = result["cards"][0]
    assert card["category"] == "example"
    assert card["id"] == "ex_data"
    assert "input" in card["data"]
    assert "expected" in card["data"]


def test_export_transforms():
    """transformカードの変換をテスト"""
    spec_ir = SpecIR(
        meta=MetaSpec(name="test-spec", version="1.0"),
        transforms=[
            TransformSpec(
                id="process_data",
                description="Process data",
                impl="apps.test:process",
                file_path="transforms/process.py",
                return_type_ref="ProcessedData",
                parameters=[ParameterSpec(name="data", type_ref="RawData", optional=False)],
            )
        ],
    )

    result = export_spec_to_cards(spec_ir, "specs/test.yaml")

    assert len(result["cards"]) == 1
    card = result["cards"][0]
    assert card["category"] == "transform"
    assert card["id"] == "process_data"
    assert "parameters" in card["data"]


def test_export_dag_stages():
    """dag_stageカードの変換をテスト"""
    spec_ir = SpecIR(
        meta=MetaSpec(name="test-spec", version="1.0"),
        dag_stages=[
            DAGStageSpec(
                stage_id="stage_process",
                description="Processing stage",
                selection_mode="single",
                input_type="RawData",
                output_type="ProcessedData",
                candidates=["process_data"],
                default_transform_id="process_data",
            )
        ],
    )

    result = export_spec_to_cards(spec_ir, "specs/test.yaml")

    assert len(result["cards"]) == 1
    card = result["cards"][0]
    assert card["category"] == "dag_stage"
    assert card["id"] == "stage_process"
    assert card["data"]["selection_mode"] == "single"


def test_export_with_spec_metadata():
    """spec_metadataを含むカードの変換をテスト"""
    spec_ir = SpecIR(
        meta=MetaSpec(name="test-spec", version="1.0"),
        checks=[
            CheckSpec(
                id="check_data",
                description="Check data",
                impl="apps.test:check_data",
                file_path="checks/checks.py",
                input_type_ref="Data",
                spec_metadata=SpecMetadata(
                    logic_steps=["Step 1", "Step 2"],
                    implementation_hints=["Hint 1"],
                    explicit_checks=["Check 1"],
                ),
            )
        ],
    )

    result = export_spec_to_cards(spec_ir, "specs/test.yaml")

    assert len(result["cards"]) == 1
    card = result["cards"][0]
    assert "spec_metadata" in card["data"]
    assert card["data"]["spec_metadata"]["logic_steps"] == ["Step 1", "Step 2"]


def test_export_metadata():
    """メタデータの変換をテスト"""
    spec_ir = SpecIR(
        meta=MetaSpec(name="test-project", version="2.0", description="Test project description"),
    )

    result = export_spec_to_cards(spec_ir, "specs/test-project.yaml")

    assert result["metadata"]["source_file"] == "test-project.yaml"
    assert result["metadata"]["spec_name"] == "test-project"
    assert result["metadata"]["version"] == "2.0"
    assert result["metadata"]["description"] == "Test project description"


def test_export_multiple_categories():
    """複数カテゴリの統合変換をテスト"""
    spec_ir = SpecIR(
        meta=MetaSpec(name="multi-spec", version="1.0"),
        checks=[CheckSpec(id="check1", impl="apps:check1", file_path="checks/c.py")],
        generators=[GeneratorDef(id="gen1", impl="apps:gen1", file_path="generators/g.py")],
        frames=[FrameSpec(id="Frame1")],
        enums=[EnumSpec(id="Enum1")],
        transforms=[TransformSpec(id="transform1", impl="apps:t1", file_path="transforms/t.py")],
    )

    result = export_spec_to_cards(spec_ir, "specs/multi.yaml")

    # 合計5つのカードが生成されることを確認
    assert len(result["cards"]) == 5

    # カテゴリ別に確認
    categories = {card["category"] for card in result["cards"]}
    assert categories == {"check", "generator", "dtype_frame", "dtype_enum", "transform"}

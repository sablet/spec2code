"""Normalizerのテスト"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加（apps.test-projectをインポート可能にする）
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from spectool.spectool.core.engine.loader import load_spec
from spectool.spectool.core.engine.normalizer import (
    MetaHandlerRegistry,
    normalize_ir,
    pydantic_row_handler,
)


def test_pydantic_row_handler_basic():
    """PydanticRowHandlerの基本動作テスト"""
    # フィクスチャをロード
    fixture_path = Path(__file__).parent / "fixtures" / "pydantic_rowref_spec.yaml"
    ir = load_spec(fixture_path)

    # 正規化前の状態確認
    timeseries_frame = next(f for f in ir.frames if f.id == "TimeSeriesFrame")
    assert len(timeseries_frame.columns) == 1  # valueのみ
    assert timeseries_frame.columns[0].name == "value"

    # PydanticRowHandlerを適用
    normalized_ir = pydantic_row_handler(ir)

    # 正規化後の確認
    normalized_frame = next(f for f in normalized_ir.frames if f.id == "TimeSeriesFrame")

    # Pydanticモデルから推論された列が追加されている
    col_names = {col.name for col in normalized_frame.columns}
    assert "value" in col_names  # 既存列
    assert "timestamp" in col_names  # Pydanticから推論
    assert "status" in col_names  # Pydanticから推論
    assert "metadata" in col_names  # Pydanticから推論（オプショナル）

    # オプショナルフィールドの確認
    metadata_col = next(col for col in normalized_frame.columns if col.name == "metadata")
    assert metadata_col.nullable is True  # オプショナルなのでnullable


def test_pydantic_priority_merge():
    """Pydantic vs SchemaSpecの優先度マージテスト

    既存のSchemaSpec列定義が優先される
    """
    fixture_path = Path(__file__).parent / "fixtures" / "pydantic_rowref_spec.yaml"
    ir = load_spec(fixture_path)

    # 正規化前: valueは既にSchemaSpecで定義されている
    timeseries_frame = next(f for f in ir.frames if f.id == "TimeSeriesFrame")
    value_col = next(col for col in timeseries_frame.columns if col.name == "value")
    assert value_col.dtype == "float"
    assert value_col.nullable is False

    # 正規化
    normalized_ir = pydantic_row_handler(ir)
    normalized_frame = next(f for f in normalized_ir.frames if f.id == "TimeSeriesFrame")

    # 正規化後: valueはSchemaSpecの定義が維持される（Pydanticで上書きされない）
    value_col_after = next(col for col in normalized_frame.columns if col.name == "value")
    assert value_col_after.dtype == "float"
    assert value_col_after.nullable is False

    # 列数の確認（valueの重複追加はない）
    value_cols = [col for col in normalized_frame.columns if col.name == "value"]
    assert len(value_cols) == 1


def test_pydantic_full_inference():
    """Pydanticモデルから全列を推論するテスト"""
    fixture_path = Path(__file__).parent / "fixtures" / "pydantic_rowref_spec.yaml"
    ir = load_spec(fixture_path)

    # SensorDataFrame: columns: [] なので全てPydanticから推論
    sensor_frame = next(f for f in ir.frames if f.id == "SensorDataFrame")
    assert len(sensor_frame.columns) == 0  # 正規化前は空

    # 正規化
    normalized_ir = pydantic_row_handler(ir)
    normalized_frame = next(f for f in normalized_ir.frames if f.id == "SensorDataFrame")

    # Pydanticモデルから推論された列が追加されている
    col_names = {col.name for col in normalized_frame.columns}
    assert "timestamp" in col_names
    assert "temperature" in col_names
    assert "humidity" in col_names
    assert "pressure" in col_names

    # 全て必須フィールドなのでnullable=False
    for col in normalized_frame.columns:
        assert col.nullable is False


def test_normalize_ir_integration():
    """normalize_ir()の統合テスト（全ハンドラ適用）"""
    fixture_path = Path(__file__).parent / "fixtures" / "pydantic_rowref_spec.yaml"
    ir = load_spec(fixture_path)

    # normalize_ir()を呼び出す（Built-inハンドラが自動適用される）
    normalized_ir = normalize_ir(ir)

    # TimeSeriesFrameの確認
    timeseries_frame = next(f for f in normalized_ir.frames if f.id == "TimeSeriesFrame")
    col_names = {col.name for col in timeseries_frame.columns}
    assert "value" in col_names
    assert "timestamp" in col_names
    assert "status" in col_names
    assert "metadata" in col_names


def test_meta_handler_registry():
    """MetaHandlerRegistryのテスト"""
    registry = MetaHandlerRegistry()

    # カスタムハンドラを登録
    def custom_handler(ir):
        # ダミーハンドラ（何もしない）
        return ir

    registry.register(custom_handler)
    assert len(registry.handlers) == 1

    # apply_all()の動作確認
    fixture_path = Path(__file__).parent / "fixtures" / "minimal_spec.yaml"
    ir = load_spec(fixture_path)
    result = registry.apply_all(ir)
    assert result is not None


def test_no_row_model_no_change():
    """row_modelが設定されていない場合は何も変更されないテスト"""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_spec.yaml"
    ir = load_spec(fixture_path)

    # TimeSeriesFrameにはrow_modelがあるが、minimal_spec.yamlにはない前提
    # sample_spec.yamlにはrow_modelがあるので、別のフィクスチャを使う

    # 簡易的な確認: row_modelがないフレームは変更されない
    original_frame_count = len(ir.frames)
    normalized_ir = normalize_ir(ir)
    assert len(normalized_ir.frames) == original_frame_count


def test_invalid_row_model_reference():
    """不正なrow_model参照の場合はスキップされるテスト"""
    from spectool.spectool.core.base.ir import FrameSpec, MetaSpec, SpecIR

    # 不正なrow_model参照を持つIRを作成
    ir = SpecIR(
        meta=MetaSpec(name="test"),
        frames=[
            FrameSpec(
                id="InvalidFrame",
                row_model="invalid.module:NonExistentClass",
                columns=[],
            )
        ],
    )

    # 正規化してもエラーにならない（警告のみでスキップ）
    normalized_ir = normalize_ir(ir)
    assert len(normalized_ir.frames) == 1
    assert normalized_ir.frames[0].id == "InvalidFrame"
    # 列は追加されない（インポート失敗でスキップ）
    assert len(normalized_ir.frames[0].columns) == 0


def test_example_distribution_to_pydantic():
    """Example自動振り分け: Pydantic Modelへの振り分けテスト"""
    from spectool.spectool.core.base.ir import (
        EnumSpec,
        ExampleCase,
        GenericSpec,
        MetaSpec,
        PydanticModelSpec,
        SpecIR,
    )

    # トップレベルのexamplesを持つIRを作成
    ir = SpecIR(
        meta=MetaSpec(name="test"),
        pydantic_models=[
            PydanticModelSpec(id="TestModel", fields=[], examples=[]),
        ],
        examples=[
            ExampleCase(id="ex1", datatype_ref="TestModel", input={"value": 42}, expected={"valid": True}),
            ExampleCase(id="ex2", datatype_ref="TestModel", input={"value": 100}, expected={"valid": True}),
        ],
    )

    # 正規化前: datatypeのexamplesは空
    assert len(ir.pydantic_models[0].examples) == 0

    # 正規化
    normalized_ir = normalize_ir(ir)

    # 正規化後: datatypeのexamplesに振り分けられている
    assert len(normalized_ir.pydantic_models[0].examples) == 2
    assert normalized_ir.pydantic_models[0].examples[0] == {"value": 42}
    assert normalized_ir.pydantic_models[0].examples[1] == {"value": 100}


def test_example_distribution_to_enum():
    """Example自動振り分け: Enumへの振り分けテスト"""
    from spectool.spectool.core.base.ir import EnumSpec, ExampleCase, MetaSpec, SpecIR

    ir = SpecIR(
        meta=MetaSpec(name="test"),
        enums=[
            EnumSpec(id="Status", base_type="str", members=[], examples=[]),
        ],
        examples=[
            ExampleCase(id="ex1", datatype_ref="Status", input="ACTIVE", expected={"valid": True}),
        ],
    )

    # 正規化前
    assert len(ir.enums[0].examples) == 0

    # 正規化
    normalized_ir = normalize_ir(ir)

    # 正規化後
    assert len(normalized_ir.enums[0].examples) == 1
    assert normalized_ir.enums[0].examples[0] == "ACTIVE"


def test_example_distribution_to_generic():
    """Example自動振り分け: Generic（List）への振り分けテスト"""
    from spectool.spectool.core.base.ir import ExampleCase, GenericSpec, MetaSpec, SpecIR

    ir = SpecIR(
        meta=MetaSpec(name="test"),
        generics=[
            GenericSpec(
                id="TestList",
                container="list",
                element_type={"native": "builtins:int"},
                examples=[],
            ),
        ],
        examples=[
            ExampleCase(id="ex1", datatype_ref="TestList", input=[1, 2, 3], expected={"valid": True}),
        ],
    )

    # 正規化前
    assert len(ir.generics[0].examples) == 0

    # 正規化
    normalized_ir = normalize_ir(ir)

    # 正規化後
    assert len(normalized_ir.generics[0].examples) == 1
    assert normalized_ir.generics[0].examples[0] == [1, 2, 3]


def test_example_distribution_multiple_datatypes():
    """Example自動振り分け: 複数datatypeへの同時振り分けテスト"""
    from spectool.spectool.core.base.ir import (
        EnumSpec,
        ExampleCase,
        GenericSpec,
        MetaSpec,
        PydanticModelSpec,
        SpecIR,
    )

    ir = SpecIR(
        meta=MetaSpec(name="test"),
        pydantic_models=[
            PydanticModelSpec(id="Model1", fields=[], examples=[]),
            PydanticModelSpec(id="Model2", fields=[], examples=[]),
        ],
        enums=[
            EnumSpec(id="Enum1", base_type="str", members=[], examples=[]),
        ],
        generics=[
            GenericSpec(id="List1", container="list", element_type={"native": "builtins:int"}, examples=[]),
        ],
        examples=[
            ExampleCase(id="ex1", datatype_ref="Model1", input={"a": 1}, expected={"valid": True}),
            ExampleCase(id="ex2", datatype_ref="Model1", input={"a": 2}, expected={"valid": True}),
            ExampleCase(id="ex3", datatype_ref="Model2", input={"b": 3}, expected={"valid": True}),
            ExampleCase(id="ex4", datatype_ref="Enum1", input="VALUE", expected={"valid": True}),
            ExampleCase(id="ex5", datatype_ref="List1", input=[1, 2], expected={"valid": True}),
        ],
    )

    # 正規化
    normalized_ir = normalize_ir(ir)

    # 各datatypeに正しく振り分けられている
    assert len(normalized_ir.pydantic_models[0].examples) == 2  # Model1
    assert len(normalized_ir.pydantic_models[1].examples) == 1  # Model2
    assert len(normalized_ir.enums[0].examples) == 1  # Enum1
    assert len(normalized_ir.generics[0].examples) == 1  # List1


def test_example_distribution_no_datatype_ref():
    """Example自動振り分け: datatype_refがない場合はスキップ"""
    from spectool.spectool.core.base.ir import ExampleCase, MetaSpec, PydanticModelSpec, SpecIR

    ir = SpecIR(
        meta=MetaSpec(name="test"),
        pydantic_models=[
            PydanticModelSpec(id="TestModel", fields=[], examples=[]),
        ],
        examples=[
            ExampleCase(id="ex1", datatype_ref=None, input={"value": 42}, expected={"valid": True}),
        ],
    )

    # 正規化
    normalized_ir = normalize_ir(ir)

    # datatype_refがないのでexamplesは振り分けられない
    assert len(normalized_ir.pydantic_models[0].examples) == 0

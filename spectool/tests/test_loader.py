"""Loaderの単体テスト"""

from pathlib import Path

import pytest
from spectool.core.engine.loader import load_spec


def test_load_minimal_spec():
    """最小限のYAMLをロード可能"""
    spec_path = Path(__file__).parent / "fixtures" / "minimal_spec.yaml"
    ir = load_spec(spec_path)

    assert ir.meta.name == "minimal-test"
    assert len(ir.frames) == 1
    assert ir.frames[0].id == "SampleFrame"
    assert ir.frames[0].index is not None
    assert ir.frames[0].index.name == "idx"
    assert len(ir.frames[0].columns) == 2


def test_load_sample_spec():
    """サンプルYAMLをロード可能"""
    spec_path = Path(__file__).parent / "fixtures" / "sample_spec.yaml"
    ir = load_spec(spec_path)

    assert ir.meta.name == "sample_project"
    assert len(ir.frames) == 1
    assert len(ir.enums) == 1
    assert len(ir.pydantic_models) == 1
    assert len(ir.transforms) == 1
    assert len(ir.dag_stages) == 1
    assert len(ir.checks) == 1
    assert len(ir.examples) == 1


def test_load_dataframe_spec():
    """DataFrame定義の読み込み"""
    spec_path = Path(__file__).parent / "fixtures" / "sample_spec.yaml"
    ir = load_spec(spec_path)

    frame = ir.frames[0]
    assert frame.id == "TimeSeriesFrame"
    assert frame.description == "Time series DataFrame"
    assert frame.index is not None
    assert frame.index.name == "timestamp"
    assert frame.index.dtype == "datetime"
    assert len(frame.columns) == 2
    assert frame.row_model == "apps.models:TimeSeriesRow"
    assert frame.generator_factory == "apps.generators:generate_timeseries"
    assert len(frame.check_functions) == 1


def test_load_enum_spec():
    """Enum定義の読み込み"""
    spec_path = Path(__file__).parent / "fixtures" / "sample_spec.yaml"
    ir = load_spec(spec_path)

    enum = ir.enums[0]
    assert enum.id == "Status"
    assert enum.base_type == "str"
    assert len(enum.members) == 2
    assert enum.members[0].name == "ACTIVE"
    assert enum.members[0].value == "active"
    assert len(enum.examples) == 2


def test_load_pydantic_model_spec():
    """Pydanticモデル定義の読み込み"""
    spec_path = Path(__file__).parent / "fixtures" / "sample_spec.yaml"
    ir = load_spec(spec_path)

    model = ir.pydantic_models[0]
    assert model.id == "DataPoint"
    assert len(model.fields) == 2
    assert model.fields[0]["name"] == "timestamp"
    assert len(model.examples) == 1


def test_load_transform_spec():
    """Transform定義の読み込み"""
    spec_path = Path(__file__).parent / "fixtures" / "sample_spec.yaml"
    ir = load_spec(spec_path)

    transform = ir.transforms[0]
    assert transform.id == "process_data"
    assert transform.impl == "apps.transforms:process_data"
    assert len(transform.parameters) == 2
    assert transform.parameters[0].name == "data"
    assert transform.parameters[0].type_ref == "TimeSeriesFrame"
    assert transform.parameters[1].optional is True
    assert transform.return_type_ref == "TimeSeriesFrame"


def test_load_dag_stage_spec():
    """DAG Stage定義の読み込み"""
    spec_path = Path(__file__).parent / "fixtures" / "sample_spec.yaml"
    ir = load_spec(spec_path)

    stage = ir.dag_stages[0]
    assert stage.stage_id == "stage_1"
    assert stage.selection_mode == "single"
    assert stage.input_type == "TimeSeriesFrame"
    assert stage.output_type == "TimeSeriesFrame"
    assert len(stage.candidates) == 1
    assert stage.default_transform_id == "process_data"


def test_load_check_spec():
    """Check定義の読み込み"""
    spec_path = Path(__file__).parent / "fixtures" / "sample_spec.yaml"
    ir = load_spec(spec_path)

    check = ir.checks[0]
    assert check.id == "validate_positive"
    assert check.impl == "apps.checks:validate_positive"


def test_load_example_spec():
    """Example定義の読み込み"""
    spec_path = Path(__file__).parent / "fixtures" / "sample_spec.yaml"
    ir = load_spec(spec_path)

    example = ir.examples[0]
    assert example.id == "example_1"
    assert "data" in example.input
    assert "timestamp" in example.expected


def test_load_column_with_checks():
    """Column定義のchecks読み込み"""
    spec_path = Path(__file__).parent / "fixtures" / "sample_spec.yaml"
    ir = load_spec(spec_path)

    frame = ir.frames[0]
    value_col = frame.columns[0]
    assert value_col.name == "value"
    assert len(value_col.checks) == 1
    assert value_col.checks[0]["type"] == "ge"
    assert value_col.checks[0]["value"] == 0


def test_load_meta():
    """メタデータの読み込み"""
    spec_path = Path(__file__).parent / "fixtures" / "minimal_spec.yaml"
    ir = load_spec(spec_path)

    assert ir.meta.name == "minimal-test"
    assert ir.meta.description == "Minimal test spec"
    assert ir.meta.version == "1.0"


def test_load_nonexistent_file():
    """存在しないファイルの読み込みエラー"""
    with pytest.raises(FileNotFoundError):
        load_spec("nonexistent.yaml")


def test_load_unsupported_format():
    """未対応のファイル形式でエラー"""
    spec_path = Path(__file__).parent / "fixtures" / "test.txt"
    spec_path.parent.mkdir(exist_ok=True)
    spec_path.write_text("dummy")

    with pytest.raises(ValueError, match="未対応のファイル形式"):
        load_spec(spec_path)

    spec_path.unlink()

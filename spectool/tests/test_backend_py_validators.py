"""Pandera Schema生成バックエンドのテスト"""

from pathlib import Path
import tempfile
import pytest

from spectool.core.base.ir import (
    ColumnRule,
    FrameSpec,
    IndexRule,
    MetaSpec,
    MultiIndexLevel,
    SpecIR,
)
from spectool.backends.py_validators import generate_pandera_schemas


def test_generate_pandera_schemas_basic():
    """基本的なPandera Schemaが生成できること"""
    frame = FrameSpec(
        id="TestFrame",
        description="Test DataFrame",
        index=IndexRule(name="idx", dtype="int"),
        columns=[
            ColumnRule(name="col1", dtype="float", nullable=False),
            ColumnRule(name="col2", dtype="str", nullable=True),
        ],
    )

    ir = SpecIR(
        meta=MetaSpec(name="test-project"),
        frames=[frame],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "schemas.py"
        generate_pandera_schemas(ir, output_path)

        assert output_path.exists()
        content = output_path.read_text()

        # 基本的な構造の確認
        assert "class TestFrameSchema(pa.DataFrameModel):" in content
        assert "import pandera as pa" in content
        assert "idx: Index[int]" in content
        assert "col1: Series[float]" in content
        assert "col2: Series[str]" in content


def test_generate_pandera_schemas_with_datetime_index():
    """datetime型のIndexが正しく生成されること"""
    frame = FrameSpec(
        id="TimeSeriesFrame",
        description="Time series data",
        index=IndexRule(name="timestamp", dtype="datetime"),
        columns=[
            ColumnRule(name="value", dtype="float", nullable=False),
        ],
    )

    ir = SpecIR(
        meta=MetaSpec(name="test-project"),
        frames=[frame],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "schemas.py"
        generate_pandera_schemas(ir, output_path)

        assert output_path.exists()
        content = output_path.read_text()

        # datetime型の確認
        assert "timestamp: Index[pd.DatetimeTZDtype]" in content


def test_generate_pandera_schemas_with_multi_index():
    """MultiIndexが正しく生成されること"""
    frame = FrameSpec(
        id="MultiIndexFrame",
        description="Multi-index DataFrame",
        multi_index=[
            MultiIndexLevel(name="level1", dtype="str"),
            MultiIndexLevel(name="level2", dtype="int"),
        ],
        columns=[
            ColumnRule(name="value", dtype="float", nullable=False),
        ],
    )

    ir = SpecIR(
        meta=MetaSpec(name="test-project"),
        frames=[frame],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "schemas.py"
        generate_pandera_schemas(ir, output_path)

        assert output_path.exists()
        content = output_path.read_text()

        # MultiIndexの確認
        assert "level1: Index[str]" in content
        assert "level2: Index[int]" in content


def test_generate_pandera_schemas_with_checks():
    """Column checksが正しく生成されること"""
    frame = FrameSpec(
        id="ValidatedFrame",
        description="Frame with validation",
        index=IndexRule(name="idx", dtype="int"),
        columns=[
            ColumnRule(
                name="price",
                dtype="float",
                nullable=False,
                checks=[
                    {"type": "ge", "value": 0},
                    {"type": "le", "value": 1000},
                ],
            ),
        ],
    )

    ir = SpecIR(
        meta=MetaSpec(name="test-project"),
        frames=[frame],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "schemas.py"
        generate_pandera_schemas(ir, output_path)

        assert output_path.exists()
        content = output_path.read_text()

        # checksの確認
        assert "ge=0" in content
        assert "le=1000" in content


def test_generate_pandera_schemas_with_config():
    """Configが正しく生成されること"""
    frame = FrameSpec(
        id="StrictFrame",
        description="Strict validation frame",
        index=IndexRule(name="idx", dtype="int"),
        columns=[
            ColumnRule(name="value", dtype="float", nullable=False),
        ],
        strict=True,
        coerce=False,
        ordered=True,
    )

    ir = SpecIR(
        meta=MetaSpec(name="test-project"),
        frames=[frame],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "schemas.py"
        generate_pandera_schemas(ir, output_path)

        assert output_path.exists()
        content = output_path.read_text()

        # Configの確認
        assert "strict = True" in content
        assert "coerce = False" in content
        assert "ordered = True" in content


def test_generate_pandera_schemas_multiple_frames():
    """複数のDataFrameが全て生成されること"""
    frame1 = FrameSpec(
        id="Frame1",
        description="First frame",
        columns=[ColumnRule(name="col1", dtype="float")],
    )

    frame2 = FrameSpec(
        id="Frame2",
        description="Second frame",
        columns=[ColumnRule(name="col2", dtype="int")],
    )

    ir = SpecIR(
        meta=MetaSpec(name="test-project"),
        frames=[frame1, frame2],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "schemas.py"
        generate_pandera_schemas(ir, output_path)

        assert output_path.exists()
        content = output_path.read_text()

        # 両方のSchemaが含まれていることを確認
        assert "class Frame1Schema(pa.DataFrameModel):" in content
        assert "class Frame2Schema(pa.DataFrameModel):" in content


def test_generate_pandera_schemas_empty(capsys):
    """DataFrameが空の場合、スキップメッセージが出力されること"""
    ir = SpecIR(
        meta=MetaSpec(name="test-project"),
        frames=[],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "schemas.py"
        generate_pandera_schemas(ir, output_path)

        # ファイルは生成されない
        assert not output_path.exists()

        # スキップメッセージの確認
        captured = capsys.readouterr()
        assert "Skip" in captured.out


def test_generate_pandera_schemas_with_description():
    """Column descriptionがコメントとして出力されること"""
    frame = FrameSpec(
        id="DescribedFrame",
        description="Frame with descriptions",
        index=IndexRule(name="idx", dtype="int", description="Index field"),
        columns=[
            ColumnRule(
                name="value",
                dtype="float",
                nullable=False,
                description="Value field",
            ),
        ],
    )

    ir = SpecIR(
        meta=MetaSpec(name="test-project"),
        frames=[frame],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "schemas.py"
        generate_pandera_schemas(ir, output_path)

        assert output_path.exists()
        content = output_path.read_text()

        # descriptionがコメントとして含まれていることを確認
        assert "# Index field" in content
        assert "# Value field" in content

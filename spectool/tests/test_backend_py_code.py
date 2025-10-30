"""TypeAlias生成バックエンドのテスト"""

from pathlib import Path
import tempfile
import pytest

from spectool.spectool.core.base.ir import (
    EnumMemberSpec,
    EnumSpec,
    FrameSpec,
    IndexRule,
    ColumnRule,
    MetaSpec,
    PydanticModelSpec,
    SpecIR,
)
from spectool.spectool.backends.py_code import (
    generate_dataframe_aliases,
    generate_enum_aliases,
    generate_pydantic_aliases,
    generate_all_type_aliases,
)


def test_generate_dataframe_aliases_basic():
    """基本的なDataFrame TypeAliasが生成できること"""
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
        output_path = Path(tmpdir) / "type_aliases.py"
        generate_dataframe_aliases(ir, output_path)

        assert output_path.exists()
        content = output_path.read_text()

        # 基本的な構造の確認
        assert "TestFrame: TypeAlias" in content
        assert "pd.DataFrame" in content
        assert "from typing import TypeAlias" in content


def test_generate_dataframe_aliases_with_metadata():
    """メタデータ付きDataFrame TypeAliasが生成できること"""
    frame = FrameSpec(
        id="OHLCVFrame",
        description="OHLCV data frame",
        index=IndexRule(name="timestamp", dtype="datetime"),
        columns=[
            ColumnRule(name="open", dtype="float", nullable=False),
            ColumnRule(name="close", dtype="float", nullable=False),
        ],
        row_model="apps.models:OHLCVRowModel",
        generator_factory="apps.generators:generate_ohlcv",
        check_functions=["apps.checks:check_ohlcv_valid"],
    )

    ir = SpecIR(
        meta=MetaSpec(name="test-project"),
        frames=[frame],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "type_aliases.py"
        generate_dataframe_aliases(ir, output_path)

        assert output_path.exists()
        content = output_path.read_text()

        # メタデータの確認
        assert "PydanticRowRef" in content
        assert "GeneratorSpec" in content
        assert "CheckedSpec" in content
        assert "OHLCVRowModel" in content
        assert "apps.generators:generate_ohlcv" in content


def test_generate_enum_aliases_basic():
    """基本的なEnum TypeAliasが生成できること"""
    enum = EnumSpec(
        id="AssetClass",
        description="Asset class type",
        base_type="str",
        members=[
            EnumMemberSpec(name="EQUITY", value="equity"),
            EnumMemberSpec(name="CRYPTO", value="crypto"),
        ],
    )

    ir = SpecIR(
        meta=MetaSpec(name="test-project"),
        enums=[enum],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "enum_aliases.py"
        generate_enum_aliases(ir, output_path)

        assert output_path.exists()
        content = output_path.read_text()

        # 基本的な構造の確認
        assert "AssetClassType: TypeAlias" in content
        assert "from apps.datatypes.models import AssetClass" in content


def test_generate_enum_aliases_with_examples():
    """例示データ付きEnum TypeAliasが生成できること"""
    enum = EnumSpec(
        id="Status",
        description="Status type",
        base_type="str",
        members=[
            EnumMemberSpec(name="ACTIVE", value="active"),
            EnumMemberSpec(name="INACTIVE", value="inactive"),
        ],
        examples=["active", "inactive"],
        check_functions=["apps.checks:validate_status"],
    )

    ir = SpecIR(
        meta=MetaSpec(name="test-project"),
        enums=[enum],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "enum_aliases.py"
        generate_enum_aliases(ir, output_path)

        assert output_path.exists()
        content = output_path.read_text()

        # メタデータの確認
        assert "ExampleSpec" in content
        assert "CheckedSpec" in content


def test_generate_pydantic_aliases_basic():
    """基本的なPydanticモデル TypeAliasが生成できること"""
    model = PydanticModelSpec(
        id="UserConfig",
        description="User configuration",
        fields=[
            {"name": "username", "type": "str"},
            {"name": "age", "type": "int"},
        ],
    )

    ir = SpecIR(
        meta=MetaSpec(name="test-project"),
        pydantic_models=[model],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "pydantic_aliases.py"
        generate_pydantic_aliases(ir, output_path)

        assert output_path.exists()
        content = output_path.read_text()

        # 基本的な構造の確認
        assert "UserConfigType: TypeAlias" in content
        assert "from apps.datatypes.models import UserConfig" in content


def test_generate_all_type_aliases():
    """全てのTypeAliasが1ファイルに統合生成できること"""
    frame = FrameSpec(
        id="TestFrame",
        description="Test frame",
        columns=[ColumnRule(name="col1", dtype="float")],
    )

    enum = EnumSpec(
        id="Status",
        description="Status type",
        members=[EnumMemberSpec(name="OK", value="ok")],
    )

    model = PydanticModelSpec(
        id="Config",
        description="Configuration",
        fields=[{"name": "value", "type": "int"}],
    )

    ir = SpecIR(
        meta=MetaSpec(name="test-project"),
        frames=[frame],
        enums=[enum],
        pydantic_models=[model],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "type_aliases.py"
        generate_all_type_aliases(ir, output_path)

        assert output_path.exists()
        content = output_path.read_text()

        # 全ての型が含まれていることを確認
        assert "TestFrame:" in content
        assert "StatusType:" in content
        assert "ConfigType:" in content
        assert "# === Pydantic Model TypeAliases ===" in content
        assert "# === Enum TypeAliases ===" in content
        assert "# === DataFrame TypeAliases ===" in content


def test_generate_dataframe_aliases_empty():
    """DataFrameが空の場合、生成をスキップすること"""
    ir = SpecIR(
        meta=MetaSpec(name="test-project"),
        frames=[],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "type_aliases.py"
        generate_dataframe_aliases(ir, output_path)

        # ファイルは生成されない
        assert not output_path.exists()

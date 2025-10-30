"""メタ型の単体テスト"""

import pytest
from spectool.spectool.core.base import (
    CheckedSpec,
    ExampleSpec,
    GeneratorSpec,
    PydanticRowRef,
    SchemaSpec,
)


def test_pydantic_row_ref_creation():
    """PydanticRowRefの作成テスト"""
    ref = PydanticRowRef(model="apps.models:OHLCVRowModel")
    assert ref.model == "apps.models:OHLCVRowModel"
    assert "PydanticRowRef" in repr(ref)


def test_pydantic_row_ref_immutable():
    """PydanticRowRefがimmutableであることを確認"""
    ref = PydanticRowRef(model="apps.models:TestModel")
    with pytest.raises(Exception):  # dataclass frozen=True によるエラー
        ref.model = "other.module:OtherModel"  # type: ignore


def test_schema_spec_creation():
    """SchemaSpecの作成テスト"""
    schema = SchemaSpec(
        index={"name": "timestamp", "dtype": "datetime"},
        columns=[
            {"name": "price", "dtype": "float"},
            {"name": "volume", "dtype": "int"},
        ],
        checks=[{"type": "custom", "expression": "price > 0"}],
        strict=True,
    )
    assert schema.index is not None
    assert len(schema.columns) == 2
    assert len(schema.checks) == 1
    assert schema.strict is True


def test_schema_spec_default_values():
    """SchemaSpec デフォルト値テスト"""
    schema = SchemaSpec()
    assert schema.index is None
    assert len(schema.columns) == 0
    assert len(schema.checks) == 0
    assert schema.strict is False


def test_generator_spec_creation():
    """GeneratorSpecの作成テスト"""
    gen = GeneratorSpec(factory="apps.generators:generate_ohlcv_frame")
    assert gen.factory == "apps.generators:generate_ohlcv_frame"
    assert "GeneratorSpec" in repr(gen)


def test_generator_spec_immutable():
    """GeneratorSpecがimmutableであることを確認"""
    gen = GeneratorSpec(factory="apps.generators:func")
    with pytest.raises(Exception):
        gen.factory = "other:func"  # type: ignore


def test_checked_spec_creation():
    """CheckedSpecの作成テスト"""
    checked = CheckedSpec(
        functions=[
            "apps.checks:check_ohlcv",
            "apps.checks:validate_prices",
        ]
    )
    assert len(checked.functions) == 2
    assert "apps.checks:check_ohlcv" in checked.functions


def test_checked_spec_empty():
    """CheckedSpec 空リストテスト"""
    checked = CheckedSpec()
    assert len(checked.functions) == 0


def test_checked_spec_immutable():
    """CheckedSpec属性がimmutableであることを確認"""
    checked = CheckedSpec(functions=["apps.checks:func"])
    with pytest.raises(Exception):
        checked.functions = ["other:func"]  # type: ignore  # 属性の再代入はエラー


def test_example_spec_creation():
    """ExampleSpecの作成テスト"""
    examples = ExampleSpec(examples=["EQUITY", "CRYPTO", "BOND"])
    assert len(examples.examples) == 3
    assert "EQUITY" in examples.examples


def test_example_spec_various_types():
    """ExampleSpec 様々な型のテスト"""
    examples = ExampleSpec(
        examples=[
            "string_value",
            42,
            {"key": "value"},
            [1, 2, 3],
        ]
    )
    assert len(examples.examples) == 4
    assert examples.examples[1] == 42
    assert examples.examples[2] == {"key": "value"}


def test_example_spec_repr():
    """ExampleSpec repr テスト"""
    examples = ExampleSpec(examples=[1, 2, 3, 4, 5])
    repr_str = repr(examples)
    assert "ExampleSpec" in repr_str
    assert "5 items" in repr_str


def test_schema_spec_multi_index():
    """SchemaSpec MultiIndexテスト"""
    schema = SchemaSpec(
        index=[
            {"name": "date", "dtype": "datetime"},
            {"name": "symbol", "dtype": "str"},
        ],
        columns=[{"name": "price", "dtype": "float"}],
    )
    assert isinstance(schema.index, list)
    assert len(schema.index) == 2


def test_all_meta_types_repr():
    """全メタ型のrepr出力テスト"""
    pydantic_ref = PydanticRowRef(model="test:Model")
    schema = SchemaSpec(columns=[{"name": "col", "dtype": "int"}])
    generator = GeneratorSpec(factory="test:gen")
    checked = CheckedSpec(functions=["test:check"])
    example = ExampleSpec(examples=[1, 2, 3])

    # 全てrepr可能であることを確認
    assert all(
        [
            repr(pydantic_ref),
            repr(schema),
            repr(generator),
            repr(checked),
            repr(example),
        ]
    )

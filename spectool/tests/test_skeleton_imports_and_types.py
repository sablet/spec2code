"""スケルトン生成時のimportと型アノテーションのテスト

Issue: transform関数生成時にimportが欠落し、型が過度にAnyになる問題を検証
"""

import tempfile
from pathlib import Path

import pytest

from spectool.spectool.backends.py_skeleton import generate_skeleton
from spectool.spectool.core.engine.loader import load_spec
from spectool.spectool.core.engine.normalizer import normalize_ir


@pytest.fixture
def sample_spec_with_models(tmp_path: Path) -> Path:
    """Pydanticモデルを使用するspecを作成"""
    spec_content = """
version: "1"
meta:
  name: "test-imports"
  description: "Test spec for imports and type annotations"

checks:
  - id: check_config
    description: "Validate config"
    impl: "apps.test-imports.checks:check_config"
    file_path: "checks/checks.py"

datatypes:
  - id: Config
    description: "Configuration model"
    check_functions:
      - check_config
    pydantic_model:
      fields:
        - name: name
          type:
            native: "builtins:str"
        - name: value
          type:
            native: "builtins:int"

  - id: Result
    description: "Result model"
    pydantic_model:
      fields:
        - name: status
          type:
            native: "builtins:str"

  - id: Status
    description: "Status enum"
    enum:
      base_type: str
      members:
        - name: SUCCESS
          value: "success"
        - name: FAILURE
          value: "failure"

transforms:
  - id: process_config
    description: "Process configuration"
    impl: "apps.test-imports.transforms:process_config"
    file_path: "transforms/transforms.py"
    parameters:
      - name: config
        datatype_ref: Config
      - name: status
        datatype_ref: Status
    return_type_ref: Result
"""
    spec_path = tmp_path / "test_spec.yaml"
    spec_path.write_text(spec_content)
    return spec_path


def test_transform_has_correct_imports(sample_spec_with_models: Path, tmp_path: Path):
    """Transform関数のimportが正しく生成されることを確認"""
    # Spec読み込み
    raw_ir = load_spec(str(sample_spec_with_models))
    ir = normalize_ir(raw_ir)

    # スケルトン生成
    output_dir = tmp_path / "output"
    generate_skeleton(ir, output_dir)

    # 生成されたtransforms.pyを確認
    transform_file = output_dir / "apps" / "test_imports" / "transforms" / "transforms.py"
    assert transform_file.exists(), f"Transform file not found: {transform_file}"

    content = transform_file.read_text()

    # 必要なimportが含まれていることを確認
    assert "from apps.test_imports.models.models import Config" in content, "Config import missing"
    assert "from apps.test_imports.models.models import Result" in content, "Result import missing"
    assert "from apps.test_imports.models.enums import Status" in content, "Status import missing"


def test_transform_has_correct_type_annotations(sample_spec_with_models: Path, tmp_path: Path):
    """Transform関数の型アノテーションが正しく生成されることを確認"""
    # Spec読み込み
    raw_ir = load_spec(str(sample_spec_with_models))
    ir = normalize_ir(raw_ir)

    # スケルトン生成
    output_dir = tmp_path / "output"
    generate_skeleton(ir, output_dir)

    # 生成されたtransforms.pyを確認
    transform_file = output_dir / "apps" / "test_imports" / "transforms" / "transforms.py"
    content = transform_file.read_text()

    # 型アノテーションが正しいことを確認
    assert "def process_config(config: Config, status: Status) -> Result:" in content, (
        "Function signature with correct types not found"
    )
    assert "-> Any:" not in content, "Any type should not be used when types are defined"


def test_transform_with_dataframe_has_pandas_import(tmp_path: Path):
    """DataFrame型を使用するtransformにpandasのimportが含まれることを確認"""
    spec_content = """
version: "1"
meta:
  name: "test-dataframe"

datatypes:
  - id: DataFrameType
    description: "DataFrame type"
    type_alias:
      type: simple
      target: "pandas:DataFrame"

transforms:
  - id: process_data
    impl: "apps.test-dataframe.transforms:process_data"
    file_path: "transforms/transforms.py"
    parameters:
      - name: data
        datatype_ref: DataFrameType
    return_type_ref: DataFrameType
"""
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(spec_content)

    raw_ir = load_spec(str(spec_path))
    ir = normalize_ir(raw_ir)

    output_dir = tmp_path / "output"
    generate_skeleton(ir, output_dir)

    transform_file = output_dir / "apps" / "test_dataframe" / "transforms" / "transforms.py"
    content = transform_file.read_text()

    assert "import pandas as pd" in content, "pandas import missing"


def test_check_function_has_correct_imports(sample_spec_with_models: Path, tmp_path: Path):
    """Check関数が正しく生成されることを確認

    Note: Check関数は payload: dict を受け取る設計なので、
    特定のPydanticモデルのimportは不要。
    """
    # Spec読み込み
    raw_ir = load_spec(str(sample_spec_with_models))
    ir = normalize_ir(raw_ir)

    # スケルトン生成
    output_dir = tmp_path / "output"
    generate_skeleton(ir, output_dir)

    # 生成されたchecks.pyを確認
    check_file = output_dir / "apps" / "test_imports" / "checks" / "checks.py"
    assert check_file.exists(), f"Check file not found: {check_file}"

    content = check_file.read_text()

    # Check関数が生成されていることを確認
    assert "def check_config(payload: dict) -> bool:" in content, "check_config function not found"


def test_no_any_type_when_return_type_is_defined(tmp_path: Path):
    """return_type_refが定義されている場合はAnyを使わないことを確認"""
    spec_content = """
version: "1"
meta:
  name: "test-any-type"

datatypes:
  - id: InputModel
    description: "Input model"
    pydantic_model:
      fields:
        - name: value
          type:
            native: "builtins:int"

  - id: OutputModel
    description: "Output model"
    pydantic_model:
      fields:
        - name: result
          type:
            native: "builtins:str"

  - id: StatusEnum
    description: "Status enum"
    enum:
      base_type: str
      members:
        - name: OK
          value: "ok"

transforms:
  - id: transform_with_pydantic
    description: "Transform returning Pydantic model"
    impl: "apps.test-any-type.transforms:transform_with_pydantic"
    file_path: "transforms/transforms.py"
    parameters:
      - name: input_data
        datatype_ref: InputModel
    return_type_ref: OutputModel

  - id: transform_with_enum
    description: "Transform returning Enum"
    impl: "apps.test-any-type.transforms:transform_with_enum"
    file_path: "transforms/transforms.py"
    parameters:
      - name: input_data
        datatype_ref: InputModel
    return_type_ref: StatusEnum
"""
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(spec_content)

    raw_ir = load_spec(str(spec_path))
    ir = normalize_ir(raw_ir)

    output_dir = tmp_path / "output"
    generate_skeleton(ir, output_dir)

    transform_file = output_dir / "apps" / "test_any_type" / "transforms" / "transforms.py"
    content = transform_file.read_text()

    # return_type_refが定義されている場合、Anyではなく正しい型が使われることを確認
    assert "-> OutputModel:" in content, "OutputModel return type not found"
    assert "-> StatusEnum:" in content, "StatusEnum return type not found"

    # 以下のパターンでAnyが使われていないことを確認
    # "-> Any:" のように、定義済みの型の代わりにAnyが使われていないか
    lines = content.split("\n")
    for line in lines:
        if "def transform_with_pydantic" in line:
            assert "-> OutputModel:" in line, (
                f"transform_with_pydantic should return OutputModel, not Any. Line: {line}"
            )
            assert "-> Any:" not in line, f"transform_with_pydantic should not return Any. Line: {line}"
        if "def transform_with_enum" in line:
            assert "-> StatusEnum:" in line, f"transform_with_enum should return StatusEnum, not Any. Line: {line}"
            assert "-> Any:" not in line, f"transform_with_enum should not return Any. Line: {line}"


def test_no_any_type_in_parameters_when_types_defined(tmp_path: Path):
    """パラメータの型が定義されている場合はAnyを使わないことを確認"""
    spec_content = """
version: "1"
meta:
  name: "test-param-any"

datatypes:
  - id: ConfigModel
    description: "Config model"
    pydantic_model:
      fields:
        - name: setting
          type:
            native: "builtins:str"

  - id: ModeEnum
    description: "Mode enum"
    enum:
      base_type: int
      members:
        - name: NORMAL
          value: 1

  - id: ResultModel
    description: "Result model"
    pydantic_model:
      fields:
        - name: status
          type:
            native: "builtins:bool"

transforms:
  - id: process_data
    impl: "apps.test-param-any.transforms:process_data"
    file_path: "transforms/transforms.py"
    parameters:
      - name: config
        datatype_ref: ConfigModel
      - name: mode
        datatype_ref: ModeEnum
    return_type_ref: ResultModel
"""
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(spec_content)

    raw_ir = load_spec(str(spec_path))
    ir = normalize_ir(raw_ir)

    output_dir = tmp_path / "output"
    generate_skeleton(ir, output_dir)

    transform_file = output_dir / "apps" / "test_param_any" / "transforms" / "transforms.py"
    content = transform_file.read_text()

    # パラメータの型が正しく設定されていることを確認
    assert "config: ConfigModel" in content, "ConfigModel parameter type not found"
    assert "mode: ModeEnum" in content, "ModeEnum parameter type not found"

    # パラメータでAnyが使われていないことを確認
    lines = content.split("\n")
    for line in lines:
        if "def process_data" in line:
            assert "config: ConfigModel" in line, f"config should be ConfigModel, not Any. Line: {line}"
            assert "mode: ModeEnum" in line, f"mode should be ModeEnum, not Any. Line: {line}"
            assert "config: Any" not in line, f"config should not be Any. Line: {line}"
            assert "mode: Any" not in line, f"mode should not be Any. Line: {line}"


def test_generic_types_not_replaced_with_any(tmp_path: Path):
    """Generic型（list、dict等）がAnyに置き換えられないことを確認"""
    spec_content = """
version: "1"
meta:
  name: "test-generic-any"

datatypes:
  - id: StringList
    description: "List of strings"
    generic:
      container: list
      element_type:
        native: "builtins:str"

  - id: IntDict
    description: "Dict with string keys and int values"
    generic:
      container: dict
      key_type:
        native: "builtins:str"
      value_type:
        native: "builtins:int"

  - id: ResultModel
    description: "Result model"
    pydantic_model:
      fields:
        - name: value
          type:
            native: "builtins:str"

transforms:
  - id: process_list
    impl: "apps.test-generic-any.transforms:process_list"
    file_path: "transforms/transforms.py"
    parameters:
      - name: items
        datatype_ref: StringList
    return_type_ref: ResultModel

  - id: process_dict
    impl: "apps.test-generic-any.transforms:process_dict"
    file_path: "transforms/transforms.py"
    parameters:
      - name: mapping
        datatype_ref: IntDict
    return_type_ref: ResultModel
"""
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(spec_content)

    raw_ir = load_spec(str(spec_path))
    ir = normalize_ir(raw_ir)

    output_dir = tmp_path / "output"
    generate_skeleton(ir, output_dir)

    transform_file = output_dir / "apps" / "test_generic_any" / "transforms" / "transforms.py"
    content = transform_file.read_text()

    # Generic型が正しく表現されていることを確認（具体的な型は実装依存だが、Anyではないことを確認）
    lines = content.split("\n")
    for line in lines:
        if "def process_list" in line:
            # items パラメータがAnyではなく、list型として認識されていることを確認
            assert "items:" in line, "items parameter should be defined"
            # StringListまたはlist[str]のような型が期待される
            # 少なくともAnyではないことを確認
            assert "items: Any" not in line, f"items should not be Any. Line: {line}"
        if "def process_dict" in line:
            assert "mapping:" in line, "mapping parameter should be defined"
            assert "mapping: Any" not in line, f"mapping should not be Any. Line: {line}"

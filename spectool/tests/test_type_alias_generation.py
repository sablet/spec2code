"""TypeAlias と Generic のコード生成テスト

type_alias (simple/tuple) と generic (list) の定義が正しくコード生成されることを確認する。
"""

from pathlib import Path
import tempfile
import pytest

from spectool.spectool.core.engine.loader import load_spec
from spectool.spectool.core.engine.normalizer import normalize_ir
from spectool.spectool.backends.py_skeleton import generate_skeleton


@pytest.fixture
def temp_project_dir():
    """一時プロジェクトディレクトリ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def type_alias_spec(temp_project_dir):
    """type_alias定義を含むspec"""
    spec_yaml = """
version: "1.0"
meta:
  name: test_type_alias
  description: "Test spec with type_alias and generic"

checks:
  - id: check_simple_frame
    description: "Check simple dataframe"
    impl: "apps.checks:check_simple_frame"
    file_path: "apps/checks/validators.py"

  - id: check_tuple_data
    description: "Check tuple data"
    impl: "apps.checks:check_tuple_data"
    file_path: "apps/checks/validators.py"

  - id: check_list_data
    description: "Check list data"
    impl: "apps.checks:check_list_data"
    file_path: "apps/checks/validators.py"

datatypes:
  # DataFrame型
  - id: OHLCVFrame
    description: "OHLCV DataFrame"
    dataframe_schema:
      index:
        name: timestamp
        dtype: datetime
        nullable: false
      columns:
        - name: close
          dtype: float
          nullable: false

  # Simple type_alias (DataFrameエイリアス)
  - id: MultiAssetFrame
    description: "Multi-asset DataFrame (type_alias: simple)"
    check_functions:
      - check_simple_frame
    type_alias:
      type: simple
      target: "pandas:DataFrame"

  # Tuple type_alias
  - id: FeatureTargetTuple
    description: "Feature and Target tuple (type_alias: tuple)"
    check_functions:
      - check_tuple_data
    type_alias:
      type: tuple
      elements:
        - datatype_ref: OHLCVFrame
        - datatype_ref: OHLCVFrame

  # Pydantic model
  - id: DataPoint
    description: "Single data point"
    pydantic_model:
      fields:
        - name: value
          type:
            native: "builtins:float"
          required: true

  # Generic list
  - id: DataPointList
    description: "List of data points (generic: list)"
    check_functions:
      - check_list_data
    generic:
      container: list
      element_type:
        datatype_ref: DataPoint

transforms:
  - id: process_multi_asset
    description: "Process multi-asset frame"
    impl: "apps.transforms:process_multi_asset"
    file_path: "apps/transforms/processors.py"
    parameters:
      - name: data
        datatype_ref: MultiAssetFrame
    return_datatype_ref: MultiAssetFrame

  - id: align_features
    description: "Align features and targets"
    impl: "apps.transforms:align_features"
    file_path: "apps/transforms/processors.py"
    parameters:
      - name: data1
        datatype_ref: OHLCVFrame
      - name: data2
        datatype_ref: OHLCVFrame
    return_datatype_ref: FeatureTargetTuple

  - id: aggregate_points
    description: "Aggregate data points"
    impl: "apps.transforms:aggregate_points"
    file_path: "apps/transforms/processors.py"
    parameters:
      - name: points
        datatype_ref: DataPointList
    return_native: "builtins:float"
"""
    spec_path = temp_project_dir / "test_spec.yaml"
    spec_path.write_text(spec_yaml)
    return spec_path


def test_type_alias_simple_generated_in_types_py(temp_project_dir, type_alias_spec):
    """Simple type_alias が types.py に生成されること"""
    # Load and generate
    ir = load_spec(str(type_alias_spec))
    normalized = normalize_ir(ir)
    generate_skeleton(normalized, temp_project_dir)

    # Check types.py exists
    types_file = temp_project_dir / "apps" / "test_type_alias" / "types.py"
    assert types_file.exists(), "types.py should be generated"

    # Read types.py content
    content = types_file.read_text()

    # Should contain MultiAssetFrame TypeAlias
    assert "MultiAssetFrame" in content, "MultiAssetFrame TypeAlias should be generated"
    assert "TypeAlias" in content, "Should import TypeAlias"
    assert "pd.DataFrame" in content or "DataFrame" in content, "Should reference DataFrame"

    # Should have CheckedSpec with check function
    assert "CheckedSpec" in content, "Should import CheckedSpec"
    assert "check_simple_frame" in content, "Should reference check function"


def test_type_alias_tuple_generated_in_types_py(temp_project_dir, type_alias_spec):
    """Tuple type_alias が types.py に生成されること"""
    # Load and generate
    ir = load_spec(str(type_alias_spec))
    normalized = normalize_ir(ir)
    generate_skeleton(normalized, temp_project_dir)

    # Check types.py
    types_file = temp_project_dir / "apps" / "test_type_alias" / "types.py"
    content = types_file.read_text()

    # Should contain FeatureTargetTuple TypeAlias
    assert "FeatureTargetTuple" in content, "FeatureTargetTuple TypeAlias should be generated"
    assert "tuple" in content.lower(), "Should reference tuple"
    assert "OHLCVFrame" in content, "Should reference element types"


def test_generic_list_generated_in_types_py(temp_project_dir, type_alias_spec):
    """Generic list が types.py に生成されること"""
    # Load and generate
    ir = load_spec(str(type_alias_spec))
    normalized = normalize_ir(ir)
    generate_skeleton(normalized, temp_project_dir)

    # Check types.py
    types_file = temp_project_dir / "apps" / "test_type_alias" / "types.py"
    content = types_file.read_text()

    # Should contain DataPointList TypeAlias
    assert "DataPointList" in content, "DataPointList TypeAlias should be generated"
    assert "list" in content or "List" in content, "Should reference list"
    assert "DataPoint" in content, "Should reference element type"


def test_transforms_can_import_type_aliases(temp_project_dir, type_alias_spec):
    """生成されたtransform関数がtype_aliasをimportできること"""
    # Load and generate
    ir = load_spec(str(type_alias_spec))
    normalized = normalize_ir(ir)
    generate_skeleton(normalized, temp_project_dir)

    # Check transform file
    transform_file = temp_project_dir / "apps" / "test_type_alias" / "transforms" / "processors.py"
    assert transform_file.exists(), "Transform file should be generated"

    content = transform_file.read_text()

    # Should import MultiAssetFrame from types
    assert "from apps.test_type_alias.types import" in content, "Should import from types module"
    assert "MultiAssetFrame" in content, "Should import MultiAssetFrame"
    assert "FeatureTargetTuple" in content, "Should import FeatureTargetTuple"
    assert "DataPointList" in content, "Should import DataPointList"


def test_type_alias_ir_loaded_correctly(temp_project_dir, type_alias_spec):
    """type_alias と generic が IR に正しくロードされること"""
    ir = load_spec(str(type_alias_spec))

    # Check type_aliases are loaded
    assert len(ir.type_aliases) > 0, "Should load type_aliases from spec"

    # Check generics are loaded
    assert len(ir.generics) > 0, "Should load generics from spec"

    # Check specific entries
    type_alias_ids = [ta.id for ta in ir.type_aliases]
    assert "MultiAssetFrame" in type_alias_ids, "MultiAssetFrame should be in type_aliases"
    assert "FeatureTargetTuple" in type_alias_ids, "FeatureTargetTuple should be in type_aliases"

    generic_ids = [g.id for g in ir.generics]
    assert "DataPointList" in generic_ids, "DataPointList should be in generics"

"""DataFrame ABCD pipeline code generation test"""

from pathlib import Path
import pytest
from spec2code.engine import load_spec, generate_skeleton


@pytest.fixture
def dataframe_abcd_spec_path():
    """Get path to dataframe-abcd.yaml spec"""
    spec_file = Path(__file__).parent.parent.parent / "specs" / "dataframe-abcd.yaml"
    return spec_file


def test_dataframe_abcd_spec_loads(dataframe_abcd_spec_path):
    """Test that the DataFrame ABCD spec loads correctly"""
    spec = load_spec(dataframe_abcd_spec_path)

    # Check meta
    assert spec.meta.name == "dataframe-abcd"

    # Check datatypes
    assert len(spec.datatypes) == 4
    assert spec.datatypes[0].id == "DataFrameA"
    assert spec.datatypes[1].id == "DataFrameB"
    assert spec.datatypes[2].id == "DataFrameC"
    assert spec.datatypes[3].id == "DataFrameD"

    # Check DataFrameA definition
    df_a = spec.datatypes[0]
    assert "check_a" in df_a.check_ids
    assert "ex_a" in df_a.example_ids
    assert df_a.schema_def["properties"]["id"]["type"] == "integer"
    assert df_a.schema_def["properties"]["value"]["type"] == "number"

    # Check DataFrameB definition
    df_b = spec.datatypes[1]
    assert "check_b" in df_b.check_ids
    assert "ex_b" in df_b.example_ids
    assert "processed" in df_b.schema_def["properties"]

    # Check DataFrameC definition
    df_c = spec.datatypes[2]
    assert "check_c" in df_c.check_ids
    assert "ex_c" in df_c.example_ids
    assert "factor" in df_c.schema_def["properties"]

    # Check DataFrameD definition
    df_d = spec.datatypes[3]
    assert "check_d" in df_d.check_ids
    assert "ex_d" in df_d.example_ids
    assert "result" in df_d.schema_def["properties"]

    # Check transforms
    assert len(spec.transforms) == 2

    # Check transform_a_to_b
    transform_a_b = spec.transforms[0]
    assert transform_a_b.id == "transform_a_to_b"
    assert len(transform_a_b.parameters) == 1
    assert transform_a_b.parameters[0].name == "data_a"
    assert transform_a_b.parameters[0].datatype_ref == "DataFrameA"
    assert transform_a_b.parameters[0].native == "pandas:DataFrame"
    assert transform_a_b.return_datatype_ref == "DataFrameB"
    assert transform_a_b.return_native == "pandas:DataFrame"

    # Check transform_bc_to_d
    transform_bc_d = spec.transforms[1]
    assert transform_bc_d.id == "transform_bc_to_d"
    assert len(transform_bc_d.parameters) == 2
    assert transform_bc_d.parameters[0].name == "data_b"
    assert transform_bc_d.parameters[0].datatype_ref == "DataFrameB"
    assert transform_bc_d.parameters[1].name == "data_c"
    assert transform_bc_d.parameters[1].datatype_ref == "DataFrameC"
    assert transform_bc_d.return_datatype_ref == "DataFrameD"


def test_dataframe_abcd_dag_structure(dataframe_abcd_spec_path):
    """Test that the DAG structure is correct (a->b, b+c->d)"""
    spec = load_spec(dataframe_abcd_spec_path)

    # Check DAG edges
    assert len(spec.dag) == 2

    # Edge 1: transform_a_to_b -> transform_bc_to_d
    edge1 = spec.dag[0]
    assert edge1.from_ == "transform_a_to_b"
    assert edge1.to == "transform_bc_to_d"

    # Edge 2: transform_bc_to_d -> null (terminal node)
    edge2 = spec.dag[1]
    assert edge2.from_ == "transform_bc_to_d"
    assert edge2.to is None


def test_dataframe_abcd_generates_skeleton(dataframe_abcd_spec_path, tmp_path):
    """Test that skeleton code is generated correctly"""
    spec = load_spec(dataframe_abcd_spec_path)

    # Generate skeleton in temp directory
    generate_skeleton(spec, project_root=tmp_path)

    app_root = tmp_path / "apps" / "dataframe-abcd"

    # Check directory structure
    assert app_root.exists()
    assert (app_root / "checks").exists()
    assert (app_root / "transforms").exists()
    assert (app_root / "checks" / "__init__.py").exists()
    assert (app_root / "transforms" / "__init__.py").exists()

    # Check files are created
    assert (app_root / "checks" / "dataframe_checks.py").exists()
    assert (app_root / "transforms" / "transform_a_to_b.py").exists()
    assert (app_root / "transforms" / "transform_bc_to_d.py").exists()


def test_dataframe_abcd_check_functions(dataframe_abcd_spec_path, tmp_path):
    """Test that all check functions are generated"""
    spec = load_spec(dataframe_abcd_spec_path)
    generate_skeleton(spec, project_root=tmp_path)

    check_file = tmp_path / "apps" / "dataframe-abcd" / "checks" / "dataframe_checks.py"
    assert check_file.exists()

    generated_code = check_file.read_text()

    # Verify all 4 check functions
    assert "def check_a(payload: dict)" in generated_code
    assert "def check_b(payload: dict)" in generated_code
    assert "def check_c(payload: dict)" in generated_code
    assert "def check_d(payload: dict)" in generated_code


def test_dataframe_abcd_transform_functions(dataframe_abcd_spec_path, tmp_path):
    """Test that transform functions are generated with correct signatures"""
    spec = load_spec(dataframe_abcd_spec_path)
    generate_skeleton(spec, project_root=tmp_path)

    # Check transform_a_to_b file
    transform_a_file = (
        tmp_path / "apps" / "dataframe-abcd" / "transforms" / "transform_a_to_b.py"
    )
    assert transform_a_file.exists()

    code_a = transform_a_file.read_text()

    # Verify imports
    assert "import pandas as pd" in code_a
    assert "from typing import Annotated" in code_a
    assert "from spec2code.engine import Check, ExampleValue" in code_a

    # Verify transform_a_to_b function
    assert "def transform_a_to_b(" in code_a
    assert "data_a: Annotated[" in code_a
    assert "pd.DataFrame" in code_a
    assert "-> Annotated[" in code_a
    assert "Check[" in code_a

    # Check transform_bc_to_d file
    transform_bc_file = (
        tmp_path / "apps" / "dataframe-abcd" / "transforms" / "transform_bc_to_d.py"
    )
    assert transform_bc_file.exists()

    code_bc = transform_bc_file.read_text()

    # Verify transform_bc_to_d function with two parameters
    assert "def transform_bc_to_d(" in code_bc
    assert "data_b: Annotated[" in code_bc
    assert "data_c: Annotated[" in code_bc

    # Verify return type annotations
    assert "-> Annotated[" in code_bc
    assert "Check[" in code_bc


def test_dataframe_abcd_type_annotations(dataframe_abcd_spec_path, tmp_path):
    """Test that type annotations use correct Check and ExampleValue markers"""
    spec = load_spec(dataframe_abcd_spec_path)
    generate_skeleton(spec, project_root=tmp_path)

    # Check transform_a_to_b file
    transform_a_file = (
        tmp_path / "apps" / "dataframe-abcd" / "transforms" / "transform_a_to_b.py"
    )
    code_a = transform_a_file.read_text()

    # Input parameters should have ExampleValue
    assert "ExampleValue[" in code_a

    # Return types should have Check
    assert "Check[" in code_a
    assert "check_b" in code_a

    # Check transform_bc_to_d file
    transform_bc_file = (
        tmp_path / "apps" / "dataframe-abcd" / "transforms" / "transform_bc_to_d.py"
    )
    code_bc = transform_bc_file.read_text()

    # Both input parameters should have ExampleValue
    assert "ExampleValue[" in code_bc

    # Return type should have Check
    assert "Check[" in code_bc
    assert "check_d" in code_bc


def test_dataframe_abcd_example_data_structure(dataframe_abcd_spec_path):
    """Test that example data is correctly structured for all datatypes"""
    spec = load_spec(dataframe_abcd_spec_path)

    # Check ex_a (single row object)
    ex_a = next(e for e in spec.examples if e.id == "ex_a")
    assert "id" in ex_a.input
    assert "value" in ex_a.input
    assert ex_a.input["id"] == 1
    assert ex_a.input["value"] == 100

    # Check ex_b (single row object)
    ex_b = next(e for e in spec.examples if e.id == "ex_b")
    assert "id" in ex_b.input
    assert "value" in ex_b.input
    assert "processed" in ex_b.input
    assert ex_b.input["processed"] == 110

    # Check ex_c (single row object)
    ex_c = next(e for e in spec.examples if e.id == "ex_c")
    assert "id" in ex_c.input
    assert "factor" in ex_c.input
    assert ex_c.input["factor"] == 1.5

    # Check ex_d (single row object)
    ex_d = next(e for e in spec.examples if e.id == "ex_d")
    assert "id" in ex_d.input
    assert "result" in ex_d.input
    assert ex_d.input["result"] == 165


def test_dataframe_abcd_dag_execution_flow(dataframe_abcd_spec_path, tmp_path):
    """Test that DAG execution passes data from a->b->d correctly"""
    import pandas as pd
    from spec2code.engine import Engine

    spec = load_spec(dataframe_abcd_spec_path)
    generate_skeleton(spec, project_root=tmp_path)

    # Implement actual transform logic
    transform_a_file = (
        tmp_path / "apps" / "dataframe-abcd" / "transforms" / "transform_a_to_b.py"
    )
    transform_a_impl = '''# Auto-generated skeleton for Transform: transform_a_to_b
from spec2code.engine import Check, ExampleValue
from typing import Annotated
import pandas as pd

def transform_a_to_b(data_a: Annotated[pd.DataFrame, ExampleValue[{'rows': [{'id': 1, 'value': 100}, {'id': 2, 'value': 200}]}]]) -> Annotated[pd.DataFrame, Check["apps.dataframe-abcd.checks.dataframe_checks:check_b"]]:
    """Transform from A to B (add processed column)"""
    # Add processed column (value + 10% for testing)
    data_b = data_a.copy()
    data_b['processed'] = data_b['value'] * 1.1
    return data_b
'''
    transform_a_file.write_text(transform_a_impl)

    transform_bc_file = (
        tmp_path / "apps" / "dataframe-abcd" / "transforms" / "transform_bc_to_d.py"
    )
    transform_bc_impl = '''# Auto-generated skeleton for Transform: transform_bc_to_d
from spec2code.engine import Check, ExampleValue
from typing import Annotated
import pandas as pd

def transform_bc_to_d(data_b: Annotated[pd.DataFrame, ExampleValue[{'rows': [{'id': 1, 'value': 100, 'processed': 110}, {'id': 2, 'value': 200, 'processed': 220}]}]], data_c: Annotated[pd.DataFrame, ExampleValue[{'rows': [{'id': 1, 'factor': 1.5}, {'id': 2, 'factor': 2.0}]}]]) -> Annotated[pd.DataFrame, Check["apps.dataframe-abcd.checks.dataframe_checks:check_d"]]:
    """Transform from B and C to D (combine and calculate result)"""
    # Merge B and C on 'id', then calculate result
    data_d = data_b.merge(data_c, on='id')
    data_d['result'] = data_d['processed'] * data_d['factor']
    return data_d
'''
    transform_bc_file.write_text(transform_bc_impl)

    # Create input data
    data_a = pd.DataFrame([{"id": 1, "value": 100}, {"id": 2, "value": 200}])

    data_c = pd.DataFrame([{"id": 1, "factor": 1.5}, {"id": 2, "factor": 2.0}])

    # Manually execute the DAG to verify data flow
    import sys

    packages_dir = str((tmp_path / "packages").resolve())
    if packages_dir not in sys.path:
        sys.path.insert(0, packages_dir)

    # Add the apps directory to sys.path
    apps_dir = str((tmp_path / "apps").resolve())
    if apps_dir not in sys.path:
        sys.path.insert(0, apps_dir)

    import importlib

    # Execute transform_a_to_b
    module_a = importlib.import_module("dataframe-abcd.transforms.transform_a_to_b")
    data_b = module_a.transform_a_to_b(data_a)

    # Verify intermediate result (data_b)
    assert "processed" in data_b.columns
    assert len(data_b) == 2
    assert abs(data_b.loc[0, "processed"] - 110.0) < 0.01  # 100 * 1.1
    assert abs(data_b.loc[1, "processed"] - 220.0) < 0.01  # 200 * 1.1

    # Execute transform_bc_to_d with the result from transform_a_to_b
    module_bc = importlib.import_module("dataframe-abcd.transforms.transform_bc_to_d")
    data_d = module_bc.transform_bc_to_d(data_b, data_c)

    # Verify final result (data_d)
    assert "result" in data_d.columns
    assert len(data_d) == 2
    assert abs(data_d.loc[0, "result"] - 165.0) < 0.01  # 110 * 1.5
    assert abs(data_d.loc[1, "result"] - 440.0) < 0.01  # 220 * 2.0

    # Verify all columns are present in final result
    assert set(data_d.columns) == {"id", "value", "processed", "factor", "result"}

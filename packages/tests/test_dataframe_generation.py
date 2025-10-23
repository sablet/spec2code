"""DataFrame pipeline code generation test"""

from pathlib import Path
import pytest
from spec2code.engine import load_spec, generate_skeleton


@pytest.fixture
def dataframe_spec_path(tmp_path):
    """Copy dataframe-pipeline.yaml to temp directory"""
    spec_file = (
        Path(__file__).parent.parent.parent / "specs" / "dataframe-pipeline.yaml"
    )
    return spec_file


def test_dataframe_pipeline_spec_loads(dataframe_spec_path):
    """Test that the DataFrame pipeline spec loads correctly"""
    spec = load_spec(dataframe_spec_path)

    # Check meta
    assert spec.meta.name == "dataframe-pipeline"

    # Check datatypes
    assert len(spec.datatypes) == 2
    assert spec.datatypes[0].id == "StepAFrame"
    assert spec.datatypes[1].id == "StepBFrame"

    # Check StepAFrame definition
    step_a = spec.datatypes[0]
    assert "check_step_a" in step_a.check_ids
    assert "ex_step_a" in step_a.example_ids

    # Check StepBFrame definition
    step_b = spec.datatypes[1]
    assert "check_step_b" in step_b.check_ids
    assert "ex_step_b" in step_b.example_ids

    # Check transform
    assert len(spec.transforms) == 1
    transform = spec.transforms[0]
    assert transform.id == "transform_step_a_to_step_b"
    assert len(transform.parameters) == 1

    # Check parameter definition
    param = transform.parameters[0]
    assert param.name == "step_a_data"
    assert param.datatype_ref == "StepAFrame"
    assert param.native == "pandas:DataFrame"

    # Check return type definition
    assert transform.return_datatype_ref == "StepBFrame"
    assert transform.return_native == "pandas:DataFrame"


def test_dataframe_pipeline_generates_correct_code(dataframe_spec_path, tmp_path):
    """Test that generated code has correct type annotations"""
    spec = load_spec(dataframe_spec_path)

    # Generate skeleton in temp directory
    generate_skeleton(spec, project_root=tmp_path)

    # Check generated transform file
    transform_file = (
        tmp_path / "apps" / "dataframe-pipeline" / "transforms" / "pipeline.py"
    )
    assert transform_file.exists()

    # Read generated code
    generated_code = transform_file.read_text()

    # Verify imports
    assert "import pandas as pd" in generated_code
    assert "from typing import Annotated" in generated_code
    assert "from spec2code.engine import Check, ExampleValue" in generated_code

    # Verify function signature - Input parameter with ExampleValue only
    assert "def transform_step_a_to_step_b(" in generated_code
    assert "step_a_data: Annotated[" in generated_code
    assert "pd.DataFrame" in generated_code
    assert "ExampleValue[" in generated_code

    # Verify that input does NOT have Check (only Example)
    lines = generated_code.split("\n")
    param_lines = []
    in_param = False
    for line in lines:
        if "step_a_data:" in line:
            in_param = True
        if in_param:
            param_lines.append(line)
            if ")" in line and "->" in line:
                break

    param_section = "\n".join(param_lines)
    # Input should have ExampleValue but NOT Check
    assert "ExampleValue[" in param_section
    # Check that Check is NOT in the parameter annotation
    # (Check should only be in return type)
    check_in_param = (
        "Check[" in param_section and "->" not in param_section.split("Check[")[0]
    )
    assert not check_in_param, "Input parameter should not have Check annotation"

    # Verify return type - with Check only
    assert "-> Annotated[" in generated_code
    return_section = generated_code.split("-> Annotated[")[1].split(":")[0]
    assert "pd.DataFrame" in return_section
    assert "Check[" in return_section
    assert "check_step_b" in generated_code

    # Verify that return does NOT have ExampleValue
    assert "ExampleValue[" not in return_section


def test_dataframe_pipeline_generates_check_files(dataframe_spec_path, tmp_path):
    """Test that check functions are generated correctly"""
    spec = load_spec(dataframe_spec_path)
    generate_skeleton(spec, project_root=tmp_path)

    # Check generated check file
    check_file = (
        tmp_path / "apps" / "dataframe-pipeline" / "checks" / "dataframe_checks.py"
    )
    assert check_file.exists()

    # Read generated code
    generated_code = check_file.read_text()

    # Verify check functions
    assert "def check_step_a(" in generated_code
    assert "def check_step_b(" in generated_code

    # Both functions should accept dict (for validation)
    assert "check_step_a(payload: dict)" in generated_code
    assert "check_step_b(payload: dict)" in generated_code


def test_generated_code_structure(dataframe_spec_path, tmp_path):
    """Test the overall structure of generated code"""
    spec = load_spec(dataframe_spec_path)
    generate_skeleton(spec, project_root=tmp_path)

    app_root = tmp_path / "apps" / "dataframe-pipeline"

    # Check directory structure
    assert (app_root / "checks").exists()
    assert (app_root / "transforms").exists()
    assert (app_root / "checks" / "__init__.py").exists()
    assert (app_root / "transforms" / "__init__.py").exists()

    # Check files are created
    assert (app_root / "checks" / "dataframe_checks.py").exists()
    assert (app_root / "transforms" / "pipeline.py").exists()


def test_example_data_structure(dataframe_spec_path):
    """Test that example data is correctly structured"""
    spec = load_spec(dataframe_spec_path)

    # Check ex_step_a (single row object)
    ex_step_a = next(e for e in spec.examples if e.id == "ex_step_a")
    assert "timestamp" in ex_step_a.input
    assert "value" in ex_step_a.input
    assert ex_step_a.input["timestamp"] == "2024-01-01"
    assert ex_step_a.input["value"] == 100

    # Check ex_step_b (single row object)
    ex_step_b = next(e for e in spec.examples if e.id == "ex_step_b")
    assert "timestamp" in ex_step_b.input
    assert "value" in ex_step_b.input
    assert "normalized" in ex_step_b.input
    assert ex_step_b.input["normalized"] == 0.67

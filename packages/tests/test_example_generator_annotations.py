"""Example and Generator annotation test"""

from pathlib import Path
import pytest
from spec2code.engine import load_spec, generate_skeleton


def test_example_and_generator_annotations(temp_project_dir):
    """Test that example and generator annotations are properly generated with distinct IDs"""

    # Define a spec with both examples and generators
    spec_data = {
        "version": "1",
        "meta": {"name": "test-annotation", "description": "Test for annotations"},
        "checks": [
            {
                "id": "check_text",
                "description": "Check text data",
                "impl": "test-annotation.checks.text:check_text",
                "file_path": "checks/text.py",
            }
        ],
        "examples": [
            {
                "id": "ex_input_text",
                "description": "Input text example",
                "input": {"text": "hello"},
                "expected": {"processed": True},
            }
        ],
        "generators": {
            "gen_output_text": {
                "id": "gen_output_text",
                "description": "Generate output text data",
                "impl": "test-annotation.generators.text:generate_text",
                "file_path": "generators/text.py",
                "parameters": [{"name": "prefix", "native": "builtins:str", "default": "test"}],
            }
        },
        "datatypes": [
            {
                "id": "InputText",
                "description": "Input text data",
                "check_ids": ["check_text"],
                "example_refs": ["ex_input_text"],
                "schema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            },
            {
                "id": "OutputText",
                "description": "Output text data",
                "check_ids": ["check_text"],
                "generator_refs": ["gen_output_text"],
                "schema": {
                    "type": "object",
                    "properties": {"processed": {"type": "boolean"}},
                    "required": ["processed"],
                },
            },
        ],
        "transforms": [
            {
                "id": "process_text",
                "description": "Process text input to output",
                "impl": "test-annotation.transforms.text:process_text",
                "file_path": "transforms/text.py",
                "parameters": [
                    {"name": "input_data", "datatype_ref": "InputText"},
                ],
                "return_datatype_ref": "OutputText",
            }
        ],
        "dag": [{"from": "process_text", "to": None}],
        "dag_stages": [],
    }

    # Write spec to file
    import yaml

    spec_path = temp_project_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    # Load and generate skeleton
    spec = load_spec(spec_path)
    generate_skeleton(spec, project_root=temp_project_dir)

    # Check generated transform file
    transform_file = temp_project_dir / "apps" / "test-annotation" / "transforms" / "text.py"
    assert transform_file.exists()

    generated_code = transform_file.read_text()

    # Verify that the input parameter has example annotation with __example_id__
    assert "__example_id__" in generated_code
    assert "ex_input_text" in generated_code

    # Verify that the return type has generator annotation with __generator_id__
    assert "__generator_id__" in generated_code
    assert "gen_output_text" in generated_code

    # Verify that both annotations are distinct
    import re

    example_annotations = re.findall(r"__example_id__.*?__example_value__", generated_code)
    generator_annotations = re.findall(r"__generator_id__.*?__generator_impl__", generated_code)

    # Should have at least one example annotation
    assert len(example_annotations) >= 1
    # Should have at least one generator annotation
    assert len(generator_annotations) >= 1

    # Verify that the generated code has correct imports
    assert "from spec2code.engine import Check, ExampleValue" in generated_code
    assert "Annotated" in generated_code

    print("✅ Example annotations with __example_id__ found:", example_annotations)
    print("✅ Generator annotations with __generator_id__ found:", generator_annotations)


def test_annotation_extraction(temp_project_dir):
    """Test that annotation extraction works for both example_id and generator_id"""

    spec_data = {
        "version": "1",
        "meta": {"name": "test-extraction", "description": "Test for annotation extraction"},
        "checks": [
            {
                "id": "check_output",
                "description": "Check output data",
                "impl": "test-extraction.checks.checks:check_output",
                "file_path": "checks/checks.py",
            }
        ],
        "examples": [
            {
                "id": "ex_sample",
                "description": "Sample example",
                "input": {"value": 123},
                "expected": {"result": 123},
            }
        ],
        "generators": {
            "gen_sample": {
                "id": "gen_sample",
                "description": "Generate sample data",
                "impl": "test-extraction.generators.data:generate_sample",
                "file_path": "generators/data.py",
                "parameters": [],
            }
        },
        "datatypes": [
            {
                "id": "InputType",
                "description": "Input type",
                "check_ids": ["check_output"],
                "example_refs": ["ex_sample"],
                "schema": {
                    "type": "object",
                    "properties": {"value": {"type": "number"}},
                    "required": ["value"],
                },
            },
            {
                "id": "OutputType",
                "description": "Output type",
                "check_ids": ["check_output"],
                "generator_refs": ["gen_sample"],
                "schema": {
                    "type": "object",
                    "properties": {"result": {"type": "number"}},
                    "required": ["result"],
                },
            },
        ],
        "transforms": [
            {
                "id": "transform_values",
                "description": "Transform values",
                "impl": "test-extraction.transforms.value:transform_values",
                "file_path": "transforms/value.py",
                "parameters": [
                    {"name": "input_val", "datatype_ref": "InputType"},
                ],
                "return_datatype_ref": "OutputType",
            }
        ],
        "dag": [{"from": "transform_values", "to": None}],
        "dag_stages": [],
    }

    # Write spec to file
    import yaml

    spec_path = temp_project_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    # Load and generate skeleton
    spec = load_spec(spec_path)
    generate_skeleton(spec, project_root=temp_project_dir)

    # Read generated code to verify annotation structure
    transform_file = temp_project_dir / "apps" / "test-extraction" / "transforms" / "value.py"
    generated_code = transform_file.read_text()

    # Check that both kinds of annotations exist with appropriate keys
    assert "__example_id__" in generated_code
    assert "ex_sample" in generated_code
    assert "__generator_id__" in generated_code
    assert "gen_sample" in generated_code

    # Make sure we have the expected structure in the code
    assert "ExampleValue[" in generated_code
    assert "Check[" in generated_code

    print("✅ Annotation extraction test passed")

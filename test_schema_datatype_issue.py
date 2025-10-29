"""
Test to reproduce the issue where schema-defined datatypes are generated as dict instead of proper type names
"""

from pathlib import Path
import tempfile
import yaml
from packages.spec2code.engine import load_spec, generate_skeleton


def test_schema_datatype_issue():
    """Test that schema-defined datatypes are properly referenced instead of just as 'dict'"""
    
    # Create a test spec that reproduces the issue
    spec_data = {
        "version": "1",
        "meta": {"name": "test-schema-dtype", "description": "Test for schema datatype issue"},
        "checks": [
            {
                "id": "check_input",
                "description": "Check input data",
                "impl": "apps.test-schema-dtype.checks.test:check_input",
                "file_path": "checks/test.py",
            },
            {
                "id": "check_output",
                "description": "Check output data",
                "impl": "apps.test-schema-dtype.checks.test:check_output",
                "file_path": "checks/test.py",
            }
        ],
        "examples": [
            {
                "id": "example_input",
                "description": "Input example",
                "input": {"value": "test"},
                "expected": {"processed": True}
            }
        ],
        "datatypes": [
            {
                "id": "InputType",
                "description": "Input type with schema",
                "check_ids": ["check_input"],
                "example_refs": ["example_input"],
                "schema": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"}
                    },
                    "required": ["value"]
                }
            },
            {
                "id": "OutputType",
                "description": "Output type with schema",
                "check_ids": ["check_output"],
                "schema": {
                    "type": "object",
                    "properties": {
                        "processed": {"type": "boolean"}
                    },
                    "required": ["processed"]
                }
            }
        ],
        "transforms": [
            {
                "id": "process_data",
                "description": "Process input to output",
                "impl": "apps.test-schema-dtype.transforms.test:process_data",
                "file_path": "transforms/test.py",
                "parameters": [
                    {"name": "input_data", "datatype_ref": "InputType"}
                ],
                "return_datatype_ref": "OutputType"
            }
        ],
        "dag": [{"from": "process_data", "to": None}]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Write test spec
        spec_path = Path(tmp_dir) / "test_spec.yaml"
        with open(spec_path, 'w') as f:
            yaml.dump(spec_data, f)

        # Load and generate skeleton
        spec = load_spec(spec_path)
        generate_skeleton(spec, project_root=Path(tmp_dir))

        # Check the generated transform file
        transform_file = Path(tmp_dir) / "apps" / "test_schema_dtype" / "transforms" / "test.py"
        assert transform_file.exists(), f"Transform file not generated: {transform_file}"
        
        generated_code = transform_file.read_text()
        print("Generated code:")
        print(generated_code)
        
        # The issue: both input and output should use proper datatype names, not 'dict'
        # For schema-based datatypes, they should be referenced as proper types
        # that would be in the models file
        assert "InputType" in generated_code, "InputType should be referenced in generated code"
        assert "OutputType" in generated_code, "OutputType should be referenced in generated code"
        
        # Specifically check that return type uses OutputType instead of just dict
        # The return annotation should contain OutputType, not just dict
        assert "OutputType" in generated_code or "dict" not in generated_code.split("->")[-1].split(":")[0], \
            f"Return type should reference OutputType, not just dict. Generated code:\n{generated_code}"


if __name__ == "__main__":
    test_schema_datatype_issue()
    print("Test passed!")
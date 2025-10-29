"""
Test that schema-defined datatypes are properly referenced in generated code instead of just as 'dict'.
This addresses the issue where fetch_yahoo_finance_ohlcv in algo-trade-pipeline.yaml
has return_datatype_ref: ProviderBatchCollection but the generated code shows just 'dict'
instead of 'ProviderBatchCollection'.
"""

import tempfile
from pathlib import Path
import pytest
import yaml
from spec2code.engine import load_spec, generate_skeleton


def test_schema_datatype_properly_referenced():
    """Test that schema-defined datatypes are referenced by name, not as 'dict'."""

    # Create a spec with schema-defined datatypes
    spec_data = {
        "version": "1",
        "meta": {"name": "test-schema-ref", "description": "Test schema datatype references"},
        "checks": [
            {
                "id": "check_input",
                "description": "Check input",
                "impl": "apps.test-schema-ref.checks.test:check_input",
                "file_path": "checks/test.py",
            },
            {
                "id": "check_output",
                "description": "Check output",
                "impl": "apps.test-schema-ref.checks.test:check_output",
                "file_path": "checks/test.py",
            },
        ],
        "examples": [
            {
                "id": "ex_input",
                "description": "Input example",
                "input": {"value": "test"},
                "expected": {"processed": True},
            }
        ],
        "datatypes": [
            {
                "id": "InputSchemaType",
                "description": "Input with schema",
                "check_ids": ["check_input"],
                "example_refs": ["ex_input"],
                "schema": {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]},
            },
            {
                "id": "OutputSchemaType",
                "description": "Output with schema",
                "check_ids": ["check_output"],
                "schema": {
                    "type": "object",
                    "properties": {"processed": {"type": "boolean"}},
                    "required": ["processed"],
                },
            },
        ],
        "transforms": [
            {
                "id": "process_data",
                "description": "Process schema-based data",
                "impl": "apps.test-schema-ref.transforms.test:process_data",
                "file_path": "transforms/test.py",
                "parameters": [{"name": "input_data", "datatype_ref": "InputSchemaType"}],
                "return_datatype_ref": "OutputSchemaType",
            }
        ],
        "dag": [{"from": "process_data", "to": None}],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Write test spec
        spec_path = Path(tmp_dir) / "test_spec.yaml"
        with open(spec_path, "w") as f:
            yaml.dump(spec_data, f)

        # Load and generate skeleton
        spec = load_spec(spec_path)
        generate_skeleton(spec, project_root=Path(tmp_dir))

        # Check the generated transform file - note: hyphens in app name get normalized
        transform_file = Path(tmp_dir) / "apps" / "test-schema-ref" / "transforms" / "test.py"
        assert transform_file.exists(), f"Transform file not generated: {transform_file}"

        generated_code = transform_file.read_text()
        print("Generated code:")
        print(generated_code)

        # The issue: input parameter and return type should reference proper datatypes,
        # not just 'dict'. Both InputSchemaType and OutputSchemaType are schema-defined
        # and should appear in the models.py file and be imported/referenced in the transform.

        # Check that InputSchemaType is referenced in the input parameter
        assert "InputSchemaType" in generated_code, (
            f"InputSchemaType should be referenced in input parameter, got:\n{generated_code}"
        )

        # Most importantly, check that OutputSchemaType is referenced in the return type
        # instead of just 'dict'
        lines = generated_code.split("\n")
        return_type_found = False
        for line in lines:
            if "->" in line and "Annotated" in line:
                # This should contain OutputSchemaType, not just dict
                if "OutputSchemaType" in line:
                    return_type_found = True
                    break
                elif "dict" in line and "OutputSchemaType" not in line:
                    # If it contains dict but not the proper type name, that's the bug
                    pytest.fail(
                        f"Return type uses 'dict' instead of 'OutputSchemaType': {line}\nFull code:\n{generated_code}"
                    )

        if not return_type_found:
            # Check if output type is in the return annotation at all
            if "OutputSchemaType" not in generated_code:
                pytest.fail(
                    f"OutputSchemaType is not referenced in return annotation.\nGenerated code:\n{generated_code}"
                )

        # Also check that the models file was generated with the schema-based types
        models_file = Path(tmp_dir) / "apps" / "test-schema-ref" / "datatypes" / "models.py"
        assert models_file.exists(), "Models file should be generated for schema-based datatypes"

        models_code = models_file.read_text()
        assert "class InputSchemaType" in models_code, (
            f"InputSchemaType should be generated as Pydantic model, got:\n{models_code}"
        )
        assert "class OutputSchemaType" in models_code, (
            f"OutputSchemaType should be generated as Pydantic model, got:\n{models_code}"
        )


if __name__ == "__main__":
    test_schema_datatype_properly_referenced()
    print("Test passed!")

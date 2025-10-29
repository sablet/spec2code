"""Type extension generation tests."""

from __future__ import annotations

import copy
import importlib
import importlib.util
from pathlib import Path

import yaml

from spec2code.engine import generate_skeleton, load_spec


def _write_spec(temp_project_dir: Path, spec_data: dict) -> Path:
    spec_path = temp_project_dir / "spec.yaml"
    spec_path.write_text(yaml.dump(spec_data))
    return spec_path


def test_type_alias_generation(temp_project_dir, sample_spec_yaml):
    """TypeAlias definitions are generated and imported."""
    spec_data = copy.deepcopy(sample_spec_yaml)
    spec_data["checks"] = [
        {
            "id": "check_dataframe",
            "description": "Dummy check for dataframe",
            "impl": "test-pipeline.checks.dummy:check_dataframe",
            "file_path": "checks/dummy.py",
        }
    ]
    spec_data["examples"] = [
        {
            "id": "example_dataframe",
            "description": "Dummy example",
            "input": {},
            "expected": {},
        }
    ]
    spec_data["datatypes"] = [
        {
            "id": "FeatureFrame",
            "description": "Feature DataFrame alias",
            "check_ids": ["check_dataframe"],
            "example_ids": ["example_dataframe"],
            "type_alias": {
                "type": "simple",
                "target": "pandas:DataFrame",
            },
        },
        {
            "id": "AlignedFeatureTarget",
            "description": "Aligned tuple",
            "check_ids": ["check_dataframe"],
            "example_ids": ["example_dataframe"],
            "type_alias": {
                "type": "tuple",
                "elements": [
                    {"native": "pandas:DataFrame"},
                    {"native": "pandas:DataFrame"},
                ],
            },
        },
    ]
    spec_data["transforms"] = [
        {
            "id": "use_alias",
            "description": "Use TypeAlias inputs",
            "impl": "test-pipeline.transforms.alias_module:use_alias",
            "file_path": "transforms/alias_module.py",
            "parameters": [
                {"name": "aligned", "datatype_ref": "AlignedFeatureTarget"},
            ],
            "return_datatype_ref": "FeatureFrame",
        }
    ]
    spec_data["dag"] = [{"from": "use_alias", "to": None}]

    spec_path = _write_spec(temp_project_dir, spec_data)
    spec = load_spec(spec_path)
    generate_skeleton(spec, project_root=temp_project_dir)

    alias_file = temp_project_dir / "apps" / "test-pipeline" / "datatypes" / "type_aliases.py"
    assert alias_file.exists()
    content = alias_file.read_text()
    assert "FeatureFrame: TypeAlias = pd.DataFrame" in content
    assert "AlignedFeatureTarget: TypeAlias = tuple[pd.DataFrame, pd.DataFrame]" in content

    transform_file = temp_project_dir / "apps" / "test-pipeline" / "transforms" / "alias_module.py"
    transform_code = transform_file.read_text()
    assert "from ..datatypes.type_aliases import AlignedFeatureTarget" in transform_code
    assert "from ..datatypes.type_aliases import FeatureFrame" in transform_code
    assert "aligned: Annotated[AlignedFeatureTarget" in transform_code
    assert "-> Annotated[FeatureFrame" in transform_code


def test_enum_generation(temp_project_dir, sample_spec_yaml):
    """Enum definitions are generated and importable."""
    spec_data = copy.deepcopy(sample_spec_yaml)
    spec_data["checks"] = [
        {
            "id": "check_signal",
            "description": "Dummy check for signal",
            "impl": "test-pipeline.checks.dummy:check_signal",
            "file_path": "checks/dummy.py",
        }
    ]
    spec_data["examples"] = [
        {
            "id": "example_signal",
            "description": "Dummy example for signal",
            "input": {},
            "expected": {},
        }
    ]
    spec_data["datatypes"] = [
        {
            "id": "PositionSignal",
            "description": "Trading position signal",
            "check_ids": ["check_signal"],
            "example_ids": ["example_signal"],
            "enum": {
                "base_type": "int",
                "members": [
                    {"name": "BUY", "value": 1},
                    {"name": "SELL", "value": -1},
                    {"name": "HOLD", "value": 0},
                ],
            },
        }
    ]
    spec_data["transforms"] = [
        {
            "id": "emit_signal",
            "description": "Emit default signal",
            "impl": "test-pipeline.transforms.signals:emit_signal",
            "file_path": "transforms/signals.py",
            "parameters": [],
            "return_datatype_ref": "PositionSignal",
        }
    ]
    spec_data["dag"] = [{"from": "emit_signal", "to": None}]

    spec_path = _write_spec(temp_project_dir, spec_data)
    spec = load_spec(spec_path)
    generate_skeleton(spec, project_root=temp_project_dir)

    enum_file = temp_project_dir / "apps" / "test-pipeline" / "datatypes" / "enums.py"
    assert enum_file.exists()
    enum_code = enum_file.read_text()
    assert "class PositionSignal(Enum):" in enum_code
    assert "BUY = 1" in enum_code
    assert "SELL = -1" in enum_code
    assert "HOLD = 0" in enum_code

    module_name = "test_pipeline_enums"
    spec_obj = importlib.util.spec_from_file_location(module_name, enum_file)
    assert spec_obj is not None and spec_obj.loader is not None
    module = importlib.util.module_from_spec(spec_obj)
    spec_obj.loader.exec_module(module)

    position_signal = getattr(module, "PositionSignal")
    assert position_signal.BUY.value == 1
    assert position_signal.SELL.value == -1
    assert position_signal.HOLD.value == 0


def test_literal_parameter_generation(temp_project_dir, sample_spec_yaml):
    """Literal parameters render Literal type annotations with defaults."""
    spec_data = copy.deepcopy(sample_spec_yaml)
    spec_data["checks"] = []
    spec_data["examples"] = []
    spec_data["datatypes"] = []
    spec_data["transforms"] = [
        {
            "id": "simulate",
            "description": "Simulate trading",
            "impl": "test-pipeline.transforms.sim:simulate",
            "file_path": "transforms/sim.py",
            "parameters": [
                {
                    "name": "allocation_method",
                    "literal": ["equal", "weighted", "risk_parity"],
                    "default": "equal",
                }
            ],
            "return_native": "builtins:bool",
        }
    ]
    spec_data["dag"] = [{"from": "simulate", "to": None}]

    spec_path = _write_spec(temp_project_dir, spec_data)
    spec = load_spec(spec_path)
    generate_skeleton(spec, project_root=temp_project_dir)

    transform_file = temp_project_dir / "apps" / "test-pipeline" / "transforms" / "sim.py"
    transform_code = transform_file.read_text()
    assert "from typing import Literal" in transform_code
    assert "allocation_method: Literal['equal', 'weighted', 'risk_parity'] = 'equal'" in transform_code
    assert "-> bool" in transform_code


def test_generator_skeleton_generation(temp_project_dir, sample_spec_yaml):
    """Generator定義に基づくスケルトンが生成される"""
    spec_data = copy.deepcopy(sample_spec_yaml)

    spec_path = _write_spec(temp_project_dir, spec_data)
    spec = load_spec(spec_path)
    generate_skeleton(spec, project_root=temp_project_dir)

    generator_file = temp_project_dir / "apps" / "test-pipeline" / "generators" / "data_generators.py"
    assert generator_file.exists()

    generator_code = generator_file.read_text()
    assert "# Auto-generated skeleton for Generator functions" in generator_code
    assert "def generate_text_input(" in generator_code
    assert "uppercase: bool = False" in generator_code
    assert "-> dict[str, Any]" in generator_code
    assert '"""テキスト入力データを生成"""' in generator_code
    assert "from typing import Any" in generator_code


def test_transform_return_has_example_annotations(temp_project_dir, sample_spec_yaml):
    """Transform戻り値にExampleValueアノテーションが付与される"""
    spec_data = copy.deepcopy(sample_spec_yaml)

    spec_path = _write_spec(temp_project_dir, spec_data)
    spec = load_spec(spec_path)
    generate_skeleton(spec, project_root=temp_project_dir)

    transform_file = temp_project_dir / "apps" / "test-pipeline" / "transforms" / "processors.py"
    transform_code = transform_file.read_text()

    assert "ExampleValue" in transform_code
    # Now schema-defined types should be referenced by name, not as 'dict'
    # Check that the return type has the defined type name (TextResult) and not just 'dict'
    assert "Annotated[" in transform_code  # Ensure we still have Annotated
    assert "TextResult" in transform_code  # Ensure we have the proper type name
    # The import from models should also be present
    assert "from ..datatypes.models import" in transform_code
    assert "__example_id__': 'example_result'" in transform_code

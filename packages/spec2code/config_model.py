"""
Config file models for configurable DAG execution
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TransformSelection(BaseModel):
    """Individual transform selection with optional parameter overrides"""

    transform_id: str
    params: dict[str, Any] = Field(default_factory=dict)


class StageExecution(BaseModel):
    """Execution config for a single DAG stage"""

    stage_id: str
    selected: list[TransformSelection] = Field(default_factory=list)


class ExecutionConfig(BaseModel):
    """Execution configuration"""

    stages: list[StageExecution] = Field(default_factory=list)


class ConfigMeta(BaseModel):
    """Config metadata"""

    config_name: str
    description: str
    base_spec: str  # Path to base spec file


class Config(BaseModel):
    """Config file root model"""

    version: str
    meta: ConfigMeta
    execution: ExecutionConfig


# ==================== Extended DAG models ====================


class DAGCandidate(BaseModel):
    """A candidate transform in a DAG stage"""

    transform_id: str


class DAGStage(BaseModel):
    """DAG stage definition with selection mode.

    Candidates are auto-collected from transforms when not specified. A transform
    qualifies when its first parameter's `datatype_ref` matches `input_type` and the
    transform's `return_datatype_ref` matches `output_type`.

    `default_transform_id` determines which transform to use when generating DAG edges
    from `dag_stages`, removing the need for an explicit `dag` field.
    """

    stage_id: str
    description: str
    selection_mode: Literal["single", "exclusive", "multiple"]
    max_select: int | None = Field(default=None)  # None = unlimited
    input_type: str
    output_type: str
    candidates: list[DAGCandidate] = Field(
        default_factory=list
    )  # Optional: auto-collected if empty
    default_transform_id: str | None = Field(
        default=None
    )  # For DAG edge generation (auto-set to candidates[0] if not specified)


class ExtendedSpec(BaseModel):
    """Extended spec model with DAG stages"""

    version: str
    meta: dict[str, Any]  # Keep flexible for Meta model compatibility
    checks: list[dict[str, Any]] = Field(default_factory=list)
    examples: list[dict[str, Any]] = Field(default_factory=list)
    datatypes: list[dict[str, Any]] = Field(default_factory=list)
    transforms: list[dict[str, Any]] = Field(default_factory=list)
    dag: list[dict[str, Any]] = Field(default_factory=list)  # Traditional DAG edges
    dag_stages: list[DAGStage] = Field(default_factory=list)  # Extended DAG stages


# ==================== Config loading ====================


def load_config(config_path: str) -> Config:
    """Load and validate config file"""
    import yaml
    from pathlib import Path

    config_path_obj = Path(config_path)
    with open(config_path_obj) as f:
        data = yaml.safe_load(f)

    return Config.model_validate(data)


def load_extended_spec(spec_path: str) -> ExtendedSpec:
    """Load and validate extended spec with DAG stages"""
    import yaml
    from pathlib import Path

    spec_path_obj = Path(spec_path)
    with open(spec_path_obj) as f:
        data = yaml.safe_load(f)

    spec = ExtendedSpec.model_validate(data)
    _auto_collect_candidates(spec)
    _generate_dag_from_stages(spec)
    return spec


def _auto_collect_candidates(spec: ExtendedSpec) -> None:
    """Auto-collect candidates for DAG stages based on input_type/output_type

    For each stage with empty candidates list, find all transforms where:
    - First parameter's datatype_ref matches stage's input_type
    - return_datatype_ref matches stage's output_type

    Also auto-sets default_transform_id to candidates[0] if not specified.
    """
    transforms = spec.transforms

    for stage in spec.dag_stages:
        if not stage.candidates:
            # Auto-collect candidates
            matched_transforms = []
            for transform in transforms:
                # Check if transform matches input/output types
                params = transform.get("parameters", [])
                if not params:
                    continue

                first_param = params[0]
                param_type = first_param.get("datatype_ref")
                return_type = transform.get("return_datatype_ref")

                if param_type == stage.input_type and return_type == stage.output_type:
                    matched_transforms.append(
                        DAGCandidate(transform_id=transform["id"])
                    )

            if matched_transforms:
                stage.candidates = matched_transforms

        # Auto-set default_transform_id to first candidate if not specified
        if not stage.default_transform_id and stage.candidates:
            stage.default_transform_id = stage.candidates[0].transform_id


def _generate_dag_from_stages(spec: ExtendedSpec) -> None:
    """Generate DAG edges from `dag_stages` using `default_transform_id`.

    Skip generation when `spec.dag` is already populated (backward compatibility).
    Otherwise, connect stages through their `default_transform_id` to derive edges.

    Algorithm:
    1. Use each stage's `default_transform_id` as the representative transform.
    2. Connect stages sequentially: stage[i] -> stage[i+1].
    3. Produce a linear pipeline by default.
    """
    if spec.dag:
        # DAG already exists (backward compatibility or manually specified)
        return

    if not spec.dag_stages:
        # No dag_stages, nothing to generate
        return

    generated_edges = []
    for i in range(len(spec.dag_stages) - 1):
        current_stage = spec.dag_stages[i]
        next_stage = spec.dag_stages[i + 1]

        if not current_stage.default_transform_id:
            # Skip when auto-collection failed to produce a default candidate
            continue

        if not next_stage.default_transform_id:
            # Skip if next stage has no default_transform_id
            continue

        # Create edge: current_stage -> next_stage
        generated_edges.append(
            {
                "from": current_stage.default_transform_id,
                "to": next_stage.default_transform_id,
            }
        )

    spec.dag = generated_edges

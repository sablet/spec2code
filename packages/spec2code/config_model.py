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
    default_params: dict[str, Any] = Field(default_factory=dict)


class DAGStage(BaseModel):
    """DAG stage definition with selection mode"""

    stage_id: str
    description: str
    selection_mode: Literal["single", "exclusive", "multiple"]
    min_select: int = Field(default=1)
    max_select: int | None = Field(default=None)  # None = unlimited
    input_type: str
    output_type: str
    candidates: list[DAGCandidate]


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

    return ExtendedSpec.model_validate(data)

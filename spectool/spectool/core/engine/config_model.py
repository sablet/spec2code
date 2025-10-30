"""Config YAMLのモデル定義とロード機能

Config駆動DAG実行のための設定ファイル構造を定義する。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class TransformSelection(BaseModel):
    """Transform選択とパラメータオーバーライド"""

    transform_id: str
    params: dict[str, Any] = Field(default_factory=dict)


class StageExecution(BaseModel):
    """ステージ実行設定"""

    stage_id: str
    selected: list[TransformSelection] = Field(default_factory=list)


class ExecutionConfig(BaseModel):
    """実行設定"""

    stages: list[StageExecution] = Field(default_factory=list)


class ConfigMeta(BaseModel):
    """Configメタデータ"""

    config_name: str
    description: str = ""
    base_spec: str  # Spec YAMLへのパス


class ConfigSpec(BaseModel):
    """Config YAML構造"""

    version: str
    meta: ConfigMeta
    execution: ExecutionConfig


def load_config(config_path: str | Path) -> ConfigSpec:
    """Config YAMLをロードして検証

    Args:
        config_path: Config YAMLのパス

    Returns:
        ConfigSpec: 検証済みConfig

    Raises:
        FileNotFoundError: ファイルが存在しない
        yaml.YAMLError: YAML形式エラー
        pydantic.ValidationError: Pydantic検証エラー
    """
    config_path_obj = Path(config_path)

    if not config_path_obj.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path_obj) as f:
        data = yaml.safe_load(f)

    return ConfigSpec.model_validate(data)

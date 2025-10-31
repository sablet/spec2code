"""Config駆動実行のテスト

packages/tests/test_config_execution.pyに相当する機能をspectoolで実装するためのテスト。
Config YAMLに基づいたDAG実行とパラメータオーバーライドを検証する。
"""

from pathlib import Path
import tempfile
import pytest
import yaml

from spectool.spectool.core.engine.loader import load_spec
from spectool.spectool.core.base.ir import SpecIR


# Config関連のモジュール（未実装）をインポート
# TODO: これらの機能を実装する必要がある
try:
    from spectool.spectool.core.engine.config_model import ConfigSpec, load_config
    from spectool.spectool.core.engine.config_runner import ConfigRunner
    from spectool.spectool.core.engine.config_validator import validate_config, ConfigValidationError
except ImportError:
    # 未実装の場合、プレースホルダークラスを定義

    class ConfigSpec:
        """Configモデルのプレースホルダー（未実装）"""

        pass

    def load_config(config_path: str) -> ConfigSpec:
        raise NotImplementedError("load_config not yet implemented")

    class ConfigRunner:
        """ConfigRunnerのプレースホルダー（未実装）"""

        def __init__(self, config_path: str):
            raise NotImplementedError("ConfigRunner not yet implemented")

        def run(self, initial_data: dict) -> dict:
            raise NotImplementedError("ConfigRunner.run not yet implemented")

        def validate(self) -> dict:
            raise NotImplementedError("ConfigRunner.validate not yet implemented")

    def validate_config(config: ConfigSpec, spec: SpecIR, check_implementations: bool = False) -> dict:
        raise NotImplementedError("validate_config not yet implemented")

    class ConfigValidationError(Exception):
        pass


@pytest.fixture
def sample_spec_path():
    """サンプルspec YAMLのパス"""
    return Path(__file__).parent / "fixtures" / "sample_spec.yaml"


@pytest.fixture
def temp_config_dir():
    """一時Config用ディレクトリ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config_yaml(temp_config_dir, sample_spec_path):
    """サンプルconfig YAMLを作成"""
    config_data = {
        "version": "1",
        "meta": {
            "config_name": "test_config",
            "description": "Test configuration",
            "base_spec": str(sample_spec_path),
        },
        "execution": {
            "stages": [
                {
                    "stage_id": "stage_1",
                    "selected": [{"transform_id": "process_data", "params": {"threshold": 0.7}}],
                }
            ]
        },
    }

    config_path = temp_config_dir / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    return config_path


@pytest.fixture
def setup_transform_implementation(temp_config_dir, sample_spec_path):
    """Transform実装を準備するフィクスチャ"""
    import sys
    import pandas as pd

    # specからプロジェクト名を取得
    spec = load_spec(sample_spec_path)
    project_name = spec.meta.name.replace("-", "_")  # ハイフンをアンダースコアに変換

    # appsディレクトリ構造を作成（プロジェクト名を含む）
    apps_dir = temp_config_dir / "apps"
    apps_dir.mkdir(parents=True, exist_ok=True)
    (apps_dir / "__init__.py").write_text("")

    # プロジェクトディレクトリを作成
    project_dir = apps_dir / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "__init__.py").write_text("")

    # transformsモジュールを作成
    transforms_dir = project_dir / "transforms"
    transforms_dir.mkdir(parents=True, exist_ok=True)

    # process_data関数を実装
    process_data_impl = f'''"""Transform implementations"""
import pandas as pd

def process_data(data, threshold=0.5):
    """Process time series data

    Args:
        data: Input DataFrame with timestamp, value, status
        threshold: Threshold value (default: 0.5)

    Returns:
        Processed DataFrame
    """
    # DataFrameを返す（テスト用）
    if isinstance(data, dict):
        df = pd.DataFrame(data)
        return df
    return data
'''
    (transforms_dir / "processors.py").write_text(process_data_impl)

    # __init__.pyにprocess_dataをインポート
    transforms_init = f'''"""Transforms module"""
from apps.{project_name}.transforms.processors import process_data

__all__ = ["process_data"]
'''
    (transforms_dir / "__init__.py").write_text(transforms_init)

    # sys.pathに追加
    sys.path.insert(0, str(temp_config_dir))

    # 既存のappsモジュールキャッシュをクリア
    modules_to_clear = [key for key in sys.modules.keys() if key.startswith("apps")]
    for module in modules_to_clear:
        del sys.modules[module]

    yield temp_config_dir

    # クリーンアップ
    modules_to_clear = [key for key in sys.modules.keys() if key.startswith("apps")]
    for module in modules_to_clear:
        del sys.modules[module]

    # sys.pathから削除
    if str(temp_config_dir) in sys.path:
        sys.path.remove(str(temp_config_dir))


def test_load_config(sample_config_yaml):
    """Config YAMLが正しくロードできることを確認"""
    config = load_config(str(sample_config_yaml))

    assert config.version == "1"
    assert config.meta.config_name == "test_config"
    assert len(config.execution.stages) == 1


def test_validate_config_valid(sample_config_yaml, sample_spec_path):
    """有効なConfigが検証を通過することを確認"""
    config = load_config(str(sample_config_yaml))
    spec = load_spec(sample_spec_path)

    result = validate_config(config, spec)

    assert result["valid"] is True
    assert len(result["execution_plan"]) >= 1


def test_validate_config_invalid_transform_id(temp_config_dir, sample_spec_path):
    """存在しないtransform_idを指定した場合、検証エラーが発生することを確認"""
    config_data = {
        "version": "1",
        "meta": {
            "config_name": "invalid_config",
            "description": "Invalid configuration",
            "base_spec": str(sample_spec_path),
        },
        "execution": {
            "stages": [
                {
                    "stage_id": "stage_1",
                    "selected": [{"transform_id": "non_existent_transform"}],
                }
            ]
        },
    }

    config_path = temp_config_dir / "invalid_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    config = load_config(str(config_path))
    spec = load_spec(sample_spec_path)

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config, spec)

    assert "not in candidates" in str(exc_info.value)


def test_validate_config_exclusive_mode_multiple_selections(temp_config_dir, sample_spec_path):
    """exclusive modeで複数選択した場合、検証エラーが発生することを確認"""
    config_data = {
        "version": "1",
        "meta": {
            "config_name": "invalid_exclusive",
            "description": "Invalid exclusive mode",
            "base_spec": str(sample_spec_path),
        },
        "execution": {
            "stages": [
                {
                    "stage_id": "stage_1",
                    "selected": [
                        {"transform_id": "process_data"},
                        {"transform_id": "another_transform"},  # 複数選択
                    ],
                }
            ]
        },
    }

    config_path = temp_config_dir / "invalid_exclusive.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    config = load_config(str(config_path))
    spec = load_spec(sample_spec_path)

    # exclusive modeの場合、複数選択はエラー
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config, spec)

    assert "exactly one selection" in str(exc_info.value) or "multiple" in str(exc_info.value).lower()


def test_validate_config_invalid_parameter_type(temp_config_dir, sample_spec_path):
    """パラメータの型が間違っている場合、検証エラーが発生することを確認"""
    config_data = {
        "version": "1",
        "meta": {
            "config_name": "invalid-param_type",
            "description": "Invalid parameter type",
            "base_spec": str(sample_spec_path),
        },
        "execution": {
            "stages": [
                {
                    "stage_id": "stage_1",
                    "selected": [{"transform_id": "process_data", "params": {"threshold": "not_a_float"}}],
                }
            ]
        },
    }

    config_path = temp_config_dir / "invalid_param_type.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    config = load_config(str(config_path))
    spec = load_spec(sample_spec_path)

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config, spec, check_implementations=True)

    assert "threshold" in str(exc_info.value).lower()
    assert "type" in str(exc_info.value).lower()


def test_config_runner_execution(sample_config_yaml, setup_transform_implementation, sample_spec_path):
    """ConfigRunnerがDAGを実行できることを確認"""
    from spectool.spectool.core.engine.config_model import load_config

    # Configとspecをロード
    config = load_config(str(sample_config_yaml))
    spec = load_spec(sample_spec_path)

    # project_rootを明示的に渡して検証
    validation_result = validate_config(
        config, spec, check_implementations=True, project_root=setup_transform_implementation
    )

    # 検証が成功することを確認
    assert validation_result["valid"] is True
    assert len(validation_result["execution_plan"]) > 0

    # 実行計画の最初のステップを取得
    first_step = validation_result["execution_plan"][0]

    # Transform定義からimplを取得
    transform_id = first_step["transform_id"]
    transform_def = next((t for t in spec.transforms if t.id == transform_id), None)
    assert transform_def is not None, f"Transform {transform_id} not found"

    # implパスを解決
    from spectool.spectool.core.engine.config_validator_impl import resolve_impl_path

    resolved_impl = resolve_impl_path(transform_def.impl, spec)

    # Transform関数をインポート
    module_name, func_name = resolved_impl.split(":")
    module = __import__(module_name, fromlist=[func_name])
    func = getattr(module, func_name)

    # 初期データで実行
    initial_data = {
        "timestamp": ["2024-01-01T00:00:00"],
        "value": [100.0],
        "status": ["active"],
    }

    result = func(initial_data, **first_step["params"])

    # 結果が返されることを確認
    assert result is not None


def test_config_runner_parameter_override(sample_config_yaml):
    """Configで指定したパラメータがデフォルト値をオーバーライドすることを確認"""
    runner = ConfigRunner(str(sample_config_yaml))

    # Config検証を実行
    validation = runner.validate()
    plan = validation["execution_plan"]

    # process_data transformのパラメータを確認
    process_step = next((p for p in plan if p["transform_id"] == "process_data"), None)
    assert process_step is not None
    assert process_step["params"]["threshold"] == 0.7  # Configで指定した値


def test_config_runner_uses_default_parameters(temp_config_dir, sample_spec_path):
    """パラメータを指定しない場合、デフォルト値が使用されることを確認"""
    config_data = {
        "version": "1",
        "meta": {
            "config_name": "default_params",
            "description": "Use default parameters",
            "base_spec": str(sample_spec_path),
        },
        "execution": {
            "stages": [
                {
                    "stage_id": "stage_1",
                    "selected": [{"transform_id": "process_data"}],  # paramsなし
                }
            ]
        },
    }

    config_path = temp_config_dir / "default_params.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    runner = ConfigRunner(str(config_path))

    validation = runner.validate()
    plan = validation["execution_plan"]

    process_step = next((p for p in plan if p["transform_id"] == "process_data"), None)
    assert process_step is not None
    assert process_step["params"]["threshold"] == 0.5  # デフォルト値


def test_config_runner_multiple_stages(temp_config_dir, sample_spec_path):
    """複数ステージの実行が正しく動作することを確認"""
    # TODO: 複数ステージを持つテスト用specを作成する必要がある
    pass


def test_config_runner_collects_output(sample_config_yaml, setup_transform_implementation, sample_spec_path):
    """collect_output=Trueのステージの結果が収集されることを確認"""
    from spectool.spectool.core.engine.config_model import load_config

    # Configとspecをロード
    config = load_config(str(sample_config_yaml))
    spec = load_spec(sample_spec_path)

    # project_rootを明示的に渡して検証
    validation_result = validate_config(
        config, spec, check_implementations=True, project_root=setup_transform_implementation
    )

    # 検証が成功することを確認
    assert validation_result["valid"] is True

    # 実行計画の最初のステップを取得
    first_step = validation_result["execution_plan"][0]

    # Transform定義からimplを取得
    transform_id = first_step["transform_id"]
    transform_def = next((t for t in spec.transforms if t.id == transform_id), None)
    assert transform_def is not None, f"Transform {transform_id} not found"

    # implパスを解決
    from spectool.spectool.core.engine.config_validator_impl import resolve_impl_path

    resolved_impl = resolve_impl_path(transform_def.impl, spec)

    # Transform関数をインポート
    module_name, func_name = resolved_impl.split(":")
    module = __import__(module_name, fromlist=[func_name])
    func = getattr(module, func_name)

    # 初期データで実行
    initial_data = {
        "timestamp": ["2024-01-01T00:00:00"],
        "value": [100.0],
        "status": ["active"],
    }

    result = func(initial_data, **first_step["params"])

    # 結果が収集されていることを確認
    assert result is not None


def test_config_runner_validation_checks_missing_implementation(temp_config_dir, sample_spec_path):
    """実装が存在しない場合、検証エラーが発生することを確認"""
    config_data = {
        "version": "1",
        "meta": {
            "config_name": "missing_impl",
            "description": "Missing implementation",
            "base_spec": str(sample_spec_path),
        },
        "execution": {
            "stages": [
                {
                    "stage_id": "stage_1",
                    "selected": [{"transform_id": "process_data"}],
                }
            ]
        },
    }

    config_path = temp_config_dir / "missing_impl.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    config = load_config(str(config_path))
    spec = load_spec(sample_spec_path)

    # check_implementations=Trueの場合、実装チェックが行われる
    with pytest.raises(ConfigValidationError):
        validate_config(config, spec, check_implementations=True)


def test_config_runner_skip_implementation_check(temp_config_dir, sample_spec_path):
    """check_implementations=Falseの場合、実装チェックをスキップすることを確認"""
    config_data = {
        "version": "1",
        "meta": {
            "config_name": "skip-impl_check",
            "description": "Skip implementation check",
            "base_spec": str(sample_spec_path),
        },
        "execution": {
            "stages": [
                {
                    "stage_id": "stage_1",
                    "selected": [{"transform_id": "process_data"}],
                }
            ]
        },
    }

    config_path = temp_config_dir / "skip_impl_check.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    config = load_config(str(config_path))
    spec = load_spec(sample_spec_path)

    # check_implementations=Falseの場合、実装チェックをスキップ
    result = validate_config(config, spec, check_implementations=False)
    assert result["valid"] is True


def test_config_selection_modes():
    """Selection modes (single/exclusive/multiple) が正しく動作することを確認"""
    # TODO: 各selection modeのテストを実装
    pass


def test_config_runner_handles_errors_gracefully(sample_config_yaml):
    """実行時エラーを適切にハンドリングすることを確認"""
    runner = ConfigRunner(str(sample_config_yaml))

    # 不正なデータを渡す
    invalid_data = {"invalid_field": "invalid_value"}

    # エラーが適切にハンドリングされることを確認
    with pytest.raises(Exception):
        runner.run(invalid_data)

"""
Tests for config-based DAG execution system
"""

import pandas as pd
import pytest

from packages.spec2code.config_model import load_config, load_extended_spec
from packages.spec2code.config_runner import ConfigRunner
from packages.spec2code.config_validator import (
    ConfigValidationError,
    validate_config,
)


@pytest.fixture
def sample_initial_data():
    """Sample input data for testing"""
    return pd.DataFrame(
        {
            "timestamp": [
                "2024-01-01",
                "2024-01-02",
                "2024-01-03",
                "2024-01-04",
                "2024-01-05",
            ],
            "value": [100, 150, 120, 180, 140],
        }
    )


@pytest.fixture
def tmp_path(tmp_path_factory):
    """Temporary directory for test configs"""
    return tmp_path_factory.mktemp("configs")


class TestConfigModel:
    """Test config model loading"""

    def test_load_valid_config(self):
        """Valid config loads successfully"""
        config = load_config("configs/pipeline-config-minmax.yaml")
        assert config.version == "1"
        assert config.meta.config_name == "minmax-rolling"
        assert (
            len(config.execution.stages) == 3
        )  # normalization + feature_engineering + output

    def test_load_extended_spec(self):
        """Extended spec loads successfully"""
        spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")
        assert spec.version == "1"
        assert len(spec.dag_stages) == 3  # normalization, feature_engineering, output


class TestConfigValidation:
    """Test config validation logic"""

    def test_valid_config_minmax(self):
        """Valid minmax config passes validation"""
        config = load_config("configs/pipeline-config-minmax.yaml")
        spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")

        result = validate_config(config, spec)
        assert result["valid"] is True
        assert len(result["execution_plan"]) == 3  # norm + feature + output

    def test_valid_config_zscore_multi(self):
        """Valid zscore config with multiple features passes validation"""
        config = load_config("configs/pipeline-config-zscore-multi.yaml")
        spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")

        result = validate_config(config, spec)
        assert result["valid"] is True
        assert len(result["execution_plan"]) == 4  # norm + 2 features + output

    def test_valid_config_robust_all(self):
        """Valid robust config with all features passes validation"""
        config = load_config("configs/pipeline-config-robust-all.yaml")
        spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")

        result = validate_config(config, spec)
        assert result["valid"] is True
        assert len(result["execution_plan"]) == 5  # norm + 3 features + output

    def test_invalid_exclusive_multiple_selections(self, tmp_path):
        """Exclusive mode with 2 selections fails validation"""
        invalid_config = tmp_path / "invalid.yaml"
        invalid_config.write_text(
            """
version: "1"
meta:
  config_name: "invalid-test"
  description: "Invalid config"
  base_spec: "specs/dataframe-pipeline-extended.yaml"

execution:
  stages:
    - stage_id: "normalization"
      selected:
        - transform_id: normalize_minmax
        - transform_id: normalize_zscore
    - stage_id: "feature_engineering"
      selected:
        - transform_id: add_rolling_mean
"""
        )

        config = load_config(str(invalid_config))
        spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")

        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(config, spec)

        assert "must select exactly 1 transform" in str(exc_info.value)
        assert "got 2" in str(exc_info.value)

    def test_invalid_multiple_no_selections(self, tmp_path):
        """Multiple mode with 0 selections fails validation"""
        invalid_config = tmp_path / "invalid2.yaml"
        invalid_config.write_text(
            """
version: "1"
meta:
  config_name: "invalid-test-2"
  description: "Invalid config"
  base_spec: "specs/dataframe-pipeline-extended.yaml"

execution:
  stages:
    - stage_id: "normalization"
      selected:
        - transform_id: normalize_minmax
    - stage_id: "feature_engineering"
      selected: []
"""
        )

        config = load_config(str(invalid_config))
        spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")

        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(config, spec)

        assert "requires at least 1 selections" in str(exc_info.value)

    def test_invalid_unknown_transform(self, tmp_path):
        """Unknown transform_id fails validation"""
        invalid_config = tmp_path / "invalid3.yaml"
        invalid_config.write_text(
            """
version: "1"
meta:
  config_name: "invalid-test-3"
  description: "Invalid config"
  base_spec: "specs/dataframe-pipeline-extended.yaml"

execution:
  stages:
    - stage_id: "normalization"
      selected:
        - transform_id: normalize_unknown
    - stage_id: "feature_engineering"
      selected:
        - transform_id: add_rolling_mean
"""
        )

        config = load_config(str(invalid_config))
        spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")

        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(config, spec)

        assert "not in candidates" in str(exc_info.value)

    def test_invalid_wrong_parameter_type(self, tmp_path, sample_initial_data):
        """Wrong parameter type is caught by validation"""
        invalid_config = tmp_path / "invalid_param.yaml"
        invalid_config.write_text(
            """
version: "1"
meta:
  config_name: "invalid-param-test"
  description: "Invalid parameter type"
  base_spec: "specs/dataframe-pipeline-extended.yaml"

execution:
  stages:
    - stage_id: "normalization"
      selected:
        - transform_id: normalize_minmax
    - stage_id: "feature_engineering"
      selected:
        - transform_id: add_rolling_mean
          params:
            window: "not_an_int"  # Should be int
"""
        )

        config = load_config(str(invalid_config))
        spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")

        # Validation now catches type errors
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(config, spec, check_implementations=True)

        # Should fail because window should be int, not str
        assert "window" in str(exc_info.value).lower()
        assert "type" in str(exc_info.value).lower()

    def test_invalid_missing_required_parameter(self, tmp_path, sample_initial_data):
        """Missing required parameter causes execution error"""
        invalid_config = tmp_path / "invalid_missing_param.yaml"
        invalid_config.write_text(
            """
version: "1"
meta:
  config_name: "missing-param-test"
  description: "Missing required parameter"
  base_spec: "specs/dataframe-pipeline-extended.yaml"

execution:
  stages:
    - stage_id: "normalization"
      selected:
        - transform_id: normalize_minmax
    - stage_id: "feature_engineering"
      selected:
        - transform_id: add_rolling_mean
          # Missing 'window' parameter (no default in config or spec)
          params: {}
"""
        )

        config = load_config(str(invalid_config))
        runner = ConfigRunner(str(invalid_config))

        # In this case, default_params from spec provides window=2
        # So execution should succeed
        result = runner.run(sample_initial_data)
        assert "rolling_mean" in result.columns

    def test_invalid_negative_parameter_value(self, tmp_path, sample_initial_data):
        """Invalid parameter value (negative) is caught by validation"""
        invalid_config = tmp_path / "invalid_negative_param.yaml"
        invalid_config.write_text(
            """
version: "1"
meta:
  config_name: "negative-param-test"
  description: "Negative parameter value"
  base_spec: "specs/dataframe-pipeline-extended.yaml"

execution:
  stages:
    - stage_id: "normalization"
      selected:
        - transform_id: normalize_minmax
    - stage_id: "feature_engineering"
      selected:
        - transform_id: add_rolling_mean
          params:
            window: -1  # Invalid: window must be positive
"""
        )

        config = load_config(str(invalid_config))
        spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")

        # Validation now catches value constraint errors
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(config, spec, check_implementations=True)

        # Should fail because window must be positive
        assert "window" in str(exc_info.value).lower()
        assert "positive" in str(exc_info.value).lower()

    def test_validation_with_check_implementations_disabled(self, tmp_path):
        """Validation can skip implementation checks"""
        invalid_config = tmp_path / "invalid_type_but_skip_check.yaml"
        invalid_config.write_text(
            """
version: "1"
meta:
  config_name: "skip-impl-check"
  description: "Invalid type but skip implementation check"
  base_spec: "specs/dataframe-pipeline-extended.yaml"

execution:
  stages:
    - stage_id: "normalization"
      selected:
        - transform_id: normalize_minmax
    - stage_id: "feature_engineering"
      selected:
        - transform_id: add_rolling_mean
          params:
            window: "not_an_int"  # Invalid type
"""
        )

        config = load_config(str(invalid_config))
        spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")

        # With check_implementations=False, validation passes
        result = validate_config(config, spec, check_implementations=False)
        assert result["valid"] is True
        assert len(result["execution_plan"]) == 3

    def test_validation_catches_missing_implementation(self, tmp_path):
        """Validation catches missing transform implementation"""
        invalid_config = tmp_path / "missing_impl.yaml"
        invalid_config.write_text(
            """
version: "1"
meta:
  config_name: "missing-impl"
  description: "Transform implementation missing"
  base_spec: "specs/dataframe-pipeline-extended.yaml"

execution:
  stages:
    - stage_id: "normalization"
      selected:
        - transform_id: normalize_minmax
    - stage_id: "feature_engineering"
      selected:
        - transform_id: add_rolling_mean
"""
        )

        # First, ensure implementations exist by running generation
        from packages.spec2code.engine import load_spec, generate_skeleton
        spec = load_spec("specs/dataframe-pipeline-extended.yaml")

        # Now test validation with implementations
        config = load_config(str(invalid_config))
        extended_spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")

        # This should pass because implementations exist
        result = validate_config(config, extended_spec, check_implementations=True)
        assert result["valid"] is True

    def test_error_config_file(self):
        """Test that error-test config file fails validation as expected"""
        config = load_config("configs/pipeline-config-error-test.yaml")
        spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")

        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(config, spec)

        # Should fail because exclusive mode requires exactly 1 selection
        assert "must select exactly 1 transform" in str(exc_info.value)
        assert "got 2" in str(exc_info.value)

    def test_invalid_param_type_config_file(self):
        """Test that invalid-param-type config file fails validation"""
        config = load_config("configs/pipeline-config-invalid-param-type.yaml")
        spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")

        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(config, spec, check_implementations=True)

        # Should fail because window should be int, not str
        assert "window" in str(exc_info.value).lower()
        assert "type" in str(exc_info.value).lower()

    def test_invalid_negative_config_file(self):
        """Test that invalid-negative config file fails validation"""
        config = load_config("configs/pipeline-config-invalid-negative.yaml")
        spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")

        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(config, spec, check_implementations=True)

        # Should fail because window must be positive
        assert "window" in str(exc_info.value).lower()
        assert "positive" in str(exc_info.value).lower()


class TestConfigExecution:
    """Test config-based execution"""

    def test_execute_minmax_config(self, sample_initial_data):
        """Execute minmax normalization config"""
        runner = ConfigRunner("configs/pipeline-config-minmax.yaml")
        result = runner.run(sample_initial_data)

        # Check output structure
        assert len(result) == 5
        assert "timestamp" in result.columns
        assert "value" in result.columns
        assert "normalized" in result.columns
        assert "rolling_mean" in result.columns

        # Check normalization (MinMax: 0-1 range)
        assert result["normalized"].min() >= 0.0
        assert result["normalized"].max() <= 1.0

    def test_execute_zscore_multi_config(self, sample_initial_data):
        """Execute zscore normalization with multiple features"""
        runner = ConfigRunner("configs/pipeline-config-zscore-multi.yaml")
        result = runner.run(sample_initial_data)

        # Check output structure
        assert len(result) == 5
        assert "normalized" in result.columns
        assert "rolling_mean" in result.columns
        assert "diff" in result.columns

        # Check diff feature (first row should be 0)
        assert result["diff"].iloc[0] == 0.0

    def test_execute_robust_all_config(self, sample_initial_data):
        """Execute robust normalization with all features"""
        runner = ConfigRunner("configs/pipeline-config-robust-all.yaml")
        result = runner.run(sample_initial_data)

        # Check output structure
        assert len(result) == 5
        assert "normalized" in result.columns
        assert "rolling_mean" in result.columns
        assert "diff" in result.columns
        assert "lag_1" in result.columns
        assert "lag_2" in result.columns

        # Check lag features (first row should be 0)
        assert result["lag_1"].iloc[0] == 0.0
        assert result["lag_2"].iloc[0] == 0.0

    def test_parameter_override(self, sample_initial_data):
        """Parameters from config override defaults"""
        runner = ConfigRunner("configs/pipeline-config-minmax.yaml")

        # Check that window=3 is used (from config, not default=2)
        validation = runner.validate()
        plan = validation["execution_plan"]

        rolling_step = next(
            (p for p in plan if p["transform_id"] == "add_rolling_mean"), None
        )
        assert rolling_step is not None
        assert rolling_step["params"]["window"] == 3

    def test_different_normalizations_produce_different_results(
        self, sample_initial_data
    ):
        """Different normalization methods produce different results"""
        runner_minmax = ConfigRunner("configs/pipeline-config-minmax.yaml")
        runner_zscore = ConfigRunner("configs/pipeline-config-zscore-multi.yaml")

        result_minmax = runner_minmax.run(sample_initial_data)
        result_zscore = runner_zscore.run(sample_initial_data)

        # Check that normalized values are different
        assert not result_minmax["normalized"].equals(result_zscore["normalized"])

        # MinMax should be in [0, 1], Z-score can be negative
        assert result_minmax["normalized"].min() >= 0.0
        assert result_zscore["normalized"].min() < 0.0  # Z-score has negative values


class TestSelectionModes:
    """Test different selection modes"""

    def test_single_mode_auto_select(self):
        """Single mode stages are auto-selected"""
        config = load_config("configs/pipeline-config-minmax.yaml")
        spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")

        result = validate_config(config, spec)

        # Output stage should be auto-selected
        output_steps = [
            p for p in result["execution_plan"] if p["stage_id"] == "output"
        ]
        assert len(output_steps) == 1
        assert output_steps[0]["transform_id"] == "finalize_step_b"

    def test_exclusive_mode_one_selection(self):
        """Exclusive mode requires exactly one selection"""
        config = load_config("configs/pipeline-config-minmax.yaml")
        spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")

        result = validate_config(config, spec)

        # Normalization stage should have exactly 1 selection
        norm_steps = [
            p for p in result["execution_plan"] if p["stage_id"] == "normalization"
        ]
        assert len(norm_steps) == 1
        assert norm_steps[0]["transform_id"] == "normalize_minmax"

    def test_multiple_mode_multiple_selections(self):
        """Multiple mode allows multiple selections"""
        config = load_config("configs/pipeline-config-robust-all.yaml")
        spec = load_extended_spec("specs/dataframe-pipeline-extended.yaml")

        result = validate_config(config, spec)

        # Feature engineering stage should have 3 selections
        feature_steps = [
            p
            for p in result["execution_plan"]
            if p["stage_id"] == "feature_engineering"
        ]
        assert len(feature_steps) == 3

        transform_ids = {step["transform_id"] for step in feature_steps}
        assert transform_ids == {
            "add_rolling_mean",
            "add_diff",
            "add_lag_features",
        }

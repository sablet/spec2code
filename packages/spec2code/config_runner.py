"""
Config-based DAG execution runner
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

import pandas as pd

from packages.spec2code.config_model import Config, load_config, load_extended_spec
from packages.spec2code.config_validator import validate_config


class ConfigRunner:
    """Execute DAG based on config file"""

    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.spec_path = self.config.meta.base_spec
        self.extended_spec = load_extended_spec(self.spec_path)

    def validate(self, check_implementations: bool = True) -> dict[str, Any]:
        """Validate config against spec

        Args:
            check_implementations: If True, validate parameter types and implementations

        Returns:
            Validation result with execution plan
        """
        return validate_config(self.config, self.extended_spec, check_implementations)

    def run(self, initial_data: pd.DataFrame) -> pd.DataFrame:
        """Execute DAG with initial data"""
        print(f"🔍 Validating config...")
        validation_result = self.validate()
        print(f"✅ Config validation passed")

        execution_plan = validation_result["execution_plan"]

        print(f"📋 Config: {self.config.meta.config_name}")
        print(f"📄 Spec: {self.spec_path}")
        print(f"🔢 Execution plan: {len(execution_plan)} transform(s)")
        print()

        current_data = initial_data
        stage_results = {}

        for step in execution_plan:
            stage_id = step["stage_id"]
            transform_id = step["transform_id"]
            transform_def = step["transform_def"]
            params = step["params"]

            print(f"▶️  Stage: {stage_id}")
            print(f"   Transform: {transform_id}")
            if params:
                print(f"   Params: {params}")

            # Import transform function
            impl = transform_def["impl"]
            module_path, func_name = impl.rsplit(":", 1)
            module = importlib.import_module(module_path)
            func = getattr(module, func_name)

            # Build function arguments
            sig = inspect.signature(func)
            func_args = {}

            # First parameter is always the data
            first_param = list(sig.parameters.keys())[0]
            func_args[first_param] = current_data

            # Add other parameters from config
            for param_name in list(sig.parameters.keys())[1:]:
                if param_name in params:
                    func_args[param_name] = params[param_name]

            # Execute transform
            try:
                result = func(**func_args)
                print(f"   ✅ Success: {len(result)} rows")

                # Store stage result
                if stage_id not in stage_results:
                    stage_results[stage_id] = []
                stage_results[stage_id].append(result)

                # For multiple-mode stages, accumulate features
                # For exclusive-mode stages, use the result directly
                stage = next(
                    (
                        s
                        for s in self.extended_spec.dag_stages
                        if s.stage_id == stage_id
                    ),
                    None,
                )

                if stage and stage.selection_mode == "multiple":
                    # Merge features from multiple transforms
                    current_data = result
                else:
                    # Use result directly
                    current_data = result

            except Exception as e:
                print(f"   ❌ Error: {e}")
                raise

            print()

        print(f"✅ Execution completed")
        print(
            f"📊 Final data: {len(current_data)} rows, {len(current_data.columns)} columns"
        )
        print(f"   Columns: {list(current_data.columns)}")

        return current_data

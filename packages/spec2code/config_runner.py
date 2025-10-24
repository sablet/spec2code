"""
Config-based DAG execution runner
"""

from __future__ import annotations

import importlib
import inspect
from typing import Any, Callable

import pandas as pd

from packages.spec2code.config_model import load_config, load_extended_spec
from packages.spec2code.config_validator import validate_config


class ConfigRunner:
    """Execute DAG based on config file"""

    def __init__(self: "ConfigRunner", config_path: str) -> None:
        self.config = load_config(config_path)
        self.spec_path = self.config.meta.base_spec
        self.extended_spec = load_extended_spec(self.spec_path)

    def validate(
        self: "ConfigRunner", check_implementations: bool = True
    ) -> dict[str, Any]:
        """Validate config against spec

        Args:
            check_implementations: If True, validate parameter types and implementations

        Returns:
            Validation result with execution plan
        """
        return validate_config(self.config, self.extended_spec, check_implementations)

    def run(self: "ConfigRunner", initial_data: pd.DataFrame) -> pd.DataFrame:
        """Execute DAG with initial data"""
        print("🔍 Validating config...")
        validation_result = self.validate()
        print("✅ Config validation passed")

        execution_plan = validation_result["execution_plan"]

        print(f"📋 Config: {self.config.meta.config_name}")
        print(f"📄 Spec: {self.spec_path}")
        print(f"🔢 Execution plan: {len(execution_plan)} transform(s)")
        print()

        current_data = initial_data
        stage_results: dict[str, list[pd.DataFrame]] = {}

        for step in execution_plan:
            current_data = self._execute_step(step, current_data, stage_results)
            print()

        print("✅ Execution completed")
        final_row_count = len(current_data)
        final_col_count = len(current_data.columns)
        print(f"📊 Final data: {final_row_count} rows, {final_col_count} columns")
        print(f"   Columns: {list(current_data.columns)}")

        return current_data

    def _execute_step(
        self: "ConfigRunner",
        step: dict[str, Any],
        current_data: pd.DataFrame,
        stage_results: dict[str, list[pd.DataFrame]],
    ) -> pd.DataFrame:
        stage_id: str = step["stage_id"]
        transform_id: str = step["transform_id"]
        transform_def: dict[str, Any] = step["transform_def"]
        params: dict[str, Any] = step["params"]

        print(f"▶️  Stage: {stage_id}")
        print(f"   Transform: {transform_id}")
        if params:
            print(f"   Params: {params}")

        func, signature = self._import_transform_callable(transform_def["impl"])
        func_args = self._build_function_args(signature, current_data, params)

        try:
            result = func(**func_args)
            print(f"   ✅ Success: {len(result)} rows")
        except Exception as exc:
            print(f"   ❌ Error: {exc}")
            raise

        return self._post_process_result(stage_id, result, stage_results)

    def _import_transform_callable(
        self: "ConfigRunner", impl: str
    ) -> tuple[Callable[..., Any], inspect.Signature]:
        module_path, func_name = impl.rsplit(":", 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        return func, inspect.signature(func)

    def _build_function_args(
        self: "ConfigRunner",
        signature: inspect.Signature,
        current_data: pd.DataFrame,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        param_names = list(signature.parameters.keys())
        func_args: dict[str, Any] = {}
        if not param_names:
            return func_args

        func_args[param_names[0]] = current_data
        for param_name in param_names[1:]:
            if param_name in params:
                func_args[param_name] = params[param_name]
        return func_args

    def _post_process_result(
        self: "ConfigRunner",
        stage_id: str,
        result: pd.DataFrame,
        stage_results: dict[str, list[pd.DataFrame]],
    ) -> pd.DataFrame:
        stage_results.setdefault(stage_id, []).append(result)
        return result

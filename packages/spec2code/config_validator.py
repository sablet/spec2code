"""
Config validation logic for configurable DAG execution
"""

from __future__ import annotations

import importlib
import inspect
from typing import Any

from packages.spec2code.config_model import Config, DAGStage, ExtendedSpec


class ConfigValidationError(Exception):
    """Config validation error"""

    pass


def _validate_transform_parameters(
    transform_id: str, transform_def: dict[str, Any], params: dict[str, Any]
) -> list[str]:
    """
    Validate transform parameters against function signature and types

    Args:
        transform_id: Transform ID for error messages
        transform_def: Transform definition from spec
        params: Parameters to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Try to import and inspect the function
    try:
        impl = transform_def["impl"]
        module_path, func_name = impl.rsplit(":", 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)

        # Get function signature
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        # First parameter is always data (skip validation)
        data_param = param_names[0] if param_names else None

        # Validate each provided parameter
        for param_name, param_value in params.items():
            if param_name not in sig.parameters:
                errors.append(
                    f"Transform '{transform_id}': unknown parameter '{param_name}'"
                )
                continue

            param_spec = sig.parameters[param_name]

            # Check parameter type annotation if available
            if param_spec.annotation != inspect.Parameter.empty:
                annotation = param_spec.annotation

                # Basic type checking for common types
                expected_type = None
                if annotation == int or str(annotation) == "<class 'int'>":
                    expected_type = int
                elif annotation == float or str(annotation) == "<class 'float'>":
                    expected_type = float
                elif annotation == str or str(annotation) == "<class 'str'>":
                    expected_type = str
                elif annotation == bool or str(annotation) == "<class 'bool'>":
                    expected_type = bool

                if expected_type and not isinstance(param_value, expected_type):
                    errors.append(
                        f"Transform '{transform_id}': parameter '{param_name}' "
                        f"expected type {expected_type.__name__}, "
                        f"got {type(param_value).__name__}"
                    )

                # Value range validation for common constraints
                if expected_type in (int, float):
                    if isinstance(param_value, (int, float)):
                        # Check for negative values in parameters that typically should be positive
                        if param_name in ("window", "n_lags", "size", "length", "count"):
                            if param_value <= 0:
                                errors.append(
                                    f"Transform '{transform_id}': parameter '{param_name}' "
                                    f"must be positive, got {param_value}"
                                )

        # Check for required parameters (parameters without defaults)
        spec_params = {p["name"] for p in transform_def.get("parameters", [])}
        provided_params = set(params.keys())

        # Get parameters from spec that are not the first (data) parameter
        spec_param_defs = [
            p for p in transform_def.get("parameters", [])
            if p["name"] != data_param
        ]

        for param_def in spec_param_defs:
            param_name = param_def["name"]
            if param_name in sig.parameters:
                param_spec = sig.parameters[param_name]
                # If parameter has no default and is not provided
                if (
                    param_spec.default == inspect.Parameter.empty
                    and param_name not in params
                ):
                    errors.append(
                        f"Transform '{transform_id}': missing required parameter '{param_name}'"
                    )

    except ImportError as e:
        errors.append(
            f"Transform '{transform_id}': cannot import implementation: {e}"
        )
    except AttributeError as e:
        errors.append(
            f"Transform '{transform_id}': function not found in module: {e}"
        )
    except Exception as e:
        errors.append(
            f"Transform '{transform_id}': validation error: {e}"
        )

    return errors


def validate_config(
    config: Config, extended_spec: ExtendedSpec, check_implementations: bool = True
) -> dict[str, Any]:
    """
    Validate config against extended spec

    Args:
        config: Config to validate
        extended_spec: Extended spec with dag_stages
        check_implementations: If True, check that transform functions exist and are importable

    Returns:
        dict with validation results and execution plan

    Raises:
        ConfigValidationError: If config is invalid
    """
    errors: list[str] = []
    execution_plan: list[dict[str, Any]] = []

    # Build stage lookup
    stage_by_id = {stage.stage_id: stage for stage in extended_spec.dag_stages}

    # Build transform lookup
    transform_by_id = {t["id"]: t for t in extended_spec.transforms}

    for stage_exec in config.execution.stages:
        stage_id = stage_exec.stage_id

        # Check if stage exists
        if stage_id not in stage_by_id:
            errors.append(f"Unknown stage_id: {stage_id}")
            continue

        stage = stage_by_id[stage_id]

        # Validate selection count
        num_selected = len(stage_exec.selected)

        if stage.selection_mode == "single":
            # Single mode: auto-select the only candidate (no config needed)
            if num_selected > 0:
                errors.append(
                    f"Stage '{stage_id}' has selection_mode='single', "
                    f"but config specifies {num_selected} selections. "
                    f"Remove this stage from config (auto-selected)."
                )

        elif stage.selection_mode == "exclusive":
            # Exclusive mode: must select exactly 1
            if num_selected != 1:
                errors.append(
                    f"Stage '{stage_id}' has selection_mode='exclusive', "
                    f"must select exactly 1 transform, but got {num_selected}"
                )

        elif stage.selection_mode == "multiple":
            # Multiple mode: must select at least 1 (fixed min), max_select is configurable
            min_sel = 1  # Always require at least one selection
            max_sel = stage.max_select

            if num_selected < min_sel:
                errors.append(
                    f"Stage '{stage_id}' requires at least {min_sel} selection(s), "
                    f"but got {num_selected}"
                )

            if max_sel is not None and num_selected > max_sel:
                errors.append(
                    f"Stage '{stage_id}' allows at most {max_sel} selections, "
                    f"but got {num_selected}"
                )

        # Validate each selection
        candidate_ids = {c.transform_id for c in stage.candidates}

        for selection in stage_exec.selected:
            transform_id = selection.transform_id

            # Check if transform is a valid candidate
            if transform_id not in candidate_ids:
                errors.append(
                    f"Stage '{stage_id}': transform '{transform_id}' "
                    f"is not in candidates: {list(candidate_ids)}"
                )
                continue

            # Check if transform exists in spec
            if transform_id not in transform_by_id:
                errors.append(
                    f"Transform '{transform_id}' not found in spec transforms"
                )
                continue

            # Build execution entry
            transform_def = transform_by_id[transform_id]

            # Use params from config selection
            # (default_params removed - handled by transform's default_args)
            final_params = selection.params.copy()

            # Validate parameters if check_implementations is enabled
            if check_implementations:
                param_errors = _validate_transform_parameters(
                    transform_id, transform_def, final_params
                )
                errors.extend(param_errors)

            execution_plan.append(
                {
                    "stage_id": stage_id,
                    "transform_id": transform_id,
                    "transform_def": transform_def,
                    "params": final_params,
                }
            )

    # Handle single-mode stages (auto-select)
    for stage in extended_spec.dag_stages:
        if stage.selection_mode == "single":
            # Auto-select the only candidate
            if len(stage.candidates) != 1:
                errors.append(
                    f"Stage '{stage.stage_id}' has selection_mode='single', "
                    f"but has {len(stage.candidates)} candidates (expected 1)"
                )
                continue

            candidate = stage.candidates[0]
            transform_id = candidate.transform_id

            if transform_id not in transform_by_id:
                errors.append(
                    f"Transform '{transform_id}' not found in spec transforms"
                )
                continue

            transform_def = transform_by_id[transform_id]

            # Validate parameters if check_implementations is enabled
            # (No default_params - use empty dict)
            if check_implementations:
                param_errors = _validate_transform_parameters(
                    transform_id, transform_def, {}
                )
                errors.extend(param_errors)

            execution_plan.append(
                {
                    "stage_id": stage.stage_id,
                    "transform_id": transform_id,
                    "transform_def": transform_def,
                    "params": {},
                }
            )

    if errors:
        raise ConfigValidationError("\n".join(errors))

    return {"valid": True, "execution_plan": execution_plan}

"""
Config validation logic for configurable DAG execution
"""

from __future__ import annotations

import importlib
import inspect
from typing import Any, cast

from packages.spec2code.config_model import (
    Config,
    ExtendedSpec,
    DAGStage,
    StageExecution,
    TransformSelection,
)


POSITIVE_PARAM_NAMES = {"window", "n_lags", "size", "length", "count"}


class ConfigValidationError(Exception):
    """Config validation error"""

    pass


def _load_transform_signature(
    transform_id: str, transform_def: dict[str, Any]
) -> tuple[inspect.Signature | None, list[str]]:
    """Import the transform implementation and return its signature."""
    impl = transform_def.get("impl")
    if not impl:
        return None, [f"Transform '{transform_id}': missing implementation path"]

    try:
        module_path, func_name = impl.rsplit(":", 1)
    except ValueError as exc:
        return None, [f"Transform '{transform_id}': invalid impl value '{impl}': {exc}"]

    try:
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
    except ImportError as exc:
        message = f"Transform '{transform_id}': import failed ({exc})"
        return None, [message]
    except AttributeError as exc:
        message = f"Transform '{transform_id}': function missing ({exc})"
        return None, [message]

    try:
        return inspect.signature(func), []
    except (TypeError, ValueError) as exc:
        message = f"Transform '{transform_id}': signature check failed ({exc})"
        return None, [message]


def _expected_basic_type(annotation: object) -> type | None:
    """Resolve basic runtime type from a type annotation."""
    basic_types: dict[str, type] = {
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "builtins.int": int,
        "builtins.float": float,
        "builtins.str": str,
        "builtins.bool": bool,
    }

    if annotation in {int, float, str, bool}:
        return cast(type, annotation)

    as_str = str(annotation)
    if as_str.startswith("<class '") and as_str.endswith("'>"):
        return basic_types.get(as_str[8:-2], None)

    return basic_types.get(as_str)


def _validate_unknown_parameters(transform_id: str, signature: inspect.Signature, params: dict[str, Any]) -> list[str]:
    """Ensure provided params exist in the callable signature."""
    errors = []
    for param_name in params:
        if param_name not in signature.parameters:
            errors.append(f"Transform '{transform_id}': unknown parameter '{param_name}'")
    return errors


def _validate_parameter_type(
    transform_id: str,
    param_name: str,
    param_value: object,
    param_spec: inspect.Parameter,
) -> list[str]:
    """Validate a single parameter against its annotation."""
    if param_spec.annotation == inspect.Parameter.empty:
        return []

    expected_type = _expected_basic_type(param_spec.annotation)
    if expected_type and not isinstance(param_value, expected_type):
        return [
            f"Transform '{transform_id}': parameter '{param_name}' expected type "
            f"{expected_type.__name__}, got {type(param_value).__name__}"
        ]

    if (
        expected_type in {int, float}
        and isinstance(param_value, (int, float))
        and param_name in POSITIVE_PARAM_NAMES
        and param_value <= 0
    ):
        return [(f"Transform '{transform_id}': parameter '{param_name}' must be " f"positive, got {param_value}")]

    return []


def _validate_required_parameters(
    transform_id: str,
    signature: inspect.Signature,
    params: dict[str, Any],
    data_param: str | None,
) -> list[str]:
    """Ensure required parameters without defaults are supplied."""
    errors = []
    for param_name, param_spec in signature.parameters.items():
        if param_name == data_param:
            continue
        if param_spec.default == inspect.Parameter.empty and param_name not in params:
            errors.append(f"Transform '{transform_id}': missing required parameter '{param_name}'")
    return errors


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
    signature, load_errors = _load_transform_signature(transform_id, transform_def)
    if load_errors:
        return load_errors

    if signature is None:
        return [f"Transform '{transform_id}': validation error: signature unavailable"]

    param_names = list(signature.parameters.keys())
    data_param = param_names[0] if param_names else None

    errors = _validate_unknown_parameters(transform_id, signature, params)

    for param_name, param_value in params.items():
        if param_name not in signature.parameters:
            continue
        param_spec = signature.parameters[param_name]
        errors.extend(_validate_parameter_type(transform_id, param_name, param_value, param_spec))

    errors.extend(_validate_required_parameters(transform_id, signature, params, data_param))

    return errors


def _validate_selection_counts(stage: DAGStage, num_selected: int) -> list[str]:
    """Validate number of selections against a stage's selection mode."""
    errors: list[str] = []
    stage_id = stage.stage_id
    mode = stage.selection_mode

    if mode == "single":
        if num_selected > 0:
            message = (
                f"Stage '{stage_id}' is single mode with {num_selected} selection(s)." " Remove this stage from config."
            )
            errors.append(message)
        return errors

    if mode == "exclusive":
        if num_selected != 1:
            errors.append(f"Stage '{stage_id}' requires exactly one selection, got {num_selected}")
        return errors

    if mode == "multiple":
        if num_selected < 1:
            errors.append(f"Stage '{stage_id}' requires at least one selection, " f"got {num_selected}")
        if stage.max_select is not None and num_selected > stage.max_select:
            errors.append(f"Stage '{stage_id}' allows at most {stage.max_select} selections, " f"got {num_selected}")
        return errors

    errors.append(f"Stage '{stage_id}' has unsupported selection_mode '{mode}'")
    return errors


def _build_plan_entry(
    stage_id: str,
    stage: DAGStage,
    selection: TransformSelection,
    transform_by_id: dict[str, dict[str, Any]],
    check_implementations: bool,
) -> tuple[list[str], dict[str, Any] | None]:
    """Validate a selection and return an execution plan entry."""
    errors: list[str] = []
    transform_id = selection.transform_id
    candidate_ids = {candidate.transform_id for candidate in stage.candidates}

    if transform_id not in candidate_ids:
        errors.append(
            f"Stage '{stage_id}': transform '{transform_id}' " f"is not in candidates: {sorted(candidate_ids)}"
        )
        return errors, None

    transform_def = transform_by_id.get(transform_id)
    if transform_def is None:
        errors.append(f"Transform '{transform_id}' not found in spec transforms")
        return errors, None

    params = selection.params.copy()
    if check_implementations:
        errors.extend(_validate_transform_parameters(transform_id, transform_def, params))

    plan_entry = {
        "stage_id": stage_id,
        "transform_id": transform_id,
        "transform_def": transform_def,
        "params": params,
    }
    return errors, plan_entry


def _process_stage_execution(
    stage_exec: StageExecution,
    stage_by_id: dict[str, DAGStage],
    transform_by_id: dict[str, dict[str, Any]],
    check_implementations: bool,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Validate one stage execution block from config."""
    errors: list[str] = []
    execution_entries: list[dict[str, Any]] = []
    stage = stage_by_id.get(stage_exec.stage_id)

    if stage is None:
        return [f"Unknown stage_id: {stage_exec.stage_id}"], []

    errors.extend(_validate_selection_counts(stage, len(stage_exec.selected)))

    for selection in stage_exec.selected:
        selection_errors, plan_entry = _build_plan_entry(
            stage_exec.stage_id,
            stage,
            selection,
            transform_by_id,
            check_implementations,
        )
        errors.extend(selection_errors)
        if plan_entry:
            execution_entries.append(plan_entry)

    return errors, execution_entries


def _auto_select_single_stages(
    extended_spec: ExtendedSpec,
    transform_by_id: dict[str, dict[str, Any]],
    check_implementations: bool,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Automatically build plan entries for single-mode stages."""
    errors: list[str] = []
    execution_entries: list[dict[str, Any]] = []

    for stage in extended_spec.dag_stages:
        if stage.selection_mode != "single":
            continue

        if len(stage.candidates) != 1:
            errors.append(
                f"Stage '{stage.stage_id}' is single mode but has " f"{len(stage.candidates)} candidates (expected 1)"
            )
            continue

        transform_id = stage.candidates[0].transform_id
        transform_def = transform_by_id.get(transform_id)
        if transform_def is None:
            errors.append(f"Transform '{transform_id}' not found in spec transforms")
            continue

        if check_implementations:
            errors.extend(_validate_transform_parameters(transform_id, transform_def, {}))

        execution_entries.append(
            {
                "stage_id": stage.stage_id,
                "transform_id": transform_id,
                "transform_def": transform_def,
                "params": {},
            }
        )

    return errors, execution_entries


def validate_config(config: Config, extended_spec: ExtendedSpec, check_implementations: bool = True) -> dict[str, Any]:
    """Validate config against extended spec and build an execution plan.

    Args:
        config: Config instance to validate.
        extended_spec: Extended spec containing dag_stages.
        check_implementations: When True, import transforms and validate parameters.

    Raises:
        ConfigValidationError: When validation fails.
    """
    errors: list[str] = []
    execution_plan: list[dict[str, Any]] = []

    stage_by_id = {stage.stage_id: stage for stage in extended_spec.dag_stages}
    transform_by_id = {transform["id"]: transform for transform in extended_spec.transforms}

    for stage_exec in config.execution.stages:
        stage_errors, stage_entries = _process_stage_execution(
            stage_exec, stage_by_id, transform_by_id, check_implementations
        )
        errors.extend(stage_errors)
        execution_plan.extend(stage_entries)

    auto_errors, auto_entries = _auto_select_single_stages(extended_spec, transform_by_id, check_implementations)
    errors.extend(auto_errors)
    execution_plan.extend(auto_entries)

    if errors:
        raise ConfigValidationError("\n".join(errors))

    return {"valid": True, "execution_plan": execution_plan}

"""Config検証機能

Config YAMLがSpec定義に適合しているかを検証する。
"""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from typing import Any

from spectool.spectool.core.base.ir import DAGStageSpec, SpecIR, TransformSpec
from spectool.spectool.core.engine.config_model import (
    ConfigSpec,
    StageExecution,
    TransformSelection,
)
from spectool.spectool.core.engine.config_validator_impl import (
    check_function_implementation,
    load_transform_signature,
    resolve_impl_path,
)
from spectool.spectool.core.engine.config_validator_types import (
    validate_param_type_from_spec,
    validate_parameter_type,
)


class ConfigValidationError(Exception):
    """Config検証エラー"""

    pass


def _validate_params_with_signature(
    transform_id: str,
    impl: str,
    params: dict[str, Any],
    signature: inspect.Signature,
    spec: SpecIR,
) -> list[str]:
    """シグネチャを使ってパラメータを検証

    Args:
        transform_id: Transform ID
        impl: 実装パス
        params: パラメータ
        signature: 関数シグネチャ
        spec: SpecIR

    Returns:
        エラーメッセージリスト
    """
    errors = []

    # 実装の完全性をチェック（TODOのままではないか）
    resolved_impl = resolve_impl_path(impl, spec)
    try:
        module_path, func_name = resolved_impl.rsplit(":", 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        errors.extend(check_function_implementation(func, transform_id))
    except (ImportError, AttributeError, ValueError):
        # インポートエラーは既にload_transform_signatureで報告されているのでスキップ
        pass

    # 未知のパラメータをチェック
    for param_name in params:
        if param_name not in signature.parameters:
            errors.append(f"Transform '{transform_id}': unknown parameter '{param_name}'")

    # 型チェック
    for param_name, param_value in params.items():
        if param_name not in signature.parameters:
            continue
        param_spec = signature.parameters[param_name]
        errors.extend(validate_parameter_type(transform_id, param_name, param_value, param_spec))

    return errors


def _validate_params_with_spec(
    transform_id: str,
    params: dict[str, Any],
    transform_def: TransformSpec,
    load_errors: list[str],
) -> list[str]:
    """Transform定義を使ってパラメータを検証

    Args:
        transform_id: Transform ID
        params: パラメータ
        transform_def: Transform定義
        load_errors: インポートエラー

    Returns:
        エラーメッセージリスト
    """
    errors = []
    for param_name, param_value in params.items():
        # パラメータ定義を検索
        param_def = next((p for p in transform_def.parameters if p.name == param_name), None)
        if not param_def:
            errors.append(f"Transform '{transform_id}': unknown parameter '{param_name}'")
            continue
        # Spec定義から型を検証
        errors.extend(validate_param_type_from_spec(transform_id, param_name, param_value, param_def))
    # パラメータ型エラーがあればそれを返す、なければインポートエラーを返す
    return errors if errors else load_errors


def _validate_transform_parameters(
    transform_id: str,
    impl: str,
    params: dict[str, Any],
    spec: SpecIR,
    transform_def: TransformSpec | None = None,
) -> list[str]:
    """Transform関数のパラメータを検証

    Args:
        transform_id: Transform ID
        impl: 実装パス
        params: パラメータ
        spec: SpecIR（implパス解決用）
        transform_def: Transform定義（オプション）

    Returns:
        エラーメッセージリスト
    """
    # 実装からシグネチャを取得（可能な場合のみ）
    signature, load_errors = load_transform_signature(transform_id, impl, spec)

    # 実装が存在する場合はシグネチャベースで検証
    if signature is not None:
        return _validate_params_with_signature(transform_id, impl, params, signature, spec)

    # 実装が存在しない場合、Transform定義から検証（可能な場合）
    if transform_def is not None:
        return _validate_params_with_spec(transform_id, params, transform_def, load_errors)

    # 実装もTransform定義もない場合はインポートエラーを返す
    return load_errors


def _validate_selection_mode(stage_id: str, selection_mode: str, num_selected: int) -> list[str]:
    """選択モードを検証

    Args:
        stage_id: ステージID
        selection_mode: 選択モード
        num_selected: 選択されたTransform数

    Returns:
        エラーメッセージリスト
    """
    errors: list[str] = []

    if selection_mode == "single":
        # singleモードは0または1つの選択を許可
        if num_selected > 1:
            errors.append(
                f"Stage '{stage_id}' is single mode but has multiple ({num_selected}) selections (max 1 allowed)"
            )
    elif selection_mode == "exclusive":
        # exclusiveモードは正確に1つ選択必須
        if num_selected != 1:
            errors.append(f"Stage '{stage_id}' requires exactly one selection, got {num_selected}")
    elif selection_mode == "multiple":
        # multipleモードは1つ以上必須
        if num_selected < 1:
            errors.append(f"Stage '{stage_id}' requires at least one selection, got {num_selected}")
    else:
        errors.append(f"Stage '{stage_id}': unsupported selection_mode '{selection_mode}'")

    return errors


def _merge_default_params(transform: TransformSpec, params: dict[str, Any]) -> dict[str, Any]:
    """Transform定義のデフォルトパラメータをマージ

    Args:
        transform: Transform定義
        params: ユーザー指定パラメータ

    Returns:
        マージされたパラメータ
    """
    merged_params = {}
    for param_def in transform.parameters:
        if param_def.default is not None and param_def.name not in params:
            merged_params[param_def.name] = param_def.default
    merged_params.update(params)
    return merged_params


def _get_and_validate_transform(
    transform_id: str,
    params: dict[str, Any],
    spec: SpecIR,
    check_implementations: bool,
) -> tuple[list[str], TransformSpec | None]:
    """Transform定義を取得して検証

    Args:
        transform_id: Transform ID
        params: パラメータ
        spec: SpecIR
        check_implementations: 実装チェック有効化

    Returns:
        (errors, transform): エラーとTransform定義（エラー時はNone）
    """
    errors: list[str] = []

    # Transform定義を取得
    transform = next((t for t in spec.transforms if t.id == transform_id), None)
    if not transform:
        errors.append(f"Transform '{transform_id}' not found in spec")
        return errors, None

    # パラメータ検証（実装チェック有効時のみ）
    if check_implementations:
        param_errors = _validate_transform_parameters(
            transform_id, transform.impl, params, spec, transform_def=transform
        )
        errors.extend(param_errors)

    return errors, transform


def _validate_selection(
    selection: TransformSelection,
    stage_exec_id: str,
    candidate_ids: set[str],
    spec: SpecIR,
    check_implementations: bool,
) -> tuple[list[str], dict[str, Any] | None]:
    """単一の選択を検証

    Args:
        selection: 選択設定
        stage_exec_id: ステージ実行ID
        candidate_ids: Transform候補IDセット
        spec: SpecIR
        check_implementations: 実装チェック有効化

    Returns:
        (errors, execution_entry): エラーと実行エントリ（エラー時はNone）
    """
    errors: list[str] = []
    transform_id = selection.transform_id

    # Transform候補に含まれているか
    if transform_id not in candidate_ids:
        errors.append(
            f"Stage '{stage_exec_id}': transform '{transform_id}' is not in candidates: {sorted(candidate_ids)}"
        )
        return errors, None

    # Transform定義を取得して検証
    validation_errors, transform = _get_and_validate_transform(
        transform_id, selection.params, spec, check_implementations
    )
    errors.extend(validation_errors)
    if not transform:
        return errors, None

    # デフォルトパラメータをマージ
    merged_params = _merge_default_params(transform, selection.params)

    # 実行計画エントリを作成
    execution_entry = {
        "stage_id": stage_exec_id,
        "transform_id": transform_id,
        "params": merged_params,
    }

    return errors, execution_entry


def _validate_stage_execution(
    stage_exec: StageExecution,
    spec: SpecIR,
    check_implementations: bool,
) -> tuple[list[str], list[dict[str, Any]]]:
    """ステージ実行設定を検証

    Args:
        stage_exec: ステージ実行設定
        spec: SpecIR
        check_implementations: 実装チェック有効化

    Returns:
        (errors, execution_entries): エラーと実行エントリ
    """
    errors: list[str] = []
    execution_entries: list[dict[str, Any]] = []

    # ステージの存在確認
    stage = next((s for s in spec.dag_stages if s.stage_id == stage_exec.stage_id), None)
    if not stage:
        return [f"Unknown stage_id: {stage_exec.stage_id}"], []

    # 選択モード検証
    errors.extend(_validate_selection_mode(stage.stage_id, stage.selection_mode, len(stage_exec.selected)))

    # Transform候補リスト作成
    candidate_ids = set(stage.candidates)

    # 各選択を検証
    for selection in stage_exec.selected:
        selection_errors, execution_entry = _validate_selection(
            selection, stage_exec.stage_id, candidate_ids, spec, check_implementations
        )
        errors.extend(selection_errors)
        if execution_entry:
            execution_entries.append(execution_entry)

    return errors, execution_entries


def _auto_select_single_stage(
    stage: DAGStageSpec,
    spec: SpecIR,
    check_implementations: bool,
) -> tuple[list[str], dict[str, Any] | None]:
    """単一ステージを自動選択

    Args:
        stage: DAGステージ
        spec: SpecIR
        check_implementations: 実装チェック有効化

    Returns:
        (errors, execution_entry): エラーと実行エントリ（エラー時はNone）
    """
    errors: list[str] = []

    # singleモードは候補が1つであるべき
    if len(stage.candidates) != 1:
        errors.append(
            f"Stage '{stage.stage_id}' is single mode but has {len(stage.candidates)} candidates (expected 1)"
        )
        return errors, None

    transform_id = stage.candidates[0]

    # Transform定義を取得して検証
    validation_errors, transform = _get_and_validate_transform(transform_id, {}, spec, check_implementations)
    errors.extend(validation_errors)
    if not transform:
        return errors, None

    # デフォルトパラメータを収集
    default_params = {}
    for param_def in transform.parameters:
        if param_def.default is not None:
            default_params[param_def.name] = param_def.default

    # 実行計画エントリを作成
    execution_entry = {
        "stage_id": stage.stage_id,
        "transform_id": transform_id,
        "params": default_params,
    }

    return errors, execution_entry


def _auto_select_single_stages(
    spec: SpecIR, check_implementations: bool, selected_stage_ids: set[str]
) -> tuple[list[str], list[dict[str, Any]]]:
    """singleモードのステージを自動選択（Configで未選択のもののみ）

    Args:
        spec: SpecIR
        check_implementations: 実装チェック有効化
        selected_stage_ids: 既にConfigで選択されたステージID

    Returns:
        (errors, execution_entries): エラーと実行エントリ
    """
    errors: list[str] = []
    execution_entries: list[dict[str, Any]] = []

    for stage in spec.dag_stages:
        # singleモード以外はスキップ
        if stage.selection_mode != "single":
            continue

        # Configで既に選択されている場合はスキップ
        if stage.stage_id in selected_stage_ids:
            continue

        # 自動選択を実行
        stage_errors, execution_entry = _auto_select_single_stage(stage, spec, check_implementations)
        errors.extend(stage_errors)
        if execution_entry:
            execution_entries.append(execution_entry)

    return errors, execution_entries


def validate_config(
    config: ConfigSpec,
    spec: SpecIR,
    check_implementations: bool = False,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Configを検証して実行計画を生成

    Args:
        config: Config
        spec: SpecIR
        check_implementations: 実装チェック有効化
        project_root: プロジェクトルートディレクトリ（オプション、implインポート用）

    Returns:
        {"valid": True, "execution_plan": [...]}

    Raises:
        ConfigValidationError: 検証エラー
    """
    # sys.pathにproject_rootを追加（apps.XXX形式のimportのため）
    if project_root is not None:
        project_root_str = str(project_root.resolve())
        if project_root_str not in sys.path:
            sys.path.insert(0, project_root_str)

    errors: list[str] = []
    execution_plan: list[dict[str, Any]] = []
    selected_stage_ids: set[str] = set()

    # Config内で明示的に選択されたステージを検証
    for stage_exec in config.execution.stages:
        selected_stage_ids.add(stage_exec.stage_id)
        stage_errors, stage_entries = _validate_stage_execution(stage_exec, spec, check_implementations)
        errors.extend(stage_errors)
        execution_plan.extend(stage_entries)

    # singleモードのステージを自動選択（未選択のもののみ）
    auto_errors, auto_entries = _auto_select_single_stages(spec, check_implementations, selected_stage_ids)
    errors.extend(auto_errors)
    execution_plan.extend(auto_entries)

    # エラーがあれば例外を発生
    if errors:
        raise ConfigValidationError("\n".join(errors))

    return {"valid": True, "execution_plan": execution_plan}

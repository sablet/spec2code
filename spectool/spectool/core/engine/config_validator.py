"""Config検証機能

Config YAMLがSpec定義に適合しているかを検証する。
"""

from __future__ import annotations

import importlib
import inspect
from typing import Any

from spectool.spectool.core.base.ir import SpecIR
from spectool.spectool.core.engine.config_model import ConfigSpec, StageExecution


class ConfigValidationError(Exception):
    """Config検証エラー"""

    pass


def _resolve_impl_path(impl: str, spec: "SpecIR") -> str:
    """implパスを解決（apps. プレフィックスをプロジェクト名を含む形に変換）

    Args:
        impl: 元のimplパス (例: "apps.transforms:func")
        spec: SpecIR（プロジェクト名取得用）

    Returns:
        解決されたimplパス (例: "apps.sample-project.transforms:func")
    """
    if not impl.startswith("apps."):
        return impl

    # プロジェクト名を取得（ハイフンをアンダースコアに変換）
    app_name = spec.meta.name if spec.meta else "app"
    app_name = app_name.replace("-", "_")  # Pythonモジュール名としてハイフンは無効

    # "apps." の後の部分を取得
    rest = impl[5:]  # "apps." を除去

    # "apps.<project-name>." + 残りの部分
    return f"apps.{app_name}.{rest}"


def _load_transform_signature(
    transform_id: str, impl: str, spec: "SpecIR"
) -> tuple[inspect.Signature | None, list[str]]:
    """Transform関数をインポートしてシグネチャを取得

    Args:
        transform_id: Transform ID
        impl: 実装パス (module:function形式)
        spec: SpecIR（implパス解決用）

    Returns:
        (signature, errors): シグネチャとエラーリスト
    """
    if not impl:
        return None, [f"Transform '{transform_id}': missing implementation"]

    # implパスを解決
    resolved_impl = _resolve_impl_path(impl, spec)

    try:
        module_path, func_name = resolved_impl.rsplit(":", 1)
    except ValueError as exc:
        return None, [f"Transform '{transform_id}': invalid impl '{impl}': {exc}"]

    try:
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
    except ImportError as exc:
        return None, [f"Transform '{transform_id}': import failed - {exc}"]
    except AttributeError as exc:
        return None, [f"Transform '{transform_id}': function not found - {exc}"]

    try:
        return inspect.signature(func), []
    except (TypeError, ValueError) as exc:
        return None, [f"Transform '{transform_id}': signature error - {exc}"]


def _check_function_implementation(func: Any, transform_id: str) -> list[str]:  # noqa: ANN401
    """関数が実装されているかをチェック（TODOのままではないか）

    Args:
        func: チェックする関数
        transform_id: Transform ID

    Returns:
        エラーメッセージリスト（実装されていれば空リスト）
    """
    try:
        source = inspect.getsource(func)
    except (OSError, TypeError):
        # ソースコードが取得できない場合（ビルトイン関数など）は実装されているとみなす
        return []

    # docstringとコメントからTODOパターンを検出
    if "TODO: Implement" in source or "# TODO: Implement" in source:
        return [f"Transform '{transform_id}': implementation incomplete (TODO markers found)"]

    # 関数本体が単純なプレースホルダーのみかチェック
    # 簡易的なチェック：return文が単純な値のみの場合
    lines = source.split("\n")
    code_lines = []
    for line in lines:
        stripped = line.strip()
        # docstring、コメント、空行、関数定義行を除外
        if (
            stripped
            and not stripped.startswith("#")
            and not stripped.startswith('"""')
            and not stripped.startswith("'''")
            and not stripped.startswith("def ")
        ):
            code_lines.append(stripped)

    # docstringを除外（複数行）
    filtered_lines = []
    in_docstring = False
    for line in code_lines:
        if '"""' in line or "'''" in line:
            if in_docstring:
                in_docstring = False
                continue
            else:
                in_docstring = True
                continue
        if not in_docstring:
            filtered_lines.append(line)

    # 実質的なコード行が1行以下（returnのみなど）の場合は未実装とみなす
    if len(filtered_lines) <= 1:
        # ただし、単純なreturn文のみの場合はチェック
        if filtered_lines and any(
            keyword in filtered_lines[0]
            for keyword in ["return True", "return pd.DataFrame()", "return None", "return {}"]
        ):
            return [f"Transform '{transform_id}': implementation incomplete (placeholder return value only)"]

    return []


def _expected_basic_type(annotation: object) -> type | None:
    """型アノテーションから基本型を抽出

    Args:
        annotation: 型アノテーション

    Returns:
        基本型 (int, float, str, bool) またはNone
    """
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
        return annotation  # type: ignore

    as_str = str(annotation)
    if as_str.startswith("<class '") and as_str.endswith("'>"):
        return basic_types.get(as_str[8:-2])

    return basic_types.get(as_str)


def _validate_parameter_type(
    transform_id: str,
    param_name: str,
    param_value: Any,  # noqa: ANN401
    param_spec: inspect.Parameter,
) -> list[str]:
    """パラメータ型を検証

    Args:
        transform_id: Transform ID
        param_name: パラメータ名
        param_value: パラメータ値
        param_spec: パラメータ仕様

    Returns:
        エラーメッセージリスト
    """
    if param_spec.annotation == inspect.Parameter.empty:
        return []

    expected_type = _expected_basic_type(param_spec.annotation)
    if expected_type and not isinstance(param_value, expected_type):
        return [
            f"Transform '{transform_id}': parameter '{param_name}' expected type "
            f"{expected_type.__name__}, got {type(param_value).__name__}"
        ]

    return []


def _validate_param_type_from_spec(
    transform_id: str,
    param_name: str,
    param_value: Any,  # noqa: ANN401
    param_def: Any,  # noqa: ANN401
) -> list[str]:
    """Spec定義からパラメータ型を検証

    Args:
        transform_id: Transform ID
        param_name: パラメータ名
        param_value: パラメータ値
        param_def: パラメータ定義

    Returns:
        エラーメッセージリスト
    """
    # nativeフィールドから型を取得
    native_type = getattr(param_def, "type_ref", None)
    if not native_type:
        return []

    # "builtins:type"形式から型名を抽出
    type_name = native_type.split(":")[-1] if ":" in native_type else native_type

    # 基本型のマッピング
    type_mapping = {
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
    }

    expected_type = type_mapping.get(type_name)
    if expected_type and not isinstance(param_value, expected_type):
        return [
            f"Transform '{transform_id}': parameter '{param_name}' expected type "
            f"{expected_type.__name__}, got {type(param_value).__name__}"
        ]

    return []


def _validate_transform_parameters(
    transform_id: str,
    impl: str,
    params: dict[str, Any],
    spec: "SpecIR",
    transform_def: Any | None = None,  # noqa: ANN401
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
    signature, load_errors = _load_transform_signature(transform_id, impl, spec)

    # 実装が存在する場合はシグネチャベースで検証
    if signature is not None:
        errors = []

        # 実装の完全性をチェック（TODOのままではないか）
        # 関数を再度インポートして実装をチェック
        resolved_impl = _resolve_impl_path(impl, spec)
        try:
            module_path, func_name = resolved_impl.rsplit(":", 1)
            module = importlib.import_module(module_path)
            func = getattr(module, func_name)
            errors.extend(_check_function_implementation(func, transform_id))
        except (ImportError, AttributeError, ValueError):
            # インポートエラーは既に_load_transform_signatureで報告されているのでスキップ
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
            errors.extend(_validate_parameter_type(transform_id, param_name, param_value, param_spec))

        return errors

    # 実装が存在しない場合、Transform定義から検証（可能な場合）
    if transform_def is not None:
        errors = []
        for param_name, param_value in params.items():
            # パラメータ定義を検索
            param_def = next((p for p in transform_def.parameters if p.name == param_name), None)
            if not param_def:
                errors.append(f"Transform '{transform_id}': unknown parameter '{param_name}'")
                continue
            # Spec定義から型を検証
            errors.extend(_validate_param_type_from_spec(transform_id, param_name, param_value, param_def))
        # パラメータ型エラーがあればそれを返す、なければインポートエラーを返す
        return errors if errors else load_errors

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
        transform_id = selection.transform_id

        # Transform候補に含まれているか
        if transform_id not in candidate_ids:
            errors.append(
                f"Stage '{stage_exec.stage_id}': transform '{transform_id}' "
                f"is not in candidates: {sorted(candidate_ids)}"
            )
            continue

        # Transform定義を取得
        transform = next((t for t in spec.transforms if t.id == transform_id), None)
        if not transform:
            errors.append(f"Transform '{transform_id}' not found in spec")
            continue

        # パラメータ検証（実装チェック有効時のみ）
        if check_implementations:
            param_errors = _validate_transform_parameters(
                transform_id, transform.impl, selection.params, spec, transform_def=transform
            )
            errors.extend(param_errors)

        # デフォルトパラメータをマージ
        merged_params = {}
        for param_def in transform.parameters:
            if param_def.default is not None and param_def.name not in selection.params:
                merged_params[param_def.name] = param_def.default
        merged_params.update(selection.params)

        # 実行計画エントリを追加
        execution_entries.append(
            {
                "stage_id": stage_exec.stage_id,
                "transform_id": transform_id,
                "params": merged_params,
            }
        )

    return errors, execution_entries


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
        if stage.selection_mode != "single":
            continue

        # Configで既に選択されている場合はスキップ
        if stage.stage_id in selected_stage_ids:
            continue

        # singleモードは候補が1つであるべき
        if len(stage.candidates) != 1:
            errors.append(
                f"Stage '{stage.stage_id}' is single mode but has {len(stage.candidates)} candidates (expected 1)"
            )
            continue

        transform_id = stage.candidates[0]

        # Transform定義を取得
        transform = next((t for t in spec.transforms if t.id == transform_id), None)
        if not transform:
            errors.append(f"Transform '{transform_id}' not found in spec")
            continue

        # パラメータ検証（実装チェック有効時のみ）
        if check_implementations:
            param_errors = _validate_transform_parameters(
                transform_id, transform.impl, {}, spec, transform_def=transform
            )
            errors.extend(param_errors)

        # デフォルトパラメータを収集
        default_params = {}
        for param_def in transform.parameters:
            if param_def.default is not None:
                default_params[param_def.name] = param_def.default

        # 実行計画エントリを追加（デフォルトパラメータ使用）
        execution_entries.append(
            {
                "stage_id": stage.stage_id,
                "transform_id": transform_id,
                "params": default_params,
            }
        )

    return errors, execution_entries


def validate_config(
    config: ConfigSpec,
    spec: SpecIR,
    check_implementations: bool = False,
    project_root: "Path | None" = None,
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
    import sys

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

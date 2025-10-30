"""Config駆動DAG実行エンジン

ConfigとSpecに基づいてDAGを実行する。
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any, Callable

from spectool.core.base.ir import SpecIR
from spectool.core.engine.config_model import load_config
from spectool.core.engine.config_validator import validate_config
from spectool.core.engine.loader import load_spec


class ConfigRunner:
    """Config駆動DAG実行クラス

    ConfigとSpecを読み込み、検証してDAG実行を行う。
    """

    def __init__(self, config_path: str | Path) -> None:
        """ConfigRunnerの初期化

        Args:
            config_path: Config YAMLのパス
        """
        self.config_path = Path(config_path)
        self.config = load_config(str(self.config_path))

        # base_specのパスを解決（相対パスの場合はconfigからの相対パス）
        base_spec_path = Path(self.config.meta.base_spec)
        if not base_spec_path.is_absolute():
            base_spec_path = self.config_path.parent / base_spec_path

        self.spec: SpecIR = load_spec(base_spec_path)

    def validate(self, check_implementations: bool = False) -> dict[str, Any]:
        """Configを検証

        Args:
            check_implementations: 実装チェック有効化（デフォルトFalse）

        Returns:
            {"valid": True, "execution_plan": [...]}

        Raises:
            ConfigValidationError: 検証エラー
        """
        return validate_config(self.config, self.spec, check_implementations)

    def run(self, initial_data: dict) -> dict:
        """DAGを実行

        Args:
            initial_data: 初期データ

        Returns:
            実行結果

        Raises:
            Exception: 実行エラー
        """
        # Configを検証
        validation_result = self.validate(check_implementations=True)
        execution_plan = validation_result["execution_plan"]

        # 実行
        current_data = initial_data

        for step in execution_plan:
            current_data = self._execute_step(step, current_data)

        return current_data

    def _execute_step(self, step: dict[str, Any], current_data: dict) -> dict:
        """実行ステップを実行

        Args:
            step: 実行ステップ
            current_data: 現在のデータ

        Returns:
            実行結果
        """
        transform_id = step["transform_id"]
        params = step["params"]

        # Transform定義を取得
        transform = next((t for t in self.spec.transforms if t.id == transform_id), None)
        if not transform:
            raise Exception(f"Transform '{transform_id}' not found")

        # Transform関数をインポート
        func, signature = self._import_transform_callable(transform.impl)

        # 引数を構築
        func_args = self._build_function_args(signature, current_data, params, transform)

        # 実行
        try:
            result = func(**func_args)
        except Exception as exc:
            raise Exception(f"Error executing transform '{transform_id}': {exc}") from exc

        return result

    @staticmethod
    def _import_transform_callable(impl: str) -> tuple[Callable[..., Any], inspect.Signature]:
        """Transform関数をインポート

        Args:
            impl: 実装パス (module:function形式)

        Returns:
            (function, signature)

        Raises:
            ImportError: インポートエラー
        """
        module_path, func_name = impl.rsplit(":", 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        return func, inspect.signature(func)

    @staticmethod
    def _build_function_args(
        signature: inspect.Signature,
        current_data: dict,
        params: dict[str, Any],
        transform: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """関数引数を構築

        Args:
            signature: 関数シグネチャ
            current_data: 現在のデータ
            params: Configで指定されたパラメータ
            transform: Transform定義

        Returns:
            関数引数
        """
        param_names = list(signature.parameters.keys())
        func_args: dict[str, Any] = {}

        if not param_names:
            return func_args

        # 最初のパラメータにcurrent_dataを渡す
        func_args[param_names[0]] = current_data

        # その他のパラメータを構築
        for param_name in param_names[1:]:
            # 優先順位: Configパラメータ > Transform定義デフォルト値 > シグネチャデフォルト値
            if param_name in params:
                func_args[param_name] = params[param_name]
            else:
                # Transform定義からデフォルト値を取得
                param_def = next((p for p in transform.parameters if p.name == param_name), None)
                if param_def and param_def.default is not None:
                    func_args[param_name] = param_def.default
                elif signature.parameters[param_name].default != inspect.Parameter.empty:
                    # シグネチャのデフォルト値を使用（引数に含めない）
                    pass
                # 必須パラメータで値が指定されていない場合はエラーになる（validate時にチェック済み）

        return func_args

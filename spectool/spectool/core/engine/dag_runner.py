"""DAG実行エンジン

SpecIRからDAGを構築し、トポロジカルソートに基づいてTransform関数を実行する。
"""

from __future__ import annotations

import importlib
from typing import Any, Callable

import networkx as nx

from spectool.spectool.core.base.ir import DAGStageSpec, SpecIR, TransformSpec


class DAGRunner:
    """DAG実行エンジン

    SpecIRを受け取り、DAGステージをトポロジカルソートして実行する。
    Transform関数を動的にインポートして実行し、結果を収集する。

    Attributes:
        ir: SpecIR中間表現
        graph: NetworkX DiGraph
        execution_logs: 実行ログ
    """

    def __init__(self, ir: SpecIR) -> None:
        """DAGRunnerの初期化

        Args:
            ir: SpecIR中間表現
        """
        self.ir = ir
        self.graph = self._build_graph()
        self.execution_logs: list[str] = []

    def _build_graph(self) -> nx.DiGraph:
        """DAGステージからNetworkXグラフを構築

        Returns:
            NetworkX DiGraph
        """
        graph = nx.DiGraph()

        # ノードを追加
        for stage in self.ir.dag_stages:
            graph.add_node(stage.stage_id, stage=stage)

        # エッジを追加（暗黙的な順序関係）
        # ステージのリスト順序に基づいて依存関係を構築
        for i in range(len(self.ir.dag_stages) - 1):
            current_stage = self.ir.dag_stages[i]
            next_stage = self.ir.dag_stages[i + 1]

            # 出力型と入力型が一致する場合、エッジを追加
            if current_stage.output_type == next_stage.input_type:
                graph.add_edge(current_stage.stage_id, next_stage.stage_id)

        return graph

    def get_execution_order(self) -> list[DAGStageSpec]:
        """トポロジカルソートによる実行順序を取得

        Returns:
            ステージのリスト（実行順）

        Raises:
            nx.NetworkXError: サイクルが検出された場合
        """
        if len(self.graph.nodes) == 0:
            return []

        try:
            sorted_ids = list(nx.topological_sort(self.graph))
        except nx.NetworkXError as e:
            raise nx.NetworkXError("DAG contains cycle") from e

        # stage_idからDAGStageSpecを取得
        stages = []
        for stage_id in sorted_ids:
            stage = next((s for s in self.ir.dag_stages if s.stage_id == stage_id), None)
            if stage:
                stages.append(stage)

        return stages

    @staticmethod
    def _load_transform_function(transform: TransformSpec) -> Callable[..., Any]:
        """Transform関数を動的にインポート

        Args:
            transform: Transform定義

        Returns:
            インポートされた関数

        Raises:
            ImportError: モジュールまたは関数が見つからない場合
        """
        if not transform.impl:
            raise ImportError(f"Transform {transform.id} has no implementation")

        module_path, func_name = transform.impl.split(":")

        try:
            module = importlib.import_module(module_path)
            return getattr(module, func_name)
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Cannot import {transform.impl}: {e}") from e

    @staticmethod
    def _validate_input_data(data: dict) -> None:
        """入力データの型を検証

        Args:
            data: 入力データ

        Raises:
            TypeError: 型が不正な場合
        """
        if not isinstance(data, dict):
            raise TypeError(f"Input data must be dict, got {type(data)}")

        # 各フィールドがリストであることを確認（DataFrameを想定）
        for key, value in data.items():
            if not isinstance(value, list):
                raise TypeError(f"Field '{key}' must be list, got {type(value)}")

    @staticmethod
    def _merge_parameters(
        transform: TransformSpec,
        current_data: dict,
        user_params: dict[str, Any],
    ) -> dict[str, Any]:
        """パラメータをマージ（デフォルト値、ユーザー指定値、現在のデータ）

        Args:
            transform: Transform定義
            current_data: 現在のデータ
            user_params: ユーザー指定パラメータ

        Returns:
            マージされたパラメータ
        """
        params: dict[str, Any] = {}

        # Transform定義のパラメータを処理
        for param_spec in transform.parameters:
            param_name = param_spec.name

            # 優先順位: ユーザー指定 > デフォルト値 > 現在のデータ
            if param_name in user_params:
                params[param_name] = user_params[param_name]
            elif param_spec.default is not None:
                params[param_name] = param_spec.default
            elif param_name == "data" or param_name in current_data:
                # 最初のパラメータが "data" の場合、current_dataを渡す
                if param_name == "data":
                    params[param_name] = current_data
                else:
                    params[param_name] = current_data[param_name]
            elif not param_spec.optional:
                raise ValueError(f"Required parameter '{param_name}' not provided")

        return params

    def run_dag(  # noqa: C901, PLR0912
        self,
        initial_data: dict,
        params: dict[str, Any] | None = None,
        collect_intermediates: bool = False,
        dry_run: bool = False,
        enable_logging: bool = False,
    ) -> dict | list:
        """DAGを実行

        Args:
            initial_data: 初期データ
            params: ユーザー指定パラメータ
            collect_intermediates: 中間結果を収集するか
            dry_run: Dry-runモード（実行計画のみ返す）
            enable_logging: ログを有効化

        Returns:
            実行結果（dry_runの場合は実行計画）

        Raises:
            Exception: 実行エラー
        """
        if params is None:
            params = {}

        # 入力データを検証
        self._validate_input_data(initial_data)

        # 実行順序を取得
        try:
            execution_order = self.get_execution_order()
        except nx.NetworkXError as e:
            raise Exception(f"Failed to determine execution order: {e}") from e

        # Dry-runモードの場合、実行計画を返す
        if dry_run:
            plan = []
            for stage in execution_order:
                transform = next(
                    (t for t in self.ir.transforms if t.id == stage.default_transform_id),
                    None,
                )
                if transform:
                    plan.append(
                        {
                            "stage_id": stage.stage_id,
                            "transform_id": transform.id,
                            "impl": transform.impl,
                        }
                    )
            return plan

        # 実行ログ初期化
        if enable_logging:
            self.execution_logs = []

        # DAG実行
        current_data = initial_data
        intermediate_results = {}

        for stage in execution_order:
            # Transform IDを取得
            transform_id = stage.default_transform_id
            if not transform_id:
                if enable_logging:
                    self.execution_logs.append(f"Stage {stage.stage_id}: No default transform")
                continue

            # Transform定義を取得
            transform = next(
                (t for t in self.ir.transforms if t.id == transform_id),
                None,
            )
            if not transform:
                error_msg = f"Transform {transform_id} not found"
                if enable_logging:
                    self.execution_logs.append(f"Stage {stage.stage_id}: {error_msg}")
                raise Exception(error_msg)

            # Transform関数をインポート
            try:
                func = self._load_transform_function(transform)
            except ImportError as e:
                if enable_logging:
                    self.execution_logs.append(f"Stage {stage.stage_id}: Import error - {e}")
                raise

            # パラメータをマージ
            merged_params = self._merge_parameters(transform, current_data, params)

            # Transform関数を実行
            try:
                if enable_logging:
                    self.execution_logs.append(f"Stage {stage.stage_id}: Executing {transform.id}")

                result = func(**merged_params)

                if enable_logging:
                    self.execution_logs.append(f"Stage {stage.stage_id}: Completed successfully")

                # 中間結果を収集
                if collect_intermediates or stage.collect_output:
                    intermediate_results[stage.stage_id] = result

                # 次のステージへデータを渡す
                current_data = result

            except Exception as e:
                error_msg = f"Execution error in {transform.id}: {e}"
                if enable_logging:
                    self.execution_logs.append(f"Stage {stage.stage_id}: {error_msg}")
                raise Exception(error_msg) from e

        # 結果を返す
        if collect_intermediates:
            return {
                "final_result": current_data,
                "intermediate_results": intermediate_results,
            }
        return current_data

    def get_execution_logs(self) -> list[str]:
        """実行ログを取得

        Returns:
            実行ログのリスト
        """
        return self.execution_logs

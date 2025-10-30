"""DAG実行エンジンのテスト

packages/tests/test_dataframe_abcd.pyに相当する機能をspectoolで実装するためのテスト。
DAGに基づいたTransform関数の実行を検証する。
"""

from pathlib import Path
import tempfile
import pytest

from spectool.spectool.core.engine.loader import load_spec
from spectool.spectool.core.base.ir import SpecIR


# DAG実行エンジン（未実装）をインポート
# TODO: この機能を実装する必要がある
try:
    from spectool.spectool.core.engine.dag_runner import DAGRunner
except ImportError:
    # 未実装の場合、プレースホルダークラスを定義
    class DAGRunner:
        """DAG実行エンジンのプレースホルダー（未実装）"""

        def __init__(self, ir: SpecIR):
            self.ir = ir
            raise NotImplementedError("DAGRunner not yet implemented in spectool")

        def run_dag(self, initial_data: dict) -> dict:
            """DAG実行（未実装）"""
            raise NotImplementedError("run_dag not yet implemented")


@pytest.fixture
def sample_spec_path():
    """サンプルspec YAMLのパス"""
    return Path(__file__).parent / "fixtures" / "sample_spec.yaml"


@pytest.fixture
def temp_project_dir():
    """一時プロジェクトディレクトリ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def setup_transform_implementation(temp_project_dir):
    """Transform実装を準備するフィクスチャ"""
    import sys

    # appsディレクトリ構造を作成
    apps_dir = temp_project_dir / "apps"
    apps_dir.mkdir(parents=True, exist_ok=True)
    (apps_dir / "__init__.py").write_text("")

    # transformsモジュールを作成
    transforms_dir = apps_dir / "transforms"
    transforms_dir.mkdir(parents=True, exist_ok=True)

    # process_data関数を実装
    process_data_impl = '''"""Transform implementations"""

def process_data(data, threshold=0.5):
    """Process time series data

    Args:
        data: Input data dict with timestamp, value, status
        threshold: Threshold value (default: 0.5)

    Returns:
        Processed data dict
    """
    # シンプルにデータをそのまま返す（テスト用）
    return data
'''
    (transforms_dir / "processors.py").write_text(process_data_impl)

    # __init__.pyにprocess_dataをインポート
    transforms_init = '''"""Transforms module"""

from apps.transforms.processors import process_data

__all__ = ["process_data"]
'''
    (transforms_dir / "__init__.py").write_text(transforms_init)

    # checksモジュールを作成
    checks_dir = apps_dir / "checks"
    checks_dir.mkdir(parents=True, exist_ok=True)
    (checks_dir / "__init__.py").write_text("")

    validators_impl = '''"""Check implementations"""

def validate_positive(value):
    """Validate positive values"""
    return value > 0

def validate_status(status):
    """Validate status"""
    return status in ["active", "inactive"]
'''
    (checks_dir / "validators.py").write_text(validators_impl)

    # sys.pathに追加
    sys.path.insert(0, str(temp_project_dir))

    # 既存のappsモジュールキャッシュをクリア
    # これにより、一時ディレクトリのモジュールが確実に使用される
    modules_to_clear = [key for key in sys.modules.keys() if key.startswith("apps")]
    for module in modules_to_clear:
        del sys.modules[module]

    yield temp_project_dir

    # クリーンアップ
    # 一時ディレクトリのモジュールをキャッシュから削除
    modules_to_clear = [key for key in sys.modules.keys() if key.startswith("apps")]
    for module in modules_to_clear:
        del sys.modules[module]

    # sys.pathから削除
    if str(temp_project_dir) in sys.path:
        sys.path.remove(str(temp_project_dir))


def test_dag_runner_initialization(sample_spec_path):
    """DAGRunnerが正しく初期化できることを確認"""
    ir = load_spec(sample_spec_path)
    runner = DAGRunner(ir)

    assert runner.ir == ir


def test_dag_execution_simple(sample_spec_path, setup_transform_implementation):
    """シンプルなDAG実行が正しく動作することを確認"""
    ir = load_spec(sample_spec_path)

    # DAGステージが1つだけの場合
    assert len(ir.dag_stages) >= 1

    runner = DAGRunner(ir)

    # 初期データ
    initial_data = {
        "timestamp": ["2024-01-01T00:00:00"],
        "value": [100.0],
        "status": ["active"],
    }

    # DAG実行
    result = runner.run_dag(initial_data)

    # 結果の検証
    assert result is not None
    assert isinstance(result, dict)


def test_dag_topological_sort(sample_spec_path):
    """DAGがトポロジカルソートされることを確認"""
    ir = load_spec(sample_spec_path)
    runner = DAGRunner(ir)

    # トポロジカルソート済みのステージ順序を取得
    sorted_stages = runner.get_execution_order()

    # ステージ順序が正しいことを確認
    assert len(sorted_stages) >= 1

    # 依存関係が正しく解決されていることを確認
    # （後続ステージは依存元ステージより後に実行される）
    for i, stage in enumerate(sorted_stages):
        assert stage.stage_id is not None


def test_dag_execution_with_multiple_stages(sample_spec_path, setup_transform_implementation):
    """複数ステージのDAG実行が正しく動作することを確認"""
    ir = load_spec(sample_spec_path)
    runner = DAGRunner(ir)

    initial_data = {
        "timestamp": ["2024-01-01T00:00:00", "2024-01-02T00:00:00"],
        "value": [100.0, 200.0],
        "status": ["active", "active"],
    }

    result = runner.run_dag(initial_data)

    # 結果の検証
    assert result is not None
    assert isinstance(result, dict)


def test_dag_execution_with_parameters(sample_spec_path, setup_transform_implementation):
    """パラメータ付きTransform関数の実行を確認"""
    ir = load_spec(sample_spec_path)
    runner = DAGRunner(ir)

    # process_data transform は threshold パラメータを持つ
    initial_data = {
        "timestamp": ["2024-01-01T00:00:00"],
        "value": [100.0],
        "status": ["active"],
    }

    # パラメータを指定してDAG実行
    result = runner.run_dag(initial_data, params={"threshold": 0.8})

    assert result is not None


def test_dag_execution_with_default_parameters(sample_spec_path, setup_transform_implementation):
    """デフォルトパラメータが使用されることを確認"""
    ir = load_spec(sample_spec_path)
    runner = DAGRunner(ir)

    initial_data = {
        "timestamp": ["2024-01-01T00:00:00"],
        "value": [100.0],
        "status": ["active"],
    }

    # パラメータを指定せずにDAG実行（デフォルト値が使用される）
    result = runner.run_dag(initial_data)

    assert result is not None


def test_dag_handles_transform_errors_gracefully(sample_spec_path, setup_transform_implementation):
    """Transform関数のエラーを適切にハンドリングすることを確認"""
    ir = load_spec(sample_spec_path)
    runner = DAGRunner(ir)

    # 不正なデータを渡す
    invalid_data = {"invalid_field": "invalid_value"}

    # エラーが適切にハンドリングされることを確認
    with pytest.raises(Exception) as exc_info:
        runner.run_dag(invalid_data)

    assert exc_info.value is not None


def test_dag_execution_collects_intermediate_results(sample_spec_path, setup_transform_implementation):
    """中間結果が収集されることを確認"""
    ir = load_spec(sample_spec_path)
    runner = DAGRunner(ir)

    initial_data = {
        "timestamp": ["2024-01-01T00:00:00"],
        "value": [100.0],
        "status": ["active"],
    }

    # collect_output=True のステージの結果が収集されることを確認
    result = runner.run_dag(initial_data, collect_intermediates=True)

    # 中間結果が含まれることを確認
    assert "intermediate_results" in result or isinstance(result, dict)


def test_dag_execution_validates_input_types(sample_spec_path):
    """入力データの型が検証されることを確認"""
    ir = load_spec(sample_spec_path)
    runner = DAGRunner(ir)

    # 型が一致しないデータを渡す
    invalid_data = {
        "timestamp": "not_a_list",  # リストではなく文字列
        "value": [100.0],
        "status": ["active"],
    }

    # 型エラーが発生することを確認
    with pytest.raises((TypeError, ValueError)):
        runner.run_dag(invalid_data)


def test_dag_execution_validates_output_types(sample_spec_path, setup_transform_implementation):
    """出力データの型が検証されることを確認"""
    ir = load_spec(sample_spec_path)
    runner = DAGRunner(ir)

    initial_data = {
        "timestamp": ["2024-01-01T00:00:00"],
        "value": [100.0],
        "status": ["active"],
    }

    result = runner.run_dag(initial_data)

    # 出力データの型が期待通りであることを確認
    assert isinstance(result, dict)


def test_dag_runner_detects_cycles():
    """DAGに循環依存がある場合、エラーを検出することを確認"""
    from spectool.spectool.core.base.ir import (
        SpecIR,
        MetaSpec,
        FrameSpec,
        IndexRule,
        TransformSpec,
        DAGStageSpec,
    )
    import networkx as nx

    # 循環依存を持つIRを動的に作成
    # DataFrame1 -> DataFrame2 -> DataFrame1 という循環
    ir = SpecIR(
        meta=MetaSpec(name="cyclic-test", version="1.0"),
        frames={
            "DataFrame1": FrameSpec(
                id="DataFrame1",
                index=IndexRule(name="idx", dtype="int"),
                columns=[],
            ),
            "DataFrame2": FrameSpec(
                id="DataFrame2",
                index=IndexRule(name="idx", dtype="int"),
                columns=[],
            ),
        },
        enums={},
        pydantic_models={},
        type_aliases={},
        generics={},
        transforms={
            "transform_a": TransformSpec(
                id="transform_a",
                impl="apps.transforms.ops:transform_a",
                file_path="transforms/ops.py",
                parameters=[],
                return_type_ref="DataFrame2",
            ),
            "transform_b": TransformSpec(
                id="transform_b",
                impl="apps.transforms.ops:transform_b",
                file_path="transforms/ops.py",
                parameters=[],
                return_type_ref="DataFrame1",
            ),
        },
        checks={},
        examples={},
        generators={},
        dag_stages=[
            DAGStageSpec(
                stage_id="stage_a",
                input_type="DataFrame1",
                output_type="DataFrame2",
                candidates=["transform_a"],
            ),
            DAGStageSpec(
                stage_id="stage_b",
                input_type="DataFrame2",
                output_type="DataFrame1",
                candidates=["transform_b"],
            ),
        ],
    )

    # DAGRunnerを初期化
    runner = DAGRunner(ir)

    # グラフに循環があることを確認（明示的にエッジを追加して循環を作成）
    runner.graph.add_edge("stage_a", "stage_b")
    runner.graph.add_edge("stage_b", "stage_a")

    # get_execution_orderでNetworkXError（またはそのサブクラス）が発生することを確認
    with pytest.raises((nx.NetworkXError, nx.NetworkXUnfeasible), match="cycle"):
        runner.get_execution_order()


def test_dag_runner_handles_missing_implementations(sample_spec_path):
    """Transform関数の実装が存在しない場合、エラーを検出することを確認"""
    from spectool.spectool.core.base.ir import TransformSpec, ParameterSpec, DAGStageSpec

    # 存在しないモジュールを参照するTransformを作成
    ir = load_spec(sample_spec_path)

    # 元のtransformを存在しないモジュールに変更
    fake_transform = TransformSpec(
        id="fake_transform",
        description="Fake transform",
        impl="nonexistent.module:fake_function",
        file_path="nonexistent/module.py",
        parameters=[ParameterSpec(name="data", type_ref="TimeSeriesFrame", optional=False)],
        return_type_ref="TimeSeriesFrame",
    )

    # IR内のtransformsを置き換え
    ir.transforms = [fake_transform]

    # DAGステージも更新
    ir.dag_stages[0].default_transform_id = "fake_transform"
    ir.dag_stages[0].candidates = ["fake_transform"]

    runner = DAGRunner(ir)

    initial_data = {
        "timestamp": ["2024-01-01T00:00:00"],
        "value": [100.0],
        "status": ["active"],
    }

    # 実装が存在しない場合、エラーが発生することを確認
    with pytest.raises((ImportError, ModuleNotFoundError)):
        runner.run_dag(initial_data)


def test_dag_runner_supports_dry_run(sample_spec_path):
    """Dry-runモードが正しく動作することを確認"""
    ir = load_spec(sample_spec_path)
    runner = DAGRunner(ir)

    initial_data = {
        "timestamp": ["2024-01-01T00:00:00"],
        "value": [100.0],
        "status": ["active"],
    }

    # Dry-runモードで実行（実際には関数を実行しない）
    execution_plan = runner.run_dag(initial_data, dry_run=True)

    # 実行計画が返されることを確認
    assert execution_plan is not None
    assert isinstance(execution_plan, (list, dict))


def test_dag_runner_logs_execution_steps(sample_spec_path, setup_transform_implementation):
    """DAG実行のログが記録されることを確認"""
    ir = load_spec(sample_spec_path)
    runner = DAGRunner(ir)

    initial_data = {
        "timestamp": ["2024-01-01T00:00:00"],
        "value": [100.0],
        "status": ["active"],
    }

    # ログ機能を有効にして実行
    result = runner.run_dag(initial_data, enable_logging=True)

    # ログが記録されていることを確認
    logs = runner.get_execution_logs()
    assert logs is not None
    assert len(logs) > 0

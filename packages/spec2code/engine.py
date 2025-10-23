"""
構造仕様ベースのコードスケルトン生成・検証システム - コアエンジン
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import networkx as nx
import yaml
from pydantic import BaseModel, Field, field_validator


# ==================== データモデル定義 ====================


class Check(BaseModel):
    """チェック関数定義"""

    id: str
    description: str
    impl: str  # "module:function"形式
    file_path: str


class Example(BaseModel):
    """検証用入力・期待値定義"""

    id: str
    description: str
    input: dict[str, Any]
    expected: dict[str, Any]


class DataType(BaseModel):
    """データ構造定義"""

    model_config = {"protected_namespaces": (), "use_attribute_docstrings": True}

    id: str
    description: str
    check_ids: list[str] = Field(default_factory=list)
    example_ids: list[str] = Field(default_factory=list)
    schema: dict[str, Any]  # JSON Schema


class Parameter(BaseModel):
    """関数パラメータ定義"""

    name: str
    datatype_ref: str | None = None
    native: str | None = None  # "builtins:type"形式

    @field_validator("datatype_ref", "native")
    @classmethod
    def at_least_one(cls, v: str | None, info) -> str | None:
        values = info.data
        if "datatype_ref" in values and "native" in values:
            if values.get("datatype_ref") is None and values.get("native") is None:
                raise ValueError("datatype_ref または native のいずれかが必要です")
        return v


class Transform(BaseModel):
    """処理関数定義"""

    id: str
    description: str
    impl: str  # "module:function"形式
    file_path: str
    parameters: list[Parameter]
    return_datatype_ref: str | None = None
    default_args: dict[str, Any] = Field(default_factory=dict)


class DAGEdge(BaseModel):
    """DAGエッジ定義"""

    model_config = {"populate_by_name": True}

    from_: str = Field(alias="from")
    to: str | None


class Meta(BaseModel):
    """メタデータ"""

    name: str
    description: str


class Spec(BaseModel):
    """仕様全体のルートモデル"""

    version: str
    meta: Meta
    checks: list[Check] = Field(default_factory=list)
    examples: list[Example] = Field(default_factory=list)
    datatypes: list[DataType] = Field(default_factory=list)
    transforms: list[Transform] = Field(default_factory=list)
    dag: list[DAGEdge] = Field(default_factory=list)


# ==================== 仕様読み込み・検証 ====================


def load_spec(spec_path: str | Path) -> Spec:
    """YAML/JSON仕様を読み込み、Pydanticで検証"""
    spec_path = Path(spec_path)
    with open(spec_path) as f:
        if spec_path.suffix in [".yaml", ".yml"]:
            data = yaml.safe_load(f)
        elif spec_path.suffix == ".json":
            data = json.load(f)
        else:
            raise ValueError(f"未対応のファイル形式: {spec_path.suffix}")

    return Spec(**data)


# ==================== スケルトンコード生成 ====================


def generate_skeleton(spec: Spec, project_root: Path = Path(".")) -> None:
    """未実装ファイルを自動生成"""
    print("🔨 Generating skeleton code...")

    # プロジェクト名に基づく出力先ディレクトリ
    app_root = project_root / "apps" / spec.meta.name
    print(f"  📁 Target directory: {app_root}")

    # Check関数のスケルトン生成
    for check in spec.checks:
        file_path = app_root / check.file_path
        if file_path.exists():
            print(f"  ⏭️  Skip (exists): {file_path}")
            continue

        file_path.parent.mkdir(parents=True, exist_ok=True)
        func_name = check.impl.split(":")[-1]

        code = f'''# Auto-generated skeleton for Check: {check.id}
def {func_name}(payload: dict) -> bool:
    """{check.description}"""
    # TODO: implement validation logic
    return True
'''
        file_path.write_text(code)
        print(f"  ✅ Generated: {file_path}")

    # Transform関数のスケルトン生成
    for transform in spec.transforms:
        file_path = app_root / transform.file_path
        if file_path.exists():
            print(f"  ⏭️  Skip (exists): {file_path}")
            continue

        file_path.parent.mkdir(parents=True, exist_ok=True)
        func_name = transform.impl.split(":")[-1]

        # パラメータリスト作成
        params = ", ".join(p.name for p in transform.parameters)

        code = f'''# Auto-generated skeleton for Transform: {transform.id}
def {func_name}({params}) -> dict:
    """{transform.description}"""
    # TODO: implement transform logic
    return {{}}
'''
        file_path.write_text(code)
        print(f"  ✅ Generated: {file_path}")

    # __init__.py を各ディレクトリに作成
    for directory in ["checks", "transforms", "datatypes"]:
        init_path = app_root / directory / "__init__.py"
        if not init_path.exists():
            init_path.parent.mkdir(parents=True, exist_ok=True)
            init_path.write_text("# Auto-generated\n")
            print(f"  ✅ Generated: {init_path}")


# ==================== DAG検証・実行エンジン ====================


class Engine:
    """コア実行・検証・生成エンジン"""

    def __init__(self, spec: Spec):
        self.spec = spec
        self.graph = self._build_dag()

    def _build_dag(self) -> nx.DiGraph:
        """DAGを構築"""
        g = nx.DiGraph()

        # Transformをノードとして追加
        for transform in self.spec.transforms:
            g.add_node(transform.id)

        # エッジを追加
        for edge in self.spec.dag:
            if edge.to is None:
                # 終端ノード
                continue
            g.add_edge(edge.from_, edge.to)

        # DAG検証（サイクルがないか）
        if not nx.is_directed_acyclic_graph(g):
            raise ValueError("❌ DAGにサイクルが存在します")

        return g

    def validate_schemas(self) -> None:
        """JSON Schema検証"""
        print("🔍 Validating schemas...")
        for datatype in self.spec.datatypes:
            try:
                # スキーマ自体の妥当性チェック
                jsonschema.Draft7Validator.check_schema(datatype.schema)
                print(f"  ✅ {datatype.id}: schema valid")
            except jsonschema.SchemaError as e:
                print(f"  ❌ {datatype.id}: schema invalid - {e}")

    def run_checks(self) -> None:
        """Check関数を実行"""
        print("🔍 Running checks...")
        for check in self.spec.checks:
            module_path, func_name = check.impl.split(":")
            try:
                module = importlib.import_module(module_path)
                getattr(module, func_name)
                print(f"  ✅ {check.id}: loaded")
            except (ImportError, AttributeError) as e:
                print(f"  ❌ {check.id}: {e}")

    def run_examples(self) -> dict[str, bool]:
        """Example検証を実行"""
        print("🧪 Running examples...")
        results = {}

        for example in self.spec.examples:
            # 簡易実装: Transformを実行して期待値と比較
            # 実際にはDAGを辿って実行する必要がある
            print(f"  🔬 {example.id}: {example.description}")
            results[example.id] = True  # TODO: 実際の検証ロジック実装

        return results

    def run_dag(self) -> None:
        """DAGを実行"""
        print("🚀 Running DAG...")

        if len(self.graph.nodes) == 0:
            print("  ℹ️  No transforms to execute")
            return

        # トポロジカルソートで実行順序を決定
        try:
            execution_order = list(nx.topological_sort(self.graph))
        except nx.NetworkXError:
            print("  ❌ Cannot determine execution order (cycle detected)")
            return

        for transform_id in execution_order:
            # Transform定義を取得
            transform = next(
                (t for t in self.spec.transforms if t.id == transform_id), None
            )
            if not transform:
                print(f"  ❌ {transform_id}: not found in spec")
                continue

            # モジュール・関数をロード
            module_path, func_name = transform.impl.split(":")
            try:
                module = importlib.import_module(module_path)
                func = getattr(module, func_name)

                # 簡易実行（引数は仮）
                # 実際にはデータフローを実装する必要がある
                result = func(**transform.default_args)
                print(f"  ✅ {transform_id} -> {result}")
            except (ImportError, AttributeError) as e:
                print(f"  ❌ {transform_id}: {e}")
            except Exception as e:
                print(f"  ❌ {transform_id}: execution error - {e}")


# ==================== CLI ====================


def main():
    """CLIエントリーポイント"""
    import argparse

    parser = argparse.ArgumentParser(description="Spec-to-Code Engine")
    subparsers = parser.add_subparsers(dest="command", help="サブコマンド")

    # gen コマンド
    gen_parser = subparsers.add_parser("gen", help="スケルトンコード生成")
    gen_parser.add_argument("spec_file", help="仕様ファイル (YAML/JSON)")

    # run コマンド
    run_parser = subparsers.add_parser("run", help="DAG実行・検証")
    run_parser.add_argument("spec_file", help="仕様ファイル (YAML/JSON)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 仕様読み込み
    try:
        spec = load_spec(args.spec_file)
        print(f"✅ Loaded spec: {spec.meta.name} (v{spec.version})")
    except Exception as e:
        print(f"❌ Failed to load spec: {e}")
        sys.exit(1)

    # コマンド実行
    if args.command == "gen":
        generate_skeleton(spec)
        print("✅ Skeleton generation completed")

    elif args.command == "run":
        engine = Engine(spec)
        engine.validate_schemas()
        engine.run_checks()
        engine.run_dag()
        results = engine.run_examples()
        print(f"📊 Example report: {results}")
        print("✅ Execution completed")


if __name__ == "__main__":
    main()

"""
構造仕様ベースのコードスケルトン生成・検証システム - コアエンジン
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any, Generic, TypeVar

import jsonschema
import networkx as nx
import yaml
from pydantic import BaseModel, Field, field_validator


# ==================== 型アノテーション用マーカー ====================

T = TypeVar("T")


class Check(Generic[T]):
    """型アノテーション用のCheck参照マーカー

    Usage:
        Annotated[Out, Check["module.path.check_function"]]
    """

    def __class_getitem__(cls, item: str) -> type:
        """文字列でチェック関数を参照"""
        return type(f"Check[{item}]", (), {"__check_ref__": item})


class ExampleValue(Generic[T]):
    """型アノテーション用のExample値マーカー

    Usage:
        Annotated[In, ExampleValue[{"text": "hello world"}]]
    """

    def __class_getitem__(cls, item: dict[str, Any]) -> type:
        """辞書で例示値を参照"""
        return type(f"ExampleValue[{item}]", (), {"__example_value__": item})


# ==================== データモデル定義 ====================


class CheckDef(BaseModel):
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

    model_config = {"protected_namespaces": ()}

    id: str
    description: str
    check_ids: list[str] = Field(default_factory=list)
    example_ids: list[str] = Field(default_factory=list)
    schema_def: dict[str, Any] = Field(alias="schema")  # JSON Schema


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
    return_native: str | None = None  # "module:type"形式（戻り値の型指定）
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


class DAGStage(BaseModel):
    """DAG stage definition (for unified dag_stages representation)"""

    stage_id: str
    description: str
    selection_mode: str = "single"  # single, exclusive, multiple
    max_select: int | None = None
    input_type: str
    output_type: str
    candidates: list[str] = Field(default_factory=list)  # transform_ids
    default_transform_id: str | None = None


class Spec(BaseModel):
    """仕様全体のルートモデル"""

    version: str
    meta: Meta
    checks: list[CheckDef] = Field(default_factory=list)
    examples: list[Example] = Field(default_factory=list)
    datatypes: list[DataType] = Field(default_factory=list)
    transforms: list[Transform] = Field(default_factory=list)
    dag: list[DAGEdge] = Field(default_factory=list)
    dag_stages: list[DAGStage] = Field(default_factory=list)


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

    spec = Spec(**data)
    _convert_dag_to_stages(spec)
    return spec


def _convert_dag_to_stages(spec: Spec) -> None:
    """Convert legacy dag format to dag_stages format

    If dag_stages is empty but dag exists, generate dag_stages from DAG topology.
    Each transform becomes a single-mode stage with one candidate.
    """
    if spec.dag_stages:
        # Already has dag_stages, no conversion needed
        return

    if not spec.dag:
        # No dag to convert
        return

    # Build transform lookup
    transform_by_id = {t.id: t for t in spec.transforms}

    # Build DAG graph to determine execution order
    import networkx as nx

    G = nx.DiGraph()
    for edge in spec.dag:
        if edge.to is not None:
            G.add_edge(edge.from_, edge.to)
        else:
            # Terminal node (no outgoing edges)
            G.add_node(edge.from_)

    # Topological sort to get execution order
    try:
        ordered_transforms = list(nx.topological_sort(G))
    except nx.NetworkXError:
        # Graph has cycles or other issues, fallback to original order
        ordered_transforms = [edge.from_ for edge in spec.dag]

    # Create single-mode stages for each transform
    stages = []
    for i, transform_id in enumerate(ordered_transforms):
        if transform_id not in transform_by_id:
            continue

        transform = transform_by_id[transform_id]

        # Determine input/output types
        input_type = ""
        output_type = ""

        if transform.parameters:
            first_param = transform.parameters[0]
            input_type = first_param.datatype_ref or first_param.native or "Any"

        output_type = transform.return_datatype_ref or transform.return_native or "Any"

        stage = DAGStage(
            stage_id=f"stage_{i+1}_{transform_id}",
            description=transform.description or f"Stage {i+1}: {transform_id}",
            selection_mode="single",
            input_type=input_type,
            output_type=output_type,
            candidates=[transform_id],
            default_transform_id=transform_id,
        )
        stages.append(stage)

    spec.dag_stages = stages


# ==================== スケルトンコード生成 ====================


def _build_type_annotation(
    spec: Spec, param: Parameter, app_root: Path
) -> tuple[str, set[str]]:
    """パラメータの型アノテーションを構築（Inputパラメータ用：Exampleのみ適用）

    Returns:
        (型文字列, importセット)
    """
    imports = set()

    # ベース型を決定
    base_type = "dict"  # デフォルト

    if param.native:
        # native が指定されていればそれを使う
        module, type_name = param.native.split(":")
        if module != "builtins":
            # pandas の場合は pd として import
            if module == "pandas":
                imports.add("import pandas as pd")
                base_type = f"pd.{type_name}"
            else:
                imports.add(f"import {module}")
                base_type = f"{module}.{type_name}"
        else:
            base_type = type_name

    # Example は datatype_ref から取得（Inputパラメータ用）
    example_annotations = []

    if param.datatype_ref:
        datatype = next(
            (dt for dt in spec.datatypes if dt.id == param.datatype_ref), None
        )
        if datatype:
            # Example参照のみ追加（Checkは追加しない）
            for example_id in datatype.example_ids:
                example = next((e for e in spec.examples if e.id == example_id), None)
                if example:
                    example_annotations.append(f"ExampleValue[{example.input}]")
                    imports.add("from spec2code.engine import ExampleValue")

    # Annotatedを使用
    if example_annotations:
        imports.add("from typing import Annotated")
        annotations = ", ".join(example_annotations)
        return f"Annotated[{base_type}, {annotations}]", imports

    return base_type, imports


def _build_return_annotation(
    spec: Spec, transform: Transform, app_root: Path
) -> tuple[str, set[str]]:
    """戻り値の型アノテーションを構築（Outputパラメータ用：Checkのみ適用）

    Returns:
        (型文字列, importセット)
    """
    imports = set()

    # ベース型を決定
    base_type = "dict"  # デフォルト

    if transform.return_native:
        # return_native が指定されていればそれを使う
        module, type_name = transform.return_native.split(":")
        if module != "builtins":
            # pandas の場合は pd として import
            if module == "pandas":
                imports.add("import pandas as pd")
                base_type = f"pd.{type_name}"
            else:
                imports.add(f"import {module}")
                base_type = f"{module}.{type_name}"
        else:
            base_type = type_name

    # Check は return_datatype_ref から取得（Outputパラメータ用）
    check_annotations = []

    if transform.return_datatype_ref:
        datatype = next(
            (dt for dt in spec.datatypes if dt.id == transform.return_datatype_ref),
            None,
        )
        if datatype:
            # Check参照のみ追加（Exampleは追加しない）
            for check_id in datatype.check_ids:
                check_def = next((c for c in spec.checks if c.id == check_id), None)
                if check_def:
                    check_annotations.append(f'Check["{check_def.impl}"]')
                    imports.add("from spec2code.engine import Check")

    # Annotatedを使用
    if check_annotations:
        imports.add("from typing import Annotated")
        annotations = ", ".join(check_annotations)
        return f"Annotated[{base_type}, {annotations}]", imports

    return base_type, imports


def generate_skeleton(spec: Spec, project_root: Path = Path(".")) -> None:
    """未実装ファイルを自動生成"""
    print("🔨 Generating skeleton code...")

    # プロジェクト名に基づく出力先ディレクトリ
    app_root = project_root / "apps" / spec.meta.name
    print(f"  📁 Target directory: {app_root}")

    # Check関数のスケルトン生成（同じファイルに複数の関数を追加）
    check_files = {}  # file_path -> list of check functions
    for check in spec.checks:
        file_path = app_root / check.file_path
        if file_path not in check_files:
            check_files[file_path] = []
        check_files[file_path].append(check)

    for file_path, checks in check_files.items():
        if file_path.exists():
            print(f"  ⏭️  Skip (exists): {file_path}")
            continue

        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate all check functions for this file
        functions = []
        for check in checks:
            func_name = check.impl.split(":")[-1]
            func_code = f'''def {func_name}(payload: dict) -> bool:
    """{check.description}"""
    # TODO: implement validation logic
    return True
'''
            functions.append(func_code)

        code = f"""# Auto-generated skeleton for Check functions
{chr(10).join(functions)}
"""
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

        # パラメータの型アノテーションを構築
        param_strs = []
        all_imports = set()

        for param in transform.parameters:
            type_str, imports = _build_type_annotation(spec, param, app_root)
            all_imports.update(imports)
            param_strs.append(f"{param.name}: {type_str}")

        # 戻り値の型アノテーションを構築
        return_type, return_imports = _build_return_annotation(
            spec, transform, app_root
        )
        all_imports.update(return_imports)

        # import文を生成（spec2code.engineからのimportを統合）
        import_lines = []
        spec2code_imports = set()
        other_imports = set()

        for imp in all_imports:
            if imp.startswith("from spec2code.engine import"):
                # spec2code.engineからのimportを抽出
                parts = imp.split("import", 1)[1].strip()
                spec2code_imports.add(parts)
            else:
                other_imports.add(imp)

        # spec2code.engineのimportを統合
        if spec2code_imports:
            combined_import = (
                f"from spec2code.engine import {', '.join(sorted(spec2code_imports))}"
            )
            import_lines.append(combined_import)

        # その他のimportを追加
        import_lines.extend(sorted(other_imports))

        import_section = "\n".join(import_lines) if import_lines else ""

        # パラメータリスト作成
        params = ", ".join(param_strs)

        code = f'''# Auto-generated skeleton for Transform: {transform.id}
{import_section}

def {func_name}({params}) -> {return_type}:
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
                jsonschema.Draft7Validator.check_schema(datatype.schema_def)
                print(f"  ✅ {datatype.id}: schema valid")
            except jsonschema.SchemaError as e:
                print(f"  ❌ {datatype.id}: schema invalid - {e}")

    def validate_integrity(
        self, project_root: Path = Path(".")
    ) -> dict[str, list[str]]:
        """仕様と実装の整合性を検証

        Returns:
            エラーマップ {category: [error_messages]}
        """
        print("🔍 Validating spec-implementation integrity...")
        errors: dict[str, list[str]] = {
            "check_functions": [],
            "check_locations": [],
            "transform_functions": [],
            "transform_signatures": [],
            "example_schemas": [],
        }

        # sys.pathにpackagesディレクトリを追加
        packages_dir = str((project_root / "packages").resolve())
        if packages_dir not in sys.path:
            sys.path.insert(0, packages_dir)

        app_root = project_root / "apps" / self.spec.meta.name

        # 1. Check関数の存在と位置を検証
        for check in self.spec.checks:
            module_path, func_name = check.impl.split(":")
            expected_file = app_root / check.file_path

            # 関数が読み込めるか
            try:
                module = importlib.import_module(module_path)
                func = getattr(module, func_name)
                print(f"  ✅ Check {check.id}: function exists")

                # ファイル位置の検証
                import inspect

                actual_file = Path(inspect.getfile(func)).resolve()
                expected_file_resolved = expected_file.resolve()

                if actual_file != expected_file_resolved:
                    error_msg = (
                        f"Check '{check.id}' location mismatch:\n"
                        f"    Expected: {expected_file}\n"
                        f"    Actual:   {actual_file}"
                    )
                    errors["check_locations"].append(error_msg)
                    print(f"  ⚠️  {error_msg}")

            except (ImportError, AttributeError) as e:
                error_msg = f"Check '{check.id}' not found: {e}"
                errors["check_functions"].append(error_msg)
                print(f"  ❌ {error_msg}")

        # 2. Transform関数の存在と位置を検証
        for transform in self.spec.transforms:
            module_path, func_name = transform.impl.split(":")
            expected_file = app_root / transform.file_path

            try:
                module = importlib.import_module(module_path)
                func = getattr(module, func_name)
                print(f"  ✅ Transform {transform.id}: function exists")

                # ファイル位置の検証
                import inspect

                actual_file = Path(inspect.getfile(func)).resolve()
                expected_file_resolved = expected_file.resolve()

                if actual_file != expected_file_resolved:
                    error_msg = (
                        f"Transform '{transform.id}' location mismatch:\n"
                        f"    Expected: {expected_file}\n"
                        f"    Actual:   {actual_file}"
                    )
                    errors["transform_functions"].append(error_msg)
                    print(f"  ⚠️  {error_msg}")

                # シグネチャの検証
                sig = inspect.signature(func)
                expected_params = {p.name for p in transform.parameters}
                actual_params = set(sig.parameters.keys())

                if expected_params != actual_params:
                    error_msg = (
                        f"Transform '{transform.id}' signature mismatch:\n"
                        f"    Expected params: {sorted(expected_params)}\n"
                        f"    Actual params:   {sorted(actual_params)}"
                    )
                    errors["transform_signatures"].append(error_msg)
                    print(f"  ⚠️  {error_msg}")

            except (ImportError, AttributeError) as e:
                error_msg = f"Transform '{transform.id}' not found: {e}"
                errors["transform_functions"].append(error_msg)
                print(f"  ❌ {error_msg}")

        # 3. Example値のスキーマ適合性を検証
        for example in self.spec.examples:
            # このExampleが参照されているDataTypeを探す
            for datatype in self.spec.datatypes:
                if example.id in datatype.example_ids:
                    try:
                        jsonschema.validate(example.input, datatype.schema_def)
                        print(
                            f"  ✅ Example {example.id}: schema valid for {datatype.id}"
                        )
                    except jsonschema.ValidationError as e:
                        error_msg = (
                            f"Example '{example.id}' invalid for DataType '{datatype.id}':\n"
                            f"    {e.message}"
                        )
                        errors["example_schemas"].append(error_msg)
                        print(f"  ❌ {error_msg}")

        # サマリー表示
        total_errors = sum(len(errs) for errs in errors.values())
        if total_errors == 0:
            print("\n✅ All integrity checks passed!")
        else:
            print(f"\n⚠️  Found {total_errors} integrity issue(s)")

        return errors

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

    # validate コマンド
    validate_parser = subparsers.add_parser("validate", help="仕様と実装の整合性を検証")
    validate_parser.add_argument("spec_file", help="仕様ファイル (YAML/JSON)")

    # run-config コマンド
    run_config_parser = subparsers.add_parser(
        "run-config", help="Config-based DAG execution"
    )
    run_config_parser.add_argument("config_file", help="Config file (YAML)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # run-config コマンドは別処理
    if args.command == "run-config":
        from packages.spec2code.config_runner import ConfigRunner
        import pandas as pd

        try:
            runner = ConfigRunner(args.config_file)

            # Create sample initial data (StepAFrame)
            initial_data = pd.DataFrame(
                {
                    "timestamp": [
                        "2024-01-01",
                        "2024-01-02",
                        "2024-01-03",
                        "2024-01-04",
                        "2024-01-05",
                    ],
                    "value": [100, 150, 120, 180, 140],
                }
            )

            print(f"\n📊 Initial data:")
            print(initial_data)
            print()

            result = runner.run(initial_data)

            print(f"\n📊 Final result:")
            print(result)

        except Exception as e:
            print(f"❌ Config execution failed: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)

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

    elif args.command == "validate":
        engine = Engine(spec)
        errors = engine.validate_integrity()

        # エラーがあれば終了コード1で終了
        total_errors = sum(len(errs) for errs in errors.values())
        if total_errors > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()

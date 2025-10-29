"""pytest設定とフィクスチャ定義"""

import shutil
import sys
from pathlib import Path

import pytest
import yaml

# spec2codeモジュールをインポート可能にする
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "packages"))


@pytest.fixture(autouse=True)
def clean_module_cache():
    """各テスト実行前にtest-pipelineモジュールをクリア"""
    modules_to_remove = [
        key
        for key in list(sys.modules.keys())
        if "test_pipeline" in key or "test-pipeline" in key
    ]
    for module in modules_to_remove:
        del sys.modules[module]
    sys.modules.pop("apps", None)
    sys.path = [
        path
        for path in sys.path
        if not ("/pytest-" in path and path.endswith("/apps"))
    ]

    yield
    # test-pipelineモジュールをクリア
    modules_to_remove = [
        key
        for key in list(sys.modules.keys())
        if "test_pipeline" in key or "test-pipeline" in key
    ]
    for module in modules_to_remove:
        del sys.modules[module]
    sys.modules.pop("apps", None)
    sys.path = [
        path
        for path in sys.path
        if not ("/pytest-" in path and path.endswith("/apps"))
    ]


@pytest.fixture
def temp_project_dir(tmp_path):
    """一時的なプロジェクトディレクトリを作成"""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # packagesディレクトリをコピー（spec2codeモジュール用）
    packages_dir = project_dir / "packages"
    shutil.copytree(REPO_ROOT / "packages" / "spec2code", packages_dir / "spec2code")
    (packages_dir / "__init__.py").write_text("")

    return project_dir


@pytest.fixture
def sample_spec_yaml():
    """サンプル仕様YAML"""
    return {
        "version": "1",
        "meta": {"name": "test-pipeline", "description": "テスト用パイプライン"},
        "checks": [
            {
                "id": "check_text_length",
                "description": "テキスト長が0より大きい",
                "impl": "test-pipeline.checks.validators:check_text_length",
                "file_path": "checks/validators.py",
            },
            {
                "id": "check_result_positive",
                "description": "結果が正の数",
                "impl": "test-pipeline.checks.validators:check_result_positive",
                "file_path": "checks/validators.py",
            },
        ],
        "examples": [
            {
                "id": "example_hello",
                "description": "Hello例",
                "input": {"text": "hello"},
                "expected": {"length": 5},
            },
            {
                "id": "example_result",
                "description": "処理結果例",
                "input": {"length": 5, "processed": True},
                "expected": {"length": 5},
            }
        ],
        "generators": [
            {
                "id": "generate_text_input",
                "description": "テキスト入力データを生成",
                "impl": "test-pipeline.generators.data_generators:generate_text_input",
                "file_path": "generators/data_generators.py",
                "parameters": [
                    {"name": "uppercase", "native": "builtins:bool", "default": False}
                ],
            }
        ],
        "datatypes": [
            {
                "id": "TextInput",
                "description": "テキスト入力",
                "check_ids": ["check_text_length"],
                "example_refs": ["example_hello"],
                "generator_refs": ["generate_text_input"],
                "schema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            },
            {
                "id": "TextResult",
                "description": "テキスト処理結果",
                "check_ids": ["check_result_positive"],
                "example_refs": ["example_result"],
                "schema": {
                    "type": "object",
                    "properties": {
                        "length": {"type": "integer"},
                        "processed": {"type": "boolean"},
                    },
                    "required": ["length"],
                },
            },
        ],
        "transforms": [
            {
                "id": "process_text",
                "description": "テキストを処理",
                "impl": "test-pipeline.transforms.processors:process_text",
                "file_path": "transforms/processors.py",
                "parameters": [
                    {"name": "input_data", "datatype_ref": "TextInput"},
                    {"name": "uppercase", "native": "builtins:bool"},
                ],
                "return_datatype_ref": "TextResult",
                "default_args": {"input_data": {"text": "test"}, "uppercase": True},
            }
        ],
        "dag": [{"from": "process_text", "to": None}],
    }


@pytest.fixture
def spec_file(temp_project_dir, sample_spec_yaml):
    """仕様YAMLファイルを作成"""
    spec_path = temp_project_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(sample_spec_yaml, f)
    return spec_path


@pytest.fixture
def generated_project(temp_project_dir, spec_file):
    """スケルトンコードを生成したプロジェクト"""
    from spec2code.engine import generate_skeleton, load_spec

    spec = load_spec(spec_file)
    generate_skeleton(spec, project_root=temp_project_dir)

    apps_dir = str((temp_project_dir / "apps").resolve())
    if apps_dir in sys.path:
        sys.path.remove(apps_dir)
    sys.path.insert(0, apps_dir)

    return temp_project_dir


@pytest.fixture
def implemented_project(generated_project):
    """実装が完了したプロジェクト"""
    # sys.pathにappsディレクトリを追加
    apps_dir = str((generated_project / "apps").resolve())
    if apps_dir in sys.path:
        sys.path.remove(apps_dir)
    sys.path.insert(0, apps_dir)

    app_root = generated_project / "apps" / "test-pipeline"

    # __init__.pyを作成してモジュール化
    (app_root / "__init__.py").write_text("")
    (app_root / "checks" / "__init__.py").write_text("")
    (app_root / "generators" / "__init__.py").write_text("")
    (app_root / "transforms" / "__init__.py").write_text("")

    # Check関数を実装
    validators_file = app_root / "checks" / "validators.py"
    validators_code = '''# Check functions
def check_text_length(payload: dict) -> bool:
    """テキスト長が0より大きい"""
    return len(payload.get("text", "")) > 0


def check_result_positive(payload: dict) -> bool:
    """結果が正の数"""
    return payload.get("length", 0) > 0
'''
    validators_file.write_text(validators_code)

    # Transform関数を実装
    processors_file = app_root / "transforms" / "processors.py"
    processors_code = '''# Transform functions
from typing import Annotated
from spec2code.engine import Check, ExampleValue


def process_text(
    input_data: Annotated[
        dict,
        Check["test-pipeline.checks.validators:check_text_length"],
        ExampleValue[{"text": "hello"}],
    ],
    uppercase: bool,
) -> Annotated[dict, Check["test-pipeline.checks.validators:check_result_positive"]]:
    """テキストを処理"""
    text = input_data.get("text", "")
    if uppercase:
        text = text.upper()
    return {"length": len(text), "processed": True}
'''
    processors_file.write_text(processors_code)

    # Generator関数を実装
    generators_file = app_root / "generators" / "data_generators.py"
    generators_code = '''# Generator functions
from typing import Any


def generate_text_input(uppercase: bool = False) -> dict[str, Any]:
    """テキスト入力データを生成"""
    payload: dict[str, Any] = {"text": "hello"}
    if uppercase:
        payload["text"] = payload["text"].upper()
    return payload
'''
    generators_file.write_text(generators_code)

    return generated_project

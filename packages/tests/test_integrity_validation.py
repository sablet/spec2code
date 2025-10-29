"""仕様と実装の整合性検証テスト"""

import copy

import pytest

from spec2code.engine import Engine, load_spec


class TestIntegrityValidation:
    """整合性検証のテストスイート"""

    def test_validate_all_passed(self, implemented_project, spec_file):
        """正常ケース: すべての検証がパスする"""
        spec = load_spec(spec_file)
        engine = Engine(spec)

        errors = engine.validate_integrity(project_root=implemented_project)

        # エラーが0件であることを確認
        total_errors = sum(len(errs) for errs in errors.values())
        if total_errors > 0:
            print("\nUnexpected errors found:")
            for category, err_list in errors.items():
                if err_list:
                    print(f"  {category}: {err_list}")

        assert total_errors == 0, f"Expected 0 errors, but got {total_errors}"
        assert len(errors["check_functions"]) == 0
        assert len(errors["check_locations"]) == 0
        assert len(errors["transform_functions"]) == 0
        assert len(errors["transform_signatures"]) == 0
        assert len(errors["generator_functions"]) == 0
        assert len(errors["generator_locations"]) == 0
        assert len(errors["generator_signatures"]) == 0
        assert len(errors["example_schemas"]) == 0

    def test_detect_missing_check_function(self, implemented_project, spec_file):
        """異常ケース: Check関数が削除された"""
        # Check関数を削除
        app_root = implemented_project / "apps" / "test-pipeline"
        validators_file = app_root / "checks" / "validators.py"

        # check_result_positive関数を削除
        validators_code = '''# Check functions
def check_text_length(payload: dict) -> bool:
    """テキスト長が0より大きい"""
    return len(payload.get("text", "")) > 0
'''
        validators_file.write_text(validators_code)

        spec = load_spec(spec_file)
        engine = Engine(spec)

        errors = engine.validate_integrity(project_root=implemented_project)

        # check_result_positiveが見つからないエラーが1件
        assert len(errors["check_functions"]) == 1
        assert "check_result_positive" in errors["check_functions"][0]

    def test_detect_file_moved(self, implemented_project, spec_file):
        """異常ケース: ファイルが移動された"""
        app_root = implemented_project / "apps" / "test-pipeline"

        # validators.pyを別ディレクトリに移動
        new_dir = app_root / "checks" / "deep"
        new_dir.mkdir(parents=True, exist_ok=True)
        old_file = app_root / "checks" / "validators.py"
        new_file = new_dir / "validators.py"
        old_file.rename(new_file)

        spec = load_spec(spec_file)
        engine = Engine(spec)

        errors = engine.validate_integrity(project_root=implemented_project)

        # 関数が見つからないエラーが発生（モジュールパスが変わったため）
        assert len(errors["check_functions"]) >= 1

    def test_detect_signature_mismatch(self, implemented_project, spec_file):
        """異常ケース: Transform関数のシグネチャが変更された"""
        app_root = implemented_project / "apps" / "test-pipeline"
        processors_file = app_root / "transforms" / "processors.py"

        # 余分なパラメータを追加
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
    extra_param: str = "default",
) -> Annotated[dict, Check["test-pipeline.checks.validators:check_result_positive"]]:
    """テキストを処理"""
    text = input_data.get("text", "")
    if uppercase:
        text = text.upper()
    return {"length": len(text), "processed": True}
'''
        processors_file.write_text(processors_code)

        spec = load_spec(spec_file)
        engine = Engine(spec)

        errors = engine.validate_integrity(project_root=implemented_project)

        # シグネチャ不一致エラーが1件
        assert len(errors["transform_signatures"]) == 1
        assert "process_text" in errors["transform_signatures"][0]
        assert "extra_param" in errors["transform_signatures"][0]

    def test_datatype_requires_example_or_generator(self, temp_project_dir, sample_spec_yaml):
        """DataTypeはexampleかgeneratorのいずれかを要求する"""
        import yaml

        spec_data = copy.deepcopy(sample_spec_yaml)
        spec_data["datatypes"][0]["example_refs"] = []
        spec_data["datatypes"][0]["generator_refs"] = []

        spec_path = temp_project_dir / "spec.yaml"
        spec_path.write_text(yaml.dump(spec_data))

        with pytest.raises(ValueError) as excinfo:
            load_spec(spec_path)
        assert "example_refs or generator_refs" in str(excinfo.value)

    def test_detect_invalid_example_schema(self, temp_project_dir, sample_spec_yaml):
        """異常ケース: Example値がスキーマに違反"""
        # 不正なExample値を設定
        sample_spec_yaml["examples"][0]["input"] = {"invalid_field": 123}

        spec_path = temp_project_dir / "spec.yaml"
        import yaml

        with open(spec_path, "w") as f:
            yaml.dump(sample_spec_yaml, f)

        spec = load_spec(spec_path)
        engine = Engine(spec)

        errors = engine.validate_integrity(project_root=temp_project_dir)

        # スキーマ検証エラーが1件
        assert len(errors["example_schemas"]) == 1
        assert "example_hello" in errors["example_schemas"][0]

    def test_detect_missing_transform_function(self, generated_project, spec_file):
        """異常ケース: Transform関数のスケルトンのみ（実装未完了）"""
        app_root = generated_project / "apps" / "test-pipeline"
        processors_file = app_root / "transforms" / "processors.py"

        # transform関数自体を削除
        processors_file.write_text("# Empty file")

        spec = load_spec(spec_file)
        engine = Engine(spec)

        errors = engine.validate_integrity(project_root=generated_project)

        # Transform関数が削除されたのでエラーが発生
        assert len(errors["transform_functions"]) >= 1
        assert "process_text" in errors["transform_functions"][0]

    def test_detect_missing_generator_function(self, generated_project, spec_file):
        """異常ケース: Generator関数が未実装"""
        app_root = generated_project / "apps" / "test-pipeline"
        generator_file = app_root / "generators" / "data_generators.py"
        generator_file.write_text("# Generator file without functions\n")

        spec = load_spec(spec_file)
        engine = Engine(spec)

        errors = engine.validate_integrity(project_root=generated_project)

        assert len(errors["generator_functions"]) >= 1
        message = "generate_text_input"
        assert any(message in err for err in errors["generator_functions"])

    def test_detect_generator_signature_mismatch(self, implemented_project, spec_file):
        """異常ケース: Generator関数のシグネチャ不一致"""
        app_root = implemented_project / "apps" / "test-pipeline"
        generator_file = app_root / "generators" / "data_generators.py"
        generator_code = '''# Generator functions
from typing import Any


def generate_text_input(uppercase: bool = False, extra: int = 1) -> dict[str, Any]:
    """テキスト入力データを生成"""
    payload: dict[str, Any] = {"text": "hello"}
    if uppercase:
        payload["text"] = payload["text"].upper()
    payload["extra"] = extra
    return payload
'''
        generator_file.write_text(generator_code)

        spec = load_spec(spec_file)
        engine = Engine(spec)

        errors = engine.validate_integrity(project_root=implemented_project)

        assert len(errors["generator_signatures"]) >= 1
        assert "generate_text_input" in errors["generator_signatures"][0]

    def test_detect_generator_location_mismatch(self, implemented_project, spec_file):
        """異常ケース: Generator関数が別ファイルから再エクスポートされる"""
        app_root = implemented_project / "apps" / "test-pipeline"
        generator_file = app_root / "generators" / "data_generators.py"
        helper_file = app_root / "generators" / "helper_generators.py"
        helper_code = '''from typing import Any


def generate_text_input(uppercase: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {"text": "hello"}
    if uppercase:
        payload["text"] = payload["text"].upper()
    payload["text"] += "_moved"
    return payload
'''
        helper_file.write_text(helper_code)
        generator_file.write_text("from .helper_generators import generate_text_input\n")

        spec = load_spec(spec_file)
        engine = Engine(spec)

        errors = engine.validate_integrity(project_root=implemented_project)

        assert len(errors["generator_locations"]) >= 1
        assert "generate_text_input" in errors["generator_locations"][0]

    def test_multiple_errors_reported(self, implemented_project, spec_file):
        """複数のエラーが同時に報告される"""
        app_root = implemented_project / "apps" / "test-pipeline"

        # 1. Check関数を削除
        validators_file = app_root / "checks" / "validators.py"
        validators_code = """# Only one check function remains
def check_text_length(payload: dict) -> bool:
    return len(payload.get("text", "")) > 0
"""
        validators_file.write_text(validators_code)

        # 2. Transform関数のシグネチャを変更
        processors_file = app_root / "transforms" / "processors.py"
        processors_code = """# Transform with wrong signature
from typing import Annotated
from spec2code.engine import Check, ExampleValue


def process_text(
    input_data: Annotated[dict, ExampleValue[{"text": "hello"}]],
    uppercase: bool,
    new_param: int,
) -> dict:
    text = input_data.get("text", "")
    return {"length": len(text), "processed": True}
"""
        processors_file.write_text(processors_code)

        spec = load_spec(spec_file)
        engine = Engine(spec)

        errors = engine.validate_integrity(project_root=implemented_project)

        # 複数のエラーが報告される
        total_errors = sum(len(errs) for errs in errors.values())
        assert total_errors >= 2
        assert len(errors["check_functions"]) >= 1  # check_result_positiveが削除
        assert len(errors["transform_signatures"]) >= 1  # process_textのシグネチャ変更

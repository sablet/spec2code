"""Docstring metadata rendering tests

spec_metadataフィールドを使った動的なdocstring生成のテスト。
"""

import pytest
from spectool.spectool.backends.py_skeleton_codegen import (
    format_metadata_section,
    build_transform_function_signature,
)


class TestFormatMetadataSection:
    """format_metadata_section() のテスト"""

    def test_format_string_value(self):
        """文字列値のフォーマット"""
        result = format_metadata_section("complexity", "O(n)")
        assert result == ["    Complexity: O(n)"]

    def test_format_multiline_string(self):
        """複数行文字列のフォーマット"""
        value = "Line 1\nLine 2\nLine 3"
        result = format_metadata_section("notes", value)
        assert result[0] == "    Notes:"
        assert result[1] == "        Line 1"
        assert result[2] == "        Line 2"
        assert result[3] == "        Line 3"

    def test_format_list_value(self):
        """リスト値のフォーマット"""
        value = ["Step 1", "Step 2", "Step 3"]
        result = format_metadata_section("logic_overview", value)
        assert result[0] == "    Logic Overview:"
        assert result[1] == "        - Step 1"
        assert result[2] == "        - Step 2"
        assert result[3] == "        - Step 3"

    def test_format_dict_value(self):
        """辞書値のフォーマット"""
        value = {"pandas": ">=2.0", "numpy": ">=1.24"}
        result = format_metadata_section("dependencies", value)
        assert result[0] == "    Dependencies:"
        assert "        pandas: >=2.0" in result
        assert "        numpy: >=1.24" in result

    def test_format_nested_dict(self):
        """ネストした辞書のフォーマット"""
        value = {"error_handling": {"missing_data": "Raise ValueError", "invalid_type": "Log warning"}}
        result = format_metadata_section("specs", value)
        assert result[0] == "    Specs:"
        # ネストされた構造が含まれる
        assert any("Error Handling:" in line for line in result)

    def test_format_numeric_value(self):
        """数値のフォーマット"""
        result = format_metadata_section("version", 2)
        assert result == ["    Version: 2"]

    def test_snake_case_to_title_case(self):
        """snake_caseキーがTitle Caseに変換される"""
        result = format_metadata_section("logic_overview", ["Step 1"])
        assert result[0] == "    Logic Overview:"

    def test_custom_indent(self):
        """カスタムインデント"""
        result = format_metadata_section("key", "value", indent=8)
        assert result[0] == "        Key: value"


class TestBuildTransformFunctionSignature:
    """build_transform_function_signature() のテスト"""

    def test_basic_signature_without_metadata(self):
        """メタデータなしの基本的なシグネチャ"""
        result = build_transform_function_signature(
            func_name="process_data",
            param_str="data: pd.DataFrame",
            return_type="pd.DataFrame",
            description="Process input data",
        )

        assert "# Process input data" in result
        assert "def process_data(data: pd.DataFrame) -> pd.DataFrame:" in result
        assert '    """TODO: Implement process_data' in result
        assert "    Process input data" in result
        assert '    """' in result
        # build_transform_function_signature doesn't include TODO comment anymore
        # Each function generator adds its own specific TODO comment

    def test_signature_with_metadata(self):
        """メタデータ付きシグネチャ"""
        spec_metadata = {
            "logic_overview": ["Step 1: Extract data", "Step 2: Transform data", "Step 3: Return result"],
            "complexity": "O(n)",
        }

        result = build_transform_function_signature(
            func_name="process_data",
            param_str="data: pd.DataFrame",
            return_type="pd.DataFrame",
            description="Process input data",
            spec_metadata=spec_metadata,
        )

        result_text = "\n".join(result)

        # 基本構造の確認
        assert "def process_data(data: pd.DataFrame) -> pd.DataFrame:" in result_text

        # メタデータの確認
        assert "Logic Overview:" in result_text
        assert "- Step 1: Extract data" in result_text
        assert "- Step 2: Transform data" in result_text
        assert "- Step 3: Return result" in result_text
        assert "Complexity: O(n)" in result_text

    def test_signature_with_pseudo_code(self):
        """疑似コード付きシグネチャ"""
        spec_metadata = {
            "pseudo_code": "result = []\nfor item in data:\n    result.append(transform(item))\nreturn result"
        }

        result = build_transform_function_signature(
            func_name="transform_items",
            param_str="data: list",
            return_type="list",
            description="Transform each item",
            spec_metadata=spec_metadata,
        )

        result_text = "\n".join(result)

        assert "Pseudo Code:" in result_text
        assert "result = []" in result_text
        assert "for item in data:" in result_text

    def test_signature_with_complex_metadata(self):
        """複雑なメタデータ構造"""
        spec_metadata = {
            "logic_overview": ["Normalize provider data", "Validate completeness", "Return bundle"],
            "pseudo_code": "for batch in batches:\n    normalize(batch)\nreturn bundle",
            "dependencies": ["pandas", "numpy"],
            "notes": "Assumes UTC timestamps",
        }

        result = build_transform_function_signature(
            func_name="normalize_data",
            param_str="batches: list",
            return_type="Bundle",
            description="Normalize data from providers",
            spec_metadata=spec_metadata,
        )

        result_text = "\n".join(result)

        # 全てのメタデータセクションが含まれる
        assert "Logic Overview:" in result_text
        assert "Pseudo Code:" in result_text
        assert "Dependencies:" in result_text
        assert "Notes:" in result_text

    def test_signature_with_empty_metadata(self):
        """空のメタデータ"""
        result = build_transform_function_signature(
            func_name="simple_func",
            param_str="x: int",
            return_type="int",
            description="Simple function",
            spec_metadata={},
        )

        result_text = "\n".join(result)

        # 基本構造のみ（メタデータなし）
        assert "def simple_func(x: int) -> int:" in result_text
        assert "Logic Overview:" not in result_text
        assert "Pseudo Code:" not in result_text

    def test_signature_with_none_metadata(self):
        """Noneメタデータ"""
        result = build_transform_function_signature(
            func_name="simple_func",
            param_str="x: int",
            return_type="int",
            description="Simple function",
            spec_metadata=None,
        )

        result_text = "\n".join(result)

        # メタデータセクションが追加されない
        assert "Logic Overview:" not in result_text


class TestCheckFunctionWithMetadata:
    """Check関数のspec_metadata docstring生成テスト"""

    def test_check_function_without_metadata(self):
        """メタデータなしのCheck関数"""
        from spectool.spectool.core.base.ir import CheckSpec, SpecIR, MetaSpec
        from spectool.spectool.backends.py_skeleton_functions import generate_check_function

        check = CheckSpec(
            id="test_check",
            description="Validate data completeness",
            impl="apps.checks:validate_data",
            file_path="checks/validators.py",
            input_type_ref="dict",
        )
        ir = SpecIR(meta=MetaSpec(name="test-app"))
        imports = set()

        result = generate_check_function(check, ir, imports)

        # 基本構造の確認
        assert "def validate_data(payload: dict) -> bool:" in result
        assert "Validate data completeness" in result
        assert "TODO: Implement validate_data" in result
        # メタデータセクションがない
        assert "Logic Overview:" not in result
        assert "Validation Steps:" not in result

    def test_check_function_with_metadata(self):
        """メタデータ付きCheck関数"""
        from spectool.spectool.core.base.ir import CheckSpec, SpecIR, MetaSpec
        from spectool.spectool.backends.py_skeleton_functions import generate_check_function

        check = CheckSpec(
            id="test_check",
            description="Validate data completeness",
            impl="apps.checks:validate_data",
            file_path="checks/validators.py",
            input_type_ref="dict",
            spec_metadata={
                "validation_steps": [
                    "Check for required fields",
                    "Validate data types",
                    "Check value ranges",
                ],
                "complexity": "O(1)",
                "error_handling": "Returns False on validation failure",
            },
        )
        ir = SpecIR(meta=MetaSpec(name="test-app"))
        imports = set()

        result = generate_check_function(check, ir, imports)

        # 基本構造の確認
        assert "def validate_data(payload: dict) -> bool:" in result
        assert "Validate data completeness" in result

        # メタデータの確認
        assert "Validation Steps:" in result
        assert "- Check for required fields" in result
        assert "- Validate data types" in result
        assert "- Check value ranges" in result
        assert "Complexity: O(1)" in result
        assert "Error Handling: Returns False on validation failure" in result


class TestGeneratorFunctionWithMetadata:
    """Generator関数のspec_metadata docstring生成テスト"""

    def test_generator_function_without_metadata(self):
        """メタデータなしのGenerator関数"""
        from spectool.spectool.core.base.ir import GeneratorDef, SpecIR, MetaSpec, ParameterSpec
        from spectool.spectool.backends.py_skeleton_functions import generate_generator_function

        generator = GeneratorDef(
            id="test_gen",
            description="Generate sample data",
            impl="apps.generators:generate_sample",
            file_path="generators/data.py",
            parameters=[ParameterSpec(name="size", type_ref="builtins:int", default=10)],
            return_type_ref="builtins:list",
        )
        ir = SpecIR(meta=MetaSpec(name="test-app"))
        imports = set()

        result = generate_generator_function(generator, ir, imports)

        # 基本構造の確認
        assert "def generate_sample(size: int = 10) -> list:" in result
        assert "Generate sample data" in result
        assert "TODO: Implement generate_sample" in result
        # メタデータセクションがない
        assert "Logic Overview:" not in result
        assert "Generation Steps:" not in result

    def test_generator_function_with_metadata(self):
        """メタデータ付きGenerator関数"""
        from spectool.spectool.core.base.ir import GeneratorDef, SpecIR, MetaSpec, ParameterSpec
        from spectool.spectool.backends.py_skeleton_functions import generate_generator_function

        generator = GeneratorDef(
            id="test_gen",
            description="Generate OHLCV sample data",
            impl="apps.generators:generate_ohlcv",
            file_path="generators/data.py",
            parameters=[ParameterSpec(name="size", type_ref="builtins:int", default=100)],
            return_type_ref="DataFrame",
            spec_metadata={
                "generation_steps": [
                    "Create timestamp index",
                    "Generate random OHLCV values",
                    "Apply realistic constraints",
                ],
                "complexity": "O(n)",
                "dependencies": ["pandas", "numpy"],
                "notes": "Generated data follows realistic market patterns",
            },
        )
        ir = SpecIR(meta=MetaSpec(name="test-app"))
        imports = set()

        result = generate_generator_function(generator, ir, imports)

        # 基本構造の確認
        assert "def generate_ohlcv(size: int = 100)" in result
        assert "Generate OHLCV sample data" in result

        # メタデータの確認
        assert "Generation Steps:" in result
        assert "- Create timestamp index" in result
        assert "- Generate random OHLCV values" in result
        assert "- Apply realistic constraints" in result
        assert "Complexity: O(n)" in result
        assert "Dependencies:" in result
        assert "- pandas" in result
        assert "- numpy" in result
        assert "Notes: Generated data follows realistic market patterns" in result

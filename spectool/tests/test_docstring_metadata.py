"""Docstring metadata rendering tests

spec_metadataフィールドを使った動的なdocstring生成のテスト。
"""

import pytest
from spectool.spectool.core.base.ir import SpecMetadata
from spectool.spectool.backends.py_skeleton_codegen import (
    build_transform_function_signature,
)


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

        assert "def process_data(data: pd.DataFrame) -> pd.DataFrame:" in result
        assert "    Process input data" in result
        assert '    """' in result
        # Function-level comments and TODO lines are not added by build_transform_function_signature
        # Each function generator adds its own specific TODO comment in the implementation

    def test_signature_with_metadata(self):
        """メタデータ付きシグネチャ"""
        spec_metadata = SpecMetadata(
            logic_steps=["Step 1: Extract data", "Step 2: Transform data", "Step 3: Return result"],
            implementation_hints=["Use pandas for efficient processing"],
        )

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

        # Policyセクションの確認（explicit_checksが空）
        assert (
            "Policy: Implement straightforwardly without defensive checks or custom exception handling" in result_text
        )

        # メタデータの確認
        assert "Logic steps:" in result_text
        assert "- Step 1: Extract data" in result_text
        assert "- Step 2: Transform data" in result_text
        assert "- Step 3: Return result" in result_text
        assert "Implementation hints:" in result_text
        assert "- Use pandas for efficient processing" in result_text

    def test_signature_with_explicit_checks(self):
        """explicit_checks付きシグネチャ"""
        spec_metadata = SpecMetadata(
            logic_steps=["Fetch data from API"],
            implementation_hints=["Use requests library"],
            explicit_checks=[
                "symbols リストが空でないことを確認 → ValueError('Empty symbols')",
                "start_date < end_date を確認 → ValueError('Invalid date range')",
            ],
        )

        result = build_transform_function_signature(
            func_name="fetch_data",
            param_str="config: dict",
            return_type="DataFrame",
            description="Fetch data from API",
            spec_metadata=spec_metadata,
        )

        result_text = "\n".join(result)

        # explicit_checksセクションの確認
        assert "Explicit checks (validate only these):" in result_text
        assert "- symbols リストが空でないことを確認 → ValueError('Empty symbols')" in result_text
        assert "- start_date < end_date を確認 → ValueError('Invalid date range')" in result_text
        assert "Do NOT add other defensive checks beyond what is explicitly listed above." in result_text

    def test_signature_with_complex_metadata(self):
        """複雑なメタデータ構造"""
        spec_metadata = SpecMetadata(
            logic_steps=[
                "Normalize provider data",
                "Validate completeness",
                "Return bundle",
            ],
            implementation_hints=[
                "Use pandas and numpy for data processing",
                "Assumes UTC timestamps",
                "Each provider may have different column names",
            ],
            explicit_checks=[
                "batches リストが空でないことを確認 → ValueError('Empty batches')",
            ],
        )

        result = build_transform_function_signature(
            func_name="normalize_data",
            param_str="batches: list",
            return_type="Bundle",
            description="Normalize data from providers",
            spec_metadata=spec_metadata,
        )

        result_text = "\n".join(result)

        # 全てのメタデータセクションが含まれる
        assert "Logic steps:" in result_text
        assert "- Normalize provider data" in result_text
        assert "Implementation hints:" in result_text
        assert "- Use pandas and numpy for data processing" in result_text
        assert "Explicit checks (validate only these):" in result_text
        assert "- batches リストが空でないことを確認 → ValueError('Empty batches')" in result_text

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
        assert "# TODO: Implement validation logic" in result
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
            spec_metadata=SpecMetadata(
                logic_steps=[
                    "Check for required fields",
                    "Validate data types",
                    "Check value ranges",
                ],
                implementation_hints=[
                    "Returns False on validation failure",
                    "Time complexity: O(1)",
                ],
            ),
        )
        ir = SpecIR(meta=MetaSpec(name="test-app"))
        imports = set()

        result = generate_check_function(check, ir, imports)

        # 基本構造の確認
        assert "def validate_data(payload: dict) -> bool:" in result
        assert "Validate data completeness" in result

        # メタデータの確認
        assert "Logic steps:" in result
        assert "- Check for required fields" in result
        assert "- Validate data types" in result
        assert "- Check value ranges" in result
        assert "Implementation hints:" in result
        assert "- Returns False on validation failure" in result


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
        assert "# TODO: Implement data generation logic" in result
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
            spec_metadata=SpecMetadata(
                logic_steps=[
                    "Create timestamp index",
                    "Generate random OHLCV values",
                    "Apply realistic constraints",
                ],
                implementation_hints=[
                    "Use pandas and numpy for data generation",
                    "Generated data follows realistic market patterns",
                    "Time complexity: O(n)",
                ],
            ),
        )
        ir = SpecIR(meta=MetaSpec(name="test-app"))
        imports = set()

        result = generate_generator_function(generator, ir, imports)

        # 基本構造の確認
        assert "def generate_ohlcv(size: int = 100)" in result
        assert "Generate OHLCV sample data" in result

        # メタデータの確認
        assert "Logic steps:" in result
        assert "- Create timestamp index" in result
        assert "- Generate random OHLCV values" in result
        assert "- Apply realistic constraints" in result
        assert "Implementation hints:" in result
        assert "- Use pandas and numpy for data generation" in result
        assert "- Generated data follows realistic market patterns" in result

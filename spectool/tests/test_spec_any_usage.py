"""Spec YAML内での不適切なAny使用を検出するテスト

通常のPydanticモデルで typing:Any を使用することは型安全性を損なうため、
このテストで検出して警告する。

DataFrame型などのフレキシブルな構造では Any は許容される。
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from spectool.spectool.core.engine.loader import load_spec


def _find_any_usage_in_pydantic_models(spec_dict: dict) -> list[str]:
    """Spec内のpydantic_modelフィールドで typing:Any を使用している箇所を検出

    Args:
        spec_dict: YAMLから読み込んだspec辞書

    Returns:
        不適切なAny使用箇所のリスト（"datatype_id.field_name" 形式）
    """
    issues = []

    datatypes = spec_dict.get("datatypes", [])

    for datatype in datatypes:
        datatype_id = datatype.get("id", "unknown")

        # pydantic_modelのみチェック（type_aliasやdataframe_schemaは除外）
        if "pydantic_model" not in datatype:
            continue

        pydantic_model = datatype["pydantic_model"]
        fields = pydantic_model.get("fields", [])

        for field in fields:
            field_name = field.get("name", "unknown")
            field_type = field.get("type", {})

            # 直接 native: "typing:Any" の場合
            if field_type.get("native") == "typing:Any":
                issues.append(f"{datatype_id}.{field_name}")
                continue

            # generic型の中で typing:Any が使われている場合
            if "generic" in field_type:
                generic_def = field_type["generic"]

                # list[Any], set[Any] などの element_type チェック
                if "element_type" in generic_def:
                    element_type = generic_def["element_type"]
                    if element_type.get("native") == "typing:Any":
                        issues.append(f"{datatype_id}.{field_name}")
                        continue

                # dict[K, Any] の value_type チェック
                if "value_type" in generic_def:
                    value_type = generic_def["value_type"]
                    if value_type.get("native") == "typing:Any":
                        issues.append(f"{datatype_id}.{field_name}")
                        continue

                # dict[Any, V] の key_type チェック（まれだが念のため）
                if "key_type" in generic_def:
                    key_type = generic_def["key_type"]
                    if key_type.get("native") == "typing:Any":
                        issues.append(f"{datatype_id}.{field_name}")

    return issues


def test_detect_any_in_pydantic_models():
    """Pydanticモデルフィールドでtyping:Anyを使用していることを検出"""
    spec_yaml = """
version: "1"
meta:
  name: "test-any-detection"
  description: "Test for detecting inappropriate Any usage"

checks:
  - id: check_data
    description: "Validate data"
    impl: "apps.test-any-detection.checks.checks:check_data"
    file_path: "checks/checks.py"

datatypes:
  # ❌ 不適切: Pydanticモデルで list[Any] 使用
  - id: BadModel1
    description: "Model with list[Any]"
    check_functions:
      - check_data
    pydantic_model:
      fields:
        - name: items
          type:
            generic:
              container: list
              element_type:
                native: "typing:Any"
          description: "Bad: list of any"

  # ❌ 不適切: Pydanticモデルで Any 使用
  - id: BadModel2
    description: "Model with Any field"
    check_functions:
      - check_data
    pydantic_model:
      fields:
        - name: data
          type:
            native: "typing:Any"
          description: "Bad: any data"

  # ✅ 適切: 具体的な型を使用
  - id: GoodModel
    description: "Model with proper types"
    check_functions:
      - check_data
    pydantic_model:
      fields:
        - name: items
          type:
            generic:
              container: list
              element_type:
                native: "builtins:str"
          description: "Good: list of strings"
"""

    spec_dict = yaml.safe_load(spec_yaml)
    issues = _find_any_usage_in_pydantic_models(spec_dict)

    # BadModel1.items と BadModel2.data が検出されるべき
    assert len(issues) == 2, f"Expected 2 issues, found {len(issues)}: {issues}"
    assert "BadModel1.items" in issues
    assert "BadModel2.data" in issues
    assert "GoodModel.items" not in issues


def test_any_in_dict_value_type_detected():
    """dict[str, Any] のような使用も検出"""
    spec_yaml = """
version: "1"
meta:
  name: "test-dict-any"

checks:
  - id: check_params
    impl: "apps.test-dict-any.checks.checks:check_params"
    file_path: "checks/checks.py"

datatypes:
  - id: ParamsModel
    check_functions:
      - check_params
    pydantic_model:
      fields:
        - name: config
          type:
            generic:
              container: dict
              key_type:
                native: "builtins:str"
              value_type:
                native: "typing:Any"
"""

    spec_dict = yaml.safe_load(spec_yaml)
    issues = _find_any_usage_in_pydantic_models(spec_dict)

    assert len(issues) == 1
    assert "ParamsModel.config" in issues


def test_any_in_type_alias_not_flagged():
    """type_aliasやdataframe_schemaでのAny使用は問題ない（チェック対象外）"""
    spec_yaml = """
version: "1"
meta:
  name: "test-type-alias-any"

checks:
  - id: check_frame
    impl: "apps.test-type-alias-any.checks.checks:check_frame"
    file_path: "checks/checks.py"

datatypes:
  # ✅ type_aliasはチェック対象外（DataFrameなどフレキシブルな構造）
  - id: FlexibleFrame
    check_functions:
      - check_frame
    type_alias:
      type: simple
      target: "pandas:DataFrame"
"""

    spec_dict = yaml.safe_load(spec_yaml)
    issues = _find_any_usage_in_pydantic_models(spec_dict)

    # type_aliasはチェック対象外なので問題なし
    assert len(issues) == 0


def test_algo_trade_pipeline_has_no_any_issues():
    """algo-trade-pipeline specでPydanticモデルに不適切なAny使用がないことを確認"""
    spec_path = Path(__file__).parent.parent.parent / "specs" / "algo-trade-pipeline.yaml"

    if not spec_path.exists():
        pytest.skip(f"Spec file not found: {spec_path}")

    with open(spec_path) as f:
        spec_dict = yaml.safe_load(f)

    issues = _find_any_usage_in_pydantic_models(spec_dict)

    # 修正後は不適切なAny使用がないはず
    assert len(issues) == 0, (
        f"Found {len(issues)} inappropriate Any usage in Pydantic models:\n"
        f"{chr(10).join(f'  - {issue}' for issue in issues)}\n"
        f"Pydanticモデルのフィールドには適切な型定義を使用してください。"
    )


def test_generic_datatype_with_any_detected():
    """generic定義（TypeAlias）でのAny使用も検出（参考）

    注: このテストはgeneric datatypeのAny使用を検出しますが、
    これはdict[str, Any]のようなTypeAliasなので、
    場合によっては許容される使用法です。
    """
    spec_yaml = """
version: "1"
meta:
  name: "test-generic-any"

checks:
  - id: check_params
    impl: "apps.test-generic-any.checks.checks:check_params"
    file_path: "checks/checks.py"

datatypes:
  # generic定義（TypeAlias）: dict[str, Any]
  # これは SimpleLGBMParams のようなケース
  - id: FlexibleParams
    description: "Flexible parameters dictionary"
    check_functions:
      - check_params
    generic:
      container: dict
      key_type:
        native: "builtins:str"
      value_type:
        native: "typing:Any"
"""

    spec_dict = yaml.safe_load(spec_yaml)

    # このテストはgeneric定義なので pydantic_model チェックには引っかからない
    issues = _find_any_usage_in_pydantic_models(spec_dict)
    assert len(issues) == 0  # generic定義はPydanticモデルではない

    # generic定義のAnyチェックは別途必要に応じて実装可能


def test_generated_models_can_be_imported():
    """生成されたmodels.pyがインポートエラーなくロードできることを検証"""
    import importlib
    import sys

    project_root = Path(__file__).parent.parent.parent
    models_path = project_root / "apps" / "algo_trade_pipeline" / "models" / "models.py"

    if not models_path.exists():
        pytest.skip(f"Generated models file not found: {models_path}")

    sys.path.insert(0, str(project_root))

    try:
        # Import the generated models module
        spec = importlib.util.spec_from_file_location("test_models", models_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            raise AssertionError("Failed to create module spec")

    except Exception as e:
        raise AssertionError(
            f"Failed to import generated models.py:\n{e}\n\n"
            f"This likely means there are undefined type references in the generated code."
        ) from e
    finally:
        if str(project_root) in sys.path:
            sys.path.remove(str(project_root))


def test_generated_models_have_no_undefined_references():
    """生成されたmodels.py内で未定義の型参照がないことを確認"""
    import re

    project_root = Path(__file__).parent.parent.parent
    models_path = project_root / "apps" / "algo_trade_pipeline" / "models" / "models.py"

    if not models_path.exists():
        pytest.skip(f"Generated models file not found: {models_path}")

    content = models_path.read_text()

    # Extract all type annotations used in the file
    type_pattern = r":\s*([A-Z][a-zA-Z0-9_]*)"
    used_types = set(re.findall(type_pattern, content))

    # Find all defined types (class definitions, enums, and type aliases)
    defined_classes = set(re.findall(r"^class\s+([A-Z][a-zA-Z0-9_]*)", content, re.MULTILINE))
    defined_aliases = set(re.findall(r"^([A-Z][a-zA-Z0-9_]*)\s*=", content, re.MULTILINE))
    defined_enums = set(re.findall(r"^class\s+([A-Z][a-zA-Z0-9_]*)\(.*Enum\)", content, re.MULTILINE))

    # Find all imported types
    imported_types = set()
    for match in re.finditer(r"^from\s+[\w.]+\s+import\s+(.*?)$", content, re.MULTILINE):
        imports = match.group(1)
        for item in imports.split(","):
            item = item.strip()
            if " as " in item:
                item = item.split(" as ")[0].strip()
            imported_types.add(item)

    defined_types = defined_classes | defined_aliases | defined_enums | imported_types

    # Check for undefined types (excluding built-in types)
    builtin_types = {"BaseModel", "str", "int", "float", "list", "dict", "Enum", "IntEnum"}
    undefined = used_types - defined_types - builtin_types

    if undefined:
        raise AssertionError(
            f"Undefined type references found in models.py: {undefined}\n\n"
            f"These types are used but not defined or imported.\n"
            f"Check the spectool backend code generation logic."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""SchemaSpec統合テスト

DataFrame TypeAliasにSchemaSpecメタデータが含まれることを検証。
doc/new_packages.md の推奨設計に基づく統合テスト。
"""

import re
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from spectool.spectool.core.engine.loader import load_spec
from spectool.spectool.backends.py_skeleton import generate_skeleton


def test_dataframe_type_alias_includes_schema_spec():
    """DataFrame TypeAliasにSchemaSpecメタデータが含まれることを検証"""

    # テスト用のspec YAML
    spec_yaml = """
version: "1"
meta:
  name: "test_schema_spec"

datatypes:
  - id: TestFrame
    description: "Test DataFrame with schema constraints"
    check_functions:
      - check_test_frame
    dataframe_schema:
      index:
        name: timestamp
        dtype: datetime
        nullable: false
        unique: false
        monotonic: ""
        description: "Timestamp index"
      columns:
        - name: price
          dtype: float
          nullable: false
          description: "Price column"
        - name: volume
          dtype: int
          nullable: true
          checks:
            - type: ge
              value: 0
              description: "Volume must be non-negative"
          description: "Volume column"
      strict: false
      coerce: true

checks:
  - id: check_test_frame
    description: "Validate TestFrame"
    impl: "apps.test_schema_spec.checks.validators:check_test_frame"
    file_path: "checks/validators.py"
"""

    with TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Specファイルを作成
        spec_path = tmppath / "test_spec.yaml"
        spec_path.write_text(spec_yaml)

        # Specをロード
        ir = load_spec(spec_path)

        # スケルトンコード生成
        generate_skeleton(ir, tmppath)

        # 生成されたtypes.pyを確認
        types_file = tmppath / "apps" / "test_schema_spec" / "types.py"
        assert types_file.exists(), f"types.py が生成されていません: {types_file}"

        content = types_file.read_text()

        # 1. SchemaSpecがインポートされていることを確認
        assert "from spectool.spectool.core.base.meta_types import SchemaSpec" in content, (
            "SchemaSpecのインポートが見つかりません"
        )

        # 2. TestFrame TypeAliasが存在することを確認
        assert "TestFrame: TypeAlias = Annotated[" in content, "TestFrame TypeAliasが見つかりません"

        # 3. SchemaSpecメタデータが含まれていることを確認
        assert "SchemaSpec(" in content, "SchemaSpecメタデータが含まれていません"

        # 4. Index定義がSchemaSpecに含まれていることを確認
        assert "'name': 'timestamp'" in content, "Index名がSchemaSpecに含まれていません"
        assert "'dtype': 'datetime'" in content, "Index dtypeがSchemaSpecに含まれていません"

        # 5. Columns定義がSchemaSpecに含まれていることを確認
        assert "'name': 'price'" in content, "price列がSchemaSpecに含まれていません"
        assert "'name': 'volume'" in content, "volume列がSchemaSpecに含まれていません"

        # 6. Column checks定義がSchemaSpecに含まれていることを確認
        assert "'checks':" in content, "Column checksがSchemaSpecに含まれていません"
        assert "'type': 'ge'" in content, "Check typeがSchemaSpecに含まれていません"


def test_multiindex_dataframe_schema_spec():
    """MultiIndex DataFrameのSchemaSpec生成を検証"""

    spec_yaml = """
version: "1"
meta:
  name: "test_multiindex"

datatypes:
  - id: MultiIndexFrame
    description: "DataFrame with MultiIndex"
    dataframe_schema:
      multi_index:
        - name: symbol
          dtype: string
          enum: []
          description: "Symbol level"
        - name: timestamp
          dtype: datetime
          enum: []
          description: "Timestamp level"
      columns:
        - name: open
          dtype: float
          nullable: false
          description: "Open price"
        - name: close
          dtype: float
          nullable: false
          description: "Close price"

checks:
  - id: check_multiindex
    description: "Validate MultiIndexFrame"
    impl: "apps.test_multiindex.checks.validators:check_multiindex"
    file_path: "checks/validators.py"
"""

    with TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Specファイルを作成
        spec_path = tmppath / "test_spec.yaml"
        spec_path.write_text(spec_yaml)

        # Specをロード
        ir = load_spec(spec_path)

        # スケルトンコード生成
        generate_skeleton(ir, tmppath)

        # 生成されたtypes.pyを確認
        types_file = tmppath / "apps" / "test_multiindex" / "types.py"
        assert types_file.exists()

        content = types_file.read_text()

        # MultiIndex定義がSchemaSpecに含まれていることを確認
        assert "SchemaSpec(" in content
        assert "'name': 'symbol'" in content
        assert "'name': 'timestamp'" in content
        assert "'dtype': 'string'" in content or "'dtype': 'datetime'" in content


def test_schema_spec_with_pydantic_row_ref():
    """PydanticRowRefとSchemaSpecの共存を検証"""

    spec_yaml = """
version: "1"
meta:
  name: "test_pydantic_schema"

datatypes:
  - id: OHLCVRow
    description: "OHLCV row model"
    pydantic_model:
      fields:
        - name: timestamp
          type:
            native: "datetime:datetime"
          description: "Timestamp"
        - name: open
          type:
            native: "builtins:float"
          description: "Open price"
        - name: close
          type:
            native: "builtins:float"
          description: "Close price"

  - id: OHLCVFrame
    description: "OHLCV DataFrame with Pydantic row model"
    row_model: "OHLCVRow"
    check_functions:
      - check_ohlcv
    dataframe_schema:
      index:
        name: timestamp
        dtype: datetime
        nullable: false
        description: "Timestamp index"
      columns:
        - name: open
          dtype: float
          nullable: false
          description: "Open price"
        - name: close
          dtype: float
          nullable: false
          description: "Close price"

checks:
  - id: check_ohlcv
    description: "Validate OHLCV"
    impl: "apps.test_pydantic_schema.checks.validators:check_ohlcv"
    file_path: "checks/validators.py"
"""

    with TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Specファイルを作成
        spec_path = tmppath / "test_spec.yaml"
        spec_path.write_text(spec_yaml)

        # Specをロード
        ir = load_spec(spec_path)

        # スケルトンコード生成
        generate_skeleton(ir, tmppath)

        # 生成されたtypes.pyを確認
        types_file = tmppath / "apps" / "test_pydantic_schema" / "types.py"
        assert types_file.exists()

        content = types_file.read_text()

        # PydanticRowRefとSchemaSpecの両方が含まれていることを確認
        assert "PydanticRowRef(" in content, "PydanticRowRefが含まれていません"
        assert "SchemaSpec(" in content, "SchemaSpecが含まれていません"

        # 順序確認: PydanticRowRef -> SchemaSpec -> GeneratorSpec -> CheckedSpec
        pydantic_pos = content.find("PydanticRowRef(")
        schema_pos = content.find("SchemaSpec(")
        assert pydantic_pos < schema_pos, "PydanticRowRefがSchemaSpecより後に配置されています"


def test_generated_schema_spec_is_valid_python():
    """生成されたSchemaSpecが有効なPythonコードであることを検証"""

    spec_yaml = """
version: "1"
meta:
  name: "test_valid_python"

datatypes:
  - id: ValidFrame
    description: "Frame for Python validation"
    dataframe_schema:
      index:
        name: idx
        dtype: int
        nullable: false
      columns:
        - name: col1
          dtype: float
          nullable: false
        - name: col2
          dtype: string
          nullable: true

checks:
  - id: check_valid
    description: "Validate"
    impl: "apps.test_valid_python.checks.validators:check_valid"
    file_path: "checks/validators.py"
"""

    with TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Specファイルを作成
        spec_path = tmppath / "test_spec.yaml"
        spec_path.write_text(spec_yaml)

        # Specをロード
        ir = load_spec(spec_path)

        # スケルトンコード生成
        generate_skeleton(ir, tmppath)

        # 生成されたtypes.pyを確認
        types_file = tmppath / "apps" / "test_valid_python" / "types.py"
        assert types_file.exists()

        content = types_file.read_text()

        # Pythonとして正しくコンパイルできることを確認
        try:
            compile(content, str(types_file), "exec")
        except SyntaxError as e:
            pytest.fail(f"生成されたコードにSyntax Errorがあります: {e}\n\nContent:\n{content}")

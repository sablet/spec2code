"""生成コードの品質検証テスト

このテストは以下の問題を検出します:
1. Transform関数でAnnotated[pd.DataFrame, Check[...]]パターンの直接使用
   → types.pyで定義されたTypeAliasを使うべき
2. Pydanticモデルに残存するAny型
   → 適切な型定義があるべき
"""

import re
import tempfile
from pathlib import Path

import pytest

from spectool.spectool.core.engine.loader import load_spec
from spectool.spectool.backends.py_skeleton import generate_skeleton


def test_no_inline_annotated_check_in_transforms():
    """Transform関数でAnnotated[pd.DataFrame, Check[...]]パターンを使用していないことを確認

    DataFrame型の戻り値や引数は、types.pyで定義されたTypeAliasを使うべき。
    例: Annotated[pd.DataFrame, Check["check_ohlcv"]] ✗
         OHLCVFrame ✓
    """
    spec_yaml = """
version: "1"
meta:
  name: "test-inline-check"
  description: "Test for inline Check pattern detection"

checks:
  - id: check_ohlcv
    description: "Validate OHLCV DataFrame"
    impl: "apps.test-inline-check.checks.checks:check_ohlcv"
    file_path: "checks/checks.py"

datatypes:
  - id: OHLCVFrame
    description: "OHLCV DataFrame"
    check_functions:
      - check_ohlcv
    type_alias:
      type: simple
      target: "pandas:DataFrame"
    dataframe_schema:
      index:
        name: timestamp
        dtype: datetime
      columns:
        - name: open
          dtype: float
        - name: close
          dtype: float

transforms:
  - id: process_data
    description: "Process OHLCV data"
    impl: "apps.test-inline-check.transforms.ops:process_data"
    file_path: "transforms/ops.py"
    parameters:
      - name: df
        datatype_ref: OHLCVFrame
    return_type_ref: OHLCVFrame
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # YAMLファイルを作成
        spec_file = tmppath / "test_spec.yaml"
        spec_file.write_text(spec_yaml, encoding="utf-8")

        # YAMLをロードしてIR生成
        ir = load_spec(spec_file)

        # スケルトンコード生成
        generate_skeleton(ir, tmppath)

        # 生成されたtransforms/ops.pyを読み込み
        transforms_file = tmppath / "apps" / "test_inline_check" / "transforms" / "ops.py"
        assert transforms_file.exists(), f"Transform file not found: {transforms_file}"

        content = transforms_file.read_text()

        # Annotated[pd.DataFrame, Check[...]]パターンを検出
        # 正規表現: Annotated\s*\[\s*pd\.DataFrame\s*,\s*Check\[
        inline_check_pattern = r"Annotated\s*\[\s*pd\.DataFrame\s*,\s*Check\["

        matches = list(re.finditer(inline_check_pattern, content))

        if matches:
            # マッチした行を抽出して詳細エラーメッセージを作成
            lines = content.split("\n")
            error_details = []
            for match in matches:
                # マッチ位置から行番号を特定
                line_num = content[: match.start()].count("\n") + 1
                error_details.append(f"  Line {line_num}: {lines[line_num - 1].strip()}")

            pytest.fail(
                f"Found {len(matches)} inline 'Annotated[pd.DataFrame, Check[...]]' pattern(s) in transforms.\n"
                f"These should use TypeAlias from types.py instead:\n" + "\n".join(error_details)
            )


def test_no_any_in_pydantic_models():
    """Pydanticモデルフィールドに'Any'型が残存していないことを確認

    適切な型定義があるべき。ただし、YAMLで明示的に"typing:Any"と指定された場合は除く。
    このテストは、generic型などで型解決に失敗してAnyになるコード生成の不備を検出する。
    """
    spec_yaml = """
version: "1"
meta:
  name: "test-any-detection"
  description: "Test for Any type detection in Pydantic models"

checks:
  - id: check_config
    description: "Validate config"
    impl: "apps.test-any-detection.checks.checks:check_config"
    file_path: "checks/checks.py"

datatypes:
  - id: ConfigModel
    description: "Configuration model"
    check_functions:
      - check_config
    pydantic_model:
      fields:
        - name: symbols
          type:
            generic:
              container: list
              element_type:
                native: "builtins:str"
          description: "List of symbols"
        - name: start_date
          type:
            native: "builtins:str"
          description: "Start date"
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # YAMLファイルを作成
        spec_file = tmppath / "test_spec.yaml"
        spec_file.write_text(spec_yaml, encoding="utf-8")

        # YAMLをロードしてIR生成
        ir = load_spec(spec_file)

        # スケルトンコード生成
        generate_skeleton(ir, tmppath)

        # 生成されたmodels/models.pyを読み込み
        models_file = tmppath / "apps" / "test_any_detection" / "models" / "models.py"
        assert models_file.exists(), f"Models file not found: {models_file}"

        content = models_file.read_text()

        # 'Any'型の使用を検出（importと定義の両方）
        # フィールド定義でのAny使用: ": Any" または "typing.Any"
        any_field_pattern = r":\s*(?:typing\.)?Any(?:\s|$|,)"

        matches = list(re.finditer(any_field_pattern, content))

        if matches:
            # マッチした行を抽出
            lines = content.split("\n")
            error_details = []
            for match in matches:
                line_num = content[: match.start()].count("\n") + 1
                error_details.append(f"  Line {line_num}: {lines[line_num - 1].strip()}")

            pytest.fail(
                f"Found {len(matches)} 'Any' type(s) in Pydantic model fields.\n"
                f"All fields should have proper type definitions:\n" + "\n".join(error_details)
            )


def test_algo_trade_pipeline_quality():
    """algo-trade-pipelineの実際の生成コードで品質チェック

    既存のalgo-trade-pipeline specを使用して、実際の問題を検出する。

    修正後: 不適切なAny使用は全て削除され、適切な型定義に置き換えられています。
    """
    spec_path = Path(__file__).parent.parent.parent / "specs" / "algo-trade-pipeline.yaml"

    if not spec_path.exists():
        pytest.skip(f"Spec file not found: {spec_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # YAMLをロードしてIR生成
        ir = load_spec(spec_path)

        # スケルトンコード生成
        generate_skeleton(ir, tmppath)

        app_name = "algo_trade_pipeline"

        # 1. transforms/features.pyでのinline Check検出
        features_file = tmppath / "apps" / app_name / "transforms" / "features.py"
        if features_file.exists():
            content = features_file.read_text()
            inline_check_pattern = r"Annotated\s*\[\s*pd\.DataFrame\s*,\s*Check\["
            matches = list(re.finditer(inline_check_pattern, content))

            assert len(matches) == 0, (
                f"Found {len(matches)} inline 'Annotated[pd.DataFrame, Check[...]]' in features.py. "
                f"Should use TypeAlias from types.py instead."
            )

        # 2. models/models.pyでのAny型検出
        models_file = tmppath / "apps" / app_name / "models" / "models.py"
        if models_file.exists():
            content = models_file.read_text()

            # Anyがフィールド型として使われているかチェック
            # importは除外して、実際のフィールド定義のみをチェック
            lines = content.split("\n")
            any_field_lines = []

            for i, line in enumerate(lines, 1):
                # "from typing import Any"などのimport行をスキップ
                if "import" in line.lower():
                    continue
                # フィールド定義でAnyを使用している行を検出
                # list[Any], dict[str, Any], または単体のAnyを検出
                if re.search(r":\s*(?:list\[)?(?:dict\[.+,\s*)?(?:typing\.)?Any(?:\])?(?:\s|$|,|\])", line):
                    any_field_lines.append(f"  Line {i}: {line.strip()}")

            # 修正後: Pydanticモデルに不適切なAny使用はない
            # - ProviderBatchCollection.batches: list[DataFrame] (修正済み)
            # - NormalizedOHLCVBundle.data: MultiAssetOHLCVFrame (修正済み)
            # - CVResult.fold_results: list[FoldResult] (修正済み)
            expected_any_count = 0
            assert len(any_field_lines) == expected_any_count, (
                f"Found {len(any_field_lines)} 'Any' type(s) in Pydantic model fields "
                f"(expected {expected_any_count} - all should use proper types):\n" + "\n".join(any_field_lines)
            )


def test_generator_spec_annotation():
    """types.pyでGeneratorSpecアノテーションが正しく付与されていることを確認

    generatorsのreturn_type_refで参照されている型には、GeneratorSpec(...) が付与されるべき。
    """
    spec_yaml = """
version: "1"
meta:
  name: "test-generator-spec"
  description: "Test for GeneratorSpec annotation"

checks:
  - id: check_data
    description: "Validate data"
    impl: "apps.test-generator-spec.checks.checks:check_data"
    file_path: "checks/checks.py"

datatypes:
  - id: DataModel
    description: "Data model"
    check_functions:
      - check_data
    pydantic_model:
      fields:
        - name: value
          type:
            native: "builtins:int"

  - id: ResultFrame
    description: "Result DataFrame"
    check_functions:
      - check_data
    dataframe_schema:
      index:
        name: timestamp
        dtype: datetime
      columns:
        - name: value
          dtype: float

generators:
  - id: gen_data_model
    description: "Generate DataModel"
    impl: "apps.test-generator-spec.generators.gen:gen_data_model"
    file_path: "generators/gen.py"
    return_type_ref: DataModel

  - id: gen_result_frame
    description: "Generate ResultFrame"
    impl: "apps.test-generator-spec.generators.gen:gen_result_frame"
    file_path: "generators/gen.py"
    return_type_ref: ResultFrame
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # YAMLファイルを作成
        spec_file = tmppath / "test_spec.yaml"
        spec_file.write_text(spec_yaml, encoding="utf-8")

        # YAMLをロードしてIR生成
        ir = load_spec(spec_file)

        # スケルトンコード生成
        generate_skeleton(ir, tmppath)

        # 生成されたtypes.pyを読み込み
        types_file = tmppath / "apps" / "test_generator_spec" / "types.py"
        assert types_file.exists(), f"Types file not found: {types_file}"

        content = types_file.read_text()

        # DataModelTypeにGeneratorSpecが付与されていることを確認
        assert "DataModelType: TypeAlias = Annotated[" in content, "DataModelType should be Annotated"
        assert 'GeneratorSpec(generators=["gen_data_model"])' in content, (
            "DataModelType should have GeneratorSpec with gen_data_model"
        )

        # ResultFrameにGeneratorSpecが付与されていることを確認
        assert "ResultFrame: TypeAlias = Annotated[" in content, "ResultFrame should be Annotated"
        assert 'GeneratorSpec(generators=["gen_result_frame"])' in content, (
            "ResultFrame should have GeneratorSpec with gen_result_frame"
        )

        # GeneratorSpecのインポートが含まれていることを確認
        assert "from spectool.spectool.core.base.meta_types import" in content
        assert "GeneratorSpec" in content


def test_algo_trade_pipeline_generator_spec_coverage():
    """algo-trade-pipelineの全generator return_typeにGeneratorSpecが付与されていることを確認"""
    spec_path = Path(__file__).parent.parent.parent / "specs" / "algo-trade-pipeline.yaml"

    if not spec_path.exists():
        pytest.skip(f"Spec file not found: {spec_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # YAMLをロードしてIR生成
        ir = load_spec(spec_path)

        # スケルトンコード生成
        generate_skeleton(ir, tmppath)

        app_name = "algo_trade_pipeline"

        # 生成されたtypes.pyを読み込み
        types_file = tmppath / "apps" / app_name / "types.py"
        assert types_file.exists(), f"Types file not found: {types_file}"

        content = types_file.read_text()

        # generatorsから期待されるマッピングを構築
        expected_generator_map = {}
        for gen in ir.generators:
            if gen.return_type_ref:
                if gen.return_type_ref not in expected_generator_map:
                    expected_generator_map[gen.return_type_ref] = []
                expected_generator_map[gen.return_type_ref].append(gen.id)

        # types.pyに存在する型のみチェック
        # TypeAliasやGenericはtypes.pyに含まれないため、Pydantic/Enum/Frameのみをチェック
        datatype_ids_in_types = set()
        for model in ir.pydantic_models:
            datatype_ids_in_types.add(model.id)
        for enum in ir.enums:
            datatype_ids_in_types.add(enum.id)
        for frame in ir.frames:
            datatype_ids_in_types.add(frame.id)

        missing_generator_specs = []
        for datatype_id, generator_ids in expected_generator_map.items():
            # types.pyに存在しない型はスキップ
            if datatype_id not in datatype_ids_in_types:
                continue

            # GeneratorSpecが含まれているか確認
            # 生成コードでは["gen_xxx"]のような形式（ダブルクォート）
            generators_str = ", ".join(f'"{gid}"' for gid in generator_ids)
            expected_generator_spec = f"GeneratorSpec(generators=[{generators_str}])"
            if expected_generator_spec not in content:
                missing_generator_specs.append(f"{datatype_id}: {generator_ids}")

        assert len(missing_generator_specs) == 0, (
            f"Missing GeneratorSpec annotations for {len(missing_generator_specs)} datatype(s):\n"
            + "\n".join(f"  - {spec}" for spec in missing_generator_specs)
        )


def test_generated_models_are_importable():
    """生成されたPydanticモデルがインポート可能であることを確認

    Any型やdatetime型などを使う場合、適切なimportが含まれているべき。
    """
    spec_yaml = """
version: "1"
meta:
  name: "test-importable"
  description: "Test for importable models"

checks:
  - id: check_data
    description: "Validate data"
    impl: "apps.test-importable.checks.checks:check_data"
    file_path: "checks/checks.py"

datatypes:
  - id: DataWithAny
    description: "Model with Any field"
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
          description: "List of any items"
        - name: created_at
          type:
            native: "datetime:datetime"
          description: "Creation timestamp"
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # YAMLファイルを作成
        spec_file = tmppath / "test_spec.yaml"
        spec_file.write_text(spec_yaml, encoding="utf-8")

        # YAMLをロードしてIR生成
        ir = load_spec(spec_file)

        # スケルトンコード生成
        generate_skeleton(ir, tmppath)

        # 生成されたmodels/models.pyを読み込み
        models_file = tmppath / "apps" / "test_importable" / "models" / "models.py"
        assert models_file.exists(), f"Models file not found: {models_file}"

        content = models_file.read_text()

        # 必要なimportが含まれていることを確認
        assert "from typing import Any" in content, "Missing 'from typing import Any'"
        assert "from datetime import datetime" in content, "Missing 'from datetime import datetime'"

        # Pythonコードとして実行可能か確認（import可能か）
        import sys

        sys.path.insert(0, str(tmppath))
        try:
            # importを試行
            import importlib.util

            spec = importlib.util.spec_from_file_location("test_models", models_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # クラスが定義されていることを確認
                assert hasattr(module, "DataWithAny"), "DataWithAny class not found"
        finally:
            sys.path.pop(0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

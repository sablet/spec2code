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
        inline_check_pattern = r'Annotated\s*\[\s*pd\.DataFrame\s*,\s*Check\['

        matches = list(re.finditer(inline_check_pattern, content))

        if matches:
            # マッチした行を抽出して詳細エラーメッセージを作成
            lines = content.split('\n')
            error_details = []
            for match in matches:
                # マッチ位置から行番号を特定
                line_num = content[:match.start()].count('\n') + 1
                error_details.append(f"  Line {line_num}: {lines[line_num - 1].strip()}")

            pytest.fail(
                f"Found {len(matches)} inline 'Annotated[pd.DataFrame, Check[...]]' pattern(s) in transforms.\n"
                f"These should use TypeAlias from types.py instead:\n"
                + "\n".join(error_details)
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
        any_field_pattern = r':\s*(?:typing\.)?Any(?:\s|$|,)'

        matches = list(re.finditer(any_field_pattern, content))

        if matches:
            # マッチした行を抽出
            lines = content.split('\n')
            error_details = []
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                error_details.append(f"  Line {line_num}: {lines[line_num - 1].strip()}")

            pytest.fail(
                f"Found {len(matches)} 'Any' type(s) in Pydantic model fields.\n"
                f"All fields should have proper type definitions:\n"
                + "\n".join(error_details)
            )


def test_algo_trade_pipeline_quality():
    """algo-trade-pipelineの実際の生成コードで品質チェック

    既存のalgo-trade-pipeline specを使用して、実際の問題を検出する。

    注意: NormalizedOHLCVBundle.dataフィールドは意図的に"typing:Any"と定義されているため、
    Any型が1つ残ることは正常です。このテストでは許容範囲を1に設定します。
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
            inline_check_pattern = r'Annotated\s*\[\s*pd\.DataFrame\s*,\s*Check\['
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
            lines = content.split('\n')
            any_field_lines = []

            for i, line in enumerate(lines, 1):
                # "from typing import Any"などのimport行をスキップ
                if 'import' in line.lower():
                    continue
                # フィールド定義でAnyを使用している行を検出
                if re.search(r':\s*(?:typing\.)?Any(?:\s|$|,)', line):
                    any_field_lines.append(f"  Line {i}: {line.strip()}")

            # NormalizedOHLCVBundle.dataは意図的にtyping:Anyなので、最大1つまで許容
            assert len(any_field_lines) <= 1, (
                f"Found {len(any_field_lines)} 'Any' type(s) in Pydantic model fields "
                f"(expected at most 1 for NormalizedOHLCVBundle.data):\n"
                + "\n".join(any_field_lines)
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

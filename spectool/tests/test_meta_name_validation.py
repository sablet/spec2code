"""meta.nameのバリデーションテスト

meta.nameにハイフンが含まれている場合にエラーになることを確認する。
"""

import subprocess
import sys
from pathlib import Path

import pytest


class TestMetaNameValidation:
    """meta.nameのバリデーションテスト"""

    def test_meta_name_with_hyphen_raises_error(self, tmp_path: Path):
        """meta.nameにハイフンが含まれているとエラーになる"""
        spec_content = """version: "1.0"
meta:
  name: my-invalid-project
  description: "Test project with hyphen in name"

datatypes:
  - id: TestFrame
    dataframe_schema:
      index:
        name: idx
        dtype: int
        nullable: false
      columns:
        - name: value
          dtype: float
          nullable: false
"""
        spec_path = tmp_path / "invalid_spec.yaml"
        spec_path.write_text(spec_content)

        # validateコマンドでエラーになることを確認
        result = subprocess.run(
            [sys.executable, "-m", "spectool", "validate", str(spec_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "hyphen" in result.stdout.lower() or "-" in result.stdout
        assert "my_invalid_project" in result.stdout  # 修正案が表示される

    def test_meta_name_with_underscore_succeeds(self, tmp_path: Path):
        """meta.nameにアンダースコアのみが含まれている場合は成功する"""
        spec_content = """version: "1.0"
meta:
  name: my_valid_project
  description: "Test project with underscore in name"

datatypes:
  - id: TestFrame
    dataframe_schema:
      index:
        name: idx
        dtype: int
        nullable: false
      columns:
        - name: value
          dtype: float
          nullable: false
"""
        spec_path = tmp_path / "valid_spec.yaml"
        spec_path.write_text(spec_content)

        # validateコマンドで成功することを確認
        result = subprocess.run(
            [sys.executable, "-m", "spectool", "validate", str(spec_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "✅" in result.stdout

    def test_gen_with_hyphen_in_name_fails(self, tmp_path: Path):
        """genコマンドでもmeta.nameにハイフンがあるとエラーになる"""
        spec_content = """version: "1.0"
meta:
  name: invalid-gen-project
  description: "Test project"

datatypes:
  - id: TestFrame
    dataframe_schema:
      index:
        name: idx
        dtype: int
        nullable: false
      columns:
        - name: value
          dtype: float
          nullable: false
"""
        spec_path = tmp_path / "invalid_spec.yaml"
        spec_path.write_text(spec_content)

        # genコマンドでエラーになることを確認（検証段階で失敗）
        result = subprocess.run(
            [sys.executable, "-m", "spectool", "gen", str(spec_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "hyphen" in result.stdout.lower() or "-" in result.stdout


class TestMetaNameEdgeCases:
    """meta.nameのエッジケーステスト"""

    def test_meta_name_empty_string(self, tmp_path: Path):
        """meta.nameが空文字列の場合（エラーにはならないがデフォルト名が使われる）"""
        spec_content = """version: "1.0"
meta:
  name: ""
  description: "Test project"

datatypes:
  - id: TestFrame
    dataframe_schema:
      index:
        name: idx
        dtype: int
        nullable: false
      columns:
        - name: value
          dtype: float
          nullable: false
"""
        spec_path = tmp_path / "empty_name_spec.yaml"
        spec_path.write_text(spec_content)

        result = subprocess.run(
            [sys.executable, "-m", "spectool", "validate", str(spec_path)],
            capture_output=True,
            text=True,
        )
        # 空文字列はエラーにならない（デフォルト名が使われる）
        assert result.returncode == 0

    def test_meta_name_with_multiple_hyphens(self, tmp_path: Path):
        """meta.nameに複数のハイフンが含まれている場合"""
        spec_content = """version: "1.0"
meta:
  name: my-very-invalid-project-name
  description: "Test project"

datatypes:
  - id: TestFrame
    dataframe_schema:
      index:
        name: idx
        dtype: int
        nullable: false
      columns:
        - name: value
          dtype: float
          nullable: false
"""
        spec_path = tmp_path / "multi_hyphen_spec.yaml"
        spec_path.write_text(spec_content)

        result = subprocess.run(
            [sys.executable, "-m", "spectool", "validate", str(spec_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "hyphen" in result.stdout.lower()
        # 修正案が表示される
        assert "my_very_invalid_project_name" in result.stdout

    def test_meta_name_with_mixed_separators(self, tmp_path: Path):
        """meta.nameにハイフンとアンダースコアが混在している場合"""
        spec_content = """version: "1.0"
meta:
  name: my_mixed-project_name
  description: "Test project"

datatypes:
  - id: TestFrame
    dataframe_schema:
      index:
        name: idx
        dtype: int
        nullable: false
      columns:
        - name: value
          dtype: float
          nullable: false
"""
        spec_path = tmp_path / "mixed_spec.yaml"
        spec_path.write_text(spec_content)

        result = subprocess.run(
            [sys.executable, "-m", "spectool", "validate", str(spec_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "hyphen" in result.stdout.lower()

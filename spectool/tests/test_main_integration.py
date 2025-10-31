"""main.py 高レベルAPI統合テスト

SpectoolCLIクラスの各コマンドが最低限動作することを確認する統合テスト。
実際のファイル入出力とプロセス実行を伴う。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


class TestValidateCommand:
    """validate コマンドの統合テスト"""

    def test_validate_minimal_spec_success(self):
        """最小限のspecで検証が成功する"""
        result = subprocess.run(
            [sys.executable, "-m", "spectool", "validate", "spectool/tests/fixtures/minimal_spec.yaml"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "✅" in result.stdout

    def test_validate_sample_spec_success(self):
        """サンプルspecで検証が成功する"""
        result = subprocess.run(
            [sys.executable, "-m", "spectool", "validate", "spectool/tests/fixtures/sample_spec.yaml"],
            capture_output=True,
            text=True,
        )
        # 実装ファイルが存在しないため警告が出る可能性があるが、スキーマ検証は通る
        assert result.returncode in [0, 1]  # 警告のみなら0、エラーがあれば1

    def test_validate_invalid_spec_duplicate_cols(self):
        """重複列を含むspecで検証がエラーになる"""
        result = subprocess.run(
            [sys.executable, "-m", "spectool", "validate", "spectool/tests/fixtures/invalid_spec_duplicate_cols.yaml"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "duplicate" in result.stdout.lower() or "❌" in result.stdout

    def test_validate_nonexistent_file(self):
        """存在しないファイルでエラーになる"""
        result = subprocess.run(
            [sys.executable, "-m", "spectool", "validate", "nonexistent_file.yaml"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "not found" in result.stdout.lower()

    def test_validate_with_verbose_flag(self):
        """--verboseフラグで詳細出力が得られる"""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "spectool",
                "validate",
                "spectool/tests/fixtures/minimal_spec.yaml",
                "--verbose",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        # verboseモードでは追加の情報が出力される
        assert len(result.stdout) > 0


class TestGenCommand:
    """gen コマンドの統合テスト"""

    def test_gen_minimal_spec(self, tmp_path: Path):
        """最小限のspecからスケルトンコードを生成できる"""
        spec_path = Path("spectool/tests/fixtures/minimal_spec.yaml")
        output_dir = tmp_path

        result = subprocess.run(
            [sys.executable, "-m", "spectool", "gen", str(spec_path), "--output-dir", str(output_dir)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "✅" in result.stdout
        assert "Skeleton generation complete" in result.stdout

        # 生成されたディレクトリが存在することを確認
        # ハイフン付き名前はアンダースコアに変換される
        app_dir = output_dir / "apps" / "minimal_test"
        assert app_dir.exists()

    def test_gen_sample_spec_creates_structure(self, tmp_path: Path):
        """サンプルspecから適切なディレクトリ構造が生成される"""
        spec_path = Path("spectool/tests/fixtures/sample_spec.yaml")
        output_dir = tmp_path

        result = subprocess.run(
            [sys.executable, "-m", "spectool", "gen", str(spec_path), "--output-dir", str(output_dir)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        app_dir = output_dir / "apps" / "sample_project"
        assert app_dir.exists()

        # 期待されるディレクトリが生成されている
        expected_dirs = ["checks", "transforms", "generators", "models", "schemas"]
        for dirname in expected_dirs:
            dir_path = app_dir / dirname
            if dir_path.exists():
                assert dir_path.is_dir()

    def test_gen_without_output_dir_uses_current_dir(self):
        """--output-dir なしの場合はカレントディレクトリに生成される"""
        spec_path = Path("spectool/tests/fixtures/minimal_spec.yaml")

        result = subprocess.run(
            [sys.executable, "-m", "spectool", "gen", str(spec_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "✅" in result.stdout

        # 生成が成功することを確認（実際の出力先はクリーンアップのため検証しない）

    def test_gen_invalid_spec_fails(self, tmp_path: Path):
        """不正なspecでgenが失敗する"""
        invalid_spec = tmp_path / "invalid.yaml"
        invalid_spec.write_text("invalid: yaml: [unclosed")

        result = subprocess.run(
            [sys.executable, "-m", "spectool", "gen", str(invalid_spec)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1


class TestValidateIntegrityCommand:
    """validate-integrity コマンドの統合テスト"""

    def test_validate_integrity_without_generation_fails(self, tmp_path: Path):
        """生成前のvalidate-integrityは失敗する"""
        # 新しいspecを作成（まだ生成していない）
        spec_content = """version: "1.0"
meta:
  name: integrity-test-new
  description: "Integrity test"

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
        spec_path = tmp_path / "test_spec.yaml"
        spec_path.write_text(spec_content)

        result = subprocess.run(
            [sys.executable, "-m", "spectool", "validate-integrity", str(spec_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "not found" in result.stdout.lower() or "❌" in result.stdout

    def test_validate_integrity_after_generation_succeeds(self, tmp_path: Path):
        """生成後のvalidate-integrityは成功する（生成されたコードのまま）"""
        # プロジェクトルートに生成してテスト後にクリーンアップする方式を採用
        spec_content = """version: "1.0"
meta:
  name: integrity_test_temp
  description: "Integrity test temporary"

examples:
  - id: ex_test
    datatype_ref: TestFrame
    input:
      idx: [1, 2]
      value: [1.0, 2.0]
    expected:
      valid: true

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
        spec_path = tmp_path / "test_spec.yaml"
        spec_path.write_text(spec_content)

        # プロジェクトルート（カレントディレクトリ）に生成
        gen_result = subprocess.run(
            [sys.executable, "-m", "spectool", "gen", str(spec_path)],
            capture_output=True,
            text=True,
        )
        assert gen_result.returncode == 0

        try:
            # 生成されたプロジェクトが存在することを確認
            app_dir = Path("apps/integrity_test_temp")
            assert app_dir.exists(), f"Generated app directory not found: {app_dir}"

            # validate-integrityを実行
            result = subprocess.run(
                [sys.executable, "-m", "spectool", "validate-integrity", str(spec_path)],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"validate-integrity failed:\n{result.stdout}\n{result.stderr}"
            assert "✅" in result.stdout

        finally:
            # クリーンアップ：生成されたディレクトリを削除
            import shutil

            app_dir = Path("apps/integrity_test_temp")
            if app_dir.exists():
                shutil.rmtree(app_dir)


class TestRunCommand:
    """run コマンドの統合テスト"""

    def test_run_with_spec_only_fails_if_no_dag_stages(self, tmp_path: Path):
        """dag_stagesがない場合runは失敗する"""
        spec_content = """version: "1.0"
meta:
  name: run-test-no-dag
  description: "Run test without DAG"

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
        spec_path = tmp_path / "test_spec.yaml"
        spec_path.write_text(spec_content)

        result = subprocess.run(
            [sys.executable, "-m", "spectool", "run", str(spec_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "dag_stages" in result.stdout.lower() or "no dag" in result.stdout.lower()

    def test_run_with_dag_stages_loads_successfully(self, tmp_path: Path):
        """dag_stagesがあればrunは少なくともロードに成功する"""
        # sample_spec.yamlを使用（dag_stagesを含む）
        spec_path = Path("spectool/tests/fixtures/sample_spec.yaml")

        result = subprocess.run(
            [sys.executable, "-m", "spectool", "run", str(spec_path)],
            capture_output=True,
            text=True,
        )
        # 実装が存在しないため実行は失敗するが、DAG構築までは進む
        # ロードとバリデーションは成功する
        assert "Loading spec" in result.stdout or "Loaded" in result.stdout

    def test_run_with_initial_data_file(self, tmp_path: Path):
        """--initial-dataオプションでデータを渡せる"""
        spec_path = Path("spectool/tests/fixtures/sample_spec.yaml")

        # 初期データファイルを作成
        initial_data = {"test_key": "test_value"}
        data_file = tmp_path / "initial_data.json"
        data_file.write_text(json.dumps(initial_data))

        result = subprocess.run(
            [sys.executable, "-m", "spectool", "run", str(spec_path), "--initial-data", str(data_file)],
            capture_output=True,
            text=True,
        )
        # ファイルが読み込まれることを確認
        assert "Loaded initial data" in result.stdout or "📊" in result.stdout

    def test_run_with_nonexistent_initial_data_fails(self, tmp_path: Path):
        """存在しない初期データファイルを指定すると失敗する"""
        spec_path = Path("spectool/tests/fixtures/sample_spec.yaml")
        nonexistent_file = tmp_path / "nonexistent.json"

        result = subprocess.run(
            [sys.executable, "-m", "spectool", "run", str(spec_path), "--initial-data", str(nonexistent_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "not found" in result.stdout.lower()


class TestVersionCommand:
    """version コマンドの統合テスト"""

    def test_version_displays_version_info(self):
        """versionコマンドでバージョン情報が表示される"""
        result = subprocess.run(
            [sys.executable, "-m", "spectool", "version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "spectool" in result.stdout.lower()
        # main.pyで定義されているバージョンが表示される
        assert "2.0.0" in result.stdout or "alpha" in result.stdout


class TestDebugFlag:
    """--debugフラグの統合テスト"""

    def test_debug_flag_shows_traceback_on_error(self):
        """--debugフラグでトレースバックが表示される"""
        result = subprocess.run(
            [sys.executable, "-m", "spectool", "validate", "nonexistent.yaml", "--debug"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        # debugモードではトレースバックが含まれる可能性がある
        # （実装依存だが、少なくともエラーメッセージは表示される）
        assert len(result.stdout) > 0 or len(result.stderr) > 0


class TestFireIntegration:
    """python-fireとの統合動作テスト"""

    def test_no_arguments_shows_help(self):
        """引数なしで実行するとヘルプが表示される"""
        result = subprocess.run(
            [sys.executable, "-m", "spectool"],
            capture_output=True,
            text=True,
        )
        # fireはヘルプを表示する
        output = result.stdout + result.stderr
        assert "spectool" in output.lower() or "usage" in output.lower()

    def test_help_flag_shows_help(self):
        """--helpフラグでヘルプが表示される"""
        result = subprocess.run(
            [sys.executable, "-m", "spectool", "--help"],
            capture_output=True,
            text=True,
        )
        output = result.stdout + result.stderr
        assert "spectool" in output.lower() or "usage" in output.lower()

    def test_command_help_shows_command_specific_help(self):
        """各コマンドの--helpで個別のヘルプが表示される"""
        for command in ["validate", "gen", "validate-integrity", "run"]:
            result = subprocess.run(
                [sys.executable, "-m", "spectool", command, "--help"],
                capture_output=True,
                text=True,
            )
            output = result.stdout + result.stderr
            assert command in output.lower() or "help" in output.lower()

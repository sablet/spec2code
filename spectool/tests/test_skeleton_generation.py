"""スケルトンコード生成のテスト

packages/tests/test_dataframe_generation.pyに相当する機能をspectoolで実装するためのテスト。
Check関数、Transform関数、Generator関数のスケルトンコード生成を検証する。
"""

from pathlib import Path
import tempfile
import pytest

from spectool.spectool.core.engine.loader import load_spec
from spectool.spectool.core.base.ir import SpecIR


# スケルトン生成機能（未実装）をインポート
# TODO: この機能を実装する必要がある
try:
    from spectool.spectool.backends.py_skeleton import generate_skeleton
except ImportError:
    # 未実装の場合、プレースホルダー関数を定義
    def generate_skeleton(ir: SpecIR, output_dir: Path) -> None:
        """スケルトン生成のプレースホルダー（未実装）"""
        raise NotImplementedError("Skeleton generation not yet implemented in spectool")


@pytest.fixture
def sample_spec_path():
    """サンプルspec YAMLのパス"""
    return Path(__file__).parent / "fixtures" / "sample_spec.yaml"


@pytest.fixture
def temp_output_dir():
    """一時出力ディレクトリ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_spec_loads_correctly(sample_spec_path):
    """Specが正しくロードできることを確認"""
    ir = load_spec(sample_spec_path)

    # メタ情報の確認
    assert ir.meta.name == "sample_project"

    # DataType定義の確認
    assert len(ir.frames) >= 1
    assert ir.frames[0].id == "TimeSeriesFrame"

    # Transform定義の確認
    assert len(ir.transforms) >= 1
    assert ir.transforms[0].id == "process_data"


def test_generate_check_function_skeletons(sample_spec_path, temp_output_dir):
    """Check関数のスケルトンが生成されることを確認"""
    ir = load_spec(sample_spec_path)
    generate_skeleton(ir, temp_output_dir)

    # Check関数ファイルが生成されることを確認
    check_file = temp_output_dir / "apps" / "sample_project" / "checks" / "validators.py"
    assert check_file.exists()

    content = check_file.read_text()

    # validate_positive関数が生成されていることを確認
    assert "def validate_positive(payload: dict) -> bool:" in content
    assert "TODO" in content  # スケルトンにはTODOコメントが含まれる


def test_generate_transform_function_skeletons(sample_spec_path, temp_output_dir):
    """Transform関数のスケルトンが生成されることを確認"""
    ir = load_spec(sample_spec_path)
    generate_skeleton(ir, temp_output_dir)

    # Transform関数ファイルが生成されることを確認
    transform_file = temp_output_dir / "apps" / "sample_project" / "transforms" / "processors.py"
    assert transform_file.exists()

    content = transform_file.read_text()

    # process_data関数が生成されていることを確認
    assert "def process_data(" in content
    assert "data:" in content  # パラメータ名
    assert "threshold:" in content  # パラメータ名
    assert "-> " in content  # 戻り値型アノテーション

    # 型アノテーションの確認
    assert "from typing import Annotated" in content

    # TODOコメントの確認
    assert "TODO" in content


def test_generate_generator_function_skeletons(sample_spec_path, temp_output_dir):
    """Generator関数のスケルトンが生成されることを確認"""
    ir = load_spec(sample_spec_path)
    generate_skeleton(ir, temp_output_dir)

    # Generator関数ファイルが生成されることを確認
    generator_file = temp_output_dir / "apps" / "sample_project" / "generators" / "data_generators.py"
    assert generator_file.exists()

    content = generator_file.read_text()

    # generate_timeseries関数が生成されていることを確認
    assert "def generate_timeseries(" in content
    assert "-> " in content  # 戻り値型アノテーション


def test_generated_code_has_type_annotations(sample_spec_path, temp_output_dir):
    """生成されたコードに正しい型アノテーションが含まれることを確認"""
    ir = load_spec(sample_spec_path)
    generate_skeleton(ir, temp_output_dir)

    transform_file = temp_output_dir / "apps" / "sample_project" / "transforms" / "processors.py"
    content = transform_file.read_text()

    # 型アノテーションの確認
    assert "Annotated[" in content

    # パラメータの型アノテーション
    assert "data: Annotated[" in content

    # 戻り値の型アノテーション
    assert "-> Annotated[" in content


def test_generated_directory_structure(sample_spec_path, temp_output_dir):
    """生成されたディレクトリ構造が正しいことを確認"""
    ir = load_spec(sample_spec_path)
    generate_skeleton(ir, temp_output_dir)

    app_root = temp_output_dir / "apps" / "sample_project"

    # ディレクトリ構造の確認
    assert (app_root / "checks").exists()
    assert (app_root / "transforms").exists()
    assert (app_root / "generators").exists()

    # __init__.pyファイルの確認
    assert (app_root / "checks" / "__init__.py").exists()
    assert (app_root / "transforms" / "__init__.py").exists()
    assert (app_root / "generators" / "__init__.py").exists()


def test_skeleton_generation_is_idempotent(sample_spec_path, temp_output_dir):
    """スケルトン生成が冪等であることを確認（既存ファイルを上書きしない）"""
    ir = load_spec(sample_spec_path)

    # 1回目の生成
    generate_skeleton(ir, temp_output_dir)

    transform_file = temp_output_dir / "apps" / "sample_project" / "transforms" / "processors.py"

    # ファイルを手動で編集
    original_content = transform_file.read_text()
    modified_content = original_content + "\n# Custom implementation\n"
    transform_file.write_text(modified_content)

    # 2回目の生成
    generate_skeleton(ir, temp_output_dir)

    # 手動編集が保持されていることを確認
    final_content = transform_file.read_text()
    assert "# Custom implementation" in final_content


def test_generate_check_function_with_correct_signature(sample_spec_path, temp_output_dir):
    """Check関数が正しいシグネチャで生成されることを確認"""
    ir = load_spec(sample_spec_path)
    generate_skeleton(ir, temp_output_dir)

    check_file = temp_output_dir / "apps" / "sample_project" / "checks" / "validators.py"
    content = check_file.read_text()

    # Check関数は dict を受け取り bool を返す
    assert "def validate_positive(payload: dict) -> bool:" in content


def test_generate_enum_datatypes(sample_spec_path, temp_output_dir):
    """Enum型が生成されることを確認"""
    ir = load_spec(sample_spec_path)
    generate_skeleton(ir, temp_output_dir)

    # Enumファイルが生成されることを確認
    enum_file = temp_output_dir / "apps" / "sample_project" / "models" / "enums.py"
    assert enum_file.exists()

    content = enum_file.read_text()

    # Status Enumが生成されていることを確認
    assert "class Status(str, Enum):" in content or "class Status(Enum):" in content
    assert "ACTIVE" in content
    assert "INACTIVE" in content


def test_generate_pydantic_models(sample_spec_path, temp_output_dir):
    """Pydanticモデルが生成されることを確認"""
    ir = load_spec(sample_spec_path)
    generate_skeleton(ir, temp_output_dir)

    # Pydanticモデルファイルが生成されることを確認
    model_file = temp_output_dir / "apps" / "sample_project" / "models" / "models.py"
    assert model_file.exists()

    content = model_file.read_text()

    # DataPoint Pydanticモデルが生成されていることを確認
    assert "class DataPoint(BaseModel):" in content
    assert "timestamp:" in content
    assert "value:" in content


def test_generate_dataframe_schemas(sample_spec_path, temp_output_dir):
    """DataFrame Schemaが生成されることを確認"""
    ir = load_spec(sample_spec_path)
    generate_skeleton(ir, temp_output_dir)

    # Pandera Schemaファイルが既に存在することを確認
    # （この機能は既にspectoolに実装されている）
    schema_file = temp_output_dir / "apps" / "sample_project" / "schemas" / "dataframe_schemas.py"
    assert schema_file.exists()

    content = schema_file.read_text()

    # TimeSeriesFrame Schemaが生成されていることを確認
    assert "TimeSeriesFrameSchema" in content


def test_generator_function_return_type_is_resolved(sample_spec_path, temp_output_dir):
    """Generator関数のreturn_type_refが正しく解決されることを確認

    問題：generator関数が全てpd.DataFrameを返すようにハードコードされていた。
    修正後：return_type_refを使って正しい型を返すべき。
    """
    ir = load_spec(sample_spec_path)
    generate_skeleton(ir, temp_output_dir)

    generator_file = temp_output_dir / "apps" / "sample_project" / "generators" / "data_generators.py"
    content = generator_file.read_text()

    # generate_timeseries は TimeSeriesFrame (DataFrame型エイリアス) を返すべき
    # TimeSeriesFrameはdataframe_schemaなので、pd.DataFrameとして解決されるはず
    assert "def generate_timeseries() -> " in content
    # TimeSeriesFrameはDataFrameなので、Annotated[pd.DataFrame, ...] または pd.DataFrame になるはず

    # generate_datapoint は DataPoint (Pydanticモデル) を返すべき
    assert "def generate_datapoint() -> DataPoint:" in content

    # Pydanticモデルの場合、適切なインポートが追加されているべき
    assert "from apps.sample_project.models.models import DataPoint" in content

    # 全ての関数が pd.DataFrame を返しているわけではないことを確認
    # （つまり return_type_ref が正しく反映されていることを確認）
    assert content.count("-> pd.DataFrame") < content.count("def generate_")

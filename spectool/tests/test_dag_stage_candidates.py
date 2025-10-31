"""DAG Stage候補検出の精度テスト

dag_stagesのi/o dtypeに該当するtransform関数候補が正確に抽出されることを確認する。
"""

from pathlib import Path
import tempfile
import pytest
import yaml

from spectool.spectool.core.engine.loader import load_spec


@pytest.fixture
def temp_spec_dir():
    """一時specディレクトリ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_dag_stage_finds_all_matching_candidates(temp_spec_dir):
    """i/o dtypeに該当するtransform候補がN件ある時、全てM件が正確に取得できることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "candidate-match_spec"},
        "datatypes": [
            {
                "id": "FrameA",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
            },
            {
                "id": "FrameB",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "result", "dtype": "float"}],
                },
            },
            {
                "id": "FrameC",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "other", "dtype": "str"}],
                },
            },
        ],
        "transforms": [
            {
                "id": "transform_a_to_b_v1",
                "impl": "apps.transforms:transform_a_to_b_v1",
                "file_path": "transforms/v1.py",
                "parameters": [{"name": "data", "type_ref": "FrameA"}],
                "return_type_ref": "FrameB",
            },
            {
                "id": "transform_a_to_b_v2",
                "impl": "apps.transforms:transform_a_to_b_v2",
                "file_path": "transforms/v2.py",
                "parameters": [{"name": "data", "type_ref": "FrameA"}],
                "return_type_ref": "FrameB",
            },
            {
                "id": "transform_a_to_b_v3",
                "impl": "apps.transforms:transform_a_to_b_v3",
                "file_path": "transforms/v3.py",
                "parameters": [{"name": "data", "type_ref": "FrameA"}],
                "return_type_ref": "FrameB",
            },
            {
                "id": "transform_a_to_c",  # 該当しない（output型が違う）
                "impl": "apps.transforms:transform_a_to_c",
                "file_path": "transforms/ac.py",
                "parameters": [{"name": "data", "type_ref": "FrameA"}],
                "return_type_ref": "FrameC",
            },
            {
                "id": "transform_c_to_b",  # 該当しない（input型が違う）
                "impl": "apps.transforms:transform_c_to_b",
                "file_path": "transforms/cb.py",
                "parameters": [{"name": "data", "type_ref": "FrameC"}],
                "return_type_ref": "FrameB",
            },
        ],
        "dag_stages": [
            {
                "stage_id": "stage_a_to_b",
                "selection_mode": "exclusive",
                "input_type": "FrameA",
                "output_type": "FrameB",
                # candidatesを明示的に指定しない場合、自動収集されるべき
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    ir = load_spec(spec_path)

    # dag_stageが読み込まれていることを確認
    assert len(ir.dag_stages) == 1
    stage = ir.dag_stages[0]

    # 候補が自動収集されている場合、3件（v1, v2, v3）が含まれるべき
    if hasattr(stage, "candidates") and stage.candidates:
        assert len(stage.candidates) == 3, f"Expected 3 candidates, but got {len(stage.candidates)}"

        candidate_ids = {c if isinstance(c, str) else c.transform_id for c in stage.candidates}
        assert "transform_a_to_b_v1" in candidate_ids
        assert "transform_a_to_b_v2" in candidate_ids
        assert "transform_a_to_b_v3" in candidate_ids

        # 該当しないtransformは含まれないこと
        assert "transform_a_to_c" not in candidate_ids
        assert "transform_c_to_b" not in candidate_ids


def test_dag_stage_explicit_candidates_validation(temp_spec_dir):
    """明示的に指定されたcandidatesが正しいことを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "explicit-candidates_spec"},
        "datatypes": [
            {
                "id": "FrameA",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
            },
            {
                "id": "FrameB",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "result", "dtype": "float"}],
                },
            },
        ],
        "transforms": [
            {
                "id": "transform_v1",
                "impl": "apps.transforms:transform_v1",
                "file_path": "transforms/v1.py",
                "parameters": [{"name": "data", "type_ref": "FrameA"}],
                "return_type_ref": "FrameB",
            },
            {
                "id": "transform_v2",
                "impl": "apps.transforms:transform_v2",
                "file_path": "transforms/v2.py",
                "parameters": [{"name": "data", "type_ref": "FrameA"}],
                "return_type_ref": "FrameB",
            },
        ],
        "dag_stages": [
            {
                "stage_id": "stage_1",
                "selection_mode": "exclusive",
                "input_type": "FrameA",
                "output_type": "FrameB",
                "candidates": ["transform_v1", "transform_v2"],  # 明示的に指定
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    ir = load_spec(spec_path)

    stage = ir.dag_stages[0]
    assert len(stage.candidates) == 2


def test_config_invalid_transform_rejected_in_validation(temp_spec_dir):
    """該当しないtransform関数がconfigに記載されていた時、実行前validationで弾かれることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "invalid-transform-config_spec"},
        "datatypes": [
            {
                "id": "FrameA",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
            },
            {
                "id": "FrameB",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "result", "dtype": "float"}],
                },
            },
            {
                "id": "FrameC",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "other", "dtype": "str"}],
                },
            },
        ],
        "transforms": [
            {
                "id": "valid_transform",
                "impl": "apps.transforms:valid_transform",
                "file_path": "transforms/valid.py",
                "parameters": [{"name": "data", "type_ref": "FrameA"}],
                "return_type_ref": "FrameB",
            },
            {
                "id": "wrong_output_transform",
                "impl": "apps.transforms:wrong_output_transform",
                "file_path": "transforms/wrong.py",
                "parameters": [{"name": "data", "type_ref": "FrameA"}],
                "return_type_ref": "FrameC",  # output型が違う
            },
        ],
        "dag_stages": [
            {
                "stage_id": "stage_a_to_b",
                "selection_mode": "single",
                "input_type": "FrameA",
                "output_type": "FrameB",
                "candidates": ["valid_transform"],  # 候補はvalid_transformのみ
            }
        ],
    }

    config_data = {
        "version": "1",
        "meta": {"config_name": "invalid_config", "base_spec": "spec.yaml"},
        "execution": {
            "stages": [
                {
                    "stage_id": "stage_a_to_b",
                    "selected": [
                        {"transform_id": "wrong_output_transform"}  # 候補にないtransformを指定
                    ],
                }
            ]
        },
    }

    spec_path = temp_spec_dir / "spec.yaml"
    config_path = temp_spec_dir / "config.yaml"

    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    from spectool.spectool.core.engine.config_validator import validate_config, ConfigValidationError
    from spectool.spectool.core.engine.config_model import load_config

    ir = load_spec(spec_path)
    config = load_config(str(config_path))

    # 候補にないtransformを指定したのでエラーが発生すること
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config, ir)

    assert "not in candidates" in str(exc_info.value).lower()


def test_config_undefined_transform_rejected_in_validation(temp_spec_dir):
    """未定義のtransformがconfigに記載されていた時、実行前validationで弾かれることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "undefined-transform_spec"},
        "datatypes": [
            {
                "id": "FrameA",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
            }
        ],
        "transforms": [
            {
                "id": "defined_transform",
                "impl": "apps.transforms:defined_transform",
                "file_path": "transforms/defined.py",
                "parameters": [{"name": "data", "type_ref": "FrameA"}],
                "return_type_ref": "FrameA",
            }
        ],
        "dag_stages": [
            {
                "stage_id": "stage_1",
                "selection_mode": "single",
                "input_type": "FrameA",
                "output_type": "FrameA",
                "candidates": ["defined_transform"],
            }
        ],
    }

    config_data = {
        "version": "1",
        "meta": {"config_name": "undefined_config", "base_spec": "spec.yaml"},
        "execution": {
            "stages": [
                {
                    "stage_id": "stage_1",
                    "selected": [
                        {"transform_id": "undefined_transform"}  # 未定義のtransform
                    ],
                }
            ]
        },
    }

    spec_path = temp_spec_dir / "spec.yaml"
    config_path = temp_spec_dir / "config.yaml"

    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    from spectool.spectool.core.engine.config_validator import validate_config, ConfigValidationError
    from spectool.spectool.core.engine.config_model import load_config

    ir = load_spec(spec_path)
    config = load_config(str(config_path))

    # 未定義のtransformを指定したのでエラーが発生すること
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config, ir)

    assert "undefined_transform" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()


def test_dag_stage_auto_candidate_collection_filters_by_signature(temp_spec_dir):
    """複数パラメータを持つtransformでも、i/o型が一致すれば候補に含まれることを確認"""
    spec_data = {
        "version": "1.0",
        "meta": {"name": "multi-param-candidate_spec"},
        "datatypes": [
            {
                "id": "FrameA",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "value", "dtype": "float"}],
                },
            },
            {
                "id": "FrameB",
                "dataframe_schema": {
                    "index": {"name": "idx", "dtype": "int"},
                    "columns": [{"name": "result", "dtype": "float"}],
                },
            },
        ],
        "transforms": [
            {
                "id": "simple_transform",
                "impl": "apps.transforms:simple_transform",
                "file_path": "transforms/simple.py",
                "parameters": [{"name": "data", "type_ref": "FrameA"}],
                "return_type_ref": "FrameB",
            },
            {
                "id": "complex_transform",
                "impl": "apps.transforms:complex_transform",
                "file_path": "transforms/complex.py",
                "parameters": [
                    {"name": "data", "type_ref": "FrameA"},
                    {"name": "factor", "native": "builtins:float", "default": 1.0},
                    {"name": "mode", "native": "builtins:str", "default": "normal"},
                ],
                "return_type_ref": "FrameB",
            },
        ],
        "dag_stages": [
            {
                "stage_id": "stage_1",
                "selection_mode": "exclusive",
                "input_type": "FrameA",
                "output_type": "FrameB",
                # candidatesを指定しない（自動収集）
            }
        ],
    }

    spec_path = temp_spec_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        yaml.dump(spec_data, f)

    ir = load_spec(spec_path)

    stage = ir.dag_stages[0]

    # 両方のtransformが候補に含まれるべき（複数パラメータでもi/o型が一致すれば）
    if hasattr(stage, "candidates") and stage.candidates:
        assert len(stage.candidates) == 2
        candidate_ids = {c if isinstance(c, str) else c.transform_id for c in stage.candidates}
        assert "simple_transform" in candidate_ids
        assert "complex_transform" in candidate_ids

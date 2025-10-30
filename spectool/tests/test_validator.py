"""Validatorのテスト"""

from pathlib import Path

from spectool.spectool.core.engine.loader import load_spec
from spectool.spectool.core.engine.normalizer import normalize_ir
from spectool.spectool.core.engine.validate import (
    validate_ir,
)


def test_validate_valid_spec():
    """正常なspecのバリデーションが通るテスト（impl参照は除く）"""
    fixture_path = Path(__file__).parent / "fixtures" / "valid_spec.yaml"
    ir = load_spec(fixture_path)
    normalized = normalize_ir(ir)

    # impl参照をクリアして構造的な検証のみ行う（実装が存在しないため）
    for check in ir.checks:
        check.impl = ""
    for transform in ir.transforms:
        transform.impl = ""

    errors = validate_ir(ir)
    assert len(errors) == 0, f"Expected no errors, but got: {errors}"


def test_validate_duplicate_columns():
    """重複列名のエラー検出テスト"""
    fixture_path = Path(__file__).parent / "fixtures" / "invalid_spec_duplicate_cols.yaml"
    ir = load_spec(fixture_path)
    errors = validate_ir(ir)

    assert len(errors) > 0, "Expected errors for duplicate columns"
    assert any("duplicate column" in e.lower() for e in errors), f"Expected duplicate column error, got: {errors}"


def test_validate_missing_dtype():
    """dtype未設定のエラー検出テスト"""
    fixture_path = Path(__file__).parent / "fixtures" / "invalid_spec_missing_type.yaml"
    ir = load_spec(fixture_path)
    errors = validate_ir(ir)

    assert len(errors) > 0, "Expected errors for missing dtype"
    assert any("dtype is not set" in e for e in errors), f"Expected dtype error, got: {errors}"


def test_validate_invalid_transform_type_ref():
    """Transform parametersの不正な型参照エラー検出テスト"""
    from spectool.spectool.core.base.ir import MetaSpec, ParameterSpec, SpecIR, TransformSpec

    ir = SpecIR(
        meta=MetaSpec(name="test"),
        transforms=[
            TransformSpec(
                id="invalid_transform",
                impl="apps.transforms:func",
                parameters=[
                    ParameterSpec(
                        name="data",
                        type_ref="NonExistentDataType",  # 存在しない型参照
                    )
                ],
            )
        ],
    )

    errors = validate_ir(ir)
    assert len(errors) > 0, "Expected errors for invalid type_ref"
    assert any("invalid type_ref" in e for e in errors), f"Expected type_ref error, got: {errors}"


def test_validate_invalid_dag_stage_candidate():
    """DAG Stageの不正なcandidate参照エラー検出テスト"""
    from spectool.spectool.core.base.ir import DAGStageSpec, MetaSpec, SpecIR

    ir = SpecIR(
        meta=MetaSpec(name="test"),
        dag_stages=[
            DAGStageSpec(
                stage_id="invalid_stage",
                candidates=["non_existent_transform"],  # 存在しないTransform
            )
        ],
    )

    errors = validate_ir(ir)
    assert len(errors) > 0, "Expected errors for invalid candidate"
    assert any("not found in transforms" in e for e in errors), f"Expected candidate error, got: {errors}"


def test_validate_invalid_selection_mode():
    """DAG Stageの不正なselection_modeエラー検出テスト"""
    from spectool.spectool.core.base.ir import DAGStageSpec, MetaSpec, SpecIR

    ir = SpecIR(
        meta=MetaSpec(name="test"),
        dag_stages=[
            DAGStageSpec(
                stage_id="invalid_stage",
                selection_mode="invalid_mode",  # 不正なselection_mode
            )
        ],
    )

    errors = validate_ir(ir)
    assert len(errors) > 0, "Expected errors for invalid selection_mode"
    assert any("invalid selection_mode" in e for e in errors), f"Expected selection_mode error, got: {errors}"


def test_validate_python_type_reference():
    """Python型参照の検証テスト"""
    from spectool.spectool.core.base.ir import FrameSpec, MetaSpec, SpecIR

    # 不正なrow_model参照
    ir = SpecIR(
        meta=MetaSpec(name="test"),
        frames=[
            FrameSpec(
                id="InvalidFrame",
                row_model="invalid.module:NonExistentClass",
                columns=[],
            )
        ],
    )

    errors = validate_ir(ir)
    assert len(errors) > 0, "Expected errors for invalid row_model"
    assert any("cannot import row_model" in e for e in errors), f"Expected import error, got: {errors}"


def test_validate_check_function_reference():
    """Check関数参照の検証テスト"""
    from spectool.spectool.core.base.ir import FrameSpec, MetaSpec, SpecIR

    ir = SpecIR(
        meta=MetaSpec(name="test"),
        frames=[
            FrameSpec(
                id="TestFrame",
                columns=[],
                check_functions=["invalid.module:non_existent_check"],
            )
        ],
    )

    errors = validate_ir(ir)
    assert len(errors) > 0, "Expected errors for invalid check_function"
    assert any("cannot import check_function" in e for e in errors), f"Expected import error, got: {errors}"


def test_validate_transform_impl_format():
    """Transform implの形式チェックテスト"""
    from spectool.spectool.core.base.ir import MetaSpec, SpecIR, TransformSpec

    ir = SpecIR(
        meta=MetaSpec(name="test"),
        transforms=[
            TransformSpec(
                id="invalid_transform",
                impl="invalid_format_without_colon",  # コロンがない不正な形式
            )
        ],
    )

    errors = validate_ir(ir)
    assert len(errors) > 0, "Expected errors for invalid impl format"
    assert any("must be in 'module:function' format" in e for e in errors), f"Expected format error, got: {errors}"


def test_validate_multiple_errors():
    """複数のエラーが同時に検出されるテスト"""
    from spectool.spectool.core.base.ir import (
        ColumnRule,
        DAGStageSpec,
        FrameSpec,
        MetaSpec,
        SpecIR,
        TransformSpec,
    )

    ir = SpecIR(
        meta=MetaSpec(name="test"),
        frames=[
            FrameSpec(
                id="MultiErrorFrame",
                columns=[
                    ColumnRule(name="col1", dtype=""),  # dtype未設定
                    ColumnRule(name="col1", dtype="float"),  # 重複列名
                ],
            )
        ],
        transforms=[
            TransformSpec(
                id="invalid_transform",
                impl="invalid_format",  # 不正な形式
            )
        ],
        dag_stages=[
            DAGStageSpec(
                stage_id="invalid_stage",
                candidates=["non_existent"],  # 存在しないTransform
            )
        ],
    )

    errors = validate_ir(ir)
    # 複数のエラーが検出される
    assert len(errors) >= 3, f"Expected at least 3 errors, got {len(errors)}: {errors}"
    assert any("duplicate column" in e.lower() for e in errors)
    assert any("dtype is not set" in e for e in errors)
    assert any("must be in 'module:function' format" in e for e in errors)
    assert any("not found in transforms" in e for e in errors)


def test_validate_native_type_ref():
    """native型参照の検証テスト（正常系）"""
    from spectool.spectool.core.base.ir import MetaSpec, ParameterSpec, SpecIR, TransformSpec

    ir = SpecIR(
        meta=MetaSpec(name="test"),
        transforms=[
            TransformSpec(
                id="valid_transform",
                impl="",  # impl参照は空にして構造的検証のみ
                parameters=[
                    ParameterSpec(
                        name="value",
                        type_ref="builtins:int",  # native型参照（正常）
                    )
                ],
            )
        ],
    )

    errors = validate_ir(ir)
    # native型参照はエラーにならない
    assert len(errors) == 0, f"Expected no errors for native type_ref, got: {errors}"

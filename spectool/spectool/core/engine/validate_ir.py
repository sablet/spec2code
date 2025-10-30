"""Validator: IR検証 - 中核ロジック

IRの意味論チェックを行う。
主な検証項目:
1. DataFrame定義の妥当性（重複列、dtype未設定等）
2. Transform定義の妥当性
3. DAG Stage定義の妥当性
4. Python型参照の解決可能性
"""

from __future__ import annotations

import importlib

from spectool.spectool.core.base.ir import FrameSpec, SpecIR


def validate_ir(ir: SpecIR, skip_impl_check: bool = False) -> list[str]:
    """IR全体の意味論チェック

    Args:
        ir: 検証対象のIR
        skip_impl_check: 実装ファイルのインポートチェックをスキップ（gen時に使用）

    Returns:
        エラーメッセージのリスト（空の場合はエラーなし）
    """
    errors: list[str] = []

    # DataFrame定義の検証
    errors.extend(_validate_dataframe_specs(ir))

    # Check定義の検証
    errors.extend(_validate_check_specs(ir))

    # Transform定義の検証
    errors.extend(_validate_transform_specs(ir))

    # DAG Stage定義の検証
    errors.extend(_validate_dag_stage_specs(ir))

    # Python型参照の検証（実装チェック含む）
    errors.extend(_validate_type_references(ir, skip_impl_check=skip_impl_check))

    return errors


_VALID_DTYPES = {
    "int",
    "int8",
    "int16",
    "int32",
    "int64",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
    "float",
    "float16",
    "float32",
    "float64",
    "str",
    "string",
    "bool",
    "boolean",
    "datetime",
    "datetime64",
    "datetime64[ns]",
    "timedelta",
    "timedelta64",
    "timedelta64[ns]",
    "object",
    "category",
}


def _validate_column_duplicates(frame: FrameSpec) -> list[str]:
    """重複列名をチェック"""
    col_names = [col.name for col in frame.columns]
    duplicates = {name for name in col_names if col_names.count(name) > 1}
    if duplicates:
        return [f"DataFrame '{frame.id}': duplicate column names: {duplicates}"]
    return []


def _validate_column_dtypes(frame: FrameSpec) -> list[str]:
    """カラムのdtypeをチェック"""
    errors = []
    for col in frame.columns:
        if not col.dtype:
            errors.append(f"DataFrame '{frame.id}', column '{col.name}': dtype is not set")
        elif col.dtype.lower() not in _VALID_DTYPES:
            errors.append(
                f"DataFrame '{frame.id}', column '{col.name}': "
                f"invalid dtype '{col.dtype}'. Valid types: {_VALID_DTYPES}"
            )
    return errors


def _validate_index_dtype(frame: FrameSpec) -> list[str]:
    """Index定義のdtypeをチェック"""
    errors = []
    if frame.index:
        if not frame.index.dtype:
            errors.append(f"DataFrame '{frame.id}': index dtype is not set")
        elif frame.index.dtype.lower() not in _VALID_DTYPES:
            errors.append(
                f"DataFrame '{frame.id}', index '{frame.index.name}': "
                f"invalid dtype '{frame.index.dtype}'. Valid types: {_VALID_DTYPES}"
            )
    return errors


def _validate_multiindex_dtypes(frame: FrameSpec) -> list[str]:
    """MultiIndex定義のdtypeをチェック"""
    errors = []
    if frame.multi_index:
        for level in frame.multi_index:
            if not level.dtype:
                errors.append(f"DataFrame '{frame.id}', MultiIndex level '{level.name}': dtype is not set")
            elif level.dtype.lower() not in _VALID_DTYPES:
                errors.append(
                    f"DataFrame '{frame.id}', MultiIndex level '{level.name}': "
                    f"invalid dtype '{level.dtype}'. Valid types: {_VALID_DTYPES}"
                )
    return errors


def _validate_dataframe_specs(ir: SpecIR) -> list[str]:
    """DataFrame定義の妥当性チェック

    検証項目:
    - 重複列名
    - dtype未設定
    - dtype値の妥当性
    - Index/MultiIndexの妥当性

    Args:
        ir: 検証対象のIR

    Returns:
        エラーメッセージのリスト
    """
    errors: list[str] = []

    for frame in ir.frames:
        errors.extend(_validate_column_duplicates(frame))
        errors.extend(_validate_column_dtypes(frame))
        errors.extend(_validate_index_dtype(frame))
        errors.extend(_validate_multiindex_dtypes(frame))

    return errors


def _validate_check_specs(ir: SpecIR) -> list[str]:
    """Check定義の妥当性チェック

    検証項目:
    - impl参照の形式チェック

    Args:
        ir: 検証対象のIR

    Returns:
        エラーメッセージのリスト
    """
    errors: list[str] = []

    for check in ir.checks:
        # impl形式チェック
        if check.impl and check.impl.strip() != "" and ":" not in check.impl:
            errors.append(f"Check '{check.id}': impl must be in 'module:function' format, got '{check.impl}'")

    return errors


def _collect_all_datatype_ids(ir: SpecIR) -> set[str]:
    """全datatype IDを収集

    Args:
        ir: 検証対象のIR

    Returns:
        全datatype IDのセット
    """
    all_datatype_ids: set[str] = set()
    all_datatype_ids.update(f.id for f in ir.frames)
    all_datatype_ids.update(e.id for e in ir.enums)
    all_datatype_ids.update(p.id for p in ir.pydantic_models)
    all_datatype_ids.update(t.id for t in ir.type_aliases)
    all_datatype_ids.update(g.id for g in ir.generics)
    return all_datatype_ids


def _validate_transform_specs(ir: SpecIR) -> list[str]:
    """Transform定義の妥当性チェック

    検証項目:
    - パラメータのtype_ref妥当性
    - return_type_refの妥当性
    - impl参照の形式チェック

    Args:
        ir: 検証対象のIR

    Returns:
        エラーメッセージのリスト
    """
    errors: list[str] = []

    # 全datatype IDを収集
    all_datatype_ids = _collect_all_datatype_ids(ir)

    for transform in ir.transforms:
        # パラメータのtype_ref検証
        for param in transform.parameters:
            if not param.type_ref:
                errors.append(f"Transform '{transform.id}', parameter '{param.name}': type_ref is not set")
                continue

            # native型またはdatatype_refかチェック
            if not _is_valid_type_ref(param.type_ref, all_datatype_ids):
                errors.append(
                    f"Transform '{transform.id}', parameter '{param.name}': invalid type_ref '{param.type_ref}'"
                )

        # return_type_refの検証
        if transform.return_type_ref and not _is_valid_type_ref(transform.return_type_ref, all_datatype_ids):
            errors.append(f"Transform '{transform.id}': invalid return_type_ref '{transform.return_type_ref}'")

        # impl形式チェック
        if transform.impl and transform.impl.strip() != "" and ":" not in transform.impl:
            errors.append(
                f"Transform '{transform.id}': impl must be in 'module:function' format, got '{transform.impl}'"
            )

    return errors


def _validate_dag_stage_specs(ir: SpecIR) -> list[str]:
    """DAG Stage定義の妥当性チェック

    検証項目:
    - candidatesに含まれるTransform IDの存在チェック
    - default_transform_idの存在チェック
    - selection_modeの妥当性

    Args:
        ir: 検証対象のIR

    Returns:
        エラーメッセージのリスト
    """
    errors: list[str] = []

    # Transform IDを収集
    transform_ids = {t.id for t in ir.transforms}

    for stage in ir.dag_stages:
        # candidatesの検証
        for candidate_id in stage.candidates:
            if candidate_id not in transform_ids:
                errors.append(f"DAG Stage '{stage.stage_id}': candidate '{candidate_id}' not found in transforms")

        # default_transform_idの検証
        if stage.default_transform_id and stage.default_transform_id not in stage.candidates:
            errors.append(
                f"DAG Stage '{stage.stage_id}': default_transform_id '{stage.default_transform_id}' not in candidates"
            )

        # selection_modeの妥当性
        valid_modes = {"single", "exclusive", "multiple"}
        if stage.selection_mode not in valid_modes:
            errors.append(
                f"DAG Stage '{stage.stage_id}': invalid selection_mode '{stage.selection_mode}', "
                f"must be one of {valid_modes}"
            )

    return errors


def _validate_type_references(ir: SpecIR, skip_impl_check: bool = False) -> list[str]:
    """Python型参照の解決可能性チェック

    検証項目:
    - FrameSpec.row_modelのインポート可能性
    - FrameSpec.generator_factoryのインポート可能性
    - CheckSpec.implのインポート可能性
    - TransformSpec.implのインポート可能性

    Args:
        ir: 検証対象のIR
        skip_impl_check: 実装ファイルのインポートチェックをスキップ

    Returns:
        エラーメッセージのリスト
    """
    errors: list[str] = []

    # 実装チェックをスキップする場合は空リストを返す
    if skip_impl_check:
        return errors

    # DataFrame row_modelの検証
    for frame in ir.frames:
        if frame.row_model and not _can_import_python_ref(frame.row_model, ir):
            errors.append(f"DataFrame '{frame.id}': cannot import row_model '{frame.row_model}'")

        if frame.generator_factory and not _can_import_python_ref(frame.generator_factory, ir):
            errors.append(f"DataFrame '{frame.id}': cannot import generator_factory '{frame.generator_factory}'")

        # check_functionsの検証
        for check_func in frame.check_functions:
            if not _can_import_python_ref(check_func, ir):
                errors.append(f"DataFrame '{frame.id}': cannot import check_function '{check_func}'")

    # Check関数の検証
    for check in ir.checks:
        if check.impl and not _can_import_python_ref(check.impl, ir):
            errors.append(f"Check '{check.id}': cannot import impl '{check.impl}'")

    # Transform関数の検証
    for transform in ir.transforms:
        if transform.impl and not _can_import_python_ref(transform.impl, ir):
            errors.append(f"Transform '{transform.id}': cannot import impl '{transform.impl}'")

    return errors


def _is_valid_type_ref(type_ref: str, all_datatype_ids: set[str]) -> bool:
    """型参照の妥当性チェック

    Args:
        type_ref: 型参照文字列
        all_datatype_ids: 全datatype IDのセット

    Returns:
        妥当な型参照の場合True
    """
    # native型の場合（"builtins:int"形式）
    if type_ref.startswith("builtins:"):
        return True

    # datatype_refの場合
    if type_ref in all_datatype_ids:
        return True

    # Python型参照の場合（"module:class"形式）
    return ":" in type_ref


def _resolve_impl_path(impl: str, ir: SpecIR) -> str:
    """implパスを解決（apps. プレフィックスをプロジェクト名を含む形に変換）

    Args:
        impl: 元のimplパス (例: "apps.checks:func")
        ir: SpecIR（プロジェクト名取得用）

    Returns:
        解決されたimplパス (例: "apps.sample-project.checks:func")
    """
    if not impl.startswith("apps."):
        return impl

    # プロジェクト名を取得
    app_name = ir.meta.name if ir.meta else "app"

    # "apps." の後の部分を取得
    rest = impl[5:]  # "apps." を除去

    # "apps.<project-name>." + 残りの部分
    return f"apps.{app_name}.{rest}"


def _can_import_python_ref(ref: str, ir: SpecIR | None = None) -> bool:
    """Python型参照のインポート可能性チェック

    Args:
        ref: "module:class"形式の参照
        ir: SpecIR（implパス解決用、オプション）

    Returns:
        インポート可能な場合True
    """
    if ":" not in ref:
        return False

    # implパスを解決
    resolved_ref = ref
    if ir is not None:
        resolved_ref = _resolve_impl_path(ref, ir)

    try:
        module_path, name = resolved_ref.rsplit(":", 1)
        module = importlib.import_module(module_path)
        getattr(module, name)
        return True
    except (ImportError, AttributeError):
        return False

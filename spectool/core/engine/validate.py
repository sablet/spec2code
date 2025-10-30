"""Validator: IR検証

IRの意味論チェックを行う。
主な検証項目:
1. DataFrame定義の妥当性（重複列、dtype未設定等）
2. Transform定義の妥当性
3. DAG Stage定義の妥当性
4. Python型参照の解決可能性
5. エッジケース検証（候補ゼロ、checkゼロ、exampleゼロ等）
"""

from __future__ import annotations

import importlib
from pathlib import Path

from spectool.core.base.ir import SpecIR


def validate_ir(ir: SpecIR) -> list[str]:
    """IR全体の意味論チェック

    Args:
        ir: 検証対象のIR

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

    # Python型参照の検証
    errors.extend(_validate_type_references(ir))

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

    # 有効なdtype値（基本型とpandas詳細型）
    valid_dtypes = {
        "int", "int8", "int16", "int32", "int64",
        "uint8", "uint16", "uint32", "uint64",
        "float", "float16", "float32", "float64",
        "str", "string",
        "bool", "boolean",
        "datetime", "datetime64", "datetime64[ns]",
        "timedelta", "timedelta64", "timedelta64[ns]",
        "object", "category",
    }

    for frame in ir.frames:
        # 重複列名チェック
        col_names = [col.name for col in frame.columns]
        duplicates = {name for name in col_names if col_names.count(name) > 1}
        if duplicates:
            errors.append(f"DataFrame '{frame.id}': duplicate column names: {duplicates}")

        # Column dtype チェック
        for col in frame.columns:
            if not col.dtype:
                errors.append(f"DataFrame '{frame.id}', column '{col.name}': dtype is not set")
            elif col.dtype.lower() not in valid_dtypes:
                errors.append(
                    f"DataFrame '{frame.id}', column '{col.name}': "
                    f"invalid dtype '{col.dtype}'. Valid types: {valid_dtypes}"
                )

        # Index定義チェック
        if frame.index:
            if not frame.index.dtype:
                errors.append(f"DataFrame '{frame.id}': index dtype is not set")
            elif frame.index.dtype.lower() not in valid_dtypes:
                errors.append(
                    f"DataFrame '{frame.id}', index '{frame.index.name}': "
                    f"invalid dtype '{frame.index.dtype}'. Valid types: {valid_dtypes}"
                )

        # MultiIndex定義チェック
        if frame.multi_index:
            for level in frame.multi_index:
                if not level.dtype:
                    errors.append(f"DataFrame '{frame.id}', MultiIndex level '{level.name}': dtype is not set")
                elif level.dtype.lower() not in valid_dtypes:
                    errors.append(
                        f"DataFrame '{frame.id}', MultiIndex level '{level.name}': "
                        f"invalid dtype '{level.dtype}'. Valid types: {valid_dtypes}"
                    )

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
        if check.impl and check.impl.strip() != "":
            # implが設定されている場合、形式をチェック
            if ":" not in check.impl:
                errors.append(f"Check '{check.id}': impl must be in 'module:function' format, got '{check.impl}'")

    return errors


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
    all_datatype_ids = set()
    all_datatype_ids.update(f.id for f in ir.frames)
    all_datatype_ids.update(e.id for e in ir.enums)
    all_datatype_ids.update(p.id for p in ir.pydantic_models)
    all_datatype_ids.update(t.id for t in ir.type_aliases)
    all_datatype_ids.update(g.id for g in ir.generics)

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
        if transform.impl and transform.impl.strip() != "":
            # implが設定されている場合、形式をチェック
            if ":" not in transform.impl:
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


def _validate_type_references(ir: SpecIR) -> list[str]:
    """Python型参照の解決可能性チェック

    検証項目:
    - FrameSpec.row_modelのインポート可能性
    - FrameSpec.generator_factoryのインポート可能性
    - CheckSpec.implのインポート可能性
    - TransformSpec.implのインポート可能性

    Args:
        ir: 検証対象のIR

    Returns:
        エラーメッセージのリスト
    """
    errors: list[str] = []

    # DataFrame row_modelの検証
    for frame in ir.frames:
        if frame.row_model:
            if not _can_import_python_ref(frame.row_model, ir):
                errors.append(f"DataFrame '{frame.id}': cannot import row_model '{frame.row_model}'")

        if frame.generator_factory:
            if not _can_import_python_ref(frame.generator_factory, ir):
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
    if ":" in type_ref:
        return True

    return False


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


def validate_spec(spec_path: str | Path) -> dict[str, dict[str, list[str]]]:
    """Spec YAMLファイルを読み込み、エラー/警告/成功をカテゴリ別に返す

    Args:
        spec_path: Spec YAMLファイルのパス

    Returns:
        3層構造の辞書: {"errors": {...}, "warnings": {...}, "successes": {...}}
        各層はカテゴリ別のメッセージリスト
    """
    import sys

    from spectool.core.engine.loader import load_spec

    spec_path = Path(spec_path)
    ir = load_spec(spec_path)

    # sys.pathにproject_rootを追加（apps.XXX形式のimportのため）
    # project_root は spec_path の親ディレクトリと仮定
    project_root = spec_path.parent.resolve()
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

    # カテゴリ別エラー辞書
    errors: dict[str, list[str]] = {
        "dataframe_schemas": [],
        "datatypes": [],
        "check_definitions": [],
        "checks": [],
        "transform_definitions": [],
        "transforms": [],
        "dag_stages": [],
        "examples": [],
        "parameter_types": [],
        "edge_cases": [],
    }

    # カテゴリ別警告辞書
    warnings: dict[str, list[str]] = {
        "dataframe_schemas": [],
        "datatypes": [],
        "check_definitions": [],
        "checks": [],
        "transform_definitions": [],
        "transforms": [],
        "dag_stages": [],
        "examples": [],
        "parameter_types": [],
        "edge_cases": [],
    }

    # カテゴリ別成功辞書
    successes: dict[str, list[str]] = {
        "dataframe_schemas": [],
        "datatypes": [],
        "check_definitions": [],
        "checks": [],
        "transform_definitions": [],
        "transforms": [],
        "dag_stages": [],
        "examples": [],
        "parameter_types": [],
        "edge_cases": [],
    }

    # 既存のvalidate_irを実行
    flat_errors = validate_ir(ir)

    # エラーをカテゴリ別に分類
    for error in flat_errors:
        categorized = False

        # DataFrame schema errors
        if "DataFrame" in error and ("duplicate column" in error.lower() or "dtype is not set" in error):
            errors["dataframe_schemas"].append(error)
            categorized = True
        # DataFrame datatype errors
        elif "DataFrame" in error:
            errors["datatypes"].append(error)
            categorized = True

        # Check definition errors (impl related)
        if "Check" in error and "impl" in error:
            errors["check_definitions"].append(error)
            categorized = True
        # Other check errors
        elif "Check" in error and not categorized:
            errors["checks"].append(error)
            categorized = True

        # Transform definition errors (impl, type_ref, parameter related)
        if "Transform" in error and ("impl" in error or "type_ref" in error or "parameter" in error):
            errors["transform_definitions"].append(error)
            categorized = True
        # Other transform errors
        elif "Transform" in error and not categorized:
            errors["transforms"].append(error)
            categorized = True

        # DAG stage errors
        if ("DAG Stage" in error or "candidate" in error.lower()) and not categorized:
            errors["dag_stages"].append(error)
            categorized = True

        # Example errors
        if "Example" in error and not categorized:
            errors["examples"].append(error)
            categorized = True

        # Parameter type errors
        if "parameter" in error.lower() and ("type" in error.lower() or "default" in error.lower()) and not categorized:
            errors["parameter_types"].append(error)
            categorized = True

        # Edge cases (uncategorized)
        if not categorized:
            errors["edge_cases"].append(error)

    # エッジケース検証を追加（エラーのみ）
    edge_case_errors = _validate_edge_cases_errors_only(ir)
    errors["edge_cases"].extend(edge_case_errors)

    # Exampleデータのschema検証
    example_data_errors = _validate_example_data(ir)
    errors["examples"].extend(example_data_errors)

    # 警告を生成
    datatype_check_warnings = _validate_datatype_checks(ir)
    warnings["datatypes"].extend(datatype_check_warnings)

    datatype_example_warnings = _validate_datatype_examples_generators(ir)
    warnings["datatypes"].extend(datatype_example_warnings)

    # 成功を記録
    _record_successes(ir, errors, successes)

    return {"errors": errors, "warnings": warnings, "successes": successes}


def _validate_edge_cases_errors_only(ir: SpecIR) -> list[str]:
    """エッジケース検証（エラーのみ、警告は除く）

    検証項目:
    1. DAG stageで候補transform関数がゼロ件
    2. Exampleのdatatype_ref妥当性
    3. Transformパラメータのデフォルト値型チェック

    Args:
        ir: 検証対象のIR

    Returns:
        エラーメッセージのリスト
    """
    errors: list[str] = []

    # 全datatype IDを収集
    all_datatype_ids = set()
    all_datatype_ids.update(f.id for f in ir.frames)
    all_datatype_ids.update(e.id for e in ir.enums)
    all_datatype_ids.update(p.id for p in ir.pydantic_models)
    all_datatype_ids.update(t.id for t in ir.type_aliases)
    all_datatype_ids.update(g.id for g in ir.generics)

    # 1. DAG stageの候補ゼロチェック
    errors.extend(_validate_dag_stage_candidates(ir, all_datatype_ids))

    # 2. Exampleのdatatype_ref妥当性チェック
    errors.extend(_validate_example_refs(ir, all_datatype_ids))

    # 3. Transformパラメータのデフォルト値型チェック
    errors.extend(_validate_parameter_defaults(ir))

    return errors


def _validate_dag_stage_candidates(ir: SpecIR, all_datatype_ids: set[str]) -> list[str]:
    """DAG stageの候補transform関数がゼロ件でないかチェック

    Args:
        ir: 検証対象のIR
        all_datatype_ids: 全datatype IDのセット

    Returns:
        エラーメッセージのリスト
    """
    errors: list[str] = []

    for stage in ir.dag_stages:
        # 候補が空の場合
        if not stage.candidates:
            # 自動収集を試みる（input_type → output_type の変換を行うtransformを探す）
            if stage.input_type and stage.output_type:
                matching_transforms = []
                for transform in ir.transforms:
                    # 第1パラメータの型がinput_typeで、return_type_refがoutput_typeのものを探す
                    if transform.parameters and transform.return_type_ref == stage.output_type:
                        first_param = transform.parameters[0]
                        if first_param.type_ref == stage.input_type:
                            matching_transforms.append(transform.id)

                if not matching_transforms:
                    errors.append(
                        f"DAG Stage '{stage.stage_id}': no transform candidates found for "
                        f"input_type '{stage.input_type}' → output_type '{stage.output_type}'. "
                        f"Please define a transform or specify candidates explicitly."
                    )
            else:
                errors.append(
                    f"DAG Stage '{stage.stage_id}': candidates list is empty and "
                    f"input_type/output_type are not specified for auto-collection."
                )

    return errors


def _validate_datatype_checks(ir: SpecIR) -> list[str]:
    """DataTypeのcheck関数がゼロ件でないかチェック（警告）

    Args:
        ir: 検証対象のIR

    Returns:
        警告メッセージのリスト
    """
    warnings: list[str] = []

    # FrameSpecのcheck_functionsをチェック
    for frame in ir.frames:
        if not frame.check_functions:
            warnings.append(
                f"DataType '{frame.id}': no check functions defined. "
                f"Consider adding check_functions for data validation."
            )

    # EnumSpecのcheck_functionsをチェック
    for enum in ir.enums:
        if not enum.check_functions:
            warnings.append(
                f"DataType '{enum.id}': no check functions defined. "
                f"Consider adding check_functions for data validation."
            )

    # PydanticModelSpecのcheck_functionsをチェック
    for model in ir.pydantic_models:
        if not model.check_functions:
            warnings.append(
                f"DataType '{model.id}': no check functions defined. "
                f"Consider adding check_functions for data validation."
            )

    # TypeAliasSpecのcheck_functionsをチェック
    for alias in ir.type_aliases:
        if not alias.check_functions:
            warnings.append(
                f"DataType '{alias.id}': no check functions defined. "
                f"Consider adding check_functions for data validation."
            )

    # GenericSpecのcheck_functionsをチェック
    for generic in ir.generics:
        if not generic.check_functions:
            warnings.append(
                f"DataType '{generic.id}': no check functions defined. "
                f"Consider adding check_functions for data validation."
            )

    return warnings


def _validate_datatype_examples_generators(ir: SpecIR) -> list[str]:
    """DataTypeのexample/generatorの両方がゼロ件でないかチェック（警告）

    Args:
        ir: 検証対象のIR

    Returns:
        警告メッセージのリスト
    """
    warnings: list[str] = []

    # Exampleからdatatype_refを収集
    example_datatypes = set()
    for example in ir.examples:
        if example.datatype_ref and example.datatype_ref.strip():
            example_datatypes.add(example.datatype_ref)

    # Generatorからreturn_type_refを収集
    generator_datatypes = set()
    for generator in ir.generators:
        if generator.return_type_ref and generator.return_type_ref.strip():
            generator_datatypes.add(generator.return_type_ref)

    # FrameSpecのgenerator_factoryもチェック
    for frame in ir.frames:
        if frame.generator_factory:
            generator_datatypes.add(frame.id)

    # 各DataTypeでexampleもgeneratorも存在しないものを警告
    for frame in ir.frames:
        if frame.id not in example_datatypes and frame.id not in generator_datatypes:
            warnings.append(
                f"DataType '{frame.id}': neither examples nor generators are defined. "
                f"Consider adding examples or a generator for testing."
            )

    for enum in ir.enums:
        if enum.id not in example_datatypes and enum.id not in generator_datatypes:
            warnings.append(
                f"DataType '{enum.id}': neither examples nor generators are defined. "
                f"Consider adding examples or a generator for testing."
            )

    for model in ir.pydantic_models:
        if model.id not in example_datatypes and model.id not in generator_datatypes:
            warnings.append(
                f"DataType '{model.id}': neither examples nor generators are defined. "
                f"Consider adding examples or a generator for testing."
            )

    for alias in ir.type_aliases:
        if alias.id not in example_datatypes and alias.id not in generator_datatypes:
            warnings.append(
                f"DataType '{alias.id}': neither examples nor generators are defined. "
                f"Consider adding examples or a generator for testing."
            )

    for generic in ir.generics:
        if generic.id not in example_datatypes and generic.id not in generator_datatypes:
            warnings.append(
                f"DataType '{generic.id}': neither examples nor generators are defined. "
                f"Consider adding examples or a generator for testing."
            )

    return warnings


def _validate_example_refs(ir: SpecIR, all_datatype_ids: set[str]) -> list[str]:
    """Exampleのdatatype_ref妥当性チェック

    Args:
        ir: 検証対象のIR
        all_datatype_ids: 全datatype IDのセット

    Returns:
        エラーメッセージのリスト
    """
    errors: list[str] = []

    for example in ir.examples:
        # datatype_refが指定されている場合（空文字列でない）
        if example.datatype_ref and example.datatype_ref.strip():
            if example.datatype_ref not in all_datatype_ids:
                errors.append(
                    f"Example '{example.id}': datatype_ref '{example.datatype_ref}' not found in defined datatypes."
                )

    return errors


def _validate_parameter_defaults(ir: SpecIR) -> list[str]:
    """Transformパラメータのデフォルト値型チェック

    Args:
        ir: 検証対象のIR

    Returns:
        エラーメッセージのリスト
    """
    errors: list[str] = []

    for transform in ir.transforms:
        for param in transform.parameters:
            # デフォルト値が設定されている場合
            if param.default is not None:
                # native型の場合、型をチェック
                if param.type_ref.startswith("builtins:"):
                    type_name = param.type_ref.split(":", 1)[1]
                    expected_type = _get_builtin_type(type_name)

                    if expected_type is not None:
                        # optional=Trueの場合はNoneを許容
                        if param.optional and param.default is None:
                            continue

                        # int→floatの変換は許容
                        if expected_type is float and isinstance(param.default, int):
                            continue

                        # 型が一致しない場合
                        if not isinstance(param.default, expected_type):
                            errors.append(
                                f"Transform '{transform.id}', parameter '{param.name}': "
                                f"default value type mismatch. Expected {type_name}, "
                                f"but got {type(param.default).__name__}."
                            )

    return errors


def _get_builtin_type(type_name: str):
    """builtins型名から対応するPython型オブジェクトを取得

    Args:
        type_name: 型名（"int", "str", "float", "bool", "list", "dict"等）

    Returns:
        対応するPython型オブジェクト、または None
    """
    builtin_types = {
        "int": int,
        "str": str,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "set": set,
    }
    return builtin_types.get(type_name)


def _validate_example_data(ir: SpecIR) -> list[str]:
    """Exampleのinputデータがdatatype schemaに適合しているかチェック

    Args:
        ir: 検証対象のIR

    Returns:
        エラーメッセージのリスト
    """
    errors: list[str] = []

    try:
        import pandas as pd
        import pandera as pa
        from pandera.typing import Index, Series
    except ImportError:
        # pandera/pandasがインストールされていない場合はスキップ
        return errors

    # FrameSpecのマップを作成
    frame_map = {frame.id: frame for frame in ir.frames}

    for example in ir.examples:
        # datatype_refがFrameSpecを参照していない場合はスキップ
        if not example.datatype_ref or example.datatype_ref not in frame_map:
            continue

        frame = frame_map[example.datatype_ref]

        # inputデータが存在しない場合はスキップ
        if not example.input:
            continue

        try:
            # inputをDataFrameに変換
            df = pd.DataFrame(example.input)

            # Panderaスキーマを動的に生成して検証
            columns = {}
            index_schema = None

            # Index
            if frame.index:
                index_dtype = _pandera_dtype_from_str(frame.index.dtype)
                if index_dtype:
                    index_schema = pa.Index(index_dtype)

            # Columns
            for col in frame.columns:
                col_dtype = _pandera_dtype_from_str(col.dtype)
                if col_dtype:
                    columns[col.name] = pa.Column(col_dtype, nullable=col.nullable, coerce=frame.coerce)

            # スキーマ作成
            schema = pa.DataFrameSchema(columns, index=index_schema, coerce=frame.coerce)

            # 検証実行
            schema.validate(df, lazy=True)

        except pa.errors.SchemaErrors as e:
            # 複数のエラーをまとめて報告
            error_msg = f"Example '{example.id}': input data violates schema for '{example.datatype_ref}'"
            errors.append(error_msg)
        except Exception as e:
            # その他のエラー（DataFrameの作成失敗など）
            errors.append(f"Example '{example.id}': failed to validate input data - {str(e)}")

    return errors


def _pandera_dtype_from_str(dtype_str: str):
    """dtype文字列をPandera型に変換

    Args:
        dtype_str: dtype文字列

    Returns:
        Pandera型、または None
    """
    mapping = {
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "datetime": "datetime64[ns]",
    }
    return mapping.get(dtype_str.lower())


def _record_successes(ir: SpecIR, errors: dict[str, list[str]], successes: dict[str, list[str]]) -> None:
    """検証に成功した項目を記録する

    Args:
        ir: 検証対象のIR
        errors: エラー辞書（どの項目にエラーがあるか確認用）
        successes: 成功辞書（ここに成功メッセージを追加）
    """
    # すべてのエラーメッセージを結合（エラーチェック用）
    all_errors = " ".join([msg for msgs in errors.values() for msg in msgs])

    # DataFrame schemas の成功
    for frame in ir.frames:
        if f"DataFrame '{frame.id}'" not in all_errors:
            successes["dataframe_schemas"].append(f"DataFrame '{frame.id}': schema is valid")

    # Check definitions の成功
    for check in ir.checks:
        if f"Check '{check.id}'" not in all_errors:
            successes["check_definitions"].append(f"Check '{check.id}': definition is valid")

    # Transform definitions の成功
    for transform in ir.transforms:
        if f"Transform '{transform.id}'" not in all_errors:
            successes["transform_definitions"].append(f"Transform '{transform.id}': definition is valid")

    # DAG stages の成功
    for stage in ir.dag_stages:
        if f"DAG Stage '{stage.stage_id}'" not in all_errors:
            successes["dag_stages"].append(f"DAG Stage '{stage.stage_id}': configuration is valid")

    # Examples の成功
    for example in ir.examples:
        if f"Example '{example.id}'" not in all_errors:
            successes["examples"].append(f"Example '{example.id}': datatype_ref is valid")

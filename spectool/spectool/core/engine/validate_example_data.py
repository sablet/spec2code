"""Validator: Exampleデータ検証

Exampleデータがschemaに適合しているかをPanderaを使って検証する。
"""

from __future__ import annotations

from spectool.spectool.core.base.ir import SpecIR


def _build_pandera_schema(frame: Any, pa: Any) -> Any:  # noqa: ANN401
    """FrameSpecからPanderaスキーマを構築

    Args:
        frame: FrameSpec
        pa: panderaモジュール

    Returns:
        Panderaスキーマ
    """
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
    return pa.DataFrameSchema(columns, index=index_schema, coerce=frame.coerce)


def _validate_dataframe_against_schema(
    example_id: str, input_data: dict, frame: Any, pd: Any, pa: Any  # noqa: ANN401
) -> str | None:
    """DataFrameをスキーマに対して検証

    Args:
        example_id: Example ID
        input_data: 入力データ
        frame: FrameSpec
        pd: pandasモジュール
        pa: panderaモジュール

    Returns:
        エラーメッセージ、または None（成功時）
    """
    try:
        # inputをDataFrameに変換
        df = pd.DataFrame(input_data)

        # Panderaスキーマを動的に生成して検証
        schema = _build_pandera_schema(frame, pa)

        # 検証実行
        schema.validate(df, lazy=True)
        return None

    except pa.errors.SchemaErrors:
        # 複数のエラーをまとめて報告
        return f"Example '{example_id}': input data violates schema for '{frame.id}'"
    except Exception as e:
        # その他のエラー（DataFrameの作成失敗など）
        return f"Example '{example_id}': failed to validate input data - {str(e)}"


def validate_example_data(ir: SpecIR) -> list[str]:
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

        # 検証実行
        error = _validate_dataframe_against_schema(example.id, example.input, frame, pd, pa)
        if error:
            errors.append(error)

    return errors


def _pandera_dtype_from_str(dtype_str: str) -> type | str | None:
    """dtype文字列をPandera型に変換

    Args:
        dtype_str: dtype文字列

    Returns:
        Pandera型、または None
    """
    mapping: dict[str, type | str] = {
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "datetime": "datetime64[ns]",
    }
    return mapping.get(dtype_str.lower())

"""Validator: Exampleデータ検証

Exampleデータがschemaに適合しているかをPanderaを使って検証する。
"""

from __future__ import annotations

from spectool.spectool.core.base.ir import SpecIR


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

        except pa.errors.SchemaErrors:
            # 複数のエラーをまとめて報告
            error_msg = f"Example '{example.id}': input data violates schema for '{example.datatype_ref}'"
            errors.append(error_msg)
        except Exception as e:
            # その他のエラー（DataFrameの作成失敗など）
            errors.append(f"Example '{example.id}': failed to validate input data - {str(e)}")

    return errors


def _pandera_dtype_from_str(dtype_str: str) -> type | str | None:
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

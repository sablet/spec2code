"""Pandera Schema生成バックエンド

IRからPandera SchemaModelを生成。
"""

from __future__ import annotations

from pathlib import Path

from spectool.spectool.core.base.ir import ColumnRule, FrameSpec, IndexRule, MultiIndexLevel, SpecIR


def _pandera_dtype_string(dtype: str) -> str:
    """dtypeをPandera型アノテーションに変換"""
    mapping = {
        "datetime": "pd.DatetimeTZDtype",
        "float": "float",
        "int": "int",
        "str": "str",
        "bool": "bool",
    }
    return mapping.get(dtype.lower(), "Any")


def _render_imports() -> str:
    """必要なインポート文を返す"""
    imports = [
        "import pandera as pa",
        "from pandera.typing import Index, Series",
        "import pandas as pd",
        "from typing import Any",
    ]
    return "\n".join(imports)


def _render_index_field(index: IndexRule) -> str:
    """Index定義を生成"""
    pandera_dtype = _pandera_dtype_string(index.dtype)
    field_args = []

    if index.nullable:
        field_args.append(f"nullable={index.nullable}")
    if index.unique:
        field_args.append(f"unique={index.unique}")
    if index.monotonic:
        if index.monotonic == "increasing":
            field_args.append("monotonic=True")
        elif index.monotonic == "decreasing":
            field_args.append("monotonic='decreasing'")

    field_str = f"pa.Field({', '.join(field_args)})" if field_args else "pa.Field()"

    comment = f"  # {index.description}" if index.description else ""
    return f"    {index.name}: Index[{pandera_dtype}] = {field_str}{comment}"


def _render_multi_index_fields(multi_index: list[MultiIndexLevel]) -> list[str]:
    """MultiIndex定義を生成"""
    lines = []
    for level in multi_index:
        pandera_dtype = _pandera_dtype_string(level.dtype)
        comment = f"  # {level.description}" if level.description else ""
        lines.append(f"    {level.name}: Index[{pandera_dtype}] = pa.Field(){comment}")
    return lines


def _render_column_field(col: ColumnRule) -> str:
    """Column定義を生成"""
    pandera_dtype = _pandera_dtype_string(col.dtype)

    field_args = [f"nullable={col.nullable}"]

    # checks（ge, le, gt, lt, isin等）をpa.Fieldの引数として追加
    for check in col.checks:
        check_type = check.get("type")
        check_value = check.get("value")

        if check_type in ("ge", "le", "gt", "lt"):
            field_args.append(f"{check_type}={check_value}")
        elif check_type == "isin":
            field_args.append(f"isin={check_value}")

    field_str = f"pa.Field({', '.join(field_args)})"

    comment = f"  # {col.description}" if col.description else ""
    return f"    {col.name}: Series[{pandera_dtype}] = {field_str}{comment}"


def _render_config(frame: FrameSpec) -> list[str]:
    """Config定義を生成"""
    lines = []
    lines.append("    class Config:")
    lines.append(f"        strict = {frame.strict}")
    lines.append(f"        coerce = {frame.coerce}")

    if frame.ordered:
        lines.append(f"        ordered = {frame.ordered}")

    return lines


def _generate_pandera_schema_class(frame: FrameSpec) -> str:
    """Pandera SchemaModelクラスを生成"""
    lines = []

    # クラス定義
    class_name = f"{frame.id}Schema"
    lines.append(f"class {class_name}(pa.DataFrameModel):")

    # docstring
    description = frame.description or f"{frame.id} DataFrame schema for validation"
    lines.append(f'    """{description}"""')
    lines.append("")

    # Index定義
    if frame.index:
        lines.append("    # Index定義")
        lines.append(_render_index_field(frame.index))
        lines.append("")

    # MultiIndex定義
    if frame.multi_index:
        lines.append("    # MultiIndex定義")
        multi_index_lines = _render_multi_index_fields(frame.multi_index)
        lines.extend(multi_index_lines)
        lines.append("")

    # Column定義
    if frame.columns:
        lines.append("    # Column定義")
        for col in frame.columns:
            lines.append(_render_column_field(col))
        lines.append("")

    # Config
    lines.extend(_render_config(frame))

    return "\n".join(lines)


def generate_pandera_schemas(ir: SpecIR, output_path: Path) -> None:
    """Pandera SchemaModelを生成

    Args:
        ir: 統合IR
        output_path: 出力ファイルパス
    """
    if not ir.frames:
        print("  ⏭️  Skip (no DataFrame schemas to generate)")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ヘッダー
    header = [
        '"""生成されたPandera Schema（DataFrame検証用）',
        "",
        "このファイルは spectool が spec.yaml から自動生成します。",
        "FrameSpec（YAML内のdataframes定義）からPandera SchemaModelを生成します。",
        '"""',
        "",
    ]

    # インポート
    imports = _render_imports()

    # Schema定義
    schema_sections = []
    for frame in ir.frames:
        schema_class = _generate_pandera_schema_class(frame)
        schema_sections.append(schema_class)
        schema_sections.append("")  # 空行

    # ファイル構築
    content = "\n".join(header) + imports + "\n\n\n" + "\n".join(schema_sections)

    output_path.write_text(content)
    print(f"  ✅ Generated: {output_path}")


if __name__ == "__main__":
    """CLI実行（テスト用）"""
    import sys
    from spectool.spectool.core.engine.loader import load_spec

    if len(sys.argv) < 3:
        print("Usage: python -m spectool.backends.py_validators <spec.yaml> -o <output.py>")
        sys.exit(1)

    spec_path = sys.argv[1]
    output_arg_idx = sys.argv.index("-o") if "-o" in sys.argv else -1
    if output_arg_idx == -1 or output_arg_idx + 1 >= len(sys.argv):
        print("Error: -o <output.py> required")
        sys.exit(1)

    output_path = Path(sys.argv[output_arg_idx + 1])

    # Load spec and generate
    ir = load_spec(spec_path)
    generate_pandera_schemas(ir, output_path)

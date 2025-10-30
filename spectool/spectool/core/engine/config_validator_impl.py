"""Config検証 - 実装チェック

関数の実装状況とシグネチャをチェックするヘルパー関数。
"""

from __future__ import annotations

import importlib
import inspect
from typing import Any

from spectool.spectool.core.base.ir import SpecIR


def resolve_impl_path(impl: str, spec: SpecIR) -> str:
    """implパスを解決（apps. プレフィックスをプロジェクト名を含む形に変換）

    Args:
        impl: 元のimplパス (例: "apps.transforms:func")
        spec: SpecIR（プロジェクト名取得用）

    Returns:
        解決されたimplパス (例: "apps.sample-project.transforms:func")
    """
    if not impl.startswith("apps."):
        return impl

    # プロジェクト名を取得（ハイフンをアンダースコアに変換）
    app_name = spec.meta.name if spec.meta else "app"
    app_name = app_name.replace("-", "_")  # Pythonモジュール名としてハイフンは無効

    # "apps." の後の部分を取得
    rest = impl[5:]  # "apps." を除去

    # "apps.<project-name>." + 残りの部分
    return f"apps.{app_name}.{rest}"


def load_transform_signature(transform_id: str, impl: str, spec: SpecIR) -> tuple[inspect.Signature | None, list[str]]:
    """Transform関数をインポートしてシグネチャを取得

    Args:
        transform_id: Transform ID
        impl: 実装パス (module:function形式)
        spec: SpecIR（implパス解決用）

    Returns:
        (signature, errors): シグネチャとエラーリスト
    """
    if not impl:
        return None, [f"Transform '{transform_id}': missing implementation"]

    # implパスを解決
    resolved_impl = resolve_impl_path(impl, spec)

    try:
        module_path, func_name = resolved_impl.rsplit(":", 1)
    except ValueError as exc:
        return None, [f"Transform '{transform_id}': invalid impl '{impl}': {exc}"]

    try:
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
    except ImportError as exc:
        return None, [f"Transform '{transform_id}': import failed - {exc}"]
    except AttributeError as exc:
        return None, [f"Transform '{transform_id}': function not found - {exc}"]

    try:
        return inspect.signature(func), []
    except (TypeError, ValueError) as exc:
        return None, [f"Transform '{transform_id}': signature error - {exc}"]


def _extract_code_lines(lines: list[str]) -> list[str]:
    """ソースコードから実質的なコード行を抽出

    Args:
        lines: ソースコードの行リスト

    Returns:
        コード行のリスト（コメント、docstring、空行を除外）
    """
    code_lines = []
    for line in lines:
        stripped = line.strip()
        # docstring、コメント、空行、関数定義行を除外
        if (
            stripped
            and not stripped.startswith("#")
            and not stripped.startswith('"""')
            and not stripped.startswith("'''")
            and not stripped.startswith("def ")
        ):
            code_lines.append(stripped)
    return code_lines


def _filter_docstrings(code_lines: list[str]) -> list[str]:
    """コード行からdocstringを除外

    Args:
        code_lines: コード行のリスト

    Returns:
        docstringを除外したコード行のリスト
    """
    filtered_lines = []
    in_docstring = False
    for line in code_lines:
        if '"""' in line or "'''" in line:
            if in_docstring:
                in_docstring = False
                continue
            in_docstring = True
            continue
        if not in_docstring:
            filtered_lines.append(line)
    return filtered_lines


def _is_placeholder_implementation(filtered_lines: list[str]) -> bool:
    """実装がプレースホルダーのみかチェック

    Args:
        filtered_lines: フィルタリングされたコード行

    Returns:
        プレースホルダーのみの場合True
    """
    if len(filtered_lines) > 1:
        return False

    if not filtered_lines:
        return False

    placeholders = ["return True", "return pd.DataFrame()", "return None", "return {}"]
    return any(keyword in filtered_lines[0] for keyword in placeholders)


def check_function_implementation(func: Any, transform_id: str) -> list[str]:  # noqa: ANN401
    """関数が実装されているかをチェック（TODOのままではないか）

    Args:
        func: チェックする関数
        transform_id: Transform ID

    Returns:
        エラーメッセージリスト（実装されていれば空リスト）
    """
    try:
        source = inspect.getsource(func)
    except (OSError, TypeError):
        # ソースコードが取得できない場合（ビルトイン関数など）は実装されているとみなす
        return []

    # docstringとコメントからTODOパターンを検出
    if "TODO: Implement" in source or "# TODO: Implement" in source:
        return [f"Transform '{transform_id}': implementation incomplete (TODO markers found)"]

    # 関数本体が単純なプレースホルダーのみかチェック
    lines = source.split("\n")
    code_lines = _extract_code_lines(lines)
    filtered_lines = _filter_docstrings(code_lines)

    # 実質的なコード行が1行以下（returnのみなど）の場合は未実装とみなす
    if _is_placeholder_implementation(filtered_lines):
        return [f"Transform '{transform_id}': implementation incomplete (placeholder return value only)"]

    return []

"""Normalizer: IR正規化

メタハンドラRegistryを用いてIRを正規化する。
主な機能:
1. PydanticRowHandlerによるDataFrame列定義の推論
2. 拡張可能なメタハンドラRegistry
"""

from __future__ import annotations

import importlib
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Protocol

from spectool.core.base.ir import ColumnRule, SpecIR


class MetaHandler(Protocol):
    """メタハンドラのプロトコル"""

    def __call__(self, ir: SpecIR) -> SpecIR:
        """IRを正規化する

        Args:
            ir: 入力IR

        Returns:
            正規化されたIR
        """
        ...


@dataclass
class MetaHandlerRegistry:
    """メタハンドラのRegistry"""

    handlers: list[MetaHandler] = field(default_factory=list)

    def register(self, handler: MetaHandler) -> None:
        """ハンドラを登録"""
        self.handlers.append(handler)

    def apply_all(self, ir: SpecIR) -> SpecIR:
        """全てのハンドラを適用"""
        result = ir
        for handler in self.handlers:
            result = handler(result)
        return result


# グローバルRegistry
_global_registry = MetaHandlerRegistry()


def register_meta_handler(handler: MetaHandler) -> None:
    """メタハンドラを登録（グローバル）

    Args:
        handler: 登録するハンドラ
    """
    _global_registry.register(handler)


def normalize_ir(ir: SpecIR) -> SpecIR:
    """IRを正規化

    Args:
        ir: 入力IR

    Returns:
        正規化されたIR
    """
    return _global_registry.apply_all(ir)


# ===== Built-in Handlers =====


def pydantic_row_handler(ir: SpecIR) -> SpecIR:
    """PydanticRowHandlerハンドラ

    FrameSpec.row_modelが設定されている場合:
    1. 動的にPydanticモデルをimport
    2. model_fieldsから列定義を抽出
    3. 既存の列定義とマージ（優先度: Pydantic < SchemaSpec）

    Args:
        ir: 入力IR

    Returns:
        正規化されたIR
    """
    ir_copy = deepcopy(ir)

    for frame in ir_copy.frames:
        if not frame.row_model:
            continue

        # Python型参照を解決
        try:
            model_class = _import_python_type(frame.row_model)
        except Exception:
            # インポート失敗時は警告のみ（Validator側で検出）
            continue

        # Pydanticモデルのmodel_fieldsを取得
        if not hasattr(model_class, "model_fields"):
            # Pydanticモデルでない場合はスキップ
            continue

        # 既存列名をセットに格納（優先度マージ用）
        existing_col_names = {col.name for col in frame.columns}

        # model_fieldsから列定義を推論
        for field_name, field_info in model_class.model_fields.items():
            if field_name in existing_col_names:
                # 既存定義が優先
                continue

            # フィールドの型情報から列定義を生成
            dtype = _infer_dtype_from_pydantic_field(field_info)
            nullable = not field_info.is_required()

            col_rule = ColumnRule(
                name=field_name,
                dtype=dtype,
                nullable=nullable,
                unique=False,
                coerce=True,
                checks=[],
                description=field_info.description or "",
            )
            frame.columns.append(col_rule)

    return ir_copy


def _import_python_type(type_ref: str) -> Any:
    """Python型参照をインポート

    Args:
        type_ref: "module.path:ClassName"形式の参照

    Returns:
        インポートされた型

    Raises:
        ValueError: 不正なフォーマット
        ImportError: インポート失敗
    """
    if ":" not in type_ref:
        raise ValueError(f"Invalid type reference format (expected 'module:class'): {type_ref}")

    module_path, class_name = type_ref.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _infer_dtype_from_pydantic_field(field_info: Any) -> str:
    """Pydanticフィールドからdtypeを推論

    Args:
        field_info: Pydanticのフィールド情報

    Returns:
        dtype文字列（"float", "int", "str", "datetime"等）
    """
    # field_info.annotationから型を取得
    annotation = field_info.annotation

    # 型名を文字列に変換
    if hasattr(annotation, "__name__"):
        type_name = annotation.__name__
    else:
        type_name = str(annotation)

    # Pandera互換のdtype文字列にマッピング
    type_mapping = {
        "int": "int",
        "float": "float",
        "str": "str",
        "bool": "bool",
        "datetime": "datetime",
        "date": "date",
        "Decimal": "float",
    }

    for key, value in type_mapping.items():
        if key in type_name:
            return value

    # デフォルトはstr
    return "str"


# Built-inハンドラを自動登録
register_meta_handler(pydantic_row_handler)

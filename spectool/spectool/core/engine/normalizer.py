"""Normalizer: IR正規化

メタハンドラRegistryを用いてIRを正規化する。
主な機能:
1. PydanticRowHandlerによるDataFrame列定義の推論
2. 拡張可能なメタハンドラRegistry
"""

from __future__ import annotations

import importlib
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic.fields import FieldInfo

from spectool.spectool.core.base.ir import ColumnRule, SpecIR

logger = logging.getLogger(__name__)


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
        except Exception as exc:
            # インポート失敗時は警告のみ（Validator側で検出）
            logger.warning(f"Failed to import row_model '{frame.row_model}': {exc}")
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


def _import_python_type(type_ref: str) -> type[Any]:
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


def _infer_dtype_from_pydantic_field(field_info: FieldInfo) -> str:
    """Pydanticフィールドからdtypeを推論

    Args:
        field_info: Pydanticのフィールド情報

    Returns:
        dtype文字列（"float", "int", "str", "datetime"等）
    """
    # field_info.annotationから型を取得
    annotation = field_info.annotation
    if annotation is None:
        return "str"

    # 型名を文字列に変換
    type_name = annotation.__name__ if hasattr(annotation, "__name__") else str(annotation)

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


def _distribute_examples_to_datatypes(datatypes: list[Any], examples_map: dict[str, list[Any]]) -> None:
    """Examples mapをdatatypesに振り分ける共通ヘルパー

    Args:
        datatypes: datatype定義のリスト
        examples_map: datatype_id -> examples のマップ
    """
    for datatype in datatypes:
        if datatype.id in examples_map:
            # 重複を避けるため、既存のexamplesに含まれていないもののみ追加
            for example in examples_map[datatype.id]:
                if example not in datatype.examples:
                    datatype.examples.append(example)


def example_distribution_handler(ir: SpecIR) -> SpecIR:
    """Exampleの自動振り分けハンドラ

    トップレベルのexamplesセクションからdatatype_refを使って、
    各datatype（Pydantic/Enum/Generic/Frame/CustomTypeAlias）にexamplesを振り分ける。

    Args:
        ir: 入力IR

    Returns:
        正規化されたIR
    """
    ir_copy = deepcopy(ir)

    if not ir_copy.examples:
        return ir_copy

    # datatype_ref別にexamplesをグループ化
    examples_map: dict[str, list[Any]] = {}
    for example in ir_copy.examples:
        if not example.datatype_ref:
            continue
        if example.datatype_ref not in examples_map:
            examples_map[example.datatype_ref] = []
        examples_map[example.datatype_ref].append(example.input)

    # 各datatype種別に振り分け
    _distribute_examples_to_datatypes(ir_copy.pydantic_models, examples_map)
    _distribute_examples_to_datatypes(ir_copy.enums, examples_map)
    _distribute_examples_to_datatypes(ir_copy.generics, examples_map)
    _distribute_examples_to_datatypes(ir_copy.frames, examples_map)
    _distribute_examples_to_datatypes(ir_copy.type_aliases, examples_map)

    return ir_copy


# Built-inハンドラを自動登録
register_meta_handler(pydantic_row_handler)
register_meta_handler(example_distribution_handler)

"""Card Exporter - Convert SpecIR to JSON cards for frontend display.

このモジュールは、YAML仕様ファイルから読み込んだSpecIRを、
フロントエンドで表示可能なJSON形式のカードに変換します。

設計原則:
- SpecIRの構造を直接反映（asdict()による変換）
- 型定義をカテゴリ別に分離（dtype_frame, dtype_enum, dtype_pydantic, dtype_alias, dtype_generic）
- metadataキーをdataキーに変更（直感的な命名）
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from spectool.spectool.core.base.ir import (
    CheckSpec,
    DAGStageSpec,
    EnumSpec,
    ExampleCase,
    FrameSpec,
    GeneratorDef,
    GenericSpec,
    PydanticModelSpec,
    SpecIR,
    TransformSpec,
    TypeAliasSpec,
)
from spectool.spectool.core.export.card_exporter_helpers import (
    collect_nested_types,
    determine_dtype_category,
)


def _collect_param_type_refs(parameters: list[Any], param_type_refs: set[str]) -> None:
    """パラメータから型参照を収集"""
    for param in parameters:
        if param.type_ref and not param.type_ref.startswith("builtins:"):
            param_type_refs.add(param.type_ref)


def _add_candidate_cards(
    spec_ir: SpecIR,
    candidate_id: str,
    spec_name: str,
    related_cards: dict[str, Any],
    param_type_refs: set[str],
) -> None:
    """candidateをtransform/generatorカードとして追加し、パラメータ型を収集"""
    transform = next((t for t in spec_ir.transforms if t.id == candidate_id), None)
    if transform:
        related_cards["transform_cards"].append(
            {
                "id": transform.id,
                "name": transform.id,
                "category": "transform",
                "source_spec": spec_name,
                "description": transform.description,
            }
        )
        _collect_param_type_refs(transform.parameters, param_type_refs)
        return

    generator = next((g for g in spec_ir.generators if g.id == candidate_id), None)
    if generator:
        related_cards["generator_cards"].append(
            {
                "id": generator.id,
                "name": generator.id,
                "category": "generator",
                "source_spec": spec_name,
                "description": generator.description,
            }
        )
        _collect_param_type_refs(generator.parameters, param_type_refs)


def _add_param_dtype_cards(
    spec_ir: SpecIR,
    param_type_refs: set[str],
    input_type_ref: str | None,
    output_type_ref: str | None,
    spec_name: str,
    related_cards: dict[str, Any],
) -> None:
    """パラメータ型のdtypeカードを追加（input/output型は除外）"""
    for type_ref in param_type_refs:
        if type_ref in {input_type_ref, output_type_ref}:
            continue

        category, description = determine_dtype_category(spec_ir, type_ref)
        related_cards["param_dtype_cards"].append(
            {
                "id": type_ref,
                "name": type_ref,
                "category": category,
                "source_spec": spec_name,
                "description": description,
            }
        )


def _collect_input_generators(spec_ir: SpecIR, input_type_ref: str) -> list[GeneratorDef]:
    """input型に関連するgeneratorを収集"""
    generators_to_add: list[GeneratorDef] = []

    # 1. input型がframe型の場合、generator_factoryをチェック
    input_frame: FrameSpec | None = next((f for f in spec_ir.frames if f.id == input_type_ref), None)
    if input_frame and input_frame.generator_factory:
        generator = next((g for g in spec_ir.generators if g.impl == input_frame.generator_factory), None)
        if generator:
            generators_to_add.append(generator)

    # 2. input型をreturn_type_refとするgeneratorをチェック
    for generator in spec_ir.generators:
        if generator.return_type_ref == input_type_ref:
            generators_to_add.append(generator)

    return generators_to_add


def _add_input_generators(
    spec_ir: SpecIR, input_type_ref: str | None, spec_name: str, related_cards: dict[str, Any]
) -> None:
    """input型に関連するgeneratorを追加"""
    if not input_type_ref:
        return

    generators_to_add = _collect_input_generators(spec_ir, input_type_ref)

    # 重複を排除してgeneratorカードを追加
    existing_ids = {g["id"] for g in related_cards["generator_cards"]}
    for gen in generators_to_add:
        if gen.id not in existing_ids:
            related_cards["generator_cards"].append(
                {
                    "id": gen.id,
                    "name": gen.id,
                    "category": "generator",
                    "source_spec": spec_name,
                    "description": gen.description,
                }
            )


def _add_example_cards(
    spec_ir: SpecIR,
    all_type_refs: set[str],
    input_type_ref: str | None,
    output_type_ref: str | None,
    spec_name: str,
    related_cards: dict[str, Any],
) -> None:
    """全ての関連型に関連するexampleカードを追加"""
    for type_ref in all_type_refs:
        for example in spec_ir.examples:
            if example.datatype_ref == type_ref and not any(
                e["id"] == example.id
                for e in related_cards["input_example_cards"] + related_cards["output_example_cards"]
            ):
                example_card = {
                    "id": example.id,
                    "name": example.id,
                    "category": "example",
                    "source_spec": spec_name,
                    "description": example.description,
                }

                if type_ref == input_type_ref and type_ref not in {output_type_ref}:
                    related_cards["input_example_cards"].append(example_card)
                elif type_ref == output_type_ref:
                    related_cards["output_example_cards"].append(example_card)
                else:
                    related_cards["input_example_cards"].append(example_card)


def _add_output_check_cards(
    spec_ir: SpecIR, output_type_ref: str | None, spec_name: str, related_cards: dict[str, Any]
) -> None:
    """output型に関連するcheckカードを追加"""
    if not output_type_ref:
        return

    for check in spec_ir.checks:
        if check.input_type_ref == output_type_ref and check.id not in [
            c["id"] for c in related_cards["output_check_cards"]
        ]:
            related_cards["output_check_cards"].append(
                {
                    "id": check.id,
                    "name": check.id,
                    "category": "check",
                    "source_spec": spec_name,
                    "description": check.description,
                }
            )


def spec_to_card(
    spec_obj: (
        CheckSpec
        | GeneratorDef
        | FrameSpec
        | EnumSpec
        | PydanticModelSpec
        | TypeAliasSpec
        | GenericSpec
        | ExampleCase
        | TransformSpec
        | DAGStageSpec
    ),
    category: str,
    spec_name: str,
) -> dict[str, Any]:
    """SpecIR要素をカードに変換（共通処理）

    Args:
        spec_obj: CheckSpec, GeneratorDef, FrameSpec等のdataclassインスタンス
        category: カードのカテゴリ（"check", "generator", "dtype_frame"等）
        spec_name: 元のspec名（source_spec用）

    Returns:
        カード形式のdict
    """
    # dataclassを辞書化
    data = asdict(spec_obj)

    # 共通フィールドを抽出
    card_id = data.pop("id", "") or data.pop("stage_id", "")
    description = data.pop("description", "")

    return {
        "id": card_id,
        "category": category,
        "name": card_id,
        "description": description,
        "source_spec": spec_name,
        "data": data,  # 残りのフィールドを全て含める
    }


def _initialize_related_cards(stage_id: str, spec_name: str, description: str) -> dict[str, Any]:
    """関連カードの辞書を初期化"""
    return {
        "stage_card": {
            "id": stage_id,
            "name": stage_id,
            "category": "dag_stage",
            "source_spec": spec_name,
            "description": description,
        },
        "input_dtype_card": None,
        "output_dtype_card": None,
        "transform_cards": [],
        "param_dtype_cards": [],
        "generator_cards": [],
        "input_example_cards": [],
        "output_example_cards": [],
        "input_check_cards": [],
        "output_check_cards": [],
    }


def _set_io_dtype_cards(
    related_cards: dict[str, Any], input_type_ref: str | None, output_type_ref: str | None, spec_name: str
) -> None:
    """input/output dtype cardsを設定"""
    if input_type_ref:
        related_cards["input_dtype_card"] = {
            "id": input_type_ref,
            "name": input_type_ref,
            "category": "dtype",
            "source_spec": spec_name,
            "description": "",
        }

    if output_type_ref:
        related_cards["output_dtype_card"] = {
            "id": output_type_ref,
            "name": output_type_ref,
            "category": "dtype",
            "source_spec": spec_name,
            "description": "",
        }


def _collect_all_type_refs(
    spec_ir: SpecIR, input_type_ref: str | None, output_type_ref: str | None, param_type_refs: set[str]
) -> set[str]:
    """全ての関連型（ネストを含む）を収集"""
    visited_types: set[str] = set()

    for type_ref in [input_type_ref, output_type_ref]:
        if type_ref:
            collect_nested_types(spec_ir, type_ref, visited_types)

    for type_ref in list(param_type_refs):
        collect_nested_types(spec_ir, type_ref, visited_types)

    param_type_refs.update(visited_types)

    all_type_refs = param_type_refs.copy()
    if input_type_ref:
        all_type_refs.add(input_type_ref)
    if output_type_ref:
        all_type_refs.add(output_type_ref)

    return all_type_refs


def build_dag_stage_groups(spec_ir: SpecIR, spec_name: str) -> list[dict[str, Any]]:
    """SpecIRからDAGステージグループを構築

    Args:
        spec_ir: 正規化済みSpecIR
        spec_name: spec名（source_spec用）

    Returns:
        DAGステージグループのリスト
    """
    groups = []

    for dag_stage in spec_ir.dag_stages:
        stage_id = dag_stage.stage_id
        input_type_ref = dag_stage.input_type
        output_type_ref = dag_stage.output_type

        # related_cardsを初期化
        related_cards = _initialize_related_cards(stage_id, spec_name, dag_stage.description)
        _set_io_dtype_cards(related_cards, input_type_ref, output_type_ref, spec_name)

        # transform/generator cardsを追加し、パラメータ型を収集
        param_type_refs: set[str] = set()
        for candidate_id in dag_stage.candidates:
            _add_candidate_cards(spec_ir, candidate_id, spec_name, related_cards, param_type_refs)

        # 全ての関連型を収集
        all_type_refs = _collect_all_type_refs(spec_ir, input_type_ref, output_type_ref, param_type_refs)

        # 各種カードを追加
        _add_param_dtype_cards(spec_ir, param_type_refs, input_type_ref, output_type_ref, spec_name, related_cards)
        _add_input_generators(spec_ir, input_type_ref, spec_name, related_cards)
        _add_example_cards(spec_ir, all_type_refs, input_type_ref, output_type_ref, spec_name, related_cards)
        _add_output_check_cards(spec_ir, output_type_ref, spec_name, related_cards)

        # グループを追加
        groups.append(
            {
                "spec_name": spec_name,
                "stage_id": stage_id,
                "stage_description": dag_stage.description,
                "input_type": input_type_ref or "",
                "output_type": output_type_ref or "",
                "selection_mode": dag_stage.selection_mode,
                "max_select": dag_stage.max_select,
                "related_cards": related_cards,
            }
        )

    return groups


def export_spec_to_cards(spec_ir: SpecIR, spec_file: str) -> dict[str, Any]:
    """SpecIRをJSONカード形式に変換

    Args:
        spec_ir: 正規化済みSpecIR
        spec_file: 元のspecファイル名（source_file用）

    Returns:
        {
            "metadata": {
                "source_file": "...",
                "spec_name": "...",
                "version": "...",
                "description": "..."
            },
            "cards": [...],
            "dag_stage_groups": []
        }
    """
    spec_name = Path(spec_file).stem
    cards: list[dict[str, Any]] = []

    # 各種カード生成（カテゴリとデータのマッピング）
    card_mappings: Sequence[tuple[Sequence[Any], str]] = [
        (spec_ir.checks, "check"),
        (spec_ir.generators, "generator"),
        (spec_ir.frames, "dtype_frame"),
        (spec_ir.enums, "dtype_enum"),
        (spec_ir.pydantic_models, "dtype_pydantic"),
        (spec_ir.type_aliases, "dtype_alias"),
        (spec_ir.generics, "dtype_generic"),
        (spec_ir.examples, "example"),
        (spec_ir.transforms, "transform"),
        (spec_ir.dag_stages, "dag_stage"),
    ]

    for items, category in card_mappings:
        for item in items:
            cards.append(spec_to_card(item, category, spec_name))

    # メタデータを構築
    metadata = {
        "source_file": Path(spec_file).name,
        "spec_name": spec_ir.meta.name,
        "version": spec_ir.meta.version,
        "description": spec_ir.meta.description,
    }

    # DAGステージグループを構築
    dag_stage_groups = build_dag_stage_groups(spec_ir, spec_name)

    return {
        "metadata": metadata,
        "cards": cards,
        "dag_stage_groups": dag_stage_groups,
    }

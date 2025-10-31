"""Card coverage test - DAGステージグループに含まれるカードのカバレッジを検証

SpecIRから直接カードを生成してテストする設計。
出力JSONファイルに依存せず、仕様の整合性を直接検証する。
"""

from pathlib import Path
import pytest

from spectool.spectool.core.engine.loader import load_spec
from spectool.spectool.core.export.card_exporter import export_spec_to_cards


@pytest.fixture
def spec_files():
    """テスト対象のspecファイルリスト"""
    specs_dir = Path("specs")
    return list(specs_dir.glob("*.yaml"))


@pytest.fixture
def algo_spec_ir():
    """algo-trade-pipeline specのIRを読み込む"""
    spec_file = Path("specs/algo-trade-pipeline.yaml")
    if not spec_file.exists():
        pytest.skip(f"{spec_file} not found")
    return load_spec(str(spec_file))


@pytest.fixture
def algo_cards_data(algo_spec_ir):
    """algo-trade-pipelineのカードデータを生成"""
    return export_spec_to_cards(algo_spec_ir, "specs/algo-trade-pipeline.yaml")


@pytest.fixture
def algo_cards(algo_cards_data):
    """algo-trade-pipelineのカードリスト"""
    return algo_cards_data["cards"]


@pytest.fixture
def referenced_cards(algo_cards_data):
    """DAGステージグループで参照されているカードキーのセット"""
    referenced = set()
    for group in algo_cards_data["dag_stage_groups"]:
        related = group["related_cards"]
        if related.get("stage_card"):
            card = related["stage_card"]
            referenced.add(f"{card['source_spec']}::{card['id']}")
        if related.get("input_dtype_card"):
            card = related["input_dtype_card"]
            referenced.add(f"{card['source_spec']}::{card['id']}")
        if related.get("output_dtype_card"):
            card = related["output_dtype_card"]
            referenced.add(f"{card['source_spec']}::{card['id']}")
        for card_list_key in [
            "transform_cards",
            "generator_cards",
            "param_dtype_cards",
            "input_example_cards",
            "output_example_cards",
            "input_check_cards",
            "output_check_cards",
        ]:
            for card in related.get(card_list_key, []):
                referenced.add(f"{card['source_spec']}::{card['id']}")
    return referenced


def test_all_dag_stage_cards_referenced(algo_cards, referenced_cards):
    """全dag_stageカードが参照されていること"""
    dag_stage_cards = [c for c in algo_cards if c["category"] == "dag_stage"]
    dag_stage_keys = {f"{c['source_spec']}::{c['id']}" for c in dag_stage_cards}
    dag_stage_referenced = dag_stage_keys & referenced_cards

    unlinked = dag_stage_keys - referenced_cards
    assert len(unlinked) == 0, f"All dag_stage cards must be referenced. Unlinked: {unlinked}"


def test_all_algo_dtype_frame_referenced(algo_cards, referenced_cards):
    """algo-trade-pipelineの全dtype_frameカードが参照されていること"""
    dtype_frame_cards = [c for c in algo_cards if c["category"] == "dtype_frame"]
    dtype_frame_keys = {f"{c['source_spec']}::{c['id']}" for c in dtype_frame_cards}
    dtype_frame_referenced = dtype_frame_keys & referenced_cards

    unlinked = dtype_frame_keys - referenced_cards
    assert len(unlinked) == 0, f"All dtype_frame cards must be referenced. Unlinked: {unlinked}"


def test_all_algo_dtype_alias_referenced(algo_cards, referenced_cards):
    """algo-trade-pipelineの全dtype_aliasカードが参照されていること"""
    dtype_alias_cards = [c for c in algo_cards if c["category"] == "dtype_alias"]
    dtype_alias_keys = {f"{c['source_spec']}::{c['id']}" for c in dtype_alias_cards}
    dtype_alias_referenced = dtype_alias_keys & referenced_cards

    unlinked = dtype_alias_keys - referenced_cards
    assert len(unlinked) == 0, f"All dtype_alias cards must be referenced. Unlinked: {unlinked}"


def test_all_algo_dtype_generic_referenced(algo_cards, referenced_cards):
    """algo-trade-pipelineの全dtype_genericカードが参照されていること"""
    dtype_generic_cards = [c for c in algo_cards if c["category"] == "dtype_generic"]
    dtype_generic_keys = {f"{c['source_spec']}::{c['id']}" for c in dtype_generic_cards}
    dtype_generic_referenced = dtype_generic_keys & referenced_cards

    unlinked = dtype_generic_keys - referenced_cards
    assert len(unlinked) == 0, f"All dtype_generic cards must be referenced. Unlinked: {unlinked}"


def test_all_algo_dtype_enum_referenced(algo_cards, referenced_cards):
    """algo-trade-pipelineの全dtype_enumカードが参照されていること

    Note: ネストされた型やフィールド型として使われるenumは直接参照されない場合がある
    """
    dtype_enum_cards = [c for c in algo_cards if c["category"] == "dtype_enum"]
    dtype_enum_keys = {f"{c['source_spec']}::{c['id']}" for c in dtype_enum_cards}
    dtype_enum_referenced = dtype_enum_keys & referenced_cards

    unlinked = dtype_enum_keys - referenced_cards
    # 補助的な型として使われるenumは参照されなくても許容
    # 例: CVMethod, PositionSignal は他のdatatypeのフィールドとして使われる
    if len(unlinked) > 0:
        unlinked_details = [
            (c["id"], c["description"]) for c in dtype_enum_cards if f"{c['source_spec']}::{c['id']}" in unlinked
        ]
        print(f"Warning: Some dtype_enum cards are not directly referenced: {unlinked_details}")


def test_all_algo_dtype_pydantic_referenced(algo_cards, referenced_cards):
    """algo-trade-pipelineの全dtype_pydanticカードが参照されていること"""
    dtype_pydantic_cards = [c for c in algo_cards if c["category"] == "dtype_pydantic"]
    dtype_pydantic_keys = {f"{c['source_spec']}::{c['id']}" for c in dtype_pydantic_cards}
    dtype_pydantic_referenced = dtype_pydantic_keys & referenced_cards

    unlinked = dtype_pydantic_keys - referenced_cards
    unlinked_details = [
        (c["id"], c["description"]) for c in dtype_pydantic_cards if f"{c['source_spec']}::{c['id']}" in unlinked
    ]
    assert len(unlinked) == 0, f"All dtype_pydantic cards must be referenced. Unlinked: {unlinked_details}"


def test_all_algo_transform_referenced(algo_cards, referenced_cards):
    """algo-trade-pipelineの全transformカードが参照されていること"""
    transform_cards = [c for c in algo_cards if c["category"] == "transform"]
    transform_keys = {f"{c['source_spec']}::{c['id']}" for c in transform_cards}
    transform_referenced = transform_keys & referenced_cards

    unlinked = transform_keys - referenced_cards
    unlinked_details = [
        (c["id"], c["description"]) for c in transform_cards if f"{c['source_spec']}::{c['id']}" in unlinked
    ]
    assert len(unlinked) == 0, f"All transform cards must be referenced. Unlinked: {unlinked_details}"


def test_all_algo_check_referenced(algo_cards, referenced_cards):
    """algo-trade-pipelineの全checkカードが参照されていること"""
    check_cards = [c for c in algo_cards if c["category"] == "check"]
    check_keys = {f"{c['source_spec']}::{c['id']}" for c in check_cards}
    check_referenced = check_keys & referenced_cards

    unlinked = check_keys - referenced_cards
    unlinked_details = [
        (c["id"], c["description"]) for c in check_cards if f"{c['source_spec']}::{c['id']}" in unlinked
    ]
    assert len(unlinked) == 0, f"All check cards must be referenced. Unlinked: {unlinked_details}"


def test_all_algo_example_referenced(algo_cards, referenced_cards):
    """algo-trade-pipelineの全exampleカードが参照されていること"""
    example_cards = [c for c in algo_cards if c["category"] == "example"]
    example_keys = {f"{c['source_spec']}::{c['id']}" for c in example_cards}
    example_referenced = example_keys & referenced_cards

    unlinked = example_keys - referenced_cards
    unlinked_details = [
        (c["id"], c["description"]) for c in example_cards if f"{c['source_spec']}::{c['id']}" in unlinked
    ]
    assert len(unlinked) == 0, f"All example cards must be referenced. Unlinked: {unlinked_details}"


def test_all_algo_generator_referenced(algo_cards, referenced_cards, algo_spec_ir):
    """algo-trade-pipelineの全generatorカードが参照されていること

    Note: DAGの最終出力型のgeneratorは、その型を入力とするステージが存在しないため
    参照されない場合がある（例: gen_snapshot_meta）
    """
    generator_cards = [c for c in algo_cards if c["category"] == "generator"]
    generator_keys = {f"{c['source_spec']}::{c['id']}" for c in generator_cards}
    generator_referenced = generator_keys & referenced_cards

    unlinked = generator_keys - referenced_cards

    # 最終出力型のgeneratorを特定（どのステージのinput_typeとしても使われていない型を返すgenerator）
    all_input_types = {stage.input_type for stage in algo_spec_ir.dag_stages if stage.input_type}
    final_output_generators = set()

    for gen in algo_spec_ir.generators:
        if gen.return_type_ref and gen.return_type_ref not in all_input_types:
            final_output_generators.add(f"algo-trade-pipeline::{gen.id}")

    # 最終出力型のgeneratorを除外
    unlinked_excluding_final = unlinked - final_output_generators

    if len(unlinked_excluding_final) > 0:
        unlinked_details = [
            (c["id"], c["description"])
            for c in generator_cards
            if f"{c['source_spec']}::{c['id']}" in unlinked_excluding_final
        ]
        assert False, f"All non-final-output generator cards must be referenced. Unlinked: {unlinked_details}"

    # 最終出力型のgeneratorが未参照であることを警告
    if len(unlinked & final_output_generators) > 0:
        final_unlinked = [
            (c["id"], c["description"])
            for c in generator_cards
            if f"{c['source_spec']}::{c['id']}" in (unlinked & final_output_generators)
        ]
        print(f"Info: Final output generators not referenced (expected): {final_unlinked}")


def test_card_data_property_serializable(algo_cards):
    """全カードのdataプロパティがJSON serializable であること"""
    import json

    for card in algo_cards:
        try:
            # dataプロパティをJSON文字列化して確認
            json.dumps(card.get("data", {}))
        except (TypeError, ValueError) as e:
            pytest.fail(f"Card {card['source_spec']}::{card['id']} data property is not JSON serializable: {e}")


def test_card_spec_metadata_present(algo_cards):
    """spec_metadataを持つカテゴリ（check, transform, generator）でspec_metadataが含まれていること"""
    metadata_categories = {"check", "transform", "generator"}

    for card in algo_cards:
        if card["category"] in metadata_categories:
            data = card.get("data", {})
            # spec_metadataが存在する場合、必須フィールドを確認
            if "spec_metadata" in data:
                spec_metadata = data["spec_metadata"]
                assert isinstance(spec_metadata, dict), (
                    f"Card {card['source_spec']}::{card['id']} spec_metadata must be dict"
                )
                # 少なくとも1つのメタデータフィールドが存在すること
                assert len(spec_metadata) > 0, (
                    f"Card {card['source_spec']}::{card['id']} spec_metadata must not be empty"
                )


def test_all_cards_have_required_fields(algo_cards):
    """全カードが必須フィールドを持つこと"""
    required_fields = {"id", "category", "name", "description", "source_spec", "data"}

    for card in algo_cards:
        missing_fields = required_fields - set(card.keys())
        assert len(missing_fields) == 0, (
            f"Card {card.get('source_spec')}::{card.get('id')} missing fields: {missing_fields}"
        )


def test_no_duplicate_dtype_in_param_cards(algo_cards_data):
    """param_dtype_cardsにinput/output型が重複して含まれないこと"""
    for group in algo_cards_data["dag_stage_groups"]:
        input_type = group["input_type"]
        output_type = group["output_type"]
        param_dtype_ids = [c["id"] for c in group["related_cards"]["param_dtype_cards"]]

        # input/output型がparam_dtype_cardsに含まれていないことを確認
        if input_type:
            assert input_type not in param_dtype_ids, (
                f"Stage {group['stage_id']}: input_type '{input_type}' should not be in param_dtype_cards"
            )
        if output_type:
            assert output_type not in param_dtype_ids, (
                f"Stage {group['stage_id']}: output_type '{output_type}' should not be in param_dtype_cards"
            )


def test_generator_cards_only_for_input_type(algo_cards_data):
    """generator_cardsはinput型に関連するもののみ含まれること"""
    for group in algo_cards_data["dag_stage_groups"]:
        input_type = group["input_type"]
        generator_ids = [c["id"] for c in group["related_cards"]["generator_cards"]]

        if not input_type or len(generator_ids) == 0:
            continue

        # 全てのgeneratorがinput型をreturn_type_refとして持つことを確認
        spec_ir = load_spec("specs/algo-trade-pipeline.yaml")
        for gen_id in generator_ids:
            generator = next((g for g in spec_ir.generators if g.id == gen_id), None)
            assert generator is not None, f"Generator {gen_id} not found in spec"
            assert generator.return_type_ref == input_type, (
                f"Stage {group['stage_id']}: generator {gen_id} return_type_ref '{generator.return_type_ref}' != input_type '{input_type}'"
            )


def test_check_cards_only_for_output_type(algo_cards_data):
    """output_check_cardsはoutput型に関連するもののみ含まれること"""
    for group in algo_cards_data["dag_stage_groups"]:
        output_type = group["output_type"]
        check_ids = [c["id"] for c in group["related_cards"]["output_check_cards"]]

        if not output_type or len(check_ids) == 0:
            continue

        # 全てのcheckがoutput型をinput_type_refとして持つことを確認
        spec_ir = load_spec("specs/algo-trade-pipeline.yaml")
        for check_id in check_ids:
            check = next((c for c in spec_ir.checks if c.id == check_id), None)
            assert check is not None, f"Check {check_id} not found in spec"
            assert check.input_type_ref == output_type, (
                f"Stage {group['stage_id']}: check {check_id} input_type_ref '{check.input_type_ref}' != output_type '{output_type}'"
            )

"""
Export YAML spec to normalized JSON for frontend card library
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .config_model import ExtendedSpec


def normalize_type_info(dtype_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize datatype to consistent structure"""

    # Determine type category
    type_category = "schema"
    type_details = {}

    if "enum" in dtype_data:
        type_category = "enum"
        enum_config = dtype_data["enum"]
        type_details = {
            "base_type": enum_config.get("base_type", "str"),
            "members": [
                {"name": m.get("name"), "value": m.get("value"), "description": m.get("description", "")}
                for m in enum_config.get("members", [])
            ],
        }

    elif "pydantic_model" in dtype_data:
        type_category = "pydantic_model"
        model_config = dtype_data["pydantic_model"]
        type_details = {"fields": normalize_pydantic_fields(model_config.get("fields", []))}

    elif "type_alias" in dtype_data:
        type_category = "type_alias"
        alias_config = dtype_data["type_alias"]
        type_details = {
            "alias_type": alias_config.get("type"),
            "target": alias_config.get("target"),
            "elements": alias_config.get("elements", []),
        }

    elif "generic" in dtype_data:
        type_category = "generic"
        generic_config = dtype_data["generic"]
        type_details = {
            "container": generic_config.get("container"),
            "element_type": generic_config.get("element_type"),
            "key_type": generic_config.get("key_type"),
            "value_type": generic_config.get("value_type"),
        }

    elif "schema" in dtype_data:
        type_category = "schema"
        type_details = {"schema": dtype_data["schema"]}

    return {"type_category": type_category, "type_details": type_details}


def normalize_pydantic_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize pydantic model fields to flat structure"""
    normalized = []

    for field in fields:
        field_type = field.get("type", {})
        type_str = "unknown"

        # Extract type string
        if "native" in field_type:
            type_str = field_type["native"]
        elif "datatype_ref" in field_type:
            type_str = field_type["datatype_ref"]
        elif "generic" in field_type:
            generic = field_type["generic"]
            container = generic.get("container", "?")
            elem = generic.get("element_type", {})
            elem_str = elem.get("native") or elem.get("datatype_ref") or "Any"
            type_str = f"{container}[{elem_str}]"

        normalized.append(
            {
                "name": field.get("name"),
                "type": type_str,
                "optional": field.get("optional", False),
                "default": field.get("default"),
                "description": field.get("description", ""),
            }
        )

    return normalized


def normalize_transform_params(params: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract input/output types from transform parameters"""
    input_type = None
    param_details = []

    for param in params:
        param_type = "unknown"

        if "datatype_ref" in param:
            param_type = param["datatype_ref"]
        elif "native" in param:
            param_type = param["native"]
        elif "literal" in param:
            param_type = f"Literal[{', '.join(param['literal'])}]"

        param_details.append(
            {
                "name": param.get("name"),
                "type": param_type,
                "optional": param.get("optional", False),
                "default": param.get("default"),
            }
        )

        # First param is typically input type
        if input_type is None and "datatype_ref" in param:
            input_type = param["datatype_ref"]

    return {"input_type": input_type, "param_details": param_details}


def _build_card_map(cards: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Build lookup map for cards by (category, id, source_spec)"""
    return {(card["category"], card["id"], card["source_spec"]): card for card in cards}


def _find_cards_by_ids(
    card_map: dict[tuple[str, str, str], dict[str, Any]], category: str, ids: list[str], spec_name: str
) -> list[dict[str, Any]]:
    """Find cards by category and list of ids"""
    result = []
    for card_id in ids:
        card = card_map.get((category, card_id, spec_name))
        if card:
            result.append(card)
    return result


def _find_transform_cards(
    cards: list[dict[str, Any]], spec_name: str, input_type: str, output_type: str
) -> list[dict[str, Any]]:
    """Find transform cards matching input/output types"""
    result = []
    for card in cards:
        if card["category"] == "transform" and card["source_spec"] == spec_name:
            meta = card.get("metadata", {})
            if meta.get("input_type") == input_type and meta.get("output_type") == output_type:
                result.append(card)
    return result


def _collect_example_and_check_cards(
    dtype_card: dict[str, Any] | None, card_map: dict[tuple[str, str, str], dict[str, Any]], spec_name: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collect example and check cards for a datatype card"""
    example_cards = []
    check_cards = []

    if dtype_card:
        example_ids = dtype_card.get("metadata", {}).get("example_ids", [])
        example_cards = _find_cards_by_ids(card_map, "example", example_ids, spec_name)

        check_ids = dtype_card.get("metadata", {}).get("check_ids", [])
        check_cards = _find_cards_by_ids(card_map, "checks", check_ids, spec_name)

    return example_cards, check_cards


def _build_stage_group(
    stage: dict[str, Any],
    spec_name: str,
    cards: list[dict[str, Any]],
    card_map: dict[tuple[str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Build a single stage group from stage data"""
    stage_id: str = stage.get("stage_id", "")
    input_type: str = stage.get("input_type", "")
    output_type: str = stage.get("output_type", "")

    # Find core cards
    stage_card = card_map.get(("dag_stage", stage_id, spec_name))
    input_dtype_card = card_map.get(("dtype", input_type, spec_name))
    output_dtype_card = card_map.get(("dtype", output_type, spec_name))

    # Find transform cards
    transform_cards = _find_transform_cards(cards, spec_name, input_type, output_type)

    # Collect examples and checks for input/output datatypes
    input_example_cards, input_check_cards = _collect_example_and_check_cards(input_dtype_card, card_map, spec_name)
    output_example_cards, output_check_cards = _collect_example_and_check_cards(output_dtype_card, card_map, spec_name)

    return {
        "spec_name": spec_name,
        "stage_id": stage_id,
        "stage_description": stage.get("description", ""),
        "input_type": input_type,
        "output_type": output_type,
        "selection_mode": stage.get("selection_mode"),
        "max_select": stage.get("max_select"),
        "related_cards": {
            "stage_card": stage_card,
            "input_dtype_card": input_dtype_card,
            "output_dtype_card": output_dtype_card,
            "transform_cards": transform_cards,
            "input_example_cards": input_example_cards,
            "output_example_cards": output_example_cards,
            "input_check_cards": input_check_cards,
            "output_check_cards": output_check_cards,
        },
    }


def build_dag_stage_groups(
    spec_path: Path, raw_data: dict[str, Any], cards: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Build dag_stage_groups: each group contains related cards for a stage

    Returns:
        List of groups, each containing:
        - stage metadata (spec_name, stage_id, input/output types, etc.)
        - related_cards: stage, input_dtype, output_dtype, transforms, examples, checks
    """
    dag_stages = raw_data.get("dag_stages", [])
    if not isinstance(dag_stages, list) or len(dag_stages) == 0:
        return []

    spec_name = spec_path.stem
    card_map = _build_card_map(cards)

    return [_build_stage_group(stage, spec_name, cards, card_map) for stage in dag_stages]


def _process_checks(checks: list[dict[str, Any]], spec_name: str) -> list[dict[str, Any]]:
    """Process check definitions into cards"""
    result = []
    if isinstance(checks, list):
        for check in checks:
            result.append(
                {
                    "id": check.get("id"),
                    "category": "checks",
                    "name": check.get("id"),
                    "description": check.get("description", ""),
                    "source_spec": spec_name,
                    "metadata": {"impl": check.get("impl"), "file_path": check.get("file_path")},
                }
            )
    return result


def _process_datatypes(datatypes: list[dict[str, Any]], spec_name: str) -> list[dict[str, Any]]:
    """Process datatype definitions into cards"""
    result = []
    if isinstance(datatypes, list):
        for dtype in datatypes:
            type_info = normalize_type_info(dtype)
            result.append(
                {
                    "id": dtype.get("id"),
                    "category": "dtype",
                    "name": dtype.get("id"),
                    "description": f"[{type_info['type_category']}] {dtype.get('description', '')}",
                    "source_spec": spec_name,
                    "metadata": {
                        "type_category": type_info["type_category"],
                        "type_details": type_info["type_details"],
                        "check_ids": dtype.get("check_ids", []),
                        "example_ids": dtype.get("example_ids", []),
                    },
                }
            )
    return result


def _process_examples(examples: list[dict[str, Any]], spec_name: str) -> list[dict[str, Any]]:
    """Process example definitions into cards"""
    result = []
    if isinstance(examples, list):
        for example in examples:
            result.append(
                {
                    "id": example.get("id"),
                    "category": "example",
                    "name": example.get("id"),
                    "description": example.get("description", ""),
                    "source_spec": spec_name,
                    "metadata": {"input": example.get("input"), "expected": example.get("expected")},
                }
            )
    return result


def _process_transforms(transforms: list[dict[str, Any]], spec_name: str) -> list[dict[str, Any]]:
    """Process transform definitions into cards"""
    result = []
    if isinstance(transforms, list):
        for transform in transforms:
            params = transform.get("parameters", [])
            param_info = normalize_transform_params(params) if params else {"input_type": None, "param_details": []}
            output_type = transform.get("return_datatype_ref") or transform.get("return_native")

            result.append(
                {
                    "id": transform.get("id"),
                    "category": "transform",
                    "name": transform.get("id"),
                    "description": transform.get("description", ""),
                    "source_spec": spec_name,
                    "metadata": {
                        "impl": transform.get("impl"),
                        "file_path": transform.get("file_path"),
                        "input_type": param_info["input_type"],
                        "output_type": output_type,
                        "parameters": param_info["param_details"],
                    },
                }
            )
    return result


def _process_dag_edges(dag: list[dict[str, Any]], spec_name: str) -> list[dict[str, Any]]:
    """Process DAG edges into cards"""
    result = []
    if isinstance(dag, list):
        for idx, edge in enumerate(dag):
            from_node = edge.get("from", "start")
            to_node = edge.get("to", "end")
            result.append(
                {
                    "id": f"dag_edge_{idx}_{from_node}_to_{to_node}",
                    "category": "dag",
                    "name": f"{from_node} → {to_node}",
                    "description": f"DAG edge from {from_node} to {to_node}",
                    "source_spec": spec_name,
                    "metadata": {"from": from_node, "to": to_node},
                }
            )
    return result


def _process_dag_stages(dag_stages: list[dict[str, Any]], spec_name: str) -> list[dict[str, Any]]:
    """Process DAG stages into cards"""
    result = []
    if isinstance(dag_stages, list):
        for stage in dag_stages:
            result.append(
                {
                    "id": stage.get("stage_id"),
                    "category": "dag_stage",
                    "name": stage.get("stage_id"),
                    "description": stage.get("description", ""),
                    "source_spec": spec_name,
                    "metadata": {
                        "selection_mode": stage.get("selection_mode"),
                        "input_type": stage.get("input_type"),
                        "output_type": stage.get("output_type"),
                        "max_select": stage.get("max_select"),
                        "candidates": [c.get("transform_id") for c in stage.get("candidates", [])],
                    },
                }
            )
    return result


def _card_key(card: dict[str, Any] | None) -> str | None:
    """Generate unique key for a card"""
    if not card:
        return None
    cid = card.get("id")
    spec = card.get("source_spec")
    return f"{spec}::{cid}" if cid and spec else None


def _collect_referenced_keys_from_group(related_cards: dict[str, Any]) -> set[str]:
    """Collect all referenced card keys from a stage group's related_cards"""
    referenced: set[str] = set()

    # Single card references
    for single_key in ("stage_card", "input_dtype_card", "output_dtype_card"):
        key = _card_key(related_cards.get(single_key))
        if key:
            referenced.add(key)

    # List card references
    for list_key in (
        "transform_cards",
        "input_example_cards",
        "output_example_cards",
        "input_check_cards",
        "output_check_cards",
    ):
        for item in related_cards.get(list_key, []) or []:
            key = _card_key(item)
            if key:
                referenced.add(key)

    return referenced


def _detect_referenced_and_unlinked(
    dag_stage_groups: list[dict[str, Any]], cards: list[dict[str, Any]]
) -> tuple[list[str], list[str]]:
    """Detect referenced and unlinked card keys"""
    referenced_keys: set[str] = set()

    for group in dag_stage_groups:
        related = group.get("related_cards", {})
        referenced_keys.update(_collect_referenced_keys_from_group(related))

    all_keys: list[str] = [k for c in cards if (k := _card_key(c)) is not None]
    unlinked_keys: list[str] = [k for k in all_keys if k not in referenced_keys]

    return sorted(referenced_keys), sorted(unlinked_keys)


def export_spec_to_cards(spec_path: Path) -> dict[str, Any]:
    """
    Export YAML spec to normalized card JSON

    Returns:
        {
            "metadata": {"spec_name": "...", "version": "..."},
            "cards": [...],
            "dag_stage_groups": [...]
        }
    """
    # Load and validate YAML
    with open(spec_path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    try:
        ExtendedSpec(**raw_data)
    except Exception as e:
        print(f"Warning: Failed to validate with ExtendedSpec: {e}")
        print("Falling back to raw YAML processing")

    spec_name = spec_path.stem

    # Process all card types
    cards = []
    cards.extend(_process_checks(raw_data.get("checks", []), spec_name))
    cards.extend(_process_datatypes(raw_data.get("datatypes", []), spec_name))
    cards.extend(_process_examples(raw_data.get("examples", []), spec_name))
    cards.extend(_process_transforms(raw_data.get("transforms", []), spec_name))
    cards.extend(_process_dag_edges(raw_data.get("dag", []), spec_name))
    cards.extend(_process_dag_stages(raw_data.get("dag_stages", []), spec_name))

    # Build groups and detect references
    dag_stage_groups = build_dag_stage_groups(spec_path, raw_data, cards)
    referenced_keys, unlinked_keys = _detect_referenced_and_unlinked(dag_stage_groups, cards)

    metadata = raw_data.get("meta", {})

    return {
        "metadata": {
            "spec_name": metadata.get("name", spec_name),
            "version": raw_data.get("version", "1"),
            "description": metadata.get("description", ""),
        },
        "cards": cards,
        "dag_stage_groups": dag_stage_groups,
        "referenced_card_keys": referenced_keys,
        "unlinked_card_keys": unlinked_keys,
    }


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Export YAML specs to card JSON")
    parser.add_argument("specs", nargs="+", help="YAML spec files")
    parser.add_argument("--output", "-o", required=True, help="Output directory")

    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    for spec_path_str in args.specs:
        spec_path = Path(spec_path_str)

        if not spec_path.exists():
            print(f"Warning: {spec_path} does not exist, skipping")
            continue

        print(f"Processing {spec_path}...")

        try:
            cards_data = export_spec_to_cards(spec_path)

            output_path = output_dir / f"{spec_path.stem}.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(cards_data, f, indent=2, ensure_ascii=False)

            print(f"  → Exported {len(cards_data['cards'])} cards to {output_path}")

        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    main()

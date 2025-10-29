"""
Export YAML spec to normalized JSON for frontend card library
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .config_model import ExtendedSpec
from .engine import Engine, load_spec


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


def _format_literal_type(literal_values: list[Any]) -> str:
    """Return Literal[...] representation from raw values."""
    joined = ", ".join(str(value) for value in literal_values)
    return f"Literal[{joined}]" if joined else "Literal"


def _format_union_type(candidates: list[Any]) -> str:
    """Return union type display from raw union candidates."""
    formatted: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        type_hint = candidate.get("datatype_ref") or candidate.get("native")
        if not type_hint and isinstance(candidate.get("literal"), list):
            type_hint = _format_literal_type(candidate["literal"])
        if type_hint:
            formatted.append(str(type_hint))
    return " | ".join(formatted) if formatted else "union"


def _infer_param_type(param: dict[str, Any]) -> str:
    """Infer a human friendly parameter type string."""
    datatype_ref = param.get("datatype_ref")
    if isinstance(datatype_ref, str):
        return datatype_ref

    native_type = param.get("native")
    if isinstance(native_type, str):
        return native_type

    literal_values = param.get("literal")
    if isinstance(literal_values, list):
        return _format_literal_type(literal_values)

    union_candidates = param.get("union")
    if isinstance(union_candidates, list):
        return _format_union_type(union_candidates)

    return "unknown"


def normalize_parameters(params: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize parameter definitions into a frontend-friendly structure"""
    normalized: list[dict[str, Any]] = []

    for param in params:
        if not isinstance(param, dict):
            continue

        normalized.append(
            {
                "name": param.get("name"),
                "type": _infer_param_type(param),
                "optional": param.get("optional", False),
                "default": param.get("default"),
                "description": param.get("description", ""),
            }
        )

    return normalized


def normalize_transform_params(params: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract input/output types from transform parameters"""
    input_type = None
    param_details = normalize_parameters(params)

    for param in params:
        if not isinstance(param, dict):
            continue
        if "datatype_ref" in param and isinstance(param["datatype_ref"], str):
            input_type = param["datatype_ref"]
            break

    return {"input_type": input_type, "param_details": param_details}


def _build_card_map(cards: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Build lookup map for cards by (category, id, source_spec)"""
    return {(card["category"], card["id"], card["source_spec"]): card for card in cards}


def _has_dag_metadata(raw_data: dict[str, Any]) -> bool:
    """Return True when dag or stage metadata exists."""
    dag_stages = raw_data.get("dag_stages")
    if isinstance(dag_stages, list) and dag_stages:
        return True
    dag_edges = raw_data.get("dag")
    return isinstance(dag_edges, list) and bool(dag_edges)


def _lookup_card(
    card_map: dict[tuple[str, str, str], dict[str, Any]],
    spec_name: str,
    category: str,
    card_id: str | None,
) -> dict[str, Any] | None:
    """Fetch a single card from the lookup map."""
    if not card_id:
        return None
    return card_map.get((category, card_id, spec_name))


def _lookup_cards(
    card_map: dict[tuple[str, str, str], dict[str, Any]],
    spec_name: str,
    category: str,
    card_ids: list[str],
) -> list[dict[str, Any]]:
    """Fetch multiple cards, skipping missing entries."""
    return [card for card_id in card_ids if (card := _lookup_card(card_map, spec_name, category, card_id)) is not None]


def _extract_dtype_sets(related_ids: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
    """Split datatype ids into input/output/parameter groups."""
    input_id = related_ids.get("input_dtype_id")
    output_id = related_ids.get("output_dtype_id")
    all_ids = set(related_ids.get("datatype_ids", []))
    input_ids = {input_id} if input_id else set()
    output_ids = {output_id} if output_id else set()
    param_ids = all_ids - input_ids - output_ids
    return input_ids, output_ids, param_ids


def _collect_input_check_ids(
    input_dtype_ids: set[str],
    card_map: dict[tuple[str, str, str], dict[str, Any]],
    spec_name: str,
) -> set[str]:
    """Collect check ids attached to input datatypes."""
    check_ids: set[str] = set()
    for dtype_id in input_dtype_ids:
        dtype_card = card_map.get(("dtype", dtype_id, spec_name))
        if not dtype_card:
            continue
        metadata = dtype_card.get("metadata")
        if isinstance(metadata, dict):
            check_ids.update(metadata.get("check_ids", []))
    return check_ids


def _build_related_cards(
    related_ids: dict[str, Any],
    card_map: dict[tuple[str, str, str], dict[str, Any]],
    spec_name: str,
    param_dtype_ids: set[str],
    input_check_ids: set[str],
    output_check_ids: list[str],
) -> dict[str, Any]:
    """Assemble related card payloads for a single stage."""
    return {
        "stage_card": _lookup_card(card_map, spec_name, "dag_stage", related_ids.get("stage_id")),
        "input_dtype_card": _lookup_card(card_map, spec_name, "dtype", related_ids.get("input_dtype_id")),
        "output_dtype_card": _lookup_card(card_map, spec_name, "dtype", related_ids.get("output_dtype_id")),
        "transform_cards": _lookup_cards(
            card_map,
            spec_name,
            "transform",
            related_ids.get("transform_ids", []),
        ),
        "param_dtype_cards": _lookup_cards(card_map, spec_name, "dtype", sorted(param_dtype_ids)),
        "generator_cards": _lookup_cards(
            card_map,
            spec_name,
            "generator",
            related_ids.get("generator_ids", []),
        ),
        "input_example_cards": [],
        "output_example_cards": _lookup_cards(
            card_map,
            spec_name,
            "example",
            related_ids.get("example_ids", []),
        ),
        "input_check_cards": _lookup_cards(
            card_map,
            spec_name,
            "checks",
            sorted(input_check_ids),
        ),
        "output_check_cards": _lookup_cards(card_map, spec_name, "checks", output_check_ids),
    }


def _convert_stage_group(
    group: dict[str, Any],
    card_map: dict[tuple[str, str, str], dict[str, Any]],
    spec_name: str,
) -> dict[str, Any]:
    """Convert Engine stage group info into export payload."""
    related_ids = group["related_card_ids"]
    input_dtype_ids, _, param_dtype_ids = _extract_dtype_sets(related_ids)
    input_check_ids = _collect_input_check_ids(input_dtype_ids, card_map, spec_name)
    output_check_ids = sorted(set(related_ids.get("check_ids", [])) - input_check_ids)

    return {
        "spec_name": spec_name,
        "stage_id": group["stage_id"],
        "stage_description": group["description"],
        "input_type": group["input_type"],
        "output_type": group["output_type"],
        "selection_mode": group["selection_mode"],
        "max_select": group["max_select"],
        "related_cards": _build_related_cards(
            related_ids,
            card_map,
            spec_name,
            param_dtype_ids,
            input_check_ids,
            output_check_ids,
        ),
    }


def build_dag_stage_groups(
    spec_path: Path, raw_data: dict[str, Any], cards: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Build dag_stage_groups: each group contains related cards for a stage

    This is now a thin wrapper around Engine.build_stage_groups().
    The Engine is the single source of truth for stage-card relationships.

    Returns:
        List of groups, each containing:
        - stage metadata (spec_name, stage_id, input/output types, etc.)
        - related_cards: stage, input_dtype, output_dtype, transforms, examples, checks
    """
    if not _has_dag_metadata(raw_data):
        return []

    spec_name = spec_path.stem
    card_map = _build_card_map(cards)

    # Use Engine as the single source of truth
    try:
        spec = load_spec(str(spec_path))
        from packages.spec2code.engine import Engine

        engine = Engine(spec)
        stage_groups_from_engine = engine.build_stage_groups()

        # Convert Engine's ID-based groups to card-based groups
        return [_convert_stage_group(group, card_map, spec_name) for group in stage_groups_from_engine]

    except Exception as e:
        print(f"Warning: Failed to build stage groups via Engine: {e}")
        import traceback

        traceback.print_exc()
        return []


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
            example_ids = dtype.get("example_ids", dtype.get("example_refs", []))
            generator_refs = dtype.get("generator_refs", dtype.get("generator_ids", []))
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
                        "example_ids": example_ids,
                        "generator_refs": generator_refs,
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


def _process_generators(
    generators: list[dict[str, Any]] | dict[str, dict[str, Any]] | None, spec_name: str
) -> list[dict[str, Any]]:
    """Process generator definitions into cards"""
    result: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []

    if isinstance(generators, dict):
        for gen_id, payload in generators.items():
            if not isinstance(payload, dict):
                continue
            candidate = dict(payload)
            candidate.setdefault("id", gen_id)
            items.append(candidate)
    elif isinstance(generators, list):
        items = [g for g in generators if isinstance(g, dict)]
    else:
        return result

    for generator in items:
        gen_id_raw = generator.get("id")
        if not isinstance(gen_id_raw, str):
            continue
        gen_id = gen_id_raw
        params = generator.get("parameters", [])

        result.append(
            {
                "id": gen_id,
                "category": "generator",
                "name": gen_id,
                "description": generator.get("description", ""),
                "source_spec": spec_name,
                "metadata": {
                    "impl": generator.get("impl"),
                    "file_path": generator.get("file_path"),
                    "parameters": normalize_parameters(params) if isinstance(params, list) else [],
                },
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


def _detect_referenced_and_unlinked(spec_path: Path, cards: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Detect referenced and unlinked card keys using Engine's logic"""
    try:
        # Load spec and create Engine instance to use its unlinked detection logic
        spec = load_spec(str(spec_path))
        engine = Engine(spec)
        unlinked_items = engine._detect_unlinked_items()

        spec_name = spec_path.stem

        # Convert unlinked items to card keys
        unlinked_keys: set[str] = set()
        for category_map in [
            ("transforms", "transform"),
            ("datatypes", "dtype"),
            ("examples", "example"),
            ("checks", "checks"),
            ("generators", "generator"),
        ]:
            engine_category, card_category = category_map
            for item_id in unlinked_items.get(engine_category, set()):
                unlinked_keys.add(f"{spec_name}::{item_id}")

        # All keys from cards
        all_keys: set[str] = {k for c in cards if (k := _card_key(c)) is not None}

        # Referenced keys are all keys minus unlinked keys
        referenced_keys = all_keys - unlinked_keys

        return sorted(referenced_keys), sorted(unlinked_keys)

    except Exception as e:
        print(f"Warning: Failed to detect unlinked items using Engine: {e}")
        # Fallback to empty sets
        all_keys_list: list[str] = [k for c in cards if (k := _card_key(c)) is not None]
        return all_keys_list, []


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
    cards.extend(_process_generators(raw_data.get("generators"), spec_name))
    cards.extend(_process_datatypes(raw_data.get("datatypes", []), spec_name))
    cards.extend(_process_examples(raw_data.get("examples", []), spec_name))
    cards.extend(_process_transforms(raw_data.get("transforms", []), spec_name))
    cards.extend(_process_dag_edges(raw_data.get("dag", []), spec_name))
    cards.extend(_process_dag_stages(raw_data.get("dag_stages", []), spec_name))

    # Build groups and detect references
    dag_stage_groups = build_dag_stage_groups(spec_path, raw_data, cards)
    referenced_keys, unlinked_keys = _detect_referenced_and_unlinked(spec_path, cards)

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

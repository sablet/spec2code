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
    output_type = None
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


def export_spec_to_cards(spec_path: Path) -> dict[str, Any]:
    """
    Export YAML spec to normalized card JSON

    Returns:
        {
            "metadata": {"spec_name": "...", "version": "..."},
            "cards": [...]
        }
    """

    # Load YAML
    with open(spec_path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    # Validate with pydantic
    try:
        spec = ExtendedSpec(**raw_data)
    except Exception as e:
        print(f"Warning: Failed to validate with ExtendedSpec: {e}")
        print("Falling back to raw YAML processing")
        spec = None

    cards = []

    # Process checks
    checks = raw_data.get("checks", [])
    if isinstance(checks, list):
        for check in checks:
            cards.append(
                {
                    "id": check.get("id"),
                    "category": "checks",
                    "name": check.get("id"),
                    "description": check.get("description", ""),
                    "source_spec": spec_path.stem,
                    "metadata": {"impl": check.get("impl"), "file_path": check.get("file_path")},
                }
            )

    # Process datatypes
    datatypes = raw_data.get("datatypes", [])
    if isinstance(datatypes, list):
        for dtype in datatypes:
            type_info = normalize_type_info(dtype)

            cards.append(
                {
                    "id": dtype.get("id"),
                    "category": "dtype",
                    "name": dtype.get("id"),
                    "description": f"[{type_info['type_category']}] {dtype.get('description', '')}",
                    "source_spec": spec_path.stem,
                    "metadata": {
                        "type_category": type_info["type_category"],
                        "type_details": type_info["type_details"],
                        "check_ids": dtype.get("check_ids", []),
                        "example_ids": dtype.get("example_ids", []),
                    },
                }
            )

    # Process examples
    examples = raw_data.get("examples", [])
    if isinstance(examples, list):
        for example in examples:
            cards.append(
                {
                    "id": example.get("id"),
                    "category": "example",
                    "name": example.get("id"),
                    "description": example.get("description", ""),
                    "source_spec": spec_path.stem,
                    "metadata": {"input": example.get("input"), "expected": example.get("expected")},
                }
            )

    # Process transforms
    transforms = raw_data.get("transforms", [])
    if isinstance(transforms, list):
        for transform in transforms:
            params = transform.get("parameters", [])
            param_info = normalize_transform_params(params) if params else {"input_type": None, "param_details": []}

            output_type = transform.get("return_datatype_ref") or transform.get("return_native")

            cards.append(
                {
                    "id": transform.get("id"),
                    "category": "transform",
                    "name": transform.get("id"),
                    "description": transform.get("description", ""),
                    "source_spec": spec_path.stem,
                    "metadata": {
                        "impl": transform.get("impl"),
                        "file_path": transform.get("file_path"),
                        "input_type": param_info["input_type"],
                        "output_type": output_type,
                        "parameters": param_info["param_details"],
                    },
                }
            )

    # Process DAG edges
    dag = raw_data.get("dag", [])
    if isinstance(dag, list):
        for idx, edge in enumerate(dag):
            from_node = edge.get("from", "start")
            to_node = edge.get("to", "end")

            cards.append(
                {
                    "id": f"dag_edge_{idx}_{from_node}_to_{to_node}",
                    "category": "dag",
                    "name": f"{from_node} → {to_node}",
                    "description": f"DAG edge from {from_node} to {to_node}",
                    "source_spec": spec_path.stem,
                    "metadata": {"from": from_node, "to": to_node},
                }
            )

    # Process DAG stages
    dag_stages = raw_data.get("dag_stages", [])
    if isinstance(dag_stages, list):
        for stage in dag_stages:
            cards.append(
                {
                    "id": stage.get("stage_id"),
                    "category": "dag_stage",
                    "name": stage.get("stage_id"),
                    "description": stage.get("description", ""),
                    "source_spec": spec_path.stem,
                    "metadata": {
                        "selection_mode": stage.get("selection_mode"),
                        "input_type": stage.get("input_type"),
                        "output_type": stage.get("output_type"),
                        "max_select": stage.get("max_select"),
                        "candidates": [c.get("transform_id") for c in stage.get("candidates", [])],
                    },
                }
            )

    metadata = raw_data.get("meta", {})

    return {
        "metadata": {
            "spec_name": metadata.get("name", spec_path.stem),
            "version": raw_data.get("version", "1"),
            "description": metadata.get("description", ""),
        },
        "cards": cards,
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

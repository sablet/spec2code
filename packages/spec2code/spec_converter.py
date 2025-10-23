"""
Convert extended spec (with DAG stages) to simple spec format for skeleton generation
"""

from __future__ import annotations

from typing import Any

from spec2code.config_model import ExtendedSpec


def extended_to_simple_spec(extended_spec: ExtendedSpec) -> dict[str, Any]:
    """
    Convert ExtendedSpec to simple spec format compatible with existing engine

    For skeleton generation, we include ALL transforms from all stages.
    The DAG edges are generated from stage dependencies.
    """
    simple_spec = {
        "version": extended_spec.version,
        "meta": extended_spec.meta,
        "checks": extended_spec.checks,
        "examples": extended_spec.examples,
        "datatypes": extended_spec.datatypes,
        "transforms": extended_spec.transforms,
        "dag": [],
    }

    # Generate DAG edges from stage structure
    # For now, create a simple linear chain based on stage order
    prev_stage = None
    for stage in extended_spec.dag:
        for candidate in stage.candidates:
            if prev_stage:
                # Connect previous stage outputs to this stage
                for prev_candidate in prev_stage.candidates:
                    simple_spec["dag"].append(
                        {
                            "from": prev_candidate.transform_id,
                            "to": candidate.transform_id,
                        }
                    )
            else:
                # First stage - no predecessors
                simple_spec["dag"].append({"from": candidate.transform_id, "to": None})

        prev_stage = stage

    # If last stage has single output, connect to null
    if extended_spec.dag and extended_spec.dag[-1].selection_mode == "single":
        last_stage = extended_spec.dag[-1]
        if last_stage.candidates:
            # Already handled in loop above
            pass

    return simple_spec

"""Bounded software-lineage reproduction for continuity handoffs.

This module demonstrates one atomic lineage:

    verified state H10
    -> handoff bound to H10
    -> newer verified state H11
    -> old handoff remains intact but becomes STALE
    -> fail-closed gate blocks continuation from the old handoff

The fixture is deterministic and uses only explicit caller-supplied state. It does not
infer truth, discover the latest head, grant authority, or claim universal coverage.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.canonical import stable_hash
from holosim.continuity_compliance import build_continuity_compliance_contract
from holosim.continuity_current_gate import evaluate_continuity_current_gate
from holosim.continuity_head_binding import (
    build_continuity_head_binding,
    evaluate_continuity_head_binding,
)

LINEAGE_TYPE = "software_lineage_reproduction"
LINEAGE_VERSION = 1


def _verified_head(*, idx: int, state: Mapping[str, Any]) -> dict[str, Any]:
    """Create a deterministic externally supplied verified-head fixture."""
    body = {
        "idx": idx,
        "state": deepcopy(dict(state)),
        "verified": True,
    }
    return {**body, "head_hash": stable_hash(body)}


def reproduce_stale_handoff_lineage() -> dict[str, Any]:
    """Reproduce the smallest stale-handoff continuity fracture.

    The same intact H10 handoff is evaluated twice: first against H10, then against
    newer verified head H11. This isolates applicability from storage integrity.
    """
    h10 = _verified_head(
        idx=10,
        state={
            "release": "S0",
            "behavior": "continue_from_baseline",
            "environment_constraint": "constraint-v1",
        },
    )
    h11 = _verified_head(
        idx=11,
        state={
            "release": "S1",
            "behavior": "continue_from_corrected_state",
            "environment_constraint": "constraint-v2",
            "correction": "supersedes-S0-for-continuation",
        },
    )

    recall_kernel = {
        "identity": "software-lineage-fixture",
        "last_verified_state": "S0",
        "corrections": [],
        "unresolved_gaps": [],
        "authority": "NONE",
        "recheck_conditions": ["newer_verified_head"],
    }
    contract = build_continuity_compliance_contract(
        contract_id="software-lineage-h10-contract",
        subject_id="software-lineage-fixture",
        recall_kernel=recall_kernel,
        observed_required_fields=[
            "identity",
            "last_verified_state",
            "corrections",
            "unresolved_gaps",
            "authority",
            "recheck_conditions",
        ],
        authority_limits=["NO_TRUTH_AUTHORITY", "NO_WRITE_AUTHORITY"],
        unresolved_gap_ids=[],
        recheck_condition_ids=["newer_verified_head"],
    )
    binding = build_continuity_head_binding(
        binding_id="software-lineage-h10-binding",
        contract=contract,
        originating_head_hash=h10["head_hash"],
        originating_head_idx=h10["idx"],
    )

    current_check = evaluate_continuity_head_binding(
        binding=binding,
        contract=contract,
        current_head_hash=h10["head_hash"],
        current_head_idx=h10["idx"],
    )
    current_gate = evaluate_continuity_current_gate(head_check=current_check)

    stale_check = evaluate_continuity_head_binding(
        binding=binding,
        contract=contract,
        current_head_hash=h11["head_hash"],
        current_head_idx=h11["idx"],
    )
    stale_gate = evaluate_continuity_current_gate(head_check=stale_check)

    payload = {
        "type": LINEAGE_TYPE,
        "version": LINEAGE_VERSION,
        "scenario": "valid_prior_handoff_survives_newer_verified_head",
        "original_verified_head": h10,
        "newer_verified_head": h11,
        "contract": contract,
        "binding": binding,
        "before_environment_change": {
            "head_check": current_check,
            "gate": current_gate,
        },
        "after_environment_change": {
            "head_check": stale_check,
            "gate": stale_gate,
        },
        "observed_fracture": (
            "stored_handoff_remains_intact_but_is_no_longer_applicable_for_continuation"
        ),
        "reproduction_passes": (
            current_check["status"] == "CURRENT"
            and current_gate["decision"] == "ALLOW"
            and stale_check["status"] == "STALE"
            and "newer_verified_head_exists" in stale_check["reasons"]
            and stale_gate["decision"] == "BLOCK"
        ),
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    return {**payload, "reproduction_hash": stable_hash(payload)}

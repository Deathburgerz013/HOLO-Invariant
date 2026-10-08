"""Bounded workflow contrast against a precommitted continuity fixture.

Research only. Decisions are simulated, never authorized actions.
"""
from __future__ import annotations

from pathlib import Path
from statistics import median
from time import perf_counter_ns
import json
import hashlib

from holosim.continuity_compliance import build_continuity_compliance_contract
from holosim.continuity_head_binding import (
    build_continuity_head_binding,
    evaluate_continuity_head_binding,
)
from holosim.continuity_current_gate import (
    ContinuityCurrentGateError,
    require_current_continuity,
)

FIXTURE = Path(__file__).resolve().parents[1] / "benchmarks" / "continuity-v1.fixture.json"

CASES = (
    ("CLEAN", "claim-current", "head-hash-11", 11, "head-hash-11", 11, "CURRENT", "CONTINUE"),
    ("SUPERSEDED", "claim-original", "head-hash-10", 10, "head-hash-11", 11, "STALE", "BLOCK"),
    ("MISSING_REVALIDATION", "claim-original", "head-hash-10", 10, None, None, "UNKNOWN", "BLOCK"),
    ("CONTRADICTED_HEAD", "claim-original", "head-hash-10", 10, "different-head-hash-10", 10, "INVALID", "BLOCK"),
)


def run_contrast():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    recorded_hash = fixture.get("fixture_hash")
    hash_body = {key: value for key, value in fixture.items() if key != "fixture_hash"}
    canonical = json.dumps(
        hash_body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    computed_hash = hashlib.sha256(canonical).hexdigest()
    if recorded_hash != computed_hash:
        raise ValueError("continuity fixture integrity mismatch")

    if (
        fixture["latest_justified_claim_ids"] != ["claim-current"]
        or fixture["superseded_claim_ids"] != ["claim-original"]
        or fixture["required_lineage_edges"] != [["claim-original", "claim-current"]]
        or fixture["stale_continuation_must_block"] is not True
    ):
        raise ValueError("precommitted fixture relationships changed")

    contract = build_continuity_compliance_contract(
        contract_id="bounded-workflow-contrast",
        subject_id="HOLO-Invariant",
        recall_kernel={
            "latest_justified": fixture["latest_justified_claim_ids"],
            "superseded": fixture["superseded_claim_ids"],
        },
        observed_required_fields=["latest_justified", "superseded"],
        authority_limits=["write:NONE", "execute:NONE"],
        unresolved_gap_ids=fixture["uncertainty_claim_ids"],
        recheck_condition_ids=["head-changed"],
    )

    results = []
    timings = {"A": [], "B": []}
    executed_checks = {
        "A": {"head_binding": 0, "current_gate": 0},
        "B": {"head_binding": 0, "current_gate": 0},
    }

    for name, claim, origin_hash, origin_idx, current_hash, current_idx, expected_status, expected_b in CASES:
        binding = build_continuity_head_binding(
            binding_id=f"contrast-{name.lower()}",
            contract=contract,
            originating_head_hash=origin_hash,
            originating_head_idx=origin_idx,
        )

        start = perf_counter_ns()
        a_decision = "CONTINUE"
        timings["A"].append(perf_counter_ns() - start)

        start = perf_counter_ns()
        executed_checks["B"]["head_binding"] += 1
        head_check = evaluate_continuity_head_binding(
            binding=binding,
            contract=contract,
            current_head_hash=current_hash,
            current_head_idx=current_idx,
        )

        if (
            head_check.get("truth_claimed") is not False
            or head_check.get("accepted") is not False
            or head_check.get("write_authority") != "NONE"
        ):
            raise ValueError("head evaluator violated denial contract")

        executed_checks["B"]["current_gate"] += 1
        try:
            gate = require_current_continuity(head_check=head_check)
            b_decision = "CONTINUE"
        except ContinuityCurrentGateError:
            gate = None
            b_decision = "BLOCK"
        timings["B"].append(perf_counter_ns() - start)

        if head_check["status"] != expected_status or b_decision != expected_b:
            raise AssertionError(f"precommitted outcome mismatch: {name}")

        results.append({
            "case": name,
            "claim_id": claim,
            "arm_a": a_decision,
            "arm_b": b_decision,
            "head_status": head_check["status"],
            "incorrect_a": name == "SUPERSEDED" and a_decision == "CONTINUE",
            "incorrect_b": name == "SUPERSEDED" and b_decision == "CONTINUE",
            "unsupported_a": name in {"MISSING_REVALIDATION", "CONTRADICTED_HEAD"} and a_decision == "CONTINUE",
            "unsupported_b": name in {"MISSING_REVALIDATION", "CONTRADICTED_HEAD"} and b_decision == "CONTINUE",
            "false_block_b": name == "CLEAN" and b_decision == "BLOCK",
            "truth_claimed": False,
            "accepted": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
        })

    return {
        "type": "bounded_workflow_contrast",
        "version": 1,
        "cases": results,
        "incorrect_continuations": {
            "A": sum(r["incorrect_a"] for r in results),
            "B": sum(r["incorrect_b"] for r in results),
        },
        "unsupported_continuations": {
            "A": sum(r["unsupported_a"] for r in results),
            "B": sum(r["unsupported_b"] for r in results),
        },
        "false_blocks_clean_b": sum(r["false_block_b"] for r in results),
        "executed_checks": executed_checks,
        "decision_time_ns": {
            arm: {"median": median(values), "max": max(values)}
            for arm, values in timings.items()
        },
        "interpretation": {
            "demonstrated": "precommitted symbolic head-currentness classification",
            "arm_a_continues_by_construction": True,
            "superseded_claim_detection_demonstrated": False,
            "claim_lineage_consumed_by_evaluator": False,
            "latency_scope": "single decision-timer reading per case",
            "latency_comparison_supported": False,
            "real_world_error_reduction_demonstrated": False,
        },
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }


if __name__ == "__main__":
    print(json.dumps(run_contrast(), indent=2))

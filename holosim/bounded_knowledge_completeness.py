"""Finite Boolean-world investigation, exhaustive audit, and epoch rechecks.

The investigator sees only answers to queries. The auditor sees the world.
This is a deterministic learner experiment, not an LLM or universal knowledge.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
import hashlib
from itertools import product
import json
from typing import Any

MAX_EPOCHS = 4
MAX_INPUTS = 8
NOTICE = (
    "Completeness applies only to every input of the declared finite Boolean "
    "world at the audited epoch. Candidate agreement is conditional on the "
    "declared family. No universal knowledge, future currentness, acceptance, "
    "or operational authority is established."
)


class KnowledgeCompletenessError(ValueError):
    """Invalid bounded experiment inputs or replay evidence."""


def _bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError) as exc:
        raise KnowledgeCompletenessError("invalid canonical value") from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _validate(inputs: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(inputs, Mapping) or set(inputs) != {
        "worlds", "family", "query_budget", "accessible_inputs"
    }:
        raise KnowledgeCompletenessError("input schema mismatch")
    worlds = inputs["worlds"]
    if not isinstance(worlds, list) or not 1 <= len(worlds) <= MAX_EPOCHS:
        raise KnowledgeCompletenessError("worlds must contain 1..4 epochs")
    size = None
    for world in worlds:
        if (not isinstance(world, list) or len(world) not in (2, 4, 8)
                or any(type(value) is not bool for value in world)):
            raise KnowledgeCompletenessError("each world must have 2, 4, or 8 Boolean outputs")
        if size is not None and len(world) != size:
            raise KnowledgeCompletenessError("epoch scopes must match")
        size = len(world)
    if inputs["family"] not in ("FULL", "AFFINE"):
        raise KnowledgeCompletenessError("unknown hypothesis family")
    budget = inputs["query_budget"]
    if type(budget) is not int or not 0 <= budget <= MAX_INPUTS:
        raise KnowledgeCompletenessError("query_budget must be an integer in 0..8")
    access = inputs["accessible_inputs"]
    if (not isinstance(access, list) or len(access) > size
            or any(type(i) is not int or not 0 <= i < size for i in access)
            or len(set(access)) != len(access)):
        raise KnowledgeCompletenessError("invalid accessible_inputs")
    return deepcopy(dict(inputs))


def _family(size: int, name: str) -> list[tuple[bool, ...]]:
    if name == "FULL":
        return list(product((False, True), repeat=size))
    # y = bias XOR parity(mask AND binary input); n is log2(size).
    return [tuple(bool(bias ^ ((mask & x).bit_count() % 2)) for x in range(size))
            for bias in (0, 1) for mask in range(size)]


def _predictions(candidates: list[tuple[bool, ...]], size: int) -> list[bool | None]:
    return [next(iter(values)) if len(values := {h[x] for h in candidates}) == 1
            else None for x in range(size)]


def _investigate(candidates: list[tuple[bool, ...]], size: int,
                 access: list[int], budget: int, observe: Callable[[int], bool]
                 ) -> tuple[list[tuple[bool, ...]], list[dict[str, Any]]]:
    """Choose balanced separating queries without access to hidden world data."""
    observations = []
    remaining = set(access)
    while candidates and remaining and len(observations) < budget:
        def separation(x: int) -> int:
            yes = sum(h[x] for h in candidates)
            return yes * (len(candidates) - yes)
        query = min(remaining, key=lambda x: (-separation(x), x))
        if separation(query) == 0:
            break
        value = observe(query)
        observations.append({"input": query, "output": value})
        candidates = [h for h in candidates if h[query] == value]
        remaining.remove(query)
    return candidates, observations


def _audit(predictions: list[bool | None], world: list[bool]) -> dict[str, Any]:
    wrong = [i for i, value in enumerate(predictions)
             if value is not None and value != world[i]]
    unknown = [i for i, value in enumerate(predictions) if value is None]
    return {"wrong_inputs": wrong, "unknown_inputs": unknown,
            "correct_count": len(world) - len(wrong) - len(unknown),
            "complete_for_epoch": not wrong and not unknown}


def run_bounded_knowledge_experiment(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Run bounded queries then audit all inputs; never feed audit answers back.

    Each epoch starts with the same declared family, keeping prior evidence
    in history. Change detection uses new query answers, not oracle audit data.
    """
    spec = _validate(inputs)
    size = len(spec["worlds"][0])
    hypotheses = _family(size, spec["family"])
    history: list[dict[str, Any]] = []
    phases = []
    previous = None
    for epoch, world in enumerate(spec["worlds"]):
        candidates, observations = _investigate(
            hypotheses[:], size, spec["accessible_inputs"], spec["query_budget"],
            lambda x: world[x],
        )
        detected = previous is not None and any(
            previous[row["input"]] is not None
            and previous[row["input"]] != row["output"] for row in observations
        )
        for row in observations:
            body = {"epoch": epoch, **row,
                    "parent_event_hash": history[-1]["event_hash"] if history else None}
            history.append({**body, "event_hash": _hash(body)})
        predictions = _predictions(candidates, size)
        phases.append({
            "epoch": epoch, "world_hash": _hash(world),
            "candidate_count": len(candidates),
            "family_contains_world": tuple(world) in hypotheses,
            "observations": observations, "predictions": predictions,
            "candidate_agreement_complete": bool(candidates) and None not in predictions,
            "audit": _audit(predictions, world),
            "stale_model_audit": _audit(previous, world) if previous is not None else None,
            "change_detected_from_queries": detected,
            "unqueried_inputs": [i for i in range(size)
                                  if i not in {r["input"] for r in observations}],
            "history_length": len(history),
        })
        previous = predictions
    body = {
        "type": "bounded_knowledge_completeness_experiment", "version": 1,
        "input_hash": _hash(spec), "scope": {"input_count": size, "output_type": "BOOLEAN"},
        "family": spec["family"], "epochs": phases, "history": history,
        "accepted": False, "truth_claimed": False,
        "write_authority": "NONE", "execution_authority": "NONE",
        "interpretation_notice": NOTICE,
    }
    return {**body, "receipt_hash": _hash(body)}


def verify_bounded_knowledge_experiment(receipt: Mapping[str, Any],
                                        inputs: Mapping[str, Any]) -> None:
    """Replay from original worlds and controls; a self-hash is insufficient."""
    expected = run_bounded_knowledge_experiment(inputs)
    if not isinstance(receipt, Mapping) or _bytes(dict(receipt)) != _bytes(expected):
        raise KnowledgeCompletenessError("receipt does not match original inputs")


def main() -> None:
    parity = [bool(x.bit_count() % 2) for x in range(8)]
    changed = parity[:]
    changed[7] = not changed[7]
    scenarios = {
        "EXHAUSTIVE": ([parity], "FULL", 8, list(range(8))),
        "LIMITED": ([parity], "FULL", 4, list(range(8))),
        "RULE_INFERENCE": ([parity], "AFFINE", 4, list(range(8))),
        "WRONG_FAMILY": ([changed], "AFFINE", 4, list(range(8))),
        "WORLD_CHANGE": ([parity, changed], "FULL", 8, list(range(8))),
        "UNOBSERVED_CHANGE": ([parity, changed], "AFFINE", 4, list(range(8))),
        "INACCESSIBLE": ([parity], "FULL", 8, [0, 1, 2, 3]),
    }
    results = {}
    for name, (worlds, family, budget, access) in scenarios.items():
        receipt = run_bounded_knowledge_experiment({"worlds": worlds, "family": family,
                      "query_budget": budget, "accessible_inputs": access})
        results[name] = {"epochs": [{k: phase[k] for k in (
            "candidate_count", "candidate_agreement_complete", "audit",
            "change_detected_from_queries", "stale_model_audit")}
            for phase in receipt["epochs"]], "receipt_hash": receipt["receipt_hash"]}
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

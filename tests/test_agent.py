from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.agent import (
    CONDITIONALLY_DIVERGENT,
    run_dependency_checked_convergence_agent,
    VerifiedConvergenceAgentError,
    run_verified_convergence_agent,
    verify_agent_convergence_receipt,
    verify_dependency_checked_agent_receipt,
)
from holosim.bounded_evidence_analyst import build_evidence_analysis_receipt
from holosim.canonical import stable_hash


def analysis(analysis_id, scope, finding_id="f1", statement="X holds", relation="SUPPORTS"):
    return build_evidence_analysis_receipt(
        analysis_id=analysis_id,
        scope=scope,
        method={
            "method_id": "fixture-method",
            "method_version": "v1",
            "description": "fixture declared-relation method",
        },
        evidence=[{
            "evidence_id": "e1",
            "content_sha256": stable_hash({"analysis": analysis_id}),
            "source_reference": f"fixture:{analysis_id}",
            "availability": "VERIFIED",
        }],
        findings=[{
            "finding_id": finding_id,
            "statement": statement,
            "evidence_assessments": [{
                "evidence_id": "e1",
                "disposition": "INCLUDED",
                "relation": relation,
                "rationale": f"fixture relation {relation}",
            }],
        }],
    )


def run(receipts):
    return run_verified_convergence_agent(
        run_id="agent.run-1",
        objective="Converge verified fixture findings without erasure.",
        analysis_receipts=receipts,
    )


def test_repeated_support_converges_same_finding() -> None:
    receipt = run([analysis("a2", "scope-1"), analysis("a1", "scope-1")])
    assert receipt["run_status"] == "CONVERGED_CANDIDATE"
    assert [item["finding_id"] for item in receipt["converged_findings"]] == ["f1"]
    assert receipt["rejected_findings"] == []
    assert receipt["unresolved_findings"] == []
    assert verify_agent_convergence_receipt(receipt) is True


def test_contradicted_finding_is_preserved_as_rejected() -> None:
    receipt = run([analysis("a1", "scope-1", relation="CONTRADICTS")])
    assert receipt["run_status"] == "NO_SUPPORTED_FINDINGS"
    assert receipt["converged_findings"] == []
    assert receipt["rejected_findings"][0]["status"] == "CONTRADICTED"


def test_scope_dependent_difference_is_not_averaged() -> None:
    receipt = run([
        analysis("a1", "condition-1", relation="SUPPORTS"),
        analysis("a2", "condition-2", relation="CONTRADICTS"),
    ])
    finding = receipt["unresolved_findings"][0]
    assert receipt["run_status"] == "PARTIAL"
    assert finding["status"] == CONDITIONALLY_DIVERGENT
    assert [item["status"] for item in finding["scope_results"]] == [
        "SUPPORTED", "CONTRADICTED",
    ]


def test_different_statement_for_same_id_remains_unresolved() -> None:
    receipt = run([
        analysis("a1", "scope-1", statement="X holds"),
        analysis("a2", "scope-1", statement="X never holds"),
    ])
    finding = receipt["unresolved_findings"][0]
    assert finding["status"] == "UNRESOLVED"
    assert finding["scope_results"][0]["reason"] == (
        "STATEMENT_IDENTITY_CONFLICT_WITHIN_SCOPE"
    )


def test_unknown_evidence_prevents_convergence() -> None:
    receipt = run([analysis("a1", "scope-1", relation="UNKNOWN")])
    assert receipt["run_status"] == "PARTIAL"
    assert receipt["unresolved_findings"][0]["status"] == "UNRESOLVED"


def test_distinct_supported_findings_are_retained() -> None:
    receipt = run([
        analysis("a1", "scope-1", finding_id="f2", statement="Y holds"),
        analysis("a2", "scope-1", finding_id="f1", statement="X holds"),
    ])
    assert [item["finding_id"] for item in receipt["converged_findings"]] == [
        "f1", "f2",
    ]


def test_input_order_does_not_change_receipt() -> None:
    first = analysis("a1", "scope-1")
    second = analysis("a2", "scope-2")
    assert run([first, second]) == run([second, first])


def test_input_receipts_are_isolated_from_later_mutation() -> None:
    source = analysis("a1", "scope-1")
    receipt = run([source])
    source["scope"] = "changed"
    assert receipt == run([analysis("a1", "scope-1")])


def test_duplicate_analysis_identity_fails_closed() -> None:
    with pytest.raises(VerifiedConvergenceAgentError, match="analysis_id"):
        run([analysis("a1", "scope-1"), analysis("a1", "scope-2")])


def test_empty_input_fails_closed() -> None:
    with pytest.raises(VerifiedConvergenceAgentError, match="at least one"):
        run([])


def test_tampered_analysis_receipt_fails_before_convergence() -> None:
    source = analysis("a1", "scope-1")
    source["finding_results"][0]["status"] = "CONTRADICTED"
    with pytest.raises(VerifiedConvergenceAgentError, match="verification failed"):
        run([source])


def test_agent_stops_before_uncomposed_effect_stages() -> None:
    receipt = run([analysis("a1", "scope-1")])
    assert receipt["pending_stages"] == [
        "DEPENDENCY_RECHECK", "ADMISSION", "PERSISTENCE",
    ]
    assert receipt["stopped"] is True


def test_agent_never_infers_usefulness_truth_or_authority() -> None:
    receipt = run([analysis("a1", "scope-1")])
    assert receipt["method_executed"] is False
    assert receipt["usefulness_inferred"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["recommended_action"] is None
    assert receipt["accepted"] is False
    assert receipt["selection_authority"] == "NONE"
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_receipt_hash_tampering_is_rejected() -> None:
    receipt = run([analysis("a1", "scope-1")])
    receipt["run_status"] = "CONVERGED"
    with pytest.raises(VerifiedConvergenceAgentError, match="hash mismatch"):
        verify_agent_convergence_receipt(receipt)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("usefulness_inferred", True),
        ("truth_claimed", True),
        ("accepted", True),
        ("selection_authority", "AGENT"),
        ("write_authority", "AGENT"),
        ("execution_authority", "AGENT"),
        ("recommended_action", "persist"),
        ("pending_stages", []),
    ],
)
def test_rehashed_semantic_forgery_is_rejected(field, value) -> None:
    receipt = run([analysis("a1", "scope-1")])
    receipt[field] = value
    body = {key: item for key, item in receipt.items() if key != "receipt_hash"}
    receipt["receipt_hash"] = stable_hash(body)
    with pytest.raises(VerifiedConvergenceAgentError, match="internally inconsistent"):
        verify_agent_convergence_receipt(receipt)


def test_extra_field_is_rejected() -> None:
    receipt = run([analysis("a1", "scope-1")])
    receipt["autonomous"] = True
    with pytest.raises(VerifiedConvergenceAgentError, match="fields mismatch"):
        verify_agent_convergence_receipt(receipt)


def dependency_checked(base, bindings, changes, dependencies=()):
    return run_dependency_checked_convergence_agent(
        run_id="agent.recheck-1",
        base_agent_receipt=base,
        dependency_bindings=bindings,
        dependency_receipts=list(dependencies),
        changed_dependency_hashes=changes,
    )


def binding(receipt, *dependencies):
    return {
        "analysis_receipt_hash": receipt["receipt_hash"],
        "dependency_receipt_hashes": list(dependencies),
    }


def test_changed_dependency_withholds_only_affected_finding() -> None:
    first = analysis("a1", "scope-1", finding_id="f1")
    second = analysis("a2", "scope-1", finding_id="f2", statement="Y holds")
    changed = stable_hash({"dependency": "changed"})
    result = dependency_checked(
        run([first, second]),
        [binding(first, changed), binding(second)],
        [changed],
    )
    assert result["run_status"] == "RECHECK_REQUIRED"
    assert result["withheld_findings"][0]["finding"]["finding_id"] == "f1"
    assert result["withheld_findings"][0]["trigger_paths"] == [
        [changed, first["receipt_hash"]]
    ]
    assert [item["finding_id"] for item in result["eligible_converged_findings"]] == ["f2"]
    assert verify_dependency_checked_agent_receipt(result) is True


def test_transitive_dependency_change_withholds_finding() -> None:
    source = analysis("a1", "scope-1")
    changed = stable_hash({"dependency": "root"})
    middle = stable_hash({"dependency": "middle"})
    result = dependency_checked(
        run([source]),
        [binding(source, middle)],
        [changed],
        [{"receipt_hash": middle, "previous_receipt_hash": changed}],
    )
    assert result["withheld_findings"][0]["trigger_paths"] == [
        [changed, middle, source["receipt_hash"]]
    ]


def test_unobserved_change_does_not_invent_impact_or_validity() -> None:
    source = analysis("a1", "scope-1")
    unrelated = stable_hash({"dependency": "unrelated"})
    result = dependency_checked(
        run([source]), [binding(source)], [unrelated]
    )
    assert result["run_status"] == "NO_DECLARED_RECHECK_IMPACT"
    assert result["withheld_findings"] == []
    assert result["eligible_converged_findings"][0]["finding_id"] == "f1"
    assert result["validity_claimed"] is False
    assert result["recheck_plan"]["unobserved_changed_hashes"] == [unrelated]


def test_every_analysis_receipt_requires_dependency_binding() -> None:
    first = analysis("a1", "scope-1")
    second = analysis("a2", "scope-1")
    with pytest.raises(VerifiedConvergenceAgentError, match="cover every"):
        dependency_checked(
            run([first, second]),
            [binding(first)],
            [stable_hash({"changed": 1})],
        )


def test_dependency_binding_order_is_deterministic() -> None:
    first = analysis("a1", "scope-1", finding_id="f1")
    second = analysis("a2", "scope-1", finding_id="f2", statement="Y holds")
    changed = stable_hash({"changed": 1})
    base = run([first, second])
    left = dependency_checked(
        base, [binding(first, changed), binding(second)], [changed]
    )
    right = dependency_checked(
        base, [binding(second), binding(first, changed)], [changed]
    )
    assert left == right


def test_tampered_base_agent_receipt_fails_before_planning() -> None:
    source = analysis("a1", "scope-1")
    base = run([source])
    base["run_status"] = "ACCEPTED"
    with pytest.raises(VerifiedConvergenceAgentError, match="base Agent"):
        dependency_checked(
            base,
            [binding(source)],
            [stable_hash({"changed": 1})],
        )


def test_dependency_cycle_fails_closed() -> None:
    source = analysis("a1", "scope-1")
    first = stable_hash({"dependency": 1})
    second = stable_hash({"dependency": 2})
    with pytest.raises(VerifiedConvergenceAgentError, match="planning failed"):
        dependency_checked(
            run([source]),
            [binding(source, first)],
            [first],
            [
                {"receipt_hash": first, "previous_receipt_hash": second},
                {"receipt_hash": second, "previous_receipt_hash": first},
            ],
        )


def test_dependency_checked_agent_stops_without_authority() -> None:
    source = analysis("a1", "scope-1")
    result = dependency_checked(
        run([source]),
        [binding(source)],
        [stable_hash({"changed": 1})],
    )
    assert result["pending_stages"] == [
        "DEPENDENCY_RECHECK_EXECUTION", "ADMISSION", "PERSISTENCE",
    ]
    assert result["stopped"] is True
    assert result["truth_claimed"] is False
    assert result["recommended_action"] is None
    assert result["accepted"] is False
    assert result["selection_authority"] == "NONE"
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_dependency_checked_receipt_tampering_is_rejected() -> None:
    source = analysis("a1", "scope-1")
    result = dependency_checked(
        run([source]),
        [binding(source)],
        [stable_hash({"changed": 1})],
    )
    result["validity_claimed"] = True
    with pytest.raises(VerifiedConvergenceAgentError, match="hash mismatch"):
        verify_dependency_checked_agent_receipt(result)


def test_rehashed_dependency_checked_authority_forgery_is_rejected() -> None:
    source = analysis("a1", "scope-1")
    result = dependency_checked(
        run([source]),
        [binding(source)],
        [stable_hash({"changed": 1})],
    )
    result["accepted"] = True
    body = {key: item for key, item in result.items() if key != "receipt_hash"}
    result["receipt_hash"] = stable_hash(body)
    with pytest.raises(VerifiedConvergenceAgentError, match="internally inconsistent"):
        verify_dependency_checked_agent_receipt(result)


def test_declared_cross_model_fact_identity_groups_different_local_ids() -> None:
    first = analysis(
        "model-a",
        "scope-1",
        finding_id="model-a.fact-17",
        statement="X holds",
    )
    second = analysis(
        "model-b",
        "scope-1",
        finding_id="model-b.output-3",
        statement="X holds",
    )

    receipt = run_verified_convergence_agent(
        run_id="agent.run-1",
        objective="Converge explicitly identity-bound findings.",
        analysis_receipts=[first, second],
        fact_identity_bindings=[
            {
                "fact_id": "fact:x",
                "members": [
                    {
                        "analysis_id": "model-a",
                        "finding_id": "model-a.fact-17",
                    },
                    {
                        "analysis_id": "model-b",
                        "finding_id": "model-b.output-3",
                    },
                ],
            },
        ],
    )

    assert len(receipt["converged_findings"]) == 1
    assert receipt["converged_findings"][0]["fact_id"] == "fact:x"


def test_cross_model_fact_identity_member_cannot_belong_to_two_facts() -> None:
    first = analysis(
        "model-a",
        "scope-1",
        finding_id="model-a.fact-17",
        statement="X holds",
    )

    with pytest.raises(
        VerifiedConvergenceAgentError,
        match="fact identity member",
    ):
        run_verified_convergence_agent(
            run_id="agent.run-1",
            objective="Reject ambiguous declared fact identity.",
            analysis_receipts=[first],
            fact_identity_bindings=[
                {
                    "fact_id": "fact:x",
                    "members": [
                        {
                            "analysis_id": "model-a",
                            "finding_id": "model-a.fact-17",
                        },
                    ],
                },
                {
                    "fact_id": "fact:y",
                    "members": [
                        {
                            "analysis_id": "model-a",
                            "finding_id": "model-a.fact-17",
                        },
                    ],
                },
            ],
        )
def test_agent_rejects_unverified_fact_identity_binding_receipt() -> None:
    first = analysis(
        "model-a",
        "scope-1",
        finding_id="model-a.fact-17",
        statement="X holds",
    )
    second = analysis(
        "model-b",
        "scope-1",
        finding_id="model-b.output-3",
        statement="X holds",
    )

    fake_identity_receipt = {
        "type": "verified_fact_identity_receipt",
        "version": 1,
        "fact_id": "fact:x",
        "members": [
            {
                "analysis_id": "model-a",
                "finding_id": "model-a.fact-17",
            },
            {
                "analysis_id": "model-b",
                "finding_id": "model-b.output-3",
            },
        ],
        "receipt_hash": "0" * 64,
    }

    with pytest.raises(
        VerifiedConvergenceAgentError,
        match="fact identity",
    ):
        run_verified_convergence_agent(
            run_id="agent.run-1",
            objective="Require verified fact identity evidence.",
            analysis_receipts=[first, second],
            fact_identity_receipts=[fake_identity_receipt],
        )
from holosim.fact_identity import build_verified_fact_identity_receipt
def test_verified_fact_identity_receipt_groups_cross_model_findings() -> None:
    first = analysis(
        "model-a",
        "scope-1",
        finding_id="model-a.fact-17",
        statement="X holds",
    )
    second = analysis(
        "model-b",
        "scope-1",
        finding_id="model-b.output-3",
        statement="X holds",
    )

    identity = build_verified_fact_identity_receipt(
        fact_id="fact:x",
        members=[
            {
                "analysis_id": "model-a",
                "finding_id": "model-a.fact-17",
            },
            {
                "analysis_id": "model-b",
                "finding_id": "model-b.output-3",
            },
        ],
    )

    receipt = run_verified_convergence_agent(
        run_id="agent.run-1",
        objective="Converge findings using a verified identity declaration.",
        analysis_receipts=[first, second],
        fact_identity_receipts=[identity],
    )

    assert len(receipt["converged_findings"]) == 1
    assert receipt["converged_findings"][0]["fact_id"] == "fact:x"
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False

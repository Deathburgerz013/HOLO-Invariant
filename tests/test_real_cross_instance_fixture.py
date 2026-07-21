from holosim.baseline_promotion_gate import STATUS_CONFLICTED
from holosim.cross_instance_runner import run_cross_instance_baseline_check


BASELINE_PROMPT = "how is true recall possible for ai honestly?"

# Grounded from two independently produced answers to the same exact baseline prompt.
# The fixture intentionally records only claim-level findings needed by the runner.
GROK_FINDINGS = {
    "parametric-memory-is-not-literal-retrieval": "SUPPORT",
    "context-window-is-direct-reading-of-current-context": "SUPPORT",
    "external-retrieval-is-closest-to-literal-recall": "SUPPORT",
    "retrieval-guarantees-traceability-not-source-correctness": "EXTENSION",
    "human-like-recall-requires-conscious-continuity": "CORRECTION",
}

CLAUDE_FINDINGS = {
    "parametric-memory-is-not-literal-retrieval": "SUPPORT",
    "context-window-is-direct-reading-of-current-context": "SUPPORT",
    "external-retrieval-is-closest-to-literal-recall": "SUPPORT",
    "retrieval-guarantees-traceability-not-source-correctness": "EXTENSION",
    "human-like-recall-requires-conscious-continuity": "SUPPORT",
}


def test_real_cross_instance_recall_fixture_exposes_shared_core_and_conflict():
    result = run_cross_instance_baseline_check(
        baseline_id="prompt:true-recall-ai",
        baseline_state_hash="sha256:baseline-how-is-true-recall-possible-for-ai-honestly",
        left_observer_id="grok",
        left_findings=GROK_FINDINGS,
        right_observer_id="claude",
        right_findings=CLAUDE_FINDINGS,
        justification_references={
            "retrieval-guarantees-traceability-not-source-correctness": "source:claude-output",
            "human-like-recall-requires-conscious-continuity": "source:cross-instance-disagreement",
        },
    )

    assert result["summary"]["agreement"] == [
        "context-window-is-direct-reading-of-current-context",
        "external-retrieval-is-closest-to-literal-recall",
        "parametric-memory-is-not-literal-retrieval",
    ]
    assert result["summary"]["extension"] == [
        "retrieval-guarantees-traceability-not-source-correctness"
    ]
    assert result["summary"]["conflict"] == [
        "human-like-recall-requires-conscious-continuity"
    ]
    assert result["summary"]["proposal_status"] == STATUS_CONFLICTED
    assert result["next_baseline_created"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_real_cross_instance_fixture_keeps_exact_prompt_as_documented_baseline():
    assert BASELINE_PROMPT == "how is true recall possible for ai honestly?"

"""Numerical controls and counterexamples, not general convergence proofs."""
import subprocess
import sys
from copy import deepcopy
import pytest
from holosim.canonical import canonical_bytes, stable_hash
from holosim.retained_correction_dynamics import (
    RetainedCorrectionDynamicsError, run_retained_correction_experiment as run,
    verify_retained_correction_experiment as verify,
)


def inputs(**changes):
    result = dict(initial=[0.0], observations=[[8.0]] * 6, gap_after=3)
    result.update(changes)
    return result


def test_three_recovery_controls():
    retained = run(**inputs())
    reset = run(**inputs(mode="RESET"))
    rebuilt = run(**inputs(mode="RECONSTRUCTED"))
    assert retained["final_model"] == rebuilt["final_model"] == [7.875]
    assert reset["final_model"] == [7.0]
    assert rebuilt["history"] == retained["history"]
    assert retained["gap"]["before"] == retained["gap"]["after"] == [7.0]
    assert reset["gap"]["after"] == [0.0]
    for result in (retained, reset, rebuilt):
        assert result["gap"]["history_preserved"] is True
        assert result["history"][:3] == retained["history"][:3]


def test_closed_form_and_telescoping_account_for_reset_jump():
    for mode in ("RETAINED", "RESET", "RECONSTRUCTED"):
        result = run(**inputs(mode=mode))
        total = sum(row["delta"][0] for row in result["history"])
        assert result["final_model"][0] == total + result["gap"]["recovery_jump"][0]
        if mode != "RESET":
            for t, row in enumerate(result["history"], 1):
                assert row["residual_after"] == 8 * 0.5 ** t


def test_deadband_stops_with_nonzero_error():
    result = run(**inputs(threshold=8))
    assert result["final_model"] == [0.0]
    assert all(r["update_stopped"] and r["raw_residual"] == [8.0]
               and r["residual_after"] == 8 for r in result["history"])


def test_projection_loss_preserves_unresolved_raw_error():
    result = run(**inputs(initial=[0, 0], observations=[[0, 8]] * 6,
                          projection=[True, False]))
    assert result["final_model"] == [0.0, 0.0]
    assert result["history"][-1]["raw_residual"] == [0.0, 8.0]
    assert result["history"][-1]["contained_residual"] == [0.0, 0.0]


def test_clip_and_gate():
    row = run(**inputs(initial=[0, 0], observations=[[3, 4]], gap_after=0,
                       clip=2, alpha=1, gates=[False]))["history"][0]
    assert row["contained_residual"] == pytest.approx([1.2, 1.6])
    assert row["raw_residual"] == [3.0, 4.0]
    assert row["delta"] == [0.0, 0.0]
    assert row["residual_after"] == 5


def test_large_gain_diverges():
    result = run(**inputs(alpha=3, clip=1_000_000))
    assert [r["residual_after"] for r in result["history"]] == [16, 32, 64, 128, 256, 512]


def test_changed_environment_reopens_error():
    result = run(**inputs(alpha=1, observations=[[8], [8], [-8]], gap_after=2))
    assert result["history"][1]["residual_after"] == 0
    assert result["history"][2]["raw_residual"] == [-16.0]


def test_no_mutation_or_authority():
    original = inputs()
    before = deepcopy(original)
    result = run(**original)
    assert original == before
    assert result["accepted"] is result["truth_claimed"] is False
    assert result["write_authority"] == result["execution_authority"] == "NONE"
    assert verify(result, **original)


@pytest.mark.parametrize("field,value", [("final_model", [8]), ("accepted", True),
                                          ("truth_claimed", 0), ("extra", "authority")])
def test_rehashed_forgery_fails(field, value):
    result = run(**inputs())
    result[field] = value
    result["receipt_hash"] = stable_hash({k: v for k, v in result.items() if k != "receipt_hash"})
    with pytest.raises(RetainedCorrectionDynamicsError):
        verify(result, **inputs())


def test_substituted_input_fails():
    with pytest.raises(RetainedCorrectionDynamicsError):
        verify(run(**inputs()), **inputs(observations=[[7]] * 6))


@pytest.mark.parametrize("changes", [dict(alpha=True), dict(alpha=float("nan")),
    dict(clip=0), dict(threshold=-1), dict(gap_after=True), dict(gap_after=7),
    dict(initial=[]), dict(initial=[float("inf")]), dict(observations=[]),
    dict(observations=[[1, 2]]), dict(observations=[[1]] * 257),
    dict(projection=[1]), dict(gates=[True]), dict(mode="UNKNOWN"),
    dict(alpha=1e308, observations=[[1e308]], gap_after=0)])
def test_invalid_or_overflow_inputs(changes):
    with pytest.raises(RetainedCorrectionDynamicsError):
        run(**inputs(**changes))


@pytest.mark.parametrize("gap", [0, 6])
def test_endpoint_gap(gap):
    result = run(**inputs(gap_after=gap))
    assert result["final_model"] == [7.875]
    assert result["gap"]["history_preserved"]


def test_fresh_process_replay(tmp_path):
    packet = tmp_path / "experiment.json"
    packet.write_bytes(canonical_bytes(dict(inputs=inputs(), receipt=run(**inputs()))))
    code = ("import json,sys; from holosim.retained_correction_dynamics import "
            "verify_retained_correction_experiment as verify; "
            "p=json.load(open(sys.argv[1])); assert verify(p['receipt'], **p['inputs']); "
            "print(p['receipt']['final_model'][0])")
    child = subprocess.run([sys.executable, "-c", code, str(packet)],
                           capture_output=True, text=True, timeout=20)
    assert child.returncode == 0, child.stderr
    assert child.stdout.strip() == "7.875"

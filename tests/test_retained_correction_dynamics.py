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


# Descent/bound analysis uses the original owning experiment and exact
# arithmetic over its stored floats. It does not certify arbitrary dynamics.
from holosim.retained_correction_dynamics import (
    evaluate_correction_descent_bounds as analyze,
    verify_correction_descent_bounds as verify_analysis,
)


def measured(changes=None, **controls):
    original = inputs(**(changes or {}))
    experiment = run(**original)
    return analyze(experiment, original_inputs=original, **controls)


def test_descent_default_independent_energy_sequence():
    result = measured()
    assert [r['energy_after'] for r in result['steps']] == [16, 4, 1, .25, .0625, .015625]
    assert result['descent_inequality_held_on_permitted_steps'] is True
    assert result['all_steps_strictly_decrease'] is True
    assert result['all_prefix_bounds_held'] is True
    assert result['total_movement_l1'] == 7.875
    assert all(r['energy_identity_held'] for r in result['steps'])


@pytest.mark.parametrize('alpha,expected', [(0, False), (.5, True), (1, True),
                                           (1.5, True), (2, False), (3, False)])
def test_scalar_gain_energy_relation(alpha, expected):
    result = measured(dict(alpha=alpha, observations=[[8]], gap_after=0, clip=100))
    row = result['steps'][0]
    assert row['energy_change'] == 64 * (alpha*alpha - 2*alpha)
    assert row['strictly_decreased'] is expected


def test_masked_clipped_exact_identity_and_partial_progress():
    result = measured(dict(initial=[0, 0], observations=[[3, 4]], gap_after=0,
                           projection=[True, False], clip=1, alpha=1))
    row = result['steps'][0]
    assert row['energy_before'] == 25
    assert row['energy_after'] == 20
    assert row['energy_change'] == -5
    assert row['energy_identity_held'] and row['strictly_decreased'] and row['error_remains']
    # A positive decrease is weaker than the requested uniform decay rate.
    assert row['descent_inequality_held'] is False


@pytest.mark.parametrize('changes', [dict(threshold=8), dict(projection=[False])])
def test_suppression_can_hold_bound_and_fail_descent(changes):
    result = measured(changes)
    assert result['movement_within_budget'] is True
    assert result['descent_inequality_held_on_permitted_steps'] is False
    assert all(r['error_remains'] and r['applied_update_stopped'] for r in result['steps'])


def test_denied_gates_are_unobserved_descent_not_vacuous_success():
    result = measured(dict(gates=[False]*6))
    assert result['permitted_step_count'] == 0
    assert result['descent_inequality_held_on_permitted_steps'] is None
    assert all(r['descent_inequality_held'] is None for r in result['steps'])


def test_allowance_can_hold_inequality_without_correction():
    result = measured(dict(threshold=8), deadband_allowance=32)
    assert result['descent_inequality_held_on_permitted_steps'] is True
    assert result['all_steps_strictly_decrease'] is False
    assert result['steps'][0]['energy_after'] == 64


def test_reset_jump_is_separate_from_local_descent():
    result = measured(dict(mode='RESET'))
    assert result['descent_inequality_held_on_permitted_steps'] is True
    assert result['gap_energy_change'] == 63
    assert result['gap_nonincreasing'] is False
    assert result['correction_movement_l1'] == 14
    assert result['recovery_movement_l1'] == 7
    assert result['total_movement_l1'] == 21
    assert result['movement_within_budget'] is False
    assert result['all_prefix_bounds_held']


def test_retained_and_reconstructed_analysis_agree():
    retained = measured()
    rebuilt = measured(dict(mode='RECONSTRUCTED'))
    assert retained['steps'] == rebuilt['steps']
    assert retained['prefixes'] == rebuilt['prefixes']


def test_cancelling_updates_have_large_path_despite_zero_displacement():
    result = measured(dict(alpha=2, clip=100))
    assert result['prefixes'][-1]['displacement_l1'] == 0
    assert result['total_movement_l1'] == 96
    assert result['movement_within_budget'] is False
    assert result['all_prefix_bounds_held']


def test_budget_equal_and_one_below():
    assert measured(movement_budget=7.875)['movement_within_budget']
    assert not measured(movement_budget=7.874)['movement_within_budget']


def test_changing_target_is_not_fixed_target_proof():
    result = measured(dict(observations=[[8], [-8]], gap_after=1))
    assert result['fixed_target'] is False
    assert result['all_steps_strictly_decrease'] is True
    assert result['steps'][1]['energy_before'] > result['steps'][0]['energy_after']


def test_requested_small_update_lost_to_float_rounding():
    result = measured(dict(initial=[1e16], observations=[[1e16+2]],
                           alpha=.25, gap_after=0))
    row = result['steps'][0]
    assert row['requested_update_applied_exactly'] is False
    assert row['applied_update_stopped'] is True
    assert row['energy_change'] == 0
    assert not row['descent_inequality_held']
    assert result['total_movement_l1'] == 0


def test_exact_decisions_survive_energy_display_underflow():
    result = measured(dict(observations=[[1e-200]], gap_after=0))
    row = result['steps'][0]
    assert row['energy_before'] == row['energy_after'] == 0.0
    assert row['strictly_decreased'] and row['error_remains']
    assert row['energy_identity_held'] and row['descent_inequality_held']


def test_negative_gain_is_rejected_not_abs_alpha_certificate():
    with pytest.raises(RetainedCorrectionDynamicsError):
        measured(dict(alpha=-.5))


@pytest.mark.parametrize('controls', [dict(decay_rate=0), dict(decay_rate=True),
    dict(deadband_allowance=-1), dict(movement_budget=-1), dict(movement_budget=float('inf'))])
def test_invalid_analysis_controls(controls):
    with pytest.raises(RetainedCorrectionDynamicsError):
        measured(**controls)


def test_energy_overflow_fails_display_closed():
    with pytest.raises(RetainedCorrectionDynamicsError):
        measured(dict(observations=[[1e200]], gap_after=0))


def test_analysis_no_mutation_and_replay_tampering():
    original = inputs()
    experiment = run(**original)
    prior = deepcopy(experiment)
    result = analyze(experiment, original_inputs=original)
    assert experiment == prior
    assert verify_analysis(result, experiment, original_inputs=original)
    assert result['accepted'] is result['truth_claimed'] is False
    for field, value in [('movement_within_budget', False), ('accepted', True),
                         ('truth_claimed', 0), ('extra', 'authority')]:
        bad = deepcopy(result)
        bad[field] = value
        bad['receipt_hash'] = stable_hash({k:v for k,v in bad.items() if k != 'receipt_hash'})
        with pytest.raises(RetainedCorrectionDynamicsError):
            verify_analysis(bad, experiment, original_inputs=original)
    with pytest.raises(RetainedCorrectionDynamicsError):
        verify_analysis(result, experiment, original_inputs=original, movement_budget=17)
    forged = deepcopy(experiment)
    forged['history'][0]['model_after'] = [8.0]
    forged['receipt_hash'] = stable_hash({k:v for k,v in forged.items() if k != 'receipt_hash'})
    with pytest.raises(RetainedCorrectionDynamicsError):
        analyze(forged, original_inputs=original)


def test_allowance_can_hide_energy_increase():
    result = measured(dict(alpha=3, observations=[[8]], gap_after=0, clip=100),
                      deadband_allowance=224)
    assert result['descent_inequality_held_on_permitted_steps'] is True
    assert result['steps'][0]['energy_change'] == 192
    assert result['all_steps_strictly_decrease'] is False

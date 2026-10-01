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


# Scheduled gaps use the same correction map and original-input replay boundary.
def scheduled_inputs(**changes):
    result = dict(initial=[0.0], observations=[[8.0]] * 6,
                  gap_schedule=[dict(after=2, mode="RETAINED"),
                                dict(after=4, mode="RETAINED")])
    result.update(changes)
    return result


def scheduled_analysis(**changes):
    original = scheduled_inputs(**changes)
    experiment = run(**original)
    return original, experiment, analyze(
        experiment, original_inputs=original)


@pytest.mark.parametrize("mode, final, movement, loss", [
    ("RETAINED", 7.875, 7.875, 0),
    ("RECONSTRUCTED", 7.875, 7.875, 0),
    ("RESET", 6, 30, 120),
])
def test_multiple_gap_closed_form_and_progress_loss(mode, final, movement, loss):
    original, experiment, audit = scheduled_analysis(gap_schedule=[
        dict(after=2, mode=mode), dict(after=4, mode=mode)])
    assert experiment["final_model"] == [final]
    assert all(g["history_preserved"] for g in experiment["gaps"])
    assert audit["total_movement_l1"] == movement
    assert audit["total_gap_progress_loss"] == loss
    assert audit["all_prefix_bounds_held"] is True
    assert len(audit["prefixes"]) == 8
    assert audit["gap_nonincreasing"] is (mode != "RESET")
    if mode != "RESET":
        assert [r["contraction_ratio"] for r in audit["steps"]] == [0.25] * 6
        assert [r["residual_after"] for r in experiment["history"]] == [4, 2, 1, .5, .25, .125]
    assert verify(experiment, **original)
    assert verify_analysis(audit, experiment, original_inputs=original)


def test_reconstruction_replays_earlier_resets_not_an_unbroken_trajectory():
    original, experiment, audit = scheduled_analysis(gap_schedule=[
        dict(after=2, mode="RESET"), dict(after=4, mode="RECONSTRUCTED")])
    assert experiment["gaps"][1]["before"] == experiment["gaps"][1]["after"] == [6.0]
    assert experiment["final_model"] == [7.5]
    assert audit["total_gap_progress_loss"] == 60
    assert audit["total_movement_l1"] == 19.5
    assert audit["all_prefix_bounds_held"]


@pytest.mark.parametrize("mode", ["RETAINED", "RECONSTRUCTED", "RESET"])
def test_rounding_and_repeated_gaps_together(mode):
    original, experiment, audit = scheduled_analysis(
        initial=[1e16, 0], observations=[[1e16 + 2, 8]] * 6, alpha=.25,
        gap_schedule=[dict(after=2, mode=mode), dict(after=4, mode=mode)])
    assert all(r["model_after"][0] == 1e16 for r in experiment["history"])
    assert all(not r["requested_update_applied_exactly"] for r in audit["steps"])
    assert all(r["energy_identity_held"] for r in audit["steps"])
    assert all(g["history_preserved"] for g in experiment["gaps"])
    assert audit["all_prefix_bounds_held"]
    if mode == "RESET":
        assert experiment["final_model"][1] == 3.5
        assert audit["total_gap_progress_loss"] == 87.5
    else:
        assert experiment["final_model"][1] == 8 * (1 - .75 ** 6)
        assert audit["total_gap_progress_loss"] == 0
    assert audit["steps"][-1]["error_remains"]


def test_masked_error_persists_while_visible_error_contracts():
    _, experiment, audit = scheduled_analysis(initial=[0, 0], observations=[[8, 3]] * 6,
                                              projection=[True, False])
    assert experiment["final_model"] == [7.875, 0]
    assert audit["projection_pullback_metric_diagonal"] == [1, 0]
    assert audit["metric_positive_definite"] is False
    assert audit["metric_positive_semidefinite"] is True
    assert [r["hidden_energy_before"] for r in audit["steps"]] == [9] * 6
    assert [r["hidden_energy_after"] for r in audit["steps"]] == [9] * 6
    assert all(r["hidden_energy_unchanged"] for r in audit["steps"])
    assert audit["steps"][-1]["energy_after"] == 9.015625
    assert all(r["strictly_decreased"] for r in audit["steps"])
    assert audit["descent_inequality_held_on_permitted_steps"] is False


@pytest.mark.parametrize("mask, diagonal, definite", [
    ([True, True], [1, 1], True), ([False, False], [0, 0], False),
])
def test_coordinate_pullback_metric_is_derived_from_declared_projection(mask, diagonal, definite):
    _, _, audit = scheduled_analysis(initial=[0, 0], observations=[[8, 3]] * 6, projection=mask)
    assert audit["projection_pullback_metric_diagonal"] == diagonal
    assert audit["metric_positive_definite"] is definite


def test_zero_energy_has_no_contraction_ratio():
    _, _, audit = scheduled_analysis(initial=[8], gap_schedule=[])
    assert all(r["contraction_ratio"] is None for r in audit["steps"])
    assert audit["gaps"] == []
    assert audit["total_gap_progress_loss"] == 0


def test_empty_and_endpoint_schedules_preserve_trajectory():
    for schedule in ([], [dict(after=0, mode="RECONSTRUCTED"), dict(after=6, mode="RESET")]):
        original, experiment, audit = scheduled_analysis(gap_schedule=schedule)
        assert experiment["final_model"] == ([0] if schedule else [7.875])
        assert len(experiment["history"]) == 6
        assert audit["all_prefix_bounds_held"]
        assert verify(experiment, **original)
    assert audit["gaps"][-1]["progress_loss"] == 64 - .015625


@pytest.mark.parametrize("schedule", [
    {}, [dict(after=True, mode="RETAINED")], [dict(after=-1, mode="RESET")],
    [dict(after=7, mode="RESET")], [dict(after=2, mode="UNKNOWN")],
    [dict(after=2, mode=1)], [dict(after=2, mode="RESET", accepted=True)],
    [dict(after=2)], [dict(after=2, mode="RESET"), dict(after=2, mode="RESET")],
    [dict(after=4, mode="RESET"), dict(after=2, mode="RESET")],
    [dict(after=i, mode="RETAINED") for i in range(33)],
])
def test_schedule_validation(schedule):
    with pytest.raises(RetainedCorrectionDynamicsError):
        run(**scheduled_inputs(gap_schedule=schedule))


@pytest.mark.parametrize("changes", [dict(gap_after=2), dict(mode="RESET")])
def test_schedule_cannot_silently_override_legacy_controls(changes):
    with pytest.raises(RetainedCorrectionDynamicsError):
        run(**scheduled_inputs(**changes))


def test_multiple_gaps_do_not_mutate_caller_inputs():
    original = scheduled_inputs()
    before = deepcopy(original)
    experiment = run(**original)
    saved = deepcopy(experiment)
    analyze(experiment, original_inputs=original)
    assert original == before and experiment == saved


def test_gap_schedule_and_hidden_metrics_cannot_be_rehashed_into_valid_receipts():
    original, experiment, audit = scheduled_analysis()
    forged = deepcopy(experiment)
    forged["gaps"][0]["after"][0] += 1
    forged["receipt_hash"] = stable_hash({k: v for k, v in forged.items() if k != "receipt_hash"})
    with pytest.raises(RetainedCorrectionDynamicsError):
        verify(forged, **original)
    for key, value in (("metric_positive_definite", False), ("total_gap_progress_loss", 1),
                       ("accepted", 0), ("foreign", True)):
        altered = deepcopy(audit)
        altered[key] = value
        altered["receipt_hash"] = stable_hash({k: v for k, v in altered.items() if k != "receipt_hash"})
        with pytest.raises(RetainedCorrectionDynamicsError):
            verify_analysis(altered, experiment, original_inputs=original)
    changed = deepcopy(original)
    changed["gap_schedule"][0]["mode"] = "RESET"
    with pytest.raises(RetainedCorrectionDynamicsError):
        verify(experiment, **changed)


def test_legacy_receipt_identity_is_preserved():
    assert run(**inputs())["receipt_hash"] == "5d25ba104549489430f8401399c5a3c07e0d7833fa04fa703f2e4e41dd5ae56b"
    assert analyze(run(**inputs()), original_inputs=inputs())["receipt_hash"] == "20ec51d131d4c2cef6a462f9ce65c116dde1f43338d7f621f9265ceb03d1340a"



def test_tiny_hidden_energy_uses_exact_flags_when_display_underflows():
    _, _, audit = scheduled_analysis(initial=[0, 0], observations=[[0, 1e-200]] * 6,
                                     projection=[True, False])
    assert all(r["hidden_energy_after"] == 0 for r in audit["steps"])
    assert all(r["hidden_error_remains"] for r in audit["steps"])
    assert all(r["energy_decomposition_held"] for r in audit["steps"])
    assert all(r["contraction_ratio"] == 1 for r in audit["steps"])


def test_maximum_schedule_replays_every_boundary():
    original, experiment, audit = scheduled_analysis(observations=[[8]] * 32,
        gap_schedule=[dict(after=i, mode="RECONSTRUCTED") for i in range(32)])
    assert len(experiment["gaps"]) == 32
    assert experiment["final_model"] == [8 * (1 - .5 ** 32)]
    assert audit["all_prefix_bounds_held"]
    assert all(g["nonincreasing"] for g in audit["gaps"])
    assert verify(experiment, **original)


def test_moving_target_gap_uses_same_declared_target_on_both_sides():
    _, experiment, audit = scheduled_analysis(observations=[[8], [8], [-8], [-8]],
        gap_schedule=[dict(after=2, mode="RESET")])
    assert audit["fixed_target"] is False
    # Reset from +6 to 0 moves closer to the next observation -8.
    assert audit["gaps"][0]["energy_before"] == 196
    assert audit["gaps"][0]["energy_after"] == 64
    assert audit["gaps"][0]["energy_change"] == -132
    assert audit["total_gap_progress_loss"] == 0
    assert experiment["gaps"][0]["recovery_jump"] == [-6]


def test_schedule_with_clipping_and_denied_gates_keeps_hidden_residuals():
    _, experiment, audit = scheduled_analysis(initial=[0, 0], observations=[[8, 3]] * 6,
        projection=[True, False], clip=1, gates=[False, True] * 3,
        gap_schedule=[dict(after=2, mode="RESET"), dict(after=4, mode="RECONSTRUCTED")])
    assert experiment["final_model"] == [1, 0]
    assert audit["permitted_step_count"] == 3
    assert all(r["hidden_error_remains"] for r in audit["steps"])
    assert all(r["descent_inequality_held"] is None for r in audit["steps"] if not r["gate"])
    assert audit["all_prefix_bounds_held"]


def test_hidden_step_and_gap_metrics_are_bound_to_external_controls():
    original, experiment, audit = scheduled_analysis()
    for field, value in (("hidden_energy_after", 10), ("contraction_ratio", 1)):
        altered = deepcopy(audit)
        altered["steps"][0][field] = value
        altered["receipt_hash"] = stable_hash({k: v for k, v in altered.items() if k != "receipt_hash"})
        with pytest.raises(RetainedCorrectionDynamicsError):
            verify_analysis(altered, experiment, original_inputs=original)
    with pytest.raises(RetainedCorrectionDynamicsError):
        verify_analysis(audit, experiment, original_inputs=original, movement_budget=100)


def test_scheduled_replay_and_cli_in_fresh_process(tmp_path):
    import json
    original, experiment, audit = scheduled_analysis(gap_schedule=[
        dict(after=2, mode="RESET"), dict(after=4, mode="RECONSTRUCTED")])
    packet = tmp_path / "scheduled.json"
    packet.write_bytes(canonical_bytes(dict(original=original, experiment=experiment, audit=audit)))
    script = (
        "import json,sys; from holosim.retained_correction_dynamics import "
        "verify_retained_correction_experiment,verify_correction_descent_bounds; "
        "p=json.load(open(sys.argv[1])); "
        "assert verify_retained_correction_experiment(p['experiment'],**p['original']); "
        "assert verify_correction_descent_bounds(p['audit'],p['experiment'],original_inputs=p['original'])"
    )
    subprocess.run([sys.executable, "-c", script, str(packet)], check=True)
    result = subprocess.run([sys.executable, "-m", "holosim.retained_correction_dynamics", "--multi-gap"],
                            check=True, capture_output=True, text=True)
    cases = json.loads(result.stdout)
    assert cases["RESET"]["total_gap_progress_loss"] == 120
    assert cases["HIDDEN_ERROR"]["hidden_energy_after"] == [9] * 6



def test_improving_gap_does_not_cancel_positive_reset_loss():
    _, _, audit = scheduled_analysis(observations=[[8]] * 4 + [[-8]] * 2,
        gap_schedule=[dict(after=2, mode="RESET"), dict(after=4, mode="RESET")])
    assert [g["energy_change"] for g in audit["gaps"]] == [60, -132]
    assert audit["gap_energy_change"] == -72
    assert audit["total_gap_progress_loss"] == 60
    assert audit["gap_nonincreasing"] is False

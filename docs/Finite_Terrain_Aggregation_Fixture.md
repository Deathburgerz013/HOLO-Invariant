| | }==============================================================|
| | █†█ Holo/Sim █†█ FINITE_TERRAIN_AGGREGATION_FIXTURE █†█     |
| | }==============================================================|
| | DOCUMENT_TYPE: FINITE_EXPLORATORY_TEST_FIXTURE               |
| | STATUS: EXACT_ARITHMETIC_CHECKED                             |
| | AUTHORITY: DESCRIPTIVE_ONLY                                  |
| | WRITE_AUTHORITY: NONE                                        |
| | ACCEPTED: false                                              |
| | PERSISTENCE_AUTHORITY: NONE                                  |
| | }==============================================================|
| | PURPOSE                                                      |
| | Provide finite, reproducible counterexamples showing that:   |
| | • improvement inside every declared layer need not imply    |
| |   improvement after pooled aggregation                      |
| | • equal endpoint summaries need not preserve equal evidence |
| |   or loss histories                                         |
| | • a favorable average cannot override a local hazard failure|
| |                                                              |
| | This fixture does not model all terrain or prove a universal |
| | law about averages.                                         |
| | }==============================================================|
| | FIXTURE_A_IDENTITIES                                         |
| | FIXTURE_ID: finite:aggregation-reversal:v1                  |
| | SUBJECT: comparison of candidate and baseline observations  |
| | BOUNDARY: exactly the counts declared below                 |
| | ORDER: one bounded comparison window                        |
| | SCHEMA: binary outcome grouped by easy and hard layer       |
| | OUTCOME: success or non-success                             |
| | LAYERS: easy • hard                                         |
| | ARMS: candidate • baseline                                  |
| | }==============================================================|
| | FIXTURE_A_EXACT_COUNTS                                       |
| |                                                              |
| | EASY_LAYER:                                                  |
| | candidate_success = 81                                      |
| | candidate_total = 87                                        |
| | baseline_success = 234                                      |
| | baseline_total = 270                                        |
| |                                                              |
| | HARD_LAYER:                                                  |
| | candidate_success = 192                                     |
| | candidate_total = 263                                       |
| | baseline_success = 55                                       |
| | baseline_total = 80                                         |
| |                                                              |
| | POOLED_TOTALS:                                               |
| | candidate_success = 81 + 192 = 273                          |
| | candidate_total = 87 + 263 = 350                            |
| | baseline_success = 234 + 55 = 289                           |
| | baseline_total = 270 + 80 = 350                             |
| | }==============================================================|
| | FIXTURE_A_EXACT_LAYER_RATES                                  |
| |                                                              |
| | easy_candidate = 81 / 87 = 27 / 29                          |
| | easy_candidate_decimal = 0.931034483...                     |
| |                                                              |
| | easy_baseline = 234 / 270 = 13 / 15                         |
| | easy_baseline_decimal = 0.866666667...                      |
| |                                                              |
| | easy_delta = 27/29 - 13/15 = 28/435                        |
| | easy_delta_decimal = +0.064367816...                        |
| |                                                              |
| | hard_candidate = 192 / 263                                  |
| | hard_candidate_decimal = 0.730038023...                     |
| |                                                              |
| | hard_baseline = 55 / 80 = 11 / 16                           |
| | hard_baseline_decimal = 0.687500000                         |
| |                                                              |
| | hard_delta = 192/263 - 11/16 = 179/4208                   |
| | hard_delta_decimal = +0.042538023...                        |
| | }==============================================================|
| | FIXTURE_A_WITHIN_LAYER_RESULT                                |
| | candidate performs better than baseline in the easy layer.   |
| | candidate performs better than baseline in the hard layer.   |
| |                                                              |
| | Both comparisons are exact consequences of the supplied      |
| | finite counts.                                              |
| | }==============================================================|
| | FIXTURE_A_POOLED_RATES                                       |
| |                                                              |
| | pooled_candidate = 273 / 350 = 39 / 50                     |
| | pooled_candidate_decimal = 0.780000000                      |
| |                                                              |
| | pooled_baseline = 289 / 350                                 |
| | pooled_baseline_decimal = 0.825714286...                    |
| |                                                              |
| | pooled_delta = 39/50 - 289/350 = -8/175                   |
| | pooled_delta_decimal = -0.045714286...                      |
| | }==============================================================|
| | FIXTURE_A_REVERSAL                                           |
| | Within both declared layers: candidate > baseline.           |
| | After pooled aggregation: candidate < baseline.              |
| |                                                              |
| | The aggregate direction reverses because the arm weights     |
| | across easy and hard layers differ.                         |
| |                                                              |
| | candidate_hard_weight = 263 / 350 = 0.751428571...         |
| | baseline_hard_weight = 80 / 350 = 0.228571429...           |
| |                                                              |
| | The candidate arm contains a much larger hard-layer share.   |
| | }==============================================================|
| | FIXTURE_A_TWO_AVERAGE_OPERATORS                              |
| |                                                              |
| | UNWEIGHTED_LAYER_MEAN:                                       |
| | A_u(candidate) = (27/29 + 192/263) / 2                     |
| | A_u(candidate) = 12669/15254 = 0.830536253...              |
| |                                                              |
| | A_u(baseline) = (13/15 + 11/16) / 2                        |
| | A_u(baseline) = 373/480 = 0.777083333...                   |
| |                                                              |
| | POOLED_OBSERVATION_MEAN:                                     |
| | A_p(candidate) = 273/350 = 0.780000000                     |
| | A_p(baseline) = 289/350 = 0.825714286...                   |
| |                                                              |
| | A_u says candidate is higher.                               |
| | A_p says baseline is higher.                                |
| |                                                              |
| | These operators answer different weighted questions.         |
| | Neither may be called the average without its contract.      |
| | }==============================================================|
| | FIXTURE_A_SCALE_RECORDS                                      |
| |                                                              |
| | FINE_SCALE_R:                                                |
| | Each observation retains arm, layer, and outcome.            |
| |                                                              |
| | LAYER_SCALE_S:                                               |
| | Each arm retains success and total counts per layer.         |
| |                                                              |
| | POOLED_SCALE_T:                                              |
| | Each arm retains only pooled success and total counts.       |
| | }==============================================================|
| | FIXTURE_A_TWO_PATHS                                          |
| |                                                              |
| | TWO_STEP_PATH: r -> s -> t                                  |
| | r -> s groups observations by arm and layer.                |
| | s -> t sums layer counts into pooled totals.                |
| |                                                              |
| | DIRECT_PATH: r -> t                                         |
| | r -> t sums observations directly into pooled totals.       |
| |                                                              |
| | Both paths produce the same pooled endpoint counts:          |
| | candidate = 273 / 350                                      |
| | baseline = 289 / 350                                       |
| | }==============================================================|
| | FIXTURE_A_LEDGER_MISMATCH                                    |
| | Endpoint equality does not imply ledger equality.            |
| |                                                              |
| | TWO_STEP_LEDGER_RETAINS:                                     |
| | • easy and hard identities                                  |
| | • four layer-specific count pairs                           |
| | • within-layer rates and directions                         |
| | • changed layer weights                                     |
| | • the exact point where strata were pooled                  |
| |                                                              |
| | DIRECT_ENDPOINT_ONLY_LEDGER_LOSES:                           |
| | • layer identities                                          |
| | • layer-specific counts                                     |
| | • conditional directions                                    |
| | • evidence of the reversal mechanism                        |
| |                                                              |
| | A valid direct map from r must record those losses explicitly|
| | even when it does not retain the strata in X_t.              |
| | }==============================================================|
| | FIXTURE_A_RECONSTRUCTION                                     |
| | From pooled endpoint counts alone, the original four layer   |
| | tables cannot be uniquely reconstructed.                    |
| |                                                              |
| | Many different layer allocations sum to the same totals.     |
| | Therefore reconstruction_from_endpoint = false.              |
| |                                                              |
| | Reconstruction may be possible only when the loss ledger or  |
| | bound raw evidence preserves the strata.                    |
| | }==============================================================|
| | FIXTURE_B_IDENTITIES                                         |
| | FIXTURE_ID: finite:rare-hazard-average:v1                   |
| | SUBJECT: one bounded set of terrain observations            |
| | SCHEMA: severity per observation                            |
| | OBSERVATION_COUNT: 1000                                     |
| | }==============================================================|
| | FIXTURE_B_EXACT_VALUES                                       |
| | 999 observations have severity 0.                           |
| | 1 observation has severity 1000.                            |
| |                                                              |
| | total_severity = 1000                                       |
| | mean_severity = 1000 / 1000 = 1                            |
| | maximum_severity = 1000                                     |
| | hazard_count = 1                                            |
| | hazard_rate = 1 / 1000 = 0.001                            |
| | }==============================================================|
| | FIXTURE_B_DECLARED_CHECKS                                    |
| | mean_threshold = 1                                           |
| | maximum_severity_invariant = 100                             |
| |                                                              |
| | mean_check:                                                  |
| | mean_severity <= mean_threshold                             |
| | 1 <= 1 -> PASS                                              |
| |                                                              |
| | local_hazard_check:                                          |
| | maximum_severity <= maximum_severity_invariant              |
| | 1000 <= 100 -> FAIL                                         |
| | }==============================================================|
| | FIXTURE_B_RESULT                                             |
| | The favorable mean check does not override the demonstrated  |
| | local hazard violation.                                     |
| |                                                              |
| | Required retained fields include:                            |
| | • count                                                     |
| | • mean                                                      |
| | • maximum                                                   |
| | • hazard count                                              |
| | • hazard rate                                               |
| | • violating evidence identity                               |
| |                                                              |
| | A summary containing only mean_severity = 1 is insufficient. |
| | }==============================================================|
| | MACHINE_CHECKABLE_ASSERTIONS                                 |
| |                                                              |
| | ASSERT 81/87 > 234/270                                      |
| | ASSERT 192/263 > 55/80                                     |
| | ASSERT 273/350 < 289/350                                   |
| | ASSERT (27/29 + 192/263)/2 > (13/15 + 11/16)/2            |
| | ASSERT max([0 repeated 999 times] + [1000]) = 1000         |
| | ASSERT mean([0 repeated 999 times] + [1000]) = 1           |
| | ASSERT 1 <= 1                                               |
| | ASSERT 1000 > 100                                           |
| | }==============================================================|
| | INVARIANT_VISIBILITY_RULE                                    |
| | Aggregation may summarize observations.                      |
| | It may not change a failed required invariant into a pass.   |
| |                                                              |
| | Local failures, missing strata, hazards, and uncertainty must|
| | remain visible beside any aggregate.                        |
| | }==============================================================|
| | AVERAGE_ON_AVERAGE_RESULT                                    |
| | Average on average is not one operator.                      |
| |                                                              |
| | At minimum it may mean:                                      |
| | • unweighted mean of layer means                            |
| | • count-weighted mean of layer means                        |
| | • pooled mean over observations                             |
| | • temporal mean of window means                             |
| |                                                              |
| | Each requires declared population, weights, strata, windows, |
| | missing-data behavior, and preserved invariant checks.       |
| | }==============================================================|
| | VERIFIED_WITHIN_FIXTURE                                      |
| | The exact fractions and inequalities above were recalculated |
| | from the finite supplied counts.                            |
| |                                                              |
| | This verifies the arithmetic of these fixtures only.         |
| | It does not verify an empirical terrain claim or universal   |
| | aggregation law.                                            |
| | }==============================================================|
| | FALSIFIERS                                                   |
| | • any declared count fails to reproduce its stated fraction|
| | • either within-layer candidate rate is not higher          |
| | • the pooled candidate rate is not lower                    |
| | • pooled endpoints uniquely reconstruct the layer table     |
| | • the hazard maximum does not exceed its invariant          |
| | • an aggregate report preserves all required information    |
| |   while contradicting the stated loss ledger                |
| | }==============================================================|
| | PROPOSED_NEXT_ACTION                                         |
| | Keep this fixture untracked and uncommitted.                 |
| |                                                              |
| | Convert the machine-checkable assertions into an isolated    |
| | executable test only after the fixture's meanings, arithmetic,|
| | and authority boundary are reviewed.                        |
| | }==============================================================|
| | NON_CLAIMS                                                   |
| | • The counts are not observations from a claimed real event.|
| | • The fixture does not prove every aggregate can reverse.   |
| | • Simpson reversal is not a contradiction in raw data.      |
| | • Mean behavior is not declared useless.                    |
| | • No terrain invariant is inferred from one fixture.        |
| | • This fixture grants no acceptance or write authority.     |
| | }==============================================================|
| | END_FINITE_TERRAIN_AGGREGATION_FIXTURE                       |
| | }==============================================================|
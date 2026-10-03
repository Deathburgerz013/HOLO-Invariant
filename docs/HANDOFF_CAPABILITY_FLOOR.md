# Handoff capability floor

PARTIAL research extension of `cross_model_correction_handoff.py`. The first
pilot and its raw evidence remain unchanged. This is a prospective fixed floor,
not a repaired result or a demonstration of model handoff.

The committed fixture freezes five isolated cases before any new calls:
schema echo, exact ordered ID copy, and each of the three strictly-greater-than-2
sums separately. Expected sums are 3, 4, and 0. No history, producer summary,
correction selection, or stale-plan flag is included in these prompts.

Each requested model receives every case twice. Options are fixed at 512 output
tokens, 8192 context, seed 0, temperature 0, and requested CPU execution. Timeout
is 300 seconds per request, no retries. Twenty generation requests total;
model and case order reverse in repeat two. Repeats are not independent samples.
Transport/format errors count as failed attempts. Exact JSON types and fields
are required; extra fields, prefixes in IDs, and booleans as integers fail.

`eligible_for_this_fixture` requires every case in both repeats to pass. This
is a descriptive prerequisite for a later experiment, not an authorization
or a runtime gate. The floor command runs no handoff, even for eligible models.
A model failing this floor remains in the report with `floor_failure`; it is
not silently excluded. Size and quantization differences must still be considered
in a later comparison. No ranking is produced.

Run after reviewing and freezing this patch:

```powershell
python -m holosim.cross_model_correction_handoff --capability-floor --sender-model "qwen2.5-coder:7b-instruct-q3_K_S" --receiver-model "llama3.2:1b" --output "D:\handoff-capability-floor-run.json"
```

Budget overrides are refused in this mode. Existing output files are refused.
The result retains exact fixture bytes and SHA256, canonical fixture identity,
raw request/response captures, parsed outputs, errors, timings, declared model
inventory, source hashes, case scores, and fixed budgets. Responses exceeding
the transport cap retain the bounded prefix as an error, not complete evidence.
The result hash binds its body; it does not authenticate the run. No live run
has been made as part of this source patch.

Server-reported weight digests and requested CPU settings are not independent
runtime witnesses. Fresh requests do not prove fresh processes. A correct
output does not establish understanding, truth, currentness, or permission.
`accepted=false`, `truth_claimed=false`, and write/execution authority `NONE`.
This change does not implement a stale-action refusal or signed external witness.

Scripted tests check scoring, fixed scheduling, transport retention, invalid
inputs, failed attempts, CLI mode/budget refusal, and compatibility with the
existing pilot. They are software checks, not empirical model results.

## Retained first floor run

The original `benchmarks/cross-model-correction-handoff-runs/handoff-capability-floor-run.json`
is retained byte-for-byte. Its SHA256 is
`aa2887da86176088d610b9438ca9c97ca720058b165128c92aaecf7b7e49ef3d`.
The run used the frozen floor fixture. Both repeats produced the same listed
outputs, all with normal `stop` completion and no recorded request errors.

| Case | Expected | Qwen 7B Q3 | Llama 3.2 1B |
| --- | --- | --- | --- |
| Schema echo | Exact object | 2/2 pass | 2/2 pass |
| Ordered ID copy | Both exact IDs | 2/2 pass | 0/2; only `{"id":"rule-current"}` |
| Arithmetic 1 | 3 | 3, twice | 5, twice |
| Arithmetic 2 | 4 | 6, twice | 5, twice |
| Arithmetic 3 | 0 | 2, twice | 1, twice |

Qwen passed 6/10 calls and Llama 2/10. Neither is eligible for this fixture.
These counts describe retained attempts, not independent success rates or a
ranking. Basic task failure remains a confounder for a later handoff comparison.
No diagnosis of model internals, quantization causality, or general capability
follows from these outputs. No additional handoff calls were made.

The existing module now supports an offline complete-capture audit:

```powershell
python -m holosim.cross_model_correction_handoff --audit-floor-run benchmarks/cross-model-correction-handoff-runs/handoff-capability-floor-run.json --output "D:\handoff-capability-floor-analysis.json"
```

It binds the result hash, captured fixture, fixed budgets, declared inventory,
20-request order, prompt/request bytes, response/output bytes, exact scores,
summary and authority flags. It emits companion analysis with the raw source
SHA256 and does not rewrite evidence. Missing, incomplete, or error-bearing
captures are refused by this bounded audit rather than treated as successful
checks. The live floor can still record errors; this auditor does not yet
validate those error-bearing reports. It does not authenticate Ollama emission,
measure CPU execution or freshness, or verify historical source/timing metadata.
Replacing a whole consistent report and recomputing hashes is outside protection.
The saved report is not modified to match the newer auditor source version.

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

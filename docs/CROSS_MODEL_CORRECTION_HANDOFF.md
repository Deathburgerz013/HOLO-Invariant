# Cross-model and fresh-session correction handoff

Classification: **PARTIAL research harness; no model result is established by
the scripted tests.** Run from a repository checkout. The fixture is in
`benchmarks/cross-model-correction-handoff.fixture.json`; this is not a new
production handoff API or a wheel-distributed benchmark resource.

## Question

Can a fresh request reconstruct a declared correction, preserve its earlier
record, and complete the revised task? Does formatting the same complete
history as a correction packet change that outcome?

Two cases are reported separately:

- Same requested model, fresh request without transferred conversational state.
- Different requested model with a different server-declared weight digest,
  also a fresh request without transferred conversational state.

These are fresh conversational requests, not fresh server processes or proof
of erased internal state. Resident weights and server caches may remain.
Inventory digests are server declarations, not authenticated model identities.
Different quantizations of one model can have different digests; disclose the
actual pair before interpreting it as a comparison between model families.

## Shared conditions

One authored fixture changes the integer-sum threshold from strictly greater
than zero to strictly greater than two. It includes an old rule, a declared
valid correction, requirement evidence, three task inputs, and a stale plan.
The oracle computes sums from the declared corrected threshold; it never asks
the model to judge its own success. Expected answers are not supplied in the
receiver prompt.

A producer model summarizes the session once. Its exact output is retained
and supplied unchanged in both conditions, including an incorrect summary.
Transport or summary-schema failure aborts receiver trials rather than
inventing producer output. This measures reconstruction of an authored
requirement, not discovery of a correction or knowledge learned by the producer.

The harness creates a disposable real HoloChain with an original, correction,
and revalidation, then uses the existing verified topology projection.
Original chain bytes and decoded nodes are retained in the report.

Both receiver conditions carry the full fixture, producer output, every
record, every hash, and every relation. Notes use readable JSONL records plus
a relations list. Packet uses structured records and relations. No baseline
history is discarded, no context truncation is requested, and neither side is
restricted to only the latest value. Prompt lengths can differ and are retained.
This is a **format comparison**, not a comparison of storage systems or a
production HOLO gate against an unguarded model.

Each case and condition receives the same maximum context/output tokens,
temperature, seed, timeout, and number of calls. Conditions and case order
alternate across repeats. Defaults: two repeats, 512 output tokens, 8192
context tokens, temperature zero, seed zero, 120 seconds per generation,
CPU-only through the existing adapter, no retries. The shared producer is one
additional call, not charged to only one condition. Two repeats produce eight
receiver calls. Prompt cap: 49,152 UTF-8 bytes; response cap: 262,144 bytes.
Smaller budgets may cause server truncation; raw token counts and stop reasons
must be inspected before claiming the complete prompt was consumed.

## Run actual models

Use two already installed local Ollama model names exactly as listed by
`ollama list`. No model download, cloud call, or arbitrary code execution is
performed. A local `/api/tags` check retains the inventory and refuses missing,
ambiguous, or identically declared weight digests.

```powershell
python -m holosim.cross_model_correction_handoff --sender-model MODEL_A --receiver-model MODEL_B --output "D:\cross-model-handoff-run.json"
```

Replace the two placeholders with installed names. Optional flags:
`--repeats`, `--timeout-seconds`, `--num-predict`, `--num-ctx`.
An existing output file is refused; use a new filename for another run.

The report preserves prompts, raw HTTP request and response bodies as base64,
parsed proposals, server inventory, requested options, elapsed time, source
hashes, fixture bytes, chain bytes, and per-trial scores. Raw envelopes retain
server-reported model names, token counts and timing where supplied. For an
oversized response, only the capped prefix is retained with an explicit error. Model
errors and malformed answers remain failures, not dropped trials. A producer
failure has zero receiver attempts, not vacuous completion.

Scores cover task correctness, current rule recall, retained original and
correction IDs, explicit lineage, declared blocking of the stale plan, and
superseded-rule resurrection. Saying `stale_plan_blocked=true` is an output
check; it is not enforcement of an action gate. The model never executes the
plan. The report prints separate notes/packet summaries for each case and
always leaves ranking null. A tie is a valid result; no reference failure is
manufactured.

## Test the harness

```powershell
python -m pytest -q tests/test_cross_model_correction_handoff.py tests/test_local_ollama_adapter.py
```

These tests use a scripted HTTP transport. They verify equal requested
budgets, no transferred context, preserved data, scoring, malformed/failed
responses, and refusal of identical declared weights. Passing them says
nothing about real models. Actual responses must be retained and inspected
before publishing empirical results. Temperature-zero repeats are not
independent statistical samples, and timing depends on load/cache/order.

No universal cross-model equivalence, superiority, authenticated execution,
production currentness, truth, or permission is established. Hashes identify
the retained report and source, not an independent run witness. All evaluator
reports retain accepted=false, truth_claimed=false, and write/execution
authority NONE. Model prose remains an unaccepted proposal, including prose
that asserts authority. The retained local pilot and its exploratory controls are described below.


## Retained local pilot, 2026-10-03 UTC

Raw files in `benchmarks/cross-model-correction-handoff-runs/` are retained
byte-for-byte. The sender was `qwen2.5-coder:7b-instruct-q3_K_S`; the distinct
receiver was `llama3.2:1b`. There were two repeats per condition, CPU generation,
512 output tokens, 8192 context tokens, seed 0, temperature 0 and a requested
300-second timeout per call. These are local, unauthenticated records.

| Condition | Qwen complete passes | Llama complete passes |
| --- | --- | --- |
| Handoff, notes | 0/2 | 0/2 |
| Handoff, packet | 0/2 | 0/2 |
| Direct arithmetic control | 0/2 | 0/2 |
| Prose rule-selection control | 0/2 | 0/2 |
| Explicit JSON ID control | 2/2 | 0/2 |

Correct arithmetic is `[3, 4, 0]`. In all four handoff receiver calls Qwen
named the current rule and reported the stale plan blocked, but returned
`[6, 8, 2]` and retained only the original ID. Llama's notes responses included
one schema failure and one incomplete JSON response stopped at the token cap.
Its packet responses returned `[1, 2, 3]`, empty retained IDs and no reported
block. The sender summary correctly described the threshold change; the
harness does not score prose as evidence of execution or independent discovery.

After observing those failures, three exploratory controls were run. Direct
arithmetic failed for both models, so the handoff failures cannot be attributed
solely to transfer. The prose control used the phrase "record rule-current";
Qwen copied that prefix into its IDs. A later control changed both wording and
structure to explicit JSON ID fields. Qwen then passed twice; Llama selected
the correction but still reported no stale-plan block, and one response added
a wrapper. This does not isolate JSON as the cause or establish a packet
advantage. No selective retries replace failed evidence.

Reproduce the scores without contacting Ollama:

```powershell
python -m holosim.cross_model_correction_handoff --audit-runs benchmarks/cross-model-correction-handoff-runs --output D:\handoff-analysis.json
```

The analysis hashes every source file, checks the handoff result hash and
fixture, checks saved request/prompt and raw response/output bindings, and
recomputes scores. It is a consistency audit of supplied records, not an
execution witness or a validation of every report field. It does not establish
currentness, model authentication, a production gate, or superiority. The
`stale_plan_blocked` field is a model answer, never an enforced refusal.

### Raw evidence SHA-256

- `cross-model-handoff-run.json`: `5c934a503793b578026ff754c6a9337f34a5ea1127a489e51f554abfc2a00a31`
- `direct-arithmetic-control.json`: `5eff64e1261be684b44e063d26d8c29029a25fd16b04a330a082d0978c5d526d`
- `rule-selection-control.json`: `07601271f7ce60c77131f457f0c24eaea394e04569853f4acecca9c624060f70`
- `explicit-id-control.json`: `83c1fa1befcea512bd760da8cf46e6275a01a0814d937cddb5ceaf392b62cd72`

# Cross-software correction benchmark — PARTIAL pilot

This pilot asks whether changing the retained store changes a fixed software
correction cycle. It runs actual Python calculations, SQLite SELECT statements,
and service-configuration checks. These are small authored fixtures, not a
sample of production repositories or a benchmark of all software.

## Run

```powershell
python -m pytest -q tests/test_cross_software_correction_benchmark.py
python -m holosim.cross_software_correction_benchmark
```

The command makes disposable temporary directories and removes them afterward.
It does not use the production chain, an Ollama model, network services, or any
installed project workspace. Run stdout can be saved as a JSON report:

```powershell
python -m holosim.cross_software_correction_benchmark > cross-software-result.json
```

## Shared experiment

| Job | First requirement | Changed requirement | Executed check |
| --- | --- | --- | --- |
| Python repair | Sum values greater than 0 | Sum values greater than 2 | Generated fixed Python function executed by a child interpreter on five input lists |
| SQLite report | Sum paid amounts greater than 0 | Sum paid amounts greater than 2 | Fixed SELECT against a fresh in-memory database, compared with an independent Python calculation |
| Service configuration | Local host, no telemetry, two workers | Same boundaries, four workers | Parse generated JSON and compare every declared field |

Each job has two candidates: an append-only JSONL notes adapter and the existing
`HoloChain` with compression enabled. Both use identical proposals, requirement
hashes, checks, and fixture-owned approval maps. The only treatment is storage.
The notes adapter does not overwrite; this is deliberately a durable baseline,
not an artificially forgetful one. Compression is enabled but the core only
uses it when the hex representation is smaller; these small events may remain
plain. This pilot does not claim a compression benefit.

Each epoch receives exactly five proposals in the same order: malformed, wrong
but approved, correct but unapproved, stale but approved, and correct/approved.
Approval binds the entire proposal hash. A changed proposal cannot inherit that
grant. These are explicit experimental grants held outside the candidate store;
they are NOT external human approval, authenticated identity, or a correction to
HOLO's production authorization paths.

The gate checks schema, current requirement, grant, then functional behavior.
Only a passing proposal writes `applied.txt` inside the disposable task root.
Both adapters record all attempts, including refusals. After the first epoch the
worker exits. A new Python interpreter reads the stored history, reruns the prior
successful artifact against its original requirement, and handles the changed
requirement. History objects and original file-byte prefixes are checked.
Keeping earlier success means preserving its old result, not claiming the old
artifact still meets a changed requirement.

## Measurements and limits

Reports include tasks completed, wrong/malformed/stale/unapproved proposals
blocked, attempts, recovered earlier success, preserved history, elapsed wall
time including worker startup, and final history-file bytes. Storage bytes
exclude lock files and task artifacts. The per-epoch attempt budget is five;
worker timeout is 30 seconds and each Python program timeout is five seconds.
Timeouts or worker errors abort the run rather than inventing a score.

Human intervention during this scripted run is zero. Fixture authoring and
review are not measured. Model cost is null because no model is invoked. Wall
time is a single noisy observation, not a repeated performance estimate or a
hard total CPU/memory limit. The subprocess is not an OS sandbox. Only the
fixed harness-authored artifact strings may be executed; there is no user/model
submission API.

A separate probe changes content in a COPY of the history without recomputing
hashes. It tests read-time detection of that specific modification. It does not
test signing, authenticated approvals, wholesale rehashing, file deletion,
rollback, metadata integrity, or protection from another process with write
access. The original store is checked unchanged after the probe. Expected integrity
error messages on stderr come from those deliberately altered copies.

With the fixed schedule both candidates should complete both epochs and block
all four bad proposal types. That outcome belongs to their shared validator;
it is not a causal benefit of HOLO storage. HOLO's hash verification should
reject the unrehashed content edit, while JSONL parsing alone should not. No
ranking is emitted. Source hashes bind the benchmark, core, replay, and canonical module bytes.
A result hash identifies report bytes, including timings;
it neither authenticates the run nor substitutes for rerunning it.

Receipts remain `accepted=false`, `truth_claimed=false`, with write and execution
authority `NONE`. The temporary harness writes are task implementation, not a
grant of production authority.

## Research expansion

Add independent task fixtures and regression suites before generalizing. Later
comparisons can vary the proposer/model while holding tools, budgets, starting
state, and scoring fixed. Add interactive apps, automation, and AI-assistant
jobs when their real task outcomes and side effects can be measured. This pilot
does not claim those categories are covered.

Method references: [SWE-bench evaluation](https://www.swebench.com/SWE-bench/guides/evaluation/)
uses executable repository tests for repair outcomes;
[SQLite testing](https://www.sqlite.org/testing.html) illustrates regression and
cross-engine result checks. This pilot does not implement either benchmark or
claim equivalent coverage.

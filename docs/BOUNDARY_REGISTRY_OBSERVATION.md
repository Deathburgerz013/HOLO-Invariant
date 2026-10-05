# Boundary registry observation

Author: Canyon Brock Haney. Implementation contributor: GPT.

This read-only report extends `holosim.guarantee_registry`; it does not create
another registration or acceptance path. The committed register remains
`core/verified_boundary_register.json`.

Every structurally discovered receipt boundary gets a listing. An
`UNREGISTERED` listing is a placeholder with a null boundary ID and test path;
those fields are not inferred from filenames. Registered test sources are also
observed. The existing discovery convention does not cover all Python checks,
shell tools, OS experiments, or all repository files.

Three independent markings are retained:

| Dimension | Meaning |
| --- | --- |
| Registration | Existing `REGISTERED`, `UNREGISTERED`, or `STALE` contract status |
| Change | `UNCHANGED`, `EDITED`, `UNKNOWN`, or `MISSING`, with comparison basis and hash |
| Duplication | Exact raw-byte peers, no raw-byte peer in this observed set, or unavailable |

Without a supplied baseline, registered implementation/test text hashes are
the comparison basis. That existing identity normalizes LF/CRLF. Unregistered
sources have unknown change status. With a supplied path-to-raw-SHA256 map,
change is measured against those raw hashes; a new path remains unknown.
Prior baseline paths are retained in the artifact listing even after removal;
they become `MISSING` without inventing a currently discovered boundary.
Consequently, a line-ending-only change can be unchanged under registered text
identity but edited under a raw baseline. Duplicate comparison always uses raw
bytes. It does not establish equivalent behavior or select a canonical copy.

Example, from the repository root:

```python
from holosim.guarantee_registry import (
    load_boundary_register,
    observe_boundary_register,
    verify_boundary_register_observation,
)

register = load_boundary_register("core/verified_boundary_register.json")
report = observe_boundary_register(register, root=".")
assert verify_boundary_register_observation(report, register, root=".")["valid"]

# Retain the original report and its hash separately if saving this baseline.
baseline = {item["path"]: item["sha256"] for item in report["artifacts"]
            if item["sha256"] is not None}
later = observe_boundary_register(register, root=".", baseline=baseline)
assert verify_boundary_register_observation(
    later, register, root=".", baseline=baseline
)["valid"]
```

The report binds the supplied baseline and current observations. It does not
authenticate historical baselines or automatically monitor changes. Replay
reobserves sources and compares every derived field; a saved report ceases to
match changed current inputs. Keep it as historical evidence rather than
rewriting it. No source, test, or register is changed by observation or replay.

Register integrity and completeness are separate from test execution. This
report runs neither test files nor listed receipt verifiers. A registered source
can be edited while its receipt contract remains registered. Discovery may be
incomplete even when all registered source hashes match.

Validation:

```sh
python -m pytest -q tests/test_boundary_registry_observation.py tests/test_verified_boundary_register.py tests/test_guarantee_registry.py
```

Reports retain `accepted: false` and `write_authority: NONE`.

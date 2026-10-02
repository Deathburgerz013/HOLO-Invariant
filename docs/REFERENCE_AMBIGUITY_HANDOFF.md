# Reference ambiguity across a handoff — PARTIAL

Names are references, not unique identifiers. This experiment asks whether an
explicitly declared binding survives serialization and a fresh-process read
without conflating two entities that share a name. It makes no claim about
selfhood or consciousness.

```powershell
python -m pytest -q tests/test_reference_ambiguity_handoff.py
python -m holosim.reference_ambiguity_handoff
```

The default fixture declares a person, Canyon Brock Haney, and a place, Grand
Canyon, with a shared alias `Canyon`. Those aliases are experimental declarations,
not geographical assertions or authenticated identity records.

| Input | Result |
| --- | --- |
| Canyon, no context | AMBIGUOUS; two candidates; no selected entity |
| Canyon, kind person | RESOLVED to the declared person ID |
| Canyon, kind place | RESOLVED to the declared place ID |
| Canyon, kind place, explicit person ID | CONFLICT; no selected entity |
| Unknown label or unmatched context | UNAVAILABLE |

Names and context values match exactly, including case and whitespace. Context
is limited to declared `kind` and `scope`; it is not inferred from prose. An
explicit ID must still match the name and all supplied context. Registry IDs
must be unique. Multiple entities may legitimately have the same names, kind,
and scope, in which case context does not necessarily resolve ambiguity.

Contributions are explicitly bound to entity IDs and built through the existing
`bounded_contributor_attribution` evaluator. Looking up a name does not assign
contributions or create approval. Renaming an alias changes the registry hash;
keeping the same entity ID preserves its declared contribution receipt. An old
lookup can resolve differently in a new registry, so old receipts must be
checked against their original registry. No automatic alias migration exists.

The evaluator serializes a canonical JSON packet and decodes it. A test writes
that receipt and its original inputs to a temporary file, launches a new Python
process, replays verification, compares the recovered packet, and checks that
the file bytes remain unchanged. This is software serialization/replay, not
proof of observer continuity or a production checkpoint mechanism.

Verification regenerates the entire receipt from caller-supplied original
registry, requests, and contributions, comparing canonical bytes. A rehashed
alteration, substituted entity, upgraded authority, or altered registry fails
against those originals. Changing both the originals and receipt coherently is
outside this check: original inputs must be independently retained and trusted.
Hashes identify bytes; they do not authenticate contributors or the registry.

Bounds: at most 256 entities, requests, contributions, or aliases per entity;
text fields at most 256 Python characters. This is not a total memory budget.
Inputs are copied, and malformed/extra fields and unknown contributor IDs are
rejected. Empty input is not a completeness claim. All results remain
`accepted=false`, `truth_claimed=false`, with write/execution authority `NONE`.
No natural-language resolver, production authorization gate, signature policy,
real-world identity proof, or approval transfer is implemented. This experiment
measures declared bindings only and leaves production paths unchanged.

# Witnessed history recovery

Classification: **PARTIAL**. This experiment compares a captured HoloChain
snapshot with a separately retained SSH-signed commitment. It does not alter
production `resume`, sign a Spine candidate, or authorize continuation.

The commitment binds a caller-declared chain ID, entry count, and head hash,
plus a fixed version, signature namespace, and signer identity. Recovery
requires an independently supplied expected chain ID and OpenSSH allowed-signers
policy. A valid signature shows control of an allowed key over these bytes;
it does not authenticate a human, prove the observations, or grant approval.

## Run

OpenSSH `ssh-keygen` with SSH signing support must be available on PATH.
There is no new Python dependency. The focused tests generate disposable keys
and keep the witness and policy outside the chain file:

```powershell
python -m pytest -q tests/test_witnessed_history_recovery.py
```

The API is `sign_history_witness(...)` followed by
`recover_witnessed_history(...)`. Signing returns a JSON object; the caller
must retain it separately. Recovery reads the witness file and policy and
returns a bounded observational receipt. It never writes to the supplied
chain, witness, or policy. Temporary captured snapshots and signature files
are removed afterward. The signing key is not needed for recovery.

## Controls

| Presented history | Internal chain check | Witness result |
| --- | --- | --- |
| Untouched snapshot | Pass | MATCHED |
| Early payload changed and every subsequent link rehashed | Pass | REJECTED_HEAD |
| Truncated valid prefix, including zero entries | Pass | REJECTED_COUNT |
| Additional valid append with old witness | Pass | REJECTED_COUNT |
| Unrehashed content edit | Fail | REJECTED_CHAIN |
| Missing or malformed witness | Not relied upon | REJECTED_WITNESS |
| Unknown signer or unavailable signature tool | Not relied upon | REJECTED_SIGNATURE |
| Different declared chain ID | Not relied upon | REJECTED_CHAIN_ID |

Recovery compares **exact snapshots**, not extension proofs. A longer valid
chain requires a new retained commitment. An existing empty file can be
committed with count zero and the all-zero genesis head. A missing chain is
rejected even for a zero-entry witness. Matching an old valid witness does
not establish that the presented snapshot is the latest one.

Chain reads capture at most 4,194,304 bytes and 4,096 entries, then verify that
captured copy using HoloChain. Witness input is capped at 16,384 bytes. Index
and hashed-field types are checked before verification; signature operations
have a 15-second subprocess timeout. These are research input limits, not
production resource or operating-system isolation guarantees. The caller
retains and protects the external policy; this module does not distribute or
rotate trust policies and does not atomically capture chain and policy together.

## Preserved limits

The current HoloChain head binds index, timestamp, content and previous links.
It does **not** bind `type`, `original_size`, arbitrary extra metadata, JSON
formatting, or blank lines. A test deliberately changes excluded metadata and
still gets MATCHED. This commitment is not a complete file-byte witness.

A test also replaces the witness using the allowed signing key and obtains a
match for changed history. Protection depends on an independently retained
commitment and policy; someone who can replace both, obtain the trusted key,
or substitute an older allowed witness is outside the protection demonstrated
here. A signed chain ID is a declaration, not proof of physical file identity.

Fresh-process recovery reproduces the receipt from the same retained inputs.
Receipt hashes identify output bytes; they are not independent execution
receipts. Every result keeps `accepted=false`, `truth_claimed=false`, and write
and execution authority `NONE`. A MATCHED result is not currentness, authorship,
truth, permission to resume, or a production gate. Composition with the actual
resume path remains a separate test.

# SQLite Bounded Verification Security Contract

Status: DRAFT - REVIEW REQUIRED
Branch: research/sqlite-read-only-verification
Authority: DESCRIPTIVE_ONLY
Write Authority: NONE
Review Verdict: PARTIAL

## Claim under test

The SQLite Merkle verifier can check internal slot-chain consistency
against a bounded SQLite observation without granting provenance,
freshness, authenticity, or acceptance authority.

This claim does not establish forensic-grade source identity binding
or strict source-directory non-mutation.

## Operations in scope

1. SlotMerkleDB(read_only=True)
2. SlotMerkleDB(read_only=True, immutable_snapshot=True)
3. SlotMerkleDB.verify_chain()
4. create_slot_snapshot(source_path, destination_path)

Ordinary writable SlotMerkleDB operation is outside the read-only
verification guarantee.

## Verification evidence

verify_chain() checks:
- Sequential slot indices beginning at 1.
- SHA-256 of retained, non-NULL content.
- Previous-root linkage.
- Recomputed Merkle prefix roots.

PASS means no violations were detected by these checks against the
observed database state.

PASS does not prove independent authenticity, completeness relative
to external history, provenance, freshness, or truth.

NULL content cannot be independently rehashed from the stored record.

## Source acquisition

Direct read-only mode uses SQLite mode=ro and PRAGMA query_only=ON.

Immutable snapshot mode:
- Requires read_only=True.
- Rejects missing or symlinked source paths.
- Opens the source using SQLite mode=ro.
- Performs pathname and filesystem identity checks.
- Copies the database through SQLite's backup API.
- Opens the private copy with mode=ro&immutable=1.
- Cleans up the private snapshot when close() completes; callers must close the object or use its context manager.

These checks do not establish identity of the actual SQLite-opened
file handle. Concurrent source replacement remains a threat.

SQLite source opening may create WAL/SHM sidecars. Therefore neither
mode guarantees strict source-directory non-mutation.

## Snapshot publication

create_slot_snapshot() produces a SQLite-consistent backup and
publishes it using a same-directory hard link.

It rejects an existing destination and does not intentionally
overwrite destination content.

Publication requires a usable destination directory and filesystem
hard-link support. Local Windows drive-letter paths with spaces have
test coverage. Genuine UNC paths, network filesystems, and cross-volume
behavior remain unvalidated; no compatibility guarantee is asserted.

Publication is a write operation and is not covered by the
read-only verification guarantee.

## Threat model

Consider:
- Corrupted or altered retained slot content.
- Broken indices, root links, or Merkle prefix roots.
- Missing or symlinked source paths.
- Concurrent source pathname replacement.
- SQLite WAL/SHM side effects.
- Entire-chain rewriting by an adversary.
- Unavailable original content.
- Unsupported filesystem behavior.

The verifier detects only the inconsistencies covered by its
implemented checks. An internally consistent forged chain may PASS.

## Open review findings

1. Opened-file-handle identity binding: UNPROVEN.
2. Concurrent source replacement safety: LIMITED; races remain.
3. Genuine UNC and cross-volume behavior: UNTESTED.
4. Strict source-directory non-mutation: UNPROVEN; sidecars possible.
5. Independent provenance and freshness: UNSUPPORTED.
6. Independent hashing of NULL content: UNSUPPORTED.

These findings remain open pending explicit threat-model review.
Listing a limitation does not constitute accepting its risk.

## Outcome definitions

PASS:
The completed chain check reports no detected violations.

FAIL:
The completed chain check reports one or more violations.

UNAVAILABLE:
The required source, snapshot, or verification result cannot be
obtained reliably. Exceptions must not be represented as PASS.

These are contract-level classifications. They do not assert that
every public API currently returns all three status strings.

## Review pass conditions

- Each claimed guarantee has reproducible supporting tests.
- Each open finding is resolved or explicitly accepted as a
  bounded limitation by the authorized reviewer.
- Tests distinguish internal consistency from external provenance.
- Source side effects and platform limitations remain disclosed.
- No verification result grants write, execution, truth, or
  acceptance authority.

## Stop conditions

- An unsupported forensic guarantee is represented as established.
- Source identity uncertainty is concealed.
- A failed or unavailable verification is treated as PASS.
- A test failure is reclassified as an acceptable limitation
  without review.
- Implementation behavior contradicts this contract.

## Scope and approval

This document records a proposed bounded security contract.
It does not modify implementation behavior or approve a merge.

Current verdict: PARTIAL.
No commit, push, or merge authorized.

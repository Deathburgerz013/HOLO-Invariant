from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence


LEDGER_TYPE = "holo_uncertainty_ledger"
LEDGER_VERSION = 1
DEFAULT_LEDGER_FILE = Path("runtime_watch") / "uncertainty_ledger.jsonl"
ZERO_HASH = "0" * 64


class UncertaintyStatus(str, Enum):
    OPEN = "open"
    BOUNDED = "bounded"
    REDUCED = "reduced"
    RESOLVED = "resolved"
    CONTRADICTED = "contradicted"


class UncertaintyLedgerError(RuntimeError):
    """Base error for uncertainty-ledger failures."""


class LedgerIntegrityError(UncertaintyLedgerError):
    """Raised when the append-only ledger fails verification."""


def utc_now() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    """Serialize JSON-compatible data deterministically."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def stable_hash(value: Any) -> str:
    """Return a deterministic SHA-256 digest."""
    return hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


def _normalize_text_list(values: Sequence[str] | None) -> list[str]:
    if values is None:
        return []

    normalized: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _entry_payload(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Return the immutable fields protected by entry_hash."""
    return {
        "type": entry["type"],
        "version": entry["version"],
        "idx": entry["idx"],
        "timestamp": entry["timestamp"],
        "claim": entry["claim"],
        "observations": entry["observations"],
        "evidence": entry["evidence"],
        "verification": entry["verification"],
        "allowed_conclusion": entry["allowed_conclusion"],
        "residual_uncertainty": entry["residual_uncertainty"],
        "resolution_conditions": entry["resolution_conditions"],
        "status": entry["status"],
        "confidence": entry["confidence"],
        "source_refs": entry["source_refs"],
        "supersedes": entry["supersedes"],
        "prev_hash": entry["prev_hash"],
    }


def _compute_entry_hash(entry: Mapping[str, Any]) -> str:
    return stable_hash(_entry_payload(entry))


def _validate_confidence(value: float | int | None) -> float | None:
    if value is None:
        return None

    confidence = float(value)
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError("confidence must be between 0.0 and 1.0")
    return confidence


def _validate_status(value: str | UncertaintyStatus) -> UncertaintyStatus:
    if isinstance(value, UncertaintyStatus):
        return value

    try:
        return UncertaintyStatus(value)
    except ValueError as exc:
        allowed = ", ".join(status.value for status in UncertaintyStatus)
        raise ValueError(
            f"status must be one of: {allowed}"
        ) from exc


def atomic_append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    """
    Append one JSON object durably.

    The ledger is append-only. Existing entries are never rewritten.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = canonical_json(value) + "\n"

    with path.open("a", encoding="utf-8", newline="\n") as file_handle:
        file_handle.write(rendered)
        file_handle.flush()
        os.fsync(file_handle.fileno())


class UncertaintyLedger:
    """Append-only, hash-chained ledger for bounded uncertainty."""

    def __init__(
        self,
        file_path: str | Path = DEFAULT_LEDGER_FILE,
    ) -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def load_and_verify(self) -> list[dict[str, Any]]:
        """Load the entire ledger and verify ordering and hashes."""
        if not self.file_path.exists():
            return []

        entries: list[dict[str, Any]] = []
        previous_hash = ZERO_HASH

        with self.file_path.open("r", encoding="utf-8") as file_handle:
            for line_number, raw_line in enumerate(file_handle, start=1):
                line = raw_line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise LedgerIntegrityError(
                        f"Invalid JSON at line {line_number}"
                    ) from exc

                if not isinstance(entry, dict):
                    raise LedgerIntegrityError(
                        f"Line {line_number} must contain a JSON object"
                    )

                expected_idx = len(entries) + 1
                if entry.get("idx") != expected_idx:
                    raise LedgerIntegrityError(
                        f"Index mismatch at line {line_number}"
                    )

                if entry.get("prev_hash") != previous_hash:
                    raise LedgerIntegrityError(
                        f"Previous-hash mismatch at line {line_number}"
                    )

                expected_hash = _compute_entry_hash(entry)
                if entry.get("entry_hash") != expected_hash:
                    raise LedgerIntegrityError(
                        f"Entry-hash mismatch at line {line_number}"
                    )

                _validate_status(str(entry.get("status")))
                _validate_confidence(entry.get("confidence"))

                previous_hash = expected_hash
                entries.append(entry)

        return entries

    def append(
        self,
        *,
        claim: str,
        observations: Sequence[str] | None = None,
        evidence: Sequence[str] | None = None,
        verification: Sequence[str] | None = None,
        allowed_conclusion: str = "",
        residual_uncertainty: Sequence[str] | None = None,
        resolution_conditions: Sequence[str] | None = None,
        status: str | UncertaintyStatus = UncertaintyStatus.OPEN,
        confidence: float | None = None,
        source_refs: Sequence[str] | None = None,
        supersedes: int | None = None,
    ) -> dict[str, Any]:
        """Append one uncertainty record after verifying the current ledger."""
        clean_claim = claim.strip()
        if not clean_claim:
            raise ValueError("claim cannot be empty")

        clean_conclusion = allowed_conclusion.strip()
        clean_status = _validate_status(status)
        clean_confidence = _validate_confidence(confidence)

        entries = self.load_and_verify()

        if supersedes is not None:
            if supersedes < 1 or supersedes > len(entries):
                raise ValueError(
                    "supersedes must reference an existing entry"
                )

        entry: dict[str, Any] = {
            "type": LEDGER_TYPE,
            "version": LEDGER_VERSION,
            "idx": len(entries) + 1,
            "timestamp": utc_now(),
            "claim": clean_claim,
            "observations": _normalize_text_list(observations),
            "evidence": _normalize_text_list(evidence),
            "verification": _normalize_text_list(verification),
            "allowed_conclusion": clean_conclusion,
            "residual_uncertainty": _normalize_text_list(
                residual_uncertainty
            ),
            "resolution_conditions": _normalize_text_list(
                resolution_conditions
            ),
            "status": clean_status.value,
            "confidence": clean_confidence,
            "source_refs": _normalize_text_list(source_refs),
            "supersedes": supersedes,
            "prev_hash": (
                entries[-1]["entry_hash"]
                if entries
                else ZERO_HASH
            ),
        }
        entry["entry_hash"] = _compute_entry_hash(entry)

        atomic_append_jsonl(self.file_path, entry)
        return entry

    def resolve(
        self,
        entry_idx: int,
        *,
        allowed_conclusion: str,
        verification: Sequence[str],
        evidence: Sequence[str] | None = None,
        residual_uncertainty: Sequence[str] | None = None,
        confidence: float | None = 1.0,
        source_refs: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """
        Resolve an earlier uncertainty by appending a superseding record.

        Prior history remains untouched.
        """
        entries = self.load_and_verify()
        if entry_idx < 1 or entry_idx > len(entries):
            raise ValueError("entry_idx must reference an existing entry")

        original = entries[entry_idx - 1]

        return self.append(
            claim=original["claim"],
            observations=original.get("observations", []),
            evidence=evidence or original.get("evidence", []),
            verification=verification,
            allowed_conclusion=allowed_conclusion,
            residual_uncertainty=residual_uncertainty,
            resolution_conditions=[],
            status=UncertaintyStatus.RESOLVED,
            confidence=confidence,
            source_refs=source_refs or original.get("source_refs", []),
            supersedes=entry_idx,
        )

    def latest_by_claim(self) -> list[dict[str, Any]]:
        """Return the newest record for each exact claim."""
        entries = self.load_and_verify()
        latest: dict[str, dict[str, Any]] = {}

        for entry in entries:
            latest[entry["claim"]] = entry

        return list(latest.values())

    def summary(self) -> dict[str, Any]:
        """Return ledger health and status counts."""
        entries = self.load_and_verify()
        counts = {
            status.value: 0
            for status in UncertaintyStatus
        }

        for entry in self.latest_by_claim():
            counts[entry["status"]] += 1

        return {
            "valid": True,
            "entries": len(entries),
            "active_claims": sum(counts.values()),
            "status_counts": counts,
            "latest_hash": (
                entries[-1]["entry_hash"]
                if entries
                else ZERO_HASH
            ),
            "file": str(self.file_path),
        }


def _split_items(values: Sequence[str] | None) -> list[str]:
    """Accept repeated CLI values and split semicolon-delimited text."""
    if not values:
        return []

    items: list[str] = []
    for value in values:
        for part in value.split(";"):
            clean = part.strip()
            if clean:
                items.append(clean)
    return items


def print_json(value: Mapping[str, Any]) -> None:
    print(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def run_self_test() -> None:
    """Verify append, resolution, summary, and tamper detection."""
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "uncertainty.jsonl"
        ledger = UncertaintyLedger(path)

        first = ledger.append(
            claim="The transition receipt is historically valid.",
            observations=["receipt exists", "hash matches"],
            evidence=["recorded commit exists"],
            verification=["receipt hash verified"],
            allowed_conclusion="The receipt is intact.",
            residual_uncertainty=[
                "Replay has not yet been performed"
            ],
            resolution_conditions=[
                "Run replay verifier"
            ],
            status=UncertaintyStatus.BOUNDED,
            confidence=0.8,
        )

        assert first["idx"] == 1
        assert ledger.summary()["status_counts"]["bounded"] == 1

        resolved = ledger.resolve(
            1,
            allowed_conclusion=(
                "The receipt is valid historical evidence."
            ),
            verification=[
                "Replay verifier passed",
                "Invariant audit passed",
            ],
            residual_uncertainty=[
                "This does not prove future repository states"
            ],
            confidence=0.95,
        )

        assert resolved["supersedes"] == 1
        assert resolved["status"] == "resolved"
        assert ledger.summary()["status_counts"]["resolved"] == 1

        raw = path.read_text(encoding="utf-8")
        path.write_text(
            raw.replace(
                "historically valid",
                "silently altered",
                1,
            ),
            encoding="utf-8",
        )

        try:
            ledger.load_and_verify()
        except LedgerIntegrityError:
            pass
        else:
            raise AssertionError("Tampering was not detected")

    print("✅ Uncertainty ledger self-test passed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Record bounded, verifiable uncertainty without "
            "rewriting prior history."
        )
    )
    parser.add_argument(
        "--file",
        default=str(DEFAULT_LEDGER_FILE),
        help="Uncertainty ledger JSONL path",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    add_parser = subparsers.add_parser(
        "add",
        help="Append one uncertainty record",
    )
    add_parser.add_argument("claim")
    add_parser.add_argument(
        "--observation",
        action="append",
        default=[],
    )
    add_parser.add_argument(
        "--evidence",
        action="append",
        default=[],
    )
    add_parser.add_argument(
        "--verification",
        action="append",
        default=[],
    )
    add_parser.add_argument(
        "--conclusion",
        default="",
    )
    add_parser.add_argument(
        "--uncertainty",
        action="append",
        default=[],
    )
    add_parser.add_argument(
        "--resolve-when",
        action="append",
        default=[],
    )
    add_parser.add_argument(
        "--status",
        choices=[status.value for status in UncertaintyStatus],
        default=UncertaintyStatus.OPEN.value,
    )
    add_parser.add_argument(
        "--confidence",
        type=float,
        default=None,
    )
    add_parser.add_argument(
        "--source",
        action="append",
        default=[],
    )

    resolve_parser = subparsers.add_parser(
        "resolve",
        help="Append a resolution for an existing entry",
    )
    resolve_parser.add_argument("entry_idx", type=int)
    resolve_parser.add_argument(
        "--conclusion",
        required=True,
    )
    resolve_parser.add_argument(
        "--verification",
        action="append",
        required=True,
    )
    resolve_parser.add_argument(
        "--evidence",
        action="append",
        default=[],
    )
    resolve_parser.add_argument(
        "--uncertainty",
        action="append",
        default=[],
    )
    resolve_parser.add_argument(
        "--confidence",
        type=float,
        default=1.0,
    )
    resolve_parser.add_argument(
        "--source",
        action="append",
        default=[],
    )

    subparsers.add_parser(
        "verify",
        help="Verify the full ledger",
    )
    subparsers.add_parser(
        "summary",
        help="Show current uncertainty status counts",
    )
    subparsers.add_parser(
        "self-test",
        help="Run isolated ledger tests",
    )

    args = parser.parse_args()
    ledger = UncertaintyLedger(args.file)

    if args.command == "add":
        entry = ledger.append(
            claim=args.claim,
            observations=_split_items(args.observation),
            evidence=_split_items(args.evidence),
            verification=_split_items(args.verification),
            allowed_conclusion=args.conclusion,
            residual_uncertainty=_split_items(args.uncertainty),
            resolution_conditions=_split_items(args.resolve_when),
            status=args.status,
            confidence=args.confidence,
            source_refs=_split_items(args.source),
        )
        print_json(entry)

    elif args.command == "resolve":
        entry = ledger.resolve(
            args.entry_idx,
            allowed_conclusion=args.conclusion,
            verification=_split_items(args.verification),
            evidence=_split_items(args.evidence),
            residual_uncertainty=_split_items(args.uncertainty),
            confidence=args.confidence,
            source_refs=_split_items(args.source),
        )
        print_json(entry)

    elif args.command == "verify":
        entries = ledger.load_and_verify()
        print_json(
            {
                "valid": True,
                "entries": len(entries),
                "latest_hash": (
                    entries[-1]["entry_hash"]
                    if entries
                    else ZERO_HASH
                ),
            }
        )

    elif args.command == "summary":
        print_json(ledger.summary())

    elif args.command == "self-test":
        run_self_test()

    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()

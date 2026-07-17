import hashlib
import json
import logging
import platform
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from holosim.config import DEFAULT_CHAIN_FILE, HOLOSIM_VERSION
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import DEFAULT_CHAIN_FILE, HOLOSIM_VERSION


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HoloChain:
    """Tamper-evident append-only chain for AI/human continuity and long-term memory (HSSCE primitive).

    Core invariants:
    - Cryptographically verifiable (SHA-256 + canonical JSON).
    - Append-only, fails-fast on tampering.
    - Optional smart compression for density.
    - Fully reproducible across time and systems.
    """

    VERSION = HOLOSIM_VERSION

    def __init__(
        self,
        file_path: str | Path = DEFAULT_CHAIN_FILE,
        genesis_hash: str = "0" * 64,
    ):
        self.file_path = Path(file_path)
        self.genesis_hash = genesis_hash
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _compute_hash(self, prev_hash: str, content: str, timestamp: str, idx: int) -> str:
        """Deterministic canonical hash for tamper-evidence."""
        canonical = json.dumps({
            "idx": idx,
            "timestamp": timestamp,
            "content": content
        }, separators=(',', ':'), sort_keys=True)
        data = prev_hash.encode() + canonical.encode()
        return hashlib.sha256(data).hexdigest()

    def _acquire_lock(self, f):
        """Platform-aware file lock for concurrent safety."""
        if platform.system() != "Windows":
            try:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            except (ImportError, AttributeError):
                pass  # Fallback for environments without fcntl
        # Windows: simple retry-based safety (no native flock)

    def load_and_verify(self) -> List[Dict]:
        """Load and fully verify the entire chain. Fails fast on tampering."""
        if not self.file_path.exists():
            return []
        entries = []
        prev_hash = self.genesis_hash
        with self.file_path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    expected = self._compute_hash(
                        prev_hash, entry["content"], entry["timestamp"], entry["idx"]
                    )
                    if entry["hash"] != expected or entry.get("prev_hash") != prev_hash:
                        raise ValueError(f"Hash mismatch at line {line_num}")
                    prev_hash = entry["hash"]
                    entries.append(entry)
                except Exception as e:
                    logger.error(f"Integrity failure at line {line_num}: {e}")
                    raise
        # Monotonic index check
        for i, e in enumerate(entries):
            if e["idx"] != i + 1:
                raise ValueError("Index not monotonic")
        logger.info(f"✅ Verified {len(entries)} entries. Chain intact. [HoloChain v{self.VERSION}]")
        return entries

    def append(self, content: Any, compress: bool = False, min_compress_size: int = 128) -> Dict:
        """Append new entry with smart optional compression for density."""
        entries = self.load_and_verify()
        idx = len(entries) + 1
        timestamp = datetime.now(timezone.utc).isoformat() + "Z"
        prev_hash = self.genesis_hash if not entries else entries[-1]["hash"]

        if isinstance(content, (dict, list)):
            content_str = json.dumps(content, ensure_ascii=False)
        elif not isinstance(content, str):
            content_str = str(content)
        else:
            content_str = content

        original_content = content_str
        entry_type = "plain"

        if compress and len(original_content) >= min_compress_size:
            compressed = zlib.compress(original_content.encode('utf-8'))
            compressed_hex = compressed.hex()
            if len(compressed_hex) < len(original_content):
                content_str = compressed_hex
                entry_type = "compressed"

        hash_val = self._compute_hash(prev_hash, content_str, timestamp, idx)

        entry = {
            "idx": idx,
            "timestamp": timestamp,
            "content": content_str,
            "prev_hash": prev_hash,
            "hash": hash_val,
            "type": entry_type,
            "original_size": len(original_content)
        }

        with self.file_path.open("a", encoding="utf-8") as f:
            self._acquire_lock(f)
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info(f"✅ Appended entry {idx} ({entry_type}) [HoloChain v{self.VERSION}]")
        return entry

    def create_checkpoint(self) -> Dict:
        """
        Create a hash-referenced checkpoint for fast verification and future recovery.

        This checkpoint records the current verified chain root and metadata.
        It is not cryptographically signed and is not automatically persisted.
        """
        entries = self.load_and_verify()
        if not entries:
            return {}
        last = entries[-1]
        checkpoint = {
            "type": "checkpoint",
            "idx": last["idx"],
            "root_hash": last["hash"],
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "total_entries": len(entries),
            "version": self.VERSION
        }
        logger.info(f"✅ Checkpoint created at idx {last['idx']}")
        return checkpoint

    def replay(self, full: bool = False) -> List[Dict]:
        """Replay full history."""
        entries = self.load_and_verify()
        print("\n=== HOLO-CHAIN REPLAY ===")
        for e in entries:
            snippet = e['content'] if full else e['content'][:120] + ('...' if len(e['content']) > 120 else '')
            ctype = e.get('type', 'plain')
            print(f"{e['idx']:3} | {e['timestamp']} | [{ctype}] {snippet}")
        return entries

    def get_state(self) -> List[Any]:
        """Reconstruct current state (decompress if needed)."""
        entries = self.load_and_verify()
        state = []
        for e in entries:
            content = e["content"]
            if e.get("type") == "compressed":
                try:
                    content = zlib.decompress(bytes.fromhex(content)).decode('utf-8')
                except Exception:
                    content = f"[DECOMPRESSION FAILED] {content[:100]}..."
            try:
                if content.startswith(('{', '[')):
                    state.append(json.loads(content))
                else:
                    state.append(content)
            except Exception:
                state.append(content)
        return state

    def get_density_stats(self) -> Dict:
        """Return compression/density statistics with accurate original size tracking."""
        entries = self.load_and_verify()
        total_original = sum(e.get("original_size", len(e["content"])) for e in entries)
        total_stored = sum(len(e["content"]) for e in entries)
        compressed_count = sum(1 for e in entries if e.get("type") == "compressed")
        overall_ratio = round(total_stored / max(total_original, 1), 4) if total_original else 0
        return {
            "total_entries": len(entries),
            "plain_entries": len(entries) - compressed_count,
            "compressed_entries": compressed_count,
            "total_original_bytes": total_original,
            "total_stored_bytes": total_stored,
            "compression_ratio": overall_ratio,
            "compression_savings_percent": round((1 - overall_ratio) * 100, 2),
            "version": self.VERSION
        }

    def get_latest(self) -> Optional[Dict]:
        """Convenience: return most recent entry (verified)."""
        entries = self.load_and_verify()
        return entries[-1] if entries else None

    # === Append-only correction overlay ===
    @staticmethod
    def _is_correction(value: Any) -> bool:
        return (
            isinstance(value, dict)
            and value.get("_holo_record_type") == "holo_correction"
        )

    def _correction_view(self) -> tuple[List[Dict], List[Any], List[tuple[Dict, Dict]]]:
        """Load correction records and fail closed on malformed references."""
        entries = self.load_and_verify()
        decoded = self.get_state()
        if len(entries) != len(decoded):
            raise ValueError("Decoded state length does not match raw chain length")

        by_idx = {entry["idx"]: entry for entry in entries}
        decoded_by_idx = {
            entry["idx"]: value for entry, value in zip(entries, decoded)
        }
        corrections: List[tuple[Dict, Dict]] = []

        for entry, value in zip(entries, decoded):
            if not self._is_correction(value):
                continue
            target = value.get("corrects_idx")
            reason = value.get("reason")
            if value.get("version") != 1:
                raise ValueError(f"Unsupported correction version at idx {entry['idx']}")
            if (
                not isinstance(target, int)
                or isinstance(target, bool)
                or target < 1
                or target >= entry["idx"]
            ):
                raise ValueError(f"Invalid correction target at idx {entry['idx']}")
            if target not in by_idx:
                raise ValueError(f"Correction targets missing idx {target}")
            if self._is_correction(decoded_by_idx[target]):
                raise ValueError("Corrections must target an original entry")
            if value.get("corrects_hash") != by_idx[target].get("hash"):
                raise ValueError(f"Correction target hash mismatch at idx {entry['idx']}")
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError(f"Correction at idx {entry['idx']} requires a reason")
            if "replacement" not in value:
                raise ValueError(f"Correction at idx {entry['idx']} lacks replacement")
            corrections.append((entry, value))

        return entries, decoded, corrections

    def correct(self, target_idx: int, new_content: Any, reason: str) -> Dict:
        """Append a reasoned correction without changing the original entry."""
        if (
            not isinstance(target_idx, int)
            or isinstance(target_idx, bool)
            or target_idx < 1
        ):
            raise ValueError("target_idx must be a positive integer")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("A correction requires a non-empty reason")

        entries = self.load_and_verify()
        decoded = self.get_state()
        positions = {entry["idx"]: pos for pos, entry in enumerate(entries)}
        if target_idx not in positions:
            raise ValueError(f"No entry with idx {target_idx} to correct")
        target = entries[positions[target_idx]]
        if self._is_correction(decoded[positions[target_idx]]):
            raise ValueError("Corrections must target an original entry")

        payload = {
            "_holo_record_type": "holo_correction",
            "version": 1,
            "corrects_idx": target_idx,
            "corrects_hash": target["hash"],
            "reason": reason.strip(),
            "replacement": new_content,
        }
        try:
            json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise TypeError("Correction replacement must be JSON-serializable") from exc
        return self.append(payload)

    def get_effective_state(self) -> List[Dict]:
        """Return the corrected view while leaving raw history untouched."""
        entries, decoded, corrections = self._correction_view()
        correction_ids = {entry["idx"] for entry, _ in corrections}
        effective = {
            entry["idx"]: {"idx": entry["idx"], "content": value}
            for entry, value in zip(entries, decoded)
            if entry["idx"] not in correction_ids
        }
        for entry, correction in corrections:
            target = correction["corrects_idx"]
            history = list(effective[target].get("correction_history", []))
            history.append(entry["idx"])
            effective[target] = {
                "idx": target,
                "content": correction["replacement"],
                "corrected_by": entry["idx"],
                "reason": correction["reason"],
                "correction_history": history,
            }
        return [effective[idx] for idx in sorted(effective)]

    def get_corrections(self, target_idx: int) -> List[Dict]:
        """Return every validated correction for one original entry."""
        entries, _, corrections = self._correction_view()
        if not any(entry["idx"] == target_idx for entry in entries):
            raise ValueError(f"No entry with idx {target_idx}")
        return [
            {
                "idx": entry["idx"],
                "timestamp": entry["timestamp"],
                "corrects_idx": correction["corrects_idx"],
                "corrects_hash": correction["corrects_hash"],
                "reason": correction["reason"],
                "content": correction["replacement"],
            }
            for entry, correction in corrections
            if correction["corrects_idx"] == target_idx
        ]

    # === Append-only revalidation receipts ===
    @staticmethod
    def _is_revalidation(value: Any) -> bool:
        return (
            isinstance(value, dict)
            and value.get("_holo_record_type") == "holo_revalidation"
        )

    @staticmethod
    def _content_digest(value: Any) -> str:
        """Return a deterministic digest for one decoded effective value."""
        try:
            canonical = json.dumps(
                value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
        except (TypeError, ValueError) as exc:
            raise TypeError("Revalidation content must be JSON-serializable") from exc
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _revalidation_view(
        self,
    ) -> tuple[List[Dict], List[Any], List[Dict], List[tuple[Dict, Dict]]]:
        """Validate receipts against the effective claim version they checked."""
        entries, decoded, corrections = self._correction_view()
        effective = self.get_effective_state()
        effective_by_idx = {item["idx"]: item for item in effective}
        entries_by_idx = {entry["idx"]: entry for entry in entries}
        receipts: List[tuple[Dict, Dict]] = []
        allowed = {"HELD", "FAILED", "REVISED", "UNAVAILABLE"}

        for entry, value in zip(entries, decoded):
            if not self._is_revalidation(value):
                continue
            if value.get("version") != 1:
                raise ValueError(f"Unsupported revalidation version at idx {entry['idx']}")
            target = value.get("target_idx")
            if (
                not isinstance(target, int)
                or isinstance(target, bool)
                or target < 1
                or target >= entry["idx"]
                or target not in entries_by_idx
            ):
                raise ValueError(f"Invalid revalidation target at idx {entry['idx']}")
            target_value = decoded[target - 1]
            if self._is_correction(target_value) or self._is_revalidation(target_value):
                raise ValueError("Revalidations must target an original entry")
            if value.get("target_hash") != entries_by_idx[target].get("hash"):
                raise ValueError(f"Revalidation target hash mismatch at idx {entry['idx']}")
            outcome = value.get("outcome")
            if outcome not in allowed:
                raise ValueError(f"Invalid revalidation outcome at idx {entry['idx']}")
            for field in ("method", "evidence"):
                field_value = value.get(field)
                if not isinstance(field_value, str) or not field_value.strip():
                    raise ValueError(
                        f"Revalidation at idx {entry['idx']} requires non-empty {field}"
                    )
            if not isinstance(value.get("subject_hash"), str):
                raise ValueError(f"Revalidation at idx {entry['idx']} lacks subject hash")
            subject_correction_idx = value.get("subject_correction_idx")
            if subject_correction_idx is not None and (
                not isinstance(subject_correction_idx, int)
                or isinstance(subject_correction_idx, bool)
                or subject_correction_idx < 1
                or subject_correction_idx >= entry["idx"]
            ):
                raise ValueError(
                    f"Invalid revalidation correction reference at idx {entry['idx']}"
                )

            historical_subject = target_value
            historical_correction_idx = None
            for correction_entry, correction in corrections:
                if (
                    correction["corrects_idx"] == target
                    and correction_entry["idx"] < entry["idx"]
                ):
                    historical_subject = correction["replacement"]
                    historical_correction_idx = correction_entry["idx"]
            if subject_correction_idx != historical_correction_idx:
                raise ValueError(
                    f"Revalidation correction reference mismatch at idx {entry['idx']}"
                )
            if value["subject_hash"] != self._content_digest(historical_subject):
                raise ValueError("Revalidation subject hash mismatch at idx {entry['idx']}")
            receipts.append((entry, value))

        return entries, decoded, effective, receipts

    def revalidate(
        self,
        target_idx: int,
        outcome: str,
        evidence: str,
        method: str,
    ) -> Dict:
        """Append a check of the current effective version of an original claim."""
        if (
            not isinstance(target_idx, int)
            or isinstance(target_idx, bool)
            or target_idx < 1
        ):
            raise ValueError("target_idx must be a positive integer")
        if not isinstance(outcome, str) or outcome not in {
            "HELD", "FAILED", "REVISED", "UNAVAILABLE"
        }:
            raise ValueError("outcome must be HELD, FAILED, REVISED, or UNAVAILABLE")
        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError("evidence must be a non-empty string")
        if not isinstance(method, str) or not method.strip():
            raise ValueError("method must be a non-empty string")

        entries, decoded, _ = self._correction_view()
        entries_by_idx = {entry["idx"]: entry for entry in entries}
        if target_idx not in entries_by_idx:
            raise ValueError(f"No entry with idx {target_idx} to revalidate")
        target_value = decoded[target_idx - 1]
        if self._is_correction(target_value) or self._is_revalidation(target_value):
            raise ValueError("Revalidations must target an original entry")
        effective_by_idx = {item["idx"]: item for item in self.get_effective_state()}
        subject = effective_by_idx[target_idx]
        payload = {
            "_holo_record_type": "holo_revalidation",
            "version": 1,
            "target_idx": target_idx,
            "target_hash": entries_by_idx[target_idx]["hash"],
            "subject_hash": self._content_digest(subject["content"]),
            "subject_correction_idx": subject.get("corrected_by"),
            "outcome": outcome,
            "method": method.strip(),
            "evidence": evidence.strip(),
        }
        return self.append(payload)

    def get_revalidations(self, target_idx: int) -> List[Dict]:
        """Return all checks and whether each still matches the effective claim."""
        entries, _, effective, receipts = self._revalidation_view()
        if not any(entry["idx"] == target_idx for entry in entries):
            raise ValueError(f"No entry with idx {target_idx}")
        effective_by_idx = {item["idx"]: item for item in effective}
        if target_idx not in effective_by_idx:
            raise ValueError("Revalidations must target an original entry")
        current = effective_by_idx[target_idx]
        current_hash = self._content_digest(current["content"])
        current_correction = current.get("corrected_by")
        return [
            {
                "idx": entry["idx"],
                "timestamp": entry["timestamp"],
                "outcome": value["outcome"],
                "method": value["method"],
                "evidence": value["evidence"],
                "subject_hash": value["subject_hash"],
                "subject_correction_idx": value.get("subject_correction_idx"),
                "current": (
                    value["subject_hash"] == current_hash
                    and value.get("subject_correction_idx") == current_correction
                ),
            }
            for entry, value in receipts
            if value["target_idx"] == target_idx
        ]

    def get_claim_index(self) -> List[Dict]:
        """Index originals, corrections, checks, and current usable status."""
        entries, decoded, effective, _ = self._revalidation_view()
        effective_by_idx = {item["idx"]: item for item in effective}
        index = []
        for entry, value in zip(entries, decoded):
            if self._is_correction(value) or self._is_revalidation(value):
                continue
            current = effective_by_idx[entry["idx"]]
            checks = self.get_revalidations(entry["idx"])
            current_checks = [check for check in checks if check["current"]]
            latest = current_checks[-1] if current_checks else None
            row = {
                "idx": entry["idx"],
                "original_hash": entry["hash"],
                "content": current["content"],
                "content_hash": self._content_digest(current["content"]),
                "correction_history": current.get("correction_history", []),
                "revalidation_history": [check["idx"] for check in checks],
                "status": (
                    latest["outcome"]
                    if latest
                    else "STALE"
                    if checks
                    else "UNCHECKED"
                ),
            }
            if current.get("corrected_by") is not None:
                row["corrected_by"] = current["corrected_by"]
            if latest is not None:
                row["revalidated_by"] = latest["idx"]
            index.append(row)
        return index

    # === Relevance & Maintenance Methods ===
    def needs_review(self, days_old: int = 90, min_access: int = 1) -> List[Dict]:
        """Flag low-need entries for human review (basic relevance tracking)."""
        entries = self.load_and_verify()
        now = datetime.now(timezone.utc)
        suggestions = []
        for e in entries:
            try:
                entry_date = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
                age_days = (now - entry_date).days
                if age_days > days_old:
                    suggestions.append({
                        "idx": e["idx"],
                        "age_days": age_days,
                        "snippet": str(e.get("content", ""))[:120] + ("..." if len(str(e.get("content", ""))) > 120 else ""),
                        "reason": f"old (> {days_old} days)"
                    })
            except Exception:
                continue
        return suggestions

    def health(self) -> Dict:
        """Simple self-check dashboard for chain maintenance."""
        stats = self.get_density_stats()
        review = self.needs_review()
        entries = self.load_and_verify()
        chain_age = 0
        if entries:
            try:
                first_date = datetime.fromisoformat(entries[0]["timestamp"].replace("Z", "+00:00"))
                chain_age = (datetime.now(timezone.utc) - first_date).days
            except Exception:
                pass

        return {
            **stats,
            "low_need_count": len(review),
            "chain_age_days": chain_age,
            "total_entries": len(entries),
            "recommendation": "Consider human review of low-need entries" if len(review) > len(entries) * 0.25 else "Healthy"
        }

    def prune_suggestions(self, max_age_days: int = 180) -> List[Dict]:
        """Safe suggestions only — never auto-delete. Human must approve."""
        return self.needs_review(days_old=max_age_days)

    def check_invariant_health(self, invariant_keywords: List[str]) -> Dict:
        """Light semantic health check on core invariants (zero-dep heuristic)."""
        state = self.get_state()
        health = {}
        for kw in invariant_keywords:
            mentions = sum(1 for item in state
                          if isinstance(item, str) and kw.lower() in item.lower())
            health[kw] = {
                "mentions": mentions,
                "density": round(mentions / len(state), 3) if state else 0
            }
        return health

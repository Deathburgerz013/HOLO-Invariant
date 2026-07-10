"""Holo/Sim Sentinel.

Lightweight telemetry for continuity health:
- chain health
- invariant distance from first baseline
- spine entropy
- anchor lag heuristic
- hash-chained metrics audit log
"""

from __future__ import annotations

import argparse
import collections
import datetime
import difflib
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from holosim.config import DEFAULT_CHAIN_FILE
    from holosim.replay import ReplayEngine
    from holosim.service import get_service
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import DEFAULT_CHAIN_FILE
    from holosim.replay import ReplayEngine
    from holosim.service import get_service


METRICS_AUDIT_PATH = "metrics_audit.jsonl"

THRESHOLDS = {
    "max_invariant_distance": 0.25,
    "max_entropy": 8.0,
    "max_anchor_lag_hours": 48,
}


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def stable_hash(data: Any) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class VerifiableAuditLog:
    def __init__(self, path: str | Path = METRICS_AUDIT_PATH) -> None:
        self.path = Path(path)
        self.path.touch(exist_ok=True)

    def append(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        prev_hash = ""
        lines = self.path.read_text(encoding="utf-8").splitlines()
        if lines:
            prev_hash = json.loads(lines[-1]).get("hash", "")

        entry = {
            "timestamp": utc_now(),
            "metrics": metrics,
            "prev_hash": prev_hash,
        }
        entry["hash"] = stable_hash(entry)

        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return entry

    def verify(self) -> bool:
        prev_hash = ""
        for line in self.path.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            given_hash = entry.get("hash")
            clean_entry = dict(entry)
            clean_entry.pop("hash", None)

            if clean_entry.get("prev_hash") != prev_hash:
                return False
            if stable_hash(clean_entry) != given_hash:
                return False

            prev_hash = given_hash

        return True


class HoloSentinel:
    def __init__(
        self,
        chain_path: str | Path = DEFAULT_CHAIN_FILE,
        audit_path: str | Path = METRICS_AUDIT_PATH,
    ) -> None:
        self.chain_path = Path(chain_path)
        self.service = get_service(self.chain_path)
        self.replay = ReplayEngine(self.chain_path)
        self.audit = VerifiableAuditLog(audit_path)
        self.baseline_text: str | None = None

    def state_text(self) -> str:
        entries = self.replay.timeline()
        return json.dumps(entries, sort_keys=True, ensure_ascii=False, default=str)

    def invariant_distance(self) -> float:
        current = self.state_text()
        if self.baseline_text is None:
            self.baseline_text = current
            return 0.0

        similarity = difflib.SequenceMatcher(None, self.baseline_text, current).ratio()
        return round(1.0 - similarity, 4)

    def spine_entropy(self) -> float:
        text = self.state_text()
        words = text.lower().split()
        if not words:
            return 0.0

        freq = collections.Counter(words)
        total = len(words)

        entropy = 0.0
        for count in freq.values():
            p = count / total
            entropy -= p * math.log2(p)

        return round(entropy, 4)

    def anchor_lag_hours(self) -> float:
        entries = self.replay.timeline()
        for entry in reversed(entries):
            preview = str(entry.get("preview", "")).lower()
            if "anchor" in preview or "canyon" in preview:
                return 0.0
        return 999.0

    def collect(self) -> Dict[str, Any]:
        return {
            "timestamp": utc_now(),
            "health": self.service.health(),
            "verify": self.service.verify(),
            "invariant_distance": self.invariant_distance(),
            "spine_entropy": self.spine_entropy(),
            "anchor_sync_lag_hours": self.anchor_lag_hours(),
        }

    def check(self, metrics: Dict[str, Any]) -> Tuple[bool, List[str]]:
        alerts: List[str] = []
        rebirth_recommended = False

        if metrics["invariant_distance"] > THRESHOLDS["max_invariant_distance"]:
            alerts.append(f"High invariant drift: {metrics['invariant_distance']}")
            rebirth_recommended = True

        if metrics["spine_entropy"] > THRESHOLDS["max_entropy"]:
            alerts.append(f"High spine entropy: {metrics['spine_entropy']}")

        if metrics["anchor_sync_lag_hours"] > THRESHOLDS["max_anchor_lag_hours"]:
            alerts.append(f"Anchor sync lag: {metrics['anchor_sync_lag_hours']} hours")
            rebirth_recommended = True

        return rebirth_recommended, alerts

    def run_once(self, *, write_audit: bool = True) -> Dict[str, Any]:
        metrics = self.collect()
        rebirth_recommended, alerts = self.check(metrics)

        audit_entry = self.audit.append(metrics) if write_audit else None

        return {
            "status": "ok",
            "metrics": metrics,
            "alerts": alerts,
            "rebirth_recommended": rebirth_recommended,
            "audit_written": bool(audit_entry),
            "audit_valid": self.audit.verify(),
        }


def get_sentinel(
    chain_path: str | Path = DEFAULT_CHAIN_FILE,
    audit_path: str | Path = METRICS_AUDIT_PATH,
) -> HoloSentinel:
    return HoloSentinel(chain_path, audit_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Holo/Sim Sentinel telemetry.")
    parser.add_argument("--file", "-f", default=str(DEFAULT_CHAIN_FILE))
    parser.add_argument("--audit", default=METRICS_AUDIT_PATH)
    parser.add_argument("--no-write", action="store_true")

    args = parser.parse_args()

    sentinel = get_sentinel(args.file, args.audit)
    result = sentinel.run_once(write_audit=not args.no_write)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
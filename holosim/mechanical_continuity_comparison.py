"""Read-only comparison of independently verified lineage snapshots."""

from pathlib import Path
from typing import Any

from holosim.canonical import stable_hash
from holosim.general_system_lineage import IDS, KINDS
from holosim.mechanical_continuity_book import open_book


def compare_books(old_path: str | Path, old_expected_hash: str, new_path: str | Path, new_expected_hash: str) -> dict[str, Any]:
    """Classify record differences without claiming ancestry or authority."""
    old = open_book(old_path, old_expected_hash)
    new = open_book(new_path, new_expected_hash)
    changes = []
    for kind in KINDS:
        old_records = {record[IDS[kind]]: stable_hash(record) for record in old[kind]}
        new_records = {record[IDS[kind]]: stable_hash(record) for record in new[kind]}
        for record_id in sorted(old_records.keys() | new_records.keys()):
            before = old_records.get(record_id)
            after = new_records.get(record_id)
            if before is None:
                classification = "ADDED"
            elif after is None:
                classification = "REMOVED"
            elif before == after:
                classification = "UNCHANGED"
            else:
                classification = "MODIFIED"
            changes.append({"kind": kind, "id": record_id, "classification": classification, "from_record_hash": before, "to_record_hash": after})
    return {"from_lineage_hash": old["lineage_hash"], "to_lineage_hash": new["lineage_hash"], "changes": changes, "truth_claimed": False, "accepted": False, "write_authority": "NONE", "ancestry_established": False}

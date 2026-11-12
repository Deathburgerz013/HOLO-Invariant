"""Read-only snapshot comparison contract tests."""

from holosim.general_system_lineage import build_general_system_lineage
from holosim.mechanical_continuity_comparison import compare_books


def test_identical_snapshots_are_unchanged(tmp_path):
    report = build_general_system_lineage([{"system_id": "machine-1", "domain": "machine", "label": "Motor"}], [], [], [])
    path = tmp_path / "snapshot.json"
    path.write_text(__import__("json").dumps(report), encoding="utf-8")
    result = compare_books(path, report["lineage_hash"], path, report["lineage_hash"])
    assert len(result["changes"]) == 1
    assert result["changes"][0]["classification"] == "UNCHANGED"


def test_modified_record_retains_both_hashes(tmp_path):
    import json
    old = build_general_system_lineage([{"system_id": "machine-1", "domain": "machine", "label": "Motor"}], [], [], [])
    new = build_general_system_lineage([{"system_id": "machine-1", "domain": "machine", "label": "Motor Revised"}], [], [], [])
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text(json.dumps(old), encoding="utf-8")
    new_path.write_text(json.dumps(new), encoding="utf-8")
    result = compare_books(old_path, old["lineage_hash"], new_path, new["lineage_hash"])
    change = result["changes"][0]
    assert change["classification"] == "MODIFIED"
    assert change["from_record_hash"] != change["to_record_hash"]


def test_added_record_has_no_old_hash(tmp_path):
    import json
    old = build_general_system_lineage([{"system_id": "machine-1", "domain": "machine", "label": "Motor"}], [], [], [])
    new = build_general_system_lineage([{"system_id": "machine-1", "domain": "machine", "label": "Motor"}, {"system_id": "machine-2", "domain": "machine", "label": "Pump"}], [], [], [])
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text(json.dumps(old), encoding="utf-8")
    new_path.write_text(json.dumps(new), encoding="utf-8")
    result = compare_books(old_path, old["lineage_hash"], new_path, new["lineage_hash"])
    change = next(item for item in result["changes"] if item["id"] == "machine-2")
    assert change["kind"] == "systems"
    assert change["classification"] == "ADDED"
    assert change["from_record_hash"] is None
    assert isinstance(change["to_record_hash"], str)


def test_removed_record_has_no_new_hash(tmp_path):
    import json
    old = build_general_system_lineage([{"system_id": "machine-1", "domain": "machine", "label": "Motor"}, {"system_id": "machine-2", "domain": "machine", "label": "Pump"}], [], [], [])
    new = build_general_system_lineage([{"system_id": "machine-1", "domain": "machine", "label": "Motor"}], [], [], [])
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text(json.dumps(old), encoding="utf-8")
    new_path.write_text(json.dumps(new), encoding="utf-8")
    result = compare_books(old_path, old["lineage_hash"], new_path, new["lineage_hash"])
    change = next(item for item in result["changes"] if item["id"] == "machine-2")
    assert change["kind"] == "systems"
    assert change["classification"] == "REMOVED"
    assert isinstance(change["from_record_hash"], str)
    assert change["to_record_hash"] is None


def test_changed_id_is_removed_and_added(tmp_path):
    import json
    old = build_general_system_lineage([{"system_id": "machine-1", "domain": "machine", "label": "Motor"}], [], [], [])
    new = build_general_system_lineage([{"system_id": "renamed", "domain": "machine", "label": "Motor"}], [], [], [])
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text(json.dumps(old), encoding="utf-8")
    new_path.write_text(json.dumps(new), encoding="utf-8")
    result = compare_books(old_path, old["lineage_hash"], new_path, new["lineage_hash"])
    changes = {(item["kind"], item["id"]): item for item in result["changes"]}
    assert changes[("systems", "machine-1")]["classification"] == "REMOVED"
    assert changes[("systems", "renamed")]["classification"] == "ADDED"


def test_wrong_retained_identity_is_rejected(tmp_path):
    import json
    import pytest
    report = build_general_system_lineage([{"system_id": "machine-1", "domain": "machine", "label": "Motor"}], [], [], [])
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError):
        compare_books(path, report["lineage_hash"], path, "0" * 64)


def test_comparison_is_deterministic_and_read_only(tmp_path):
    import json
    old = build_general_system_lineage([{"system_id": "machine-1", "domain": "machine", "label": "Motor"}], [], [], [])
    new = build_general_system_lineage([{"system_id": "machine-1", "domain": "machine", "label": "Revised"}], [], [], [])
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text(json.dumps(old), encoding="utf-8")
    new_path.write_text(json.dumps(new), encoding="utf-8")
    before = (old_path.read_bytes(), new_path.read_bytes())
    first = compare_books(old_path, old["lineage_hash"], new_path, new["lineage_hash"])
    second = compare_books(old_path, old["lineage_hash"], new_path, new["lineage_hash"])
    assert first == second
    assert before == (old_path.read_bytes(), new_path.read_bytes())


def test_comparison_claims_no_authority_or_ancestry(tmp_path):
    import json
    report = build_general_system_lineage([{"system_id": "machine-1", "domain": "machine", "label": "Motor"}], [], [], [])
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    result = compare_books(path, report["lineage_hash"], path, report["lineage_hash"])
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["ancestry_established"] is False

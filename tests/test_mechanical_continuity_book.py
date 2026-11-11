
"""Tests for the read-only Mechanical Continuity Book."""

import json
import subprocess
import sys
from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.general_system_lineage import (
    build_general_system_lineage,
)
from holosim.mechanical_continuity_book import (
    MechanicalContinuityBookError,
    contents,
    open_book,
    read_page,
)


def make_report():
    systems = [
        {"system_id": "machine-1", "domain": "machine", "label": "Motor"},
        {"system_id": "software-1", "domain": "software", "label": "Controller"},
    ]
    observations = [
        {
            "observation_id": "observation-1",
            "system_id": "machine-1",
            "source_id": "sensor-1",
            "boundary": "2026-11-10T00:00:00Z",
            "evidence_hash": "a" * 64,
            "finding": {"temperature": 42},
        },
    ]
    relationships = [
        {
            "relationship_id": "relationship-1",
            "source_system_id": "software-1",
            "target_system_id": "machine-1",
            "relationship_type": "controls",
            "evidence_observation_ids": ["observation-1"],
            "status": "PROPOSED",
        },
    ]
    corrections = [
        {
            "correction_id": "correction-1",
            "target_record_hash": stable_hash(relationships[0]),
            "evidence_observation_ids": ["observation-1"],
            "assessment": "Requires independent confirmation",
        },
    ]
    return build_general_system_lineage(
        systems, observations, relationships, corrections
    )


def persist(tmp_path, report=None):
    report = make_report() if report is None else report
    path = tmp_path / "lineage.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path, report


def test_open_verified_report_without_mutation(tmp_path):
    path, report = persist(tmp_path)
    before = path.read_bytes()

    opened = open_book(path, report["lineage_hash"])

    assert opened == report
    assert path.read_bytes() == before


def test_contents_preserve_explicit_record_identities():
    report = make_report()
    entries = contents(report)

    assert len(entries) == 5
    assert [(item["kind"], item["id"]) for item in entries] == [
        ("systems", "machine-1"),
        ("systems", "software-1"),
        ("observations", "observation-1"),
        ("relationships", "relationship-1"),
        ("corrections", "correction-1"),
    ]


def test_read_page_returns_exact_record_and_hash():
    report = make_report()
    page = read_page(report, "relationships", "relationship-1")

    assert page["record"] == report["relationships"][0]
    assert page["record_hash"] == stable_hash(report["relationships"][0])


def test_page_mutation_does_not_change_source():
    report = make_report()
    original = deepcopy(report)

    page = read_page(report, "observations", "observation-1")
    page["record"]["finding"]["temperature"] = 999

    assert report == original


@pytest.mark.parametrize(
    "kind,record_id",
    [
        ("missing", "machine-1"),
        ("systems", "missing"),
        ("observations", "machine-1"),
    ],
)
def test_unknown_page_rejected(kind, record_id):
    with pytest.raises(MechanicalContinuityBookError):
        read_page(make_report(), kind, record_id)


def test_retained_identity_rejects_self_consistent_replacement(tmp_path):
    original = make_report()
    path, _ = persist(tmp_path, original)

    replacement = deepcopy(original)
    replacement["systems"][0]["label"] = "Replacement Motor"
    replacement["lineage_hash"] = stable_hash({
        key: value
        for key, value in replacement.items()
        if key != "lineage_hash"
    })
    path.write_text(json.dumps(replacement), encoding="utf-8")

    with pytest.raises(
        MechanicalContinuityBookError,
        match="retained lineage identity mismatch",
    ):
        open_book(path, original["lineage_hash"])


def test_nested_tampering_rejected(tmp_path):
    path, report = persist(tmp_path)
    report["observations"][0]["finding"]["temperature"] = 999
    path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(MechanicalContinuityBookError):
        open_book(path, report["lineage_hash"])


def test_duplicate_json_keys_rejected(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"type":"x","type":"y"}', encoding="utf-8")

    with pytest.raises(
        MechanicalContinuityBookError,
        match="duplicate JSON key",
    ):
        open_book(path, "a" * 64)


@pytest.mark.parametrize("expected", ["bad", "A" * 64, None])
def test_invalid_retained_identity_rejected(tmp_path, expected):
    path, _ = persist(tmp_path)

    with pytest.raises(MechanicalContinuityBookError):
        open_book(path, expected)


def test_missing_artifact_rejected(tmp_path):
    with pytest.raises(MechanicalContinuityBookError):
        open_book(tmp_path / "missing.json", "a" * 64)


def test_fresh_process_reopens_and_reads_same_record(tmp_path):
    path, report = persist(tmp_path)
    before = path.read_bytes()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "holosim.mechanical_continuity_book",
            str(path),
            "--expected-hash",
            report["lineage_hash"],
            "--kind",
            "observations",
            "--id",
            "observation-1",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    page = json.loads(result.stdout)
    assert page["record"] == report["observations"][0]
    assert path.read_bytes() == before


def test_fresh_process_rejects_wrong_identity(tmp_path):
    path, _ = persist(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "holosim.mechanical_continuity_book",
            str(path),
            "--expected-hash",
            "0" * 64,
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "REJECTED"

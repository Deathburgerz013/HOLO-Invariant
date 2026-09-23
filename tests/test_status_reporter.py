import pytest

from holosim.status_reporter import build_status_report


def _audit():
    return {
        "type": "holo_invariant_audit",
        "version": 2,
        "valid": True,
        "status": "PASS",
        "integrity_percent": 100.0,
        "operational_status": "clean",
    }


def _spine():
    return {
        "type": "holo_spine_validation_report",
        "version": "0.1",
        "overall_status": "PASS",
        "summary": {
            "expected_spines": 8,
            "discovered_spines": 8,
            "missing_spines": 0,
            "failed_spines": 0,
            "additional_spines": 0,
        },
    }


def test_status_report_preserves_subsystem_reports():
    result = build_status_report(
        invariant_audit=_audit(),
        spine_validation=_spine(),
    )

    assert result["invariant_audit"] == _audit()
    assert result["spine_validation"] == _spine()


def test_status_report_represents_missing_subsystem():
    result = build_status_report(
        invariant_audit=_audit(),
        spine_validation=None,
    )

    assert result["invariant_audit"] == _audit()
    assert result["spine_validation"] is None


def test_status_report_preserves_conflicting_statuses():
    spine = _spine()
    spine["overall_status"] = "FAIL"

    result = build_status_report(
        invariant_audit=_audit(),
        spine_validation=spine,
    )

    assert result["invariant_audit"]["status"] == "PASS"
    assert result["spine_validation"]["overall_status"] == "FAIL"


def test_status_report_does_not_upgrade_evidence():
    audit = _audit()
    audit["valid"] = False
    audit["status"] = "FAIL"

    result = build_status_report(
        invariant_audit=audit,
        spine_validation=_spine(),
    )

    assert result["invariant_audit"]["valid"] is False
    assert result["invariant_audit"]["status"] == "FAIL"


def test_status_report_is_deterministic():
    first = build_status_report(
        invariant_audit=_audit(),
        spine_validation=_spine(),
    )
    second = build_status_report(
        invariant_audit=_audit(),
        spine_validation=_spine(),
    )

    assert first == second


def test_status_report_fails_closed_for_invalid_report():
    with pytest.raises(ValueError):
        build_status_report(
            invariant_audit={"status": "PASS"},
            spine_validation=_spine(),
        )


def test_status_report_has_no_authority():
    result = build_status_report(
        invariant_audit=_audit(),
        spine_validation=_spine(),
    )

    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
def test_status_report_does_not_mutate_source_reports():
    audit = _audit()
    spine = _spine()

    original_audit = audit.copy()
    original_spine = spine.copy()

    result = build_status_report(
        invariant_audit=audit,
        spine_validation=spine,
    )

    result["invariant_audit"]["status"] = "CHANGED"
    result["spine_validation"]["overall_status"] = "CHANGED"

    assert audit == original_audit
    assert spine == original_spine
def test_status_report_has_deterministic_report_hash():
    first = build_status_report(
        invariant_audit=_audit(),
        spine_validation=_spine(),
    )
    second = build_status_report(
        invariant_audit=_audit(),
        spine_validation=_spine(),
    )

    assert type(first["report_hash"]) is str
    assert len(first["report_hash"]) == 64
    assert first["report_hash"] == second["report_hash"]
def test_status_report_hash_detects_tampering():
    from holosim.status_reporter import verify_status_report

    report = build_status_report(
        invariant_audit=_audit(),
        spine_validation=_spine(),
    )

    assert verify_status_report(report) is True

    report["invariant_audit"]["status"] = "FAIL"

    with pytest.raises(ValueError):
        verify_status_report(report)
def test_status_report_verifier_rejects_authority_change():
    from holosim.status_reporter import verify_status_report

    report = build_status_report(
        invariant_audit=_audit(),
        spine_validation=_spine(),
    )

    report["accepted"] = True

    with pytest.raises(ValueError):
        verify_status_report(report)
def test_status_report_preserves_real_audit_state():
    from holosim.invariant_audit import audit_repository

    audit = audit_repository(
        repo_root=__import__("pathlib").Path("."),
        receipt_dir=__import__("pathlib").Path("runtime_watch/receipts"),
        chain_path=__import__("pathlib").Path("holo_memory.jsonl"),
        merkle_path=__import__("pathlib").Path("holo_merkle.jsonl"),
    )

    result = build_status_report(
        invariant_audit=audit,
        spine_validation=None,
    )

    assert result["invariant_audit"]["type"] == "holo_invariant_audit"
    assert result["invariant_audit"]["version"] == 2
    assert result["invariant_audit"]["status"] == audit["status"]
    assert result["invariant_audit"]["valid"] == audit["valid"]
    assert result["invariant_audit"]["operational_status"] == audit["operational_status"]
def test_status_report_preserves_real_spine_state_without_writing_report():
    from pathlib import Path

    from holosim.spine_validator import HoloSpineValidator

    validator = HoloSpineValidator(
        repo_root=Path("."),
        chain_path=Path("holo_memory.jsonl"),
        report_path=Path("Spine_Validation_Report.json"),
    )

    spine = validator.run(write_report=False)

    result = build_status_report(
        invariant_audit=None,
        spine_validation=spine,
    )

    assert result["spine_validation"]["type"] == "holo_spine_validation_report"
    assert result["spine_validation"]["version"] == "0.1"
    assert result["spine_validation"]["overall_status"] == spine["overall_status"]
    assert result["spine_validation"]["summary"] == spine["summary"]
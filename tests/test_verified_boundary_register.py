from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from holosim.guarantee_registry import (
    compare_boundary_register_completeness,
    discover_receipt_boundaries,
    GuaranteeRegistryError,
    load_boundary_register,
    lookup_boundary,
    validate_boundary_register,
    verify_boundary_register,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTER_PATH = ROOT / "core" / "verified_boundary_register.json"


def register() -> dict[str, object]:
    return load_boundary_register(REGISTER_PATH)


def rehash(value: dict[str, object]) -> None:
    from holosim.guarantee_registry import _canonical_hash

    body = {key: item for key, item in value.items() if key != "register_hash"}
    value["register_hash"] = _canonical_hash(body)


def test_committed_register_verifies_current_boundaries() -> None:
    result = verify_boundary_register(register(), root=ROOT)
    assert result["status"] == "PASS"
    assert len(result["results"]) == 10
    assert all(item["status"] == "PASS" for item in result["results"])
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_each_recent_boundary_has_one_keyed_slot() -> None:
    expected = {
        "agent-verified-convergence",
        "bounded-architect",
        "bounded-evidence-analyst",
        "choice-consequence-oracle",
        "deterministic-boundary-key-maker",
        "functional-awareness-loop",
        "genesis-origins",
        "python-surface-inventory",
        "time-scoped-truth",
        "verified-recall",
    }
    assert {item["boundary_id"] for item in register()["boundaries"]} == expected


def test_lookup_returns_exact_slot() -> None:
    item = lookup_boundary(register(), "functional-awareness-loop")
    assert item["module"] == "holosim.functional_awareness_loop"
    assert item["receipts"][0]["verifier"] == "verify_functional_awareness_receipt"


def test_unknown_lookup_fails_closed() -> None:
    with pytest.raises(GuaranteeRegistryError, match="not registered"):
        lookup_boundary(register(), "unknown-boundary")


def test_duplicate_boundary_id_is_rejected_even_if_rehashed() -> None:
    value = register()
    value["boundaries"].append(deepcopy(value["boundaries"][0]))
    rehash(value)
    with pytest.raises(GuaranteeRegistryError, match="duplicate boundary_id"):
        validate_boundary_register(value)


def test_extra_field_is_rejected_even_if_rehashed() -> None:
    value = register()
    value["boundaries"][0]["authority"] = "SELF"
    rehash(value)
    with pytest.raises(GuaranteeRegistryError, match="boundary fields"):
        validate_boundary_register(value)


def test_authority_is_rejected_even_if_rehashed() -> None:
    value = register()
    value["accepted"] = True
    rehash(value)
    with pytest.raises(GuaranteeRegistryError, match="forbidden authority"):
        validate_boundary_register(value)


def test_register_hash_tamper_is_rejected() -> None:
    value = register()
    value["register_hash"] = "0" * 64
    with pytest.raises(GuaranteeRegistryError, match="hash mismatch"):
        validate_boundary_register(value)


@pytest.mark.parametrize(
    ("target", "expected_failure"),
    [
        ("implementation", "implementation_hash_mismatch"),
        ("test", "test_hash_mismatch"),
    ],
)
def test_changed_registered_artifact_is_detected(
    tmp_path: Path, target: str, expected_failure: str
) -> None:
    value = register()
    item = value["boundaries"][0]
    implementation = tmp_path / item["implementation_path"]
    test = tmp_path / item["test_path"]
    implementation.parent.mkdir(parents=True)
    test.parent.mkdir(parents=True)
    implementation.write_bytes((ROOT / item["implementation_path"]).read_bytes())
    test.write_bytes((ROOT / item["test_path"]).read_bytes())
    (implementation if target == "implementation" else test).write_text(
        "changed\n", encoding="utf-8"
    )
    value["boundaries"] = [item]
    rehash(value)
    result = verify_boundary_register(value, root=tmp_path)
    assert result["status"] == "FAIL"
    assert expected_failure in result["results"][0]["failures"]


def test_missing_registered_verifier_is_detected(tmp_path: Path) -> None:
    value = register()
    item = deepcopy(value["boundaries"][0])
    item["receipts"] = [item["receipts"][0]]
    source_path = tmp_path / item["implementation_path"]
    test_path = tmp_path / item["test_path"]
    source_path.parent.mkdir(parents=True)
    test_path.parent.mkdir(parents=True)
    source = (
        f'{item["receipts"][0]["type_constant"]} = {item["receipts"][0]["type"]!r}\n'
        f'{item["receipts"][0]["version_constant"]} = {item["receipts"][0]["version"]}\n'
    )
    source_path.write_text(source, encoding="utf-8")
    test_path.write_text("test evidence\n", encoding="utf-8")
    item["implementation_sha256"] = hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()
    item["test_sha256"] = hashlib.sha256(
        b"test evidence\n"
    ).hexdigest()
    value["boundaries"] = [item]
    rehash(value)
    result = verify_boundary_register(value, root=tmp_path)
    assert result["status"] == "FAIL"
    assert result["results"][0]["failures"] == [
        "verifier_missing:" + item["receipts"][0]["verifier"]
    ]


def test_lf_and_crlf_have_the_same_registered_source_identity(
    tmp_path: Path,
) -> None:
    value = register()
    item = deepcopy(value["boundaries"][0])
    source_path = tmp_path / item["implementation_path"]
    test_path = tmp_path / item["test_path"]
    source_path.parent.mkdir(parents=True)
    test_path.parent.mkdir(parents=True)
    source_lf = (ROOT / item["implementation_path"]).read_text(
        encoding="utf-8"
    ).replace("\r\n", "\n")
    test_lf = (ROOT / item["test_path"]).read_text(
        encoding="utf-8"
    ).replace("\r\n", "\n")
    source_path.write_bytes(source_lf.replace("\n", "\r\n").encode("utf-8"))
    test_path.write_bytes(test_lf.replace("\n", "\r\n").encode("utf-8"))
    item["implementation_sha256"] = hashlib.sha256(
        source_lf.encode("utf-8")
    ).hexdigest()
    item["test_sha256"] = hashlib.sha256(test_lf.encode("utf-8")).hexdigest()
    value["boundaries"] = [item]
    rehash(value)
    result = verify_boundary_register(value, root=tmp_path)
    assert result["status"] == "PASS"


def test_committed_json_is_canonical_data_not_generated_authority() -> None:
    raw = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
    assert raw["accepted"] is False
    assert raw["write_authority"] == "NONE"


def test_discovery_finds_current_versioned_receipt_boundaries() -> None:
    discovered = discover_receipt_boundaries(root=ROOT)
    assert len(discovered) == 21
    paths = {item["implementation_path"] for item in discovered}
    assert "holosim/functional_awareness_loop.py" in paths
    assert "holosim/time_scoped_truth.py" in paths


def test_completeness_preserves_current_unregistered_baseline() -> None:
    result = compare_boundary_register_completeness(register(), root=ROOT)
    assert result["status"] == "INCOMPLETE"
    assert result["counts"] == {
        "REGISTERED": 10,
        "UNREGISTERED": 11,
        "STALE": 0,
    }
    assert [
        item["implementation_path"]
        for item in result["results"]
        if item["status"] == "UNREGISTERED"
    ] == [
        "holosim/bounded_repository_compression_evaluator.py",
        "holosim/bounded_transformation_engine.py",
        "holosim/environment_episode_reopen_receipt.py",
        "holosim/environment_invariant_receipts.py",
        "holosim/fact_identity.py",
        "holosim/functional_motion_equivalence.py",
        "holosim/interpretation.py",
        "holosim/perceptual_capability_boundary.py",
        "holosim/semantic_signal_loss_receipts.py",
        "holosim/spine_admission.py",
        "holosim/transition_receipt.py",
    ]
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_discovery_reports_new_boundary_against_existing_register(
    tmp_path: Path,
) -> None:
    package = tmp_path / "holosim"
    package.mkdir()
    source = package / "new_boundary.py"
    source.write_text(
        'RECEIPT_TYPE = "new_receipt"\n'
        "RECEIPT_VERSION = 1\n"
        "def verify_new_receipt(receipt):\n"
        "    return True\n",
        encoding="utf-8",
    )
    value = register()
    result = compare_boundary_register_completeness(value, root=tmp_path)
    assert result["status"] == "INCOMPLETE"
    assert result["counts"]["UNREGISTERED"] == 1
    matching = [
        item for item in result["results"]
        if item["implementation_path"] == "holosim/new_boundary.py"
    ]
    assert matching[0]["status"] == "UNREGISTERED"


def test_discovery_reports_changed_registered_contract_as_stale(
    tmp_path: Path,
) -> None:
    value = register()
    item = value["boundaries"][0]
    source = tmp_path / item["implementation_path"]
    source.parent.mkdir(parents=True)
    receipt = item["receipts"][0]
    source.write_text(
        f'{receipt["type_constant"]} = "changed_type"\n'
        f'{receipt["version_constant"]} = {receipt["version"]}\n'
        f'def {receipt["verifier"]}(receipt):\n'
        "    return True\n",
        encoding="utf-8",
    )
    result = compare_boundary_register_completeness(value, root=tmp_path)
    matching = [
        entry for entry in result["results"]
        if entry["implementation_path"] == item["implementation_path"]
    ]
    assert matching[0]["status"] == "STALE"

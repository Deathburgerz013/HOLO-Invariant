from copy import deepcopy
import hashlib

import pytest

from holosim.guarantee_registry import (
    GuaranteeRegistryError,
    _canonical_hash,
    observe_boundary_register,
    verify_boundary_register_observation,
)


SOURCE = ('RECEIPT_TYPE = "example_receipt"\nRECEIPT_VERSION = 1\n'
          'def verify_example(receipt):\n    return True\n')


def sha(content):
    return hashlib.sha256(content).hexdigest()


@pytest.fixture
def setup(tmp_path):
    (tmp_path / "holosim").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "holosim/first.py").write_bytes(SOURCE.encode())
    (tmp_path / "tests/test_first.py").write_bytes(b"# test source\n")
    body = {
        "type": "holo_verified_boundary_register", "version": 1,
        "boundaries": [{
            "boundary_id": "first", "module": "holosim.first",
            "implementation_path": "holosim/first.py",
            "implementation_sha256": sha(SOURCE.encode()),
            "receipts": [{
                "type_constant": "RECEIPT_TYPE", "type": "example_receipt",
                "version_constant": "RECEIPT_VERSION", "version": 1,
                "verifier": "verify_example",
            }],
            "test_path": "tests/test_first.py",
            "test_sha256": sha(b"# test source\n"),
        }],
        "accepted": False, "write_authority": "NONE",
    }
    return tmp_path, {**body, "register_hash": _canonical_hash(body)}


def artifacts(report):
    return {item["path"]: item for item in report["artifacts"]}


def baseline(report):
    return {item["path"]: item["sha256"] for item in report["artifacts"]
            if item["sha256"] is not None}


def test_unregistered_placeholder_preserves_unknowns(setup):
    root, register = setup
    (root / "holosim/new.py").write_text(SOURCE + "# new\n")
    before = deepcopy(register)
    report = observe_boundary_register(register, root=root)
    placeholder = next(x for x in report["boundaries"] if x["placeholder"])
    assert placeholder["implementation_path"] == "holosim/new.py"
    assert placeholder["status"] == "UNREGISTERED"
    assert placeholder["boundary_id"] is None and placeholder["test_path"] is None
    assert placeholder["verifiers"] == ["verify_example"]
    assert artifacts(report)["holosim/new.py"]["change_status"] == "UNKNOWN"
    assert register == before
    assert report["accepted"] is False and report["write_authority"] == "NONE"
    assert verify_boundary_register_observation(report, register, root=root)["valid"]


def test_registered_source_edit_is_independent_of_registration(setup):
    root, register = setup
    (root / "holosim/first.py").write_text(SOURCE + "# edit\n")
    report = observe_boundary_register(register, root=root)
    assert report["boundaries"][0]["status"] == "REGISTERED"
    assert report["integrity_check"]["status"] == "FAIL"
    item = artifacts(report)["holosim/first.py"]
    assert item["change_status"] == "EDITED"
    assert item["comparison_basis"] == "REGISTERED_TEXT_SHA256"


def test_unregistered_edit_uses_explicit_prior_raw_baseline(setup):
    root, register = setup
    path = root / "holosim/new.py"
    path.write_text(SOURCE + "# original\n")
    first = observe_boundary_register(register, root=root)
    prior = baseline(first)
    path.write_text(SOURCE + "# changed\n")
    report = observe_boundary_register(register, root=root, baseline=prior)
    item = artifacts(report)["holosim/new.py"]
    assert item["change_status"] == "EDITED"
    assert item["comparison_basis"] == "PRIOR_RAW_SHA256"
    assert item["comparison_sha256"] == prior["holosim/new.py"]
    assert verify_boundary_register_observation(
        report, register, root=root, baseline=prior
    )["valid"]
    assert not verify_boundary_register_observation(report, register, root=root)["valid"]


def test_new_path_with_supplied_baseline_has_unknown_change(setup):
    root, register = setup
    prior = baseline(observe_boundary_register(register, root=root))
    (root / "holosim/new.py").write_text(SOURCE)
    report = observe_boundary_register(register, root=root, baseline=prior)
    assert artifacts(report)["holosim/new.py"]["change_status"] == "UNKNOWN"


def test_byte_identical_peers_are_symmetric_without_merging(setup):
    root, register = setup
    (root / "holosim/copy.py").write_bytes(SOURCE.encode())
    report = observe_boundary_register(register, root=root)
    items = artifacts(report)
    assert items["holosim/first.py"]["duplicate_paths"] == ["holosim/copy.py"]
    assert items["holosim/copy.py"]["duplicate_paths"] == ["holosim/first.py"]
    assert items["holosim/copy.py"]["duplicate_status"] == "BYTE_IDENTICAL"
    assert len(report["boundaries"]) == 2


def test_line_endings_have_distinct_raw_duplicate_and_edit_identity(setup):
    root, register = setup
    prior = baseline(observe_boundary_register(register, root=root))
    (root / "holosim/first.py").write_bytes(SOURCE.replace("\n", "\r\n").encode())
    (root / "holosim/copy.py").write_bytes(SOURCE.encode())
    report = observe_boundary_register(register, root=root)
    item = artifacts(report)["holosim/first.py"]
    assert item["change_status"] == "UNCHANGED"
    assert item["duplicate_status"] == "NO_BYTE_IDENTICAL_PEER"
    assert report["integrity_check"]["status"] == "PASS"
    raw_report = observe_boundary_register(register, root=root, baseline=prior)
    assert artifacts(raw_report)["holosim/first.py"]["change_status"] == "EDITED"


def test_missing_source_is_not_a_duplicate_or_silent_unchanged(setup):
    root, register = setup
    (root / "holosim/first.py").unlink()
    item = artifacts(observe_boundary_register(register, root=root))["holosim/first.py"]
    assert item["change_status"] == "MISSING"
    assert item["sha256"] is None and item["size_bytes"] is None
    assert item["duplicate_status"] == "UNAVAILABLE"
    assert item["duplicate_paths"] == []


def test_changed_test_source_is_observed(setup):
    root, register = setup
    (root / "tests/test_first.py").write_text("# edited test\n")
    report = observe_boundary_register(register, root=root)
    assert artifacts(report)["tests/test_first.py"]["change_status"] == "EDITED"


def test_removed_unregistered_source_remains_missing_in_baseline_inventory(setup):
    root, register = setup
    path = root / "holosim/new.py"
    path.write_text(SOURCE)
    prior = baseline(observe_boundary_register(register, root=root))
    path.unlink()
    report = observe_boundary_register(register, root=root, baseline=prior)
    assert artifacts(report)["holosim/new.py"]["change_status"] == "MISSING"
    assert all(x["implementation_path"] != "holosim/new.py" for x in report["boundaries"])


def test_symlink_source_fails_observation(setup):
    root, register = setup
    test = root / "tests/test_first.py"
    test.unlink()
    try:
        test.symlink_to(root / "holosim/first.py")
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(GuaranteeRegistryError, match="symlinks"):
        observe_boundary_register(register, root=root)


def test_current_source_change_invalidates_previous_observation(setup):
    root, register = setup
    report = observe_boundary_register(register, root=root)
    (root / "holosim/first.py").write_text(SOURCE + "# later\n")
    assert not verify_boundary_register_observation(report, register, root=root)["valid"]


@pytest.mark.parametrize("field,value", [
    ("change_status", "EDITED"),
    ("duplicate_status", "BYTE_IDENTICAL"),
    ("duplicate_paths", ["fabricated.py"]),
    ("size_bytes", True),
])
def test_forged_marker_rejected_even_if_rehashed(setup, field, value):
    root, register = setup
    report = observe_boundary_register(register, root=root)
    report["artifacts"][0][field] = value
    body = {k: v for k, v in report.items() if k != "observation_hash"}
    report["observation_hash"] = _canonical_hash(body)
    assert not verify_boundary_register_observation(report, register, root=root)["valid"]


@pytest.mark.parametrize("prior", [[], {"../escape.py": "a" * 64},
                                     {"/absolute.py": "a" * 64},
                                     {"bad.py": "invalid"},
                                     {"a\\b.py": "a" * 64}])
def test_malformed_baseline_fails_closed(setup, prior):
    root, register = setup
    with pytest.raises(GuaranteeRegistryError):
        observe_boundary_register(register, root=root, baseline=prior)


def test_observation_is_deterministic_and_preserves_bytes(setup):
    root, register = setup
    before = (root / "holosim/first.py").read_bytes()
    first = observe_boundary_register(register, root=root)
    assert first == observe_boundary_register(register, root=root)
    assert (root / "holosim/first.py").read_bytes() == before


def test_plain_python_without_receipt_contract_is_outside_discovery(setup):
    root, register = setup
    (root / "holosim/plain.py").write_text("def plain():\n    return 1\n")
    report = observe_boundary_register(register, root=root)
    assert "holosim/plain.py" not in artifacts(report)


def test_baseline_order_is_canonical(setup):
    root, register = setup
    prior = baseline(observe_boundary_register(register, root=root))
    reversed_prior = dict(reversed(list(prior.items())))
    assert observe_boundary_register(register, root=root, baseline=prior) == (
        observe_boundary_register(register, root=root, baseline=reversed_prior)
    )

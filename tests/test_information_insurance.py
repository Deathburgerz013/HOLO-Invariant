import hashlib

from holosim.information_insurance import assess_information_insurance


def test_copies_in_declared_failed_domain_do_not_establish_protection():
    original = b"HOLO continuity evidence"
    digest = hashlib.sha256(original).hexdigest()

    result = assess_information_insurance(
        expected_sha256=digest,
        copies=[
            {
                "copy_id": "primary",
                "data": original,
                "failure_domain": "device-A",
            },
            {
                "copy_id": "backup",
                "data": original,
                "failure_domain": "device-A",
            },
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["surviving_verified_copies"] == 0
    assert result["write_authority"] == "NONE"


def test_surviving_copy_without_independence_evidence_is_unknown():
    original = b"HOLO continuity evidence"
    digest = hashlib.sha256(original).hexdigest()

    result = assess_information_insurance(
        expected_sha256=digest,
        copies=[
            {
                "copy_id": "backup",
                "data": original,
                "failure_domain": "device-B",
            },
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["reconstruction_sufficient"] is True
    assert result["verified_raw_copies"] == 1
    assert result["survival_independently_verified"] is False
    assert result["failure_model"] == "DECLARED_ONLY"
    assert result["write_authority"] == "NONE"


def test_surviving_copy_with_conflicting_domain_evidence_is_unknown():
    original = b"HOLO continuity evidence"
    digest = hashlib.sha256(original).hexdigest()

    result = assess_information_insurance(
        expected_sha256=digest,
        copies=[
            {
                "copy_id": "backup",
                "data": original,
                "failure_domain": "device-B",
                "domain_evidence": [
                    {"observed_domain": "device-A"},
                    {"observed_domain": "device-B"},
                ],
            },
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["write_authority"] == "NONE"


def test_observer_labels_do_not_establish_independent_protection():
    original = b"HOLO continuity evidence"
    digest = hashlib.sha256(original).hexdigest()

    result = assess_information_insurance(
        expected_sha256=digest,
        copies=[
            {
                "copy_id": "backup",
                "data": original,
                "failure_domain": "device-B",
                "domain_evidence": [
                    {"observer": "observer-1", "observed_domain": "device-B"},
                    {"observer": "observer-2", "observed_domain": "device-B"},
                ],
            },
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["surviving_verified_copies"] == 1
    assert result["write_authority"] == "NONE"


def test_surviving_copy_with_unusable_data_is_not_counted():
    original = b"HOLO continuity evidence"
    digest = hashlib.sha256(original).hexdigest()

    result = assess_information_insurance(
        expected_sha256=digest,
        copies=[
            {
                "copy_id": "backup",
                "data": None,
                "failure_domain": "device-B",
            },
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["surviving_verified_copies"] == 0
    assert result["write_authority"] == "NONE"


def test_empty_inventory_without_completeness_evidence_is_unknown():
    digest = hashlib.sha256(b"HOLO continuity evidence").hexdigest()

    result = assess_information_insurance(
        expected_sha256=digest,
        copies=[],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["surviving_verified_copies"] == 0
    assert result["write_authority"] == "NONE"


def test_failed_domain_copy_without_complete_inventory_is_unknown():
    original = b"HOLO continuity evidence"
    digest = hashlib.sha256(original).hexdigest()

    result = assess_information_insurance(
        expected_sha256=digest,
        copies=[
            {
                "copy_id": "primary",
                "data": original,
                "failure_domain": "device-A",
            },
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["surviving_verified_copies"] == 0
    assert result["write_authority"] == "NONE"
import hashlib

from holosim.lossless_file_breaker import create_lossless_file_break


def test_verified_surviving_workspace_under_declared_failure(tmp_path):
    original = b"HOLO information insurance recovery evidence"
    source = tmp_path / "source.bin"
    workspace = tmp_path / "surviving-workspace"

    source.write_bytes(original)

    create_lossless_file_break(
        source,
        workspace,
        max_chunk_bytes=8,
    )

    # Simulate primary-source loss. The workspace remains available.
    source.unlink()

    result = assess_information_insurance(
        expected_sha256=hashlib.sha256(original).hexdigest(),
        copies=[
            {
                "copy_id": "recovery-workspace",
                "failure_domain": "device-B",
                "workspace_path": workspace,
            }
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["reconstruction_sufficient"] is True
    assert result["surviving_verified_copies"] == 1
    assert result["write_authority"] == "NONE"


def test_corrupted_surviving_workspace_is_not_protected(tmp_path):
    original = b"HOLO information insurance recovery evidence"
    source = tmp_path / "source.bin"
    workspace = tmp_path / "surviving-workspace"

    source.write_bytes(original)

    manifest = create_lossless_file_break(
        source,
        workspace,
        max_chunk_bytes=8,
    )

    source.unlink()

    # Corrupt one chunk after workspace creation.
    chunk_path = workspace / manifest["chunks"][0]["filename"]
    chunk_path.write_bytes(b"CORRUPTED")

    result = assess_information_insurance(
        expected_sha256=hashlib.sha256(original).hexdigest(),
        copies=[
            {
                "copy_id": "corrupted-workspace",
                "failure_domain": "device-B",
                "workspace_path": workspace,
            }
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["surviving_verified_copies"] == 0
    assert result["write_authority"] == "NONE"


def test_unverified_domain_label_cannot_establish_protection(tmp_path):
    original = b"HOLO insurance independence boundary"
    source = tmp_path / "source.bin"
    workspace = tmp_path / "recovery"

    source.write_bytes(original)

    create_lossless_file_break(
        source,
        workspace,
        max_chunk_bytes=8,
    )

    result = assess_information_insurance(
        expected_sha256=hashlib.sha256(original).hexdigest(),
        copies=[
            {
                "copy_id": "claimed-backup",
                "failure_domain": "device-B",
                "workspace_path": workspace,
            }
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["surviving_verified_copies"] == 1
    assert result["write_authority"] == "NONE"


def test_missing_failure_domain_fails_closed():
    original = b"HOLO malformed evidence"
    digest = hashlib.sha256(original).hexdigest()

    result = assess_information_insurance(
        expected_sha256=digest,
        copies=[
            {
                "copy_id": "unlocated-copy",
                "data": original,
            }
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["reconstruction_sufficient"] is False
    assert result["survival_independently_verified"] is False
    assert result["write_authority"] == "NONE"


def test_malformed_inventory_entry_fails_closed():
    original = b"HOLO malformed inventory"
    digest = hashlib.sha256(original).hexdigest()

    result = assess_information_insurance(
        expected_sha256=digest,
        copies=[
            None,
            "not-a-copy",
            {
                "copy_id": "valid-copy",
                "data": original,
                "failure_domain": "device-B",
            },
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["reconstruction_sufficient"] is False
    assert result["survival_independently_verified"] is False
    assert result["write_authority"] == "NONE"


def test_malformed_failed_domains_fails_closed():
    original = b"HOLO failure model validation"

    result = assess_information_insurance(
        expected_sha256=hashlib.sha256(original).hexdigest(),
        copies=[
            {
                "copy_id": "backup",
                "data": original,
                "failure_domain": "device-B",
            }
        ],
        failed_domains=None,
    )

    assert result["status"] == "UNKNOWN"
    assert result["reconstruction_sufficient"] is False
    assert result["surviving_verified_copies"] == 0
    assert result["survival_independently_verified"] is False
    assert result["write_authority"] == "NONE"


def test_invalid_expected_digest_fails_closed():
    result = assess_information_insurance(
        expected_sha256=None,
        copies=[
            {
                "copy_id": "backup",
                "data": b"HOLO evidence",
                "failure_domain": "device-B",
            }
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["reconstruction_sufficient"] is False
    assert result["surviving_verified_copies"] == 0
    assert result["write_authority"] == "NONE"


def test_excessive_copy_inventory_fails_closed():
    original = b"HOLO bounded inventory"
    digest = hashlib.sha256(original).hexdigest()

    result = assess_information_insurance(
        expected_sha256=digest,
        copies=[
            {"data": original, "failure_domain": "device-B"}
            for _ in range(257)
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["reconstruction_sufficient"] is False
    assert result["surviving_verified_copies"] == 0
    assert result["write_authority"] == "NONE"


def test_oversized_raw_copy_fails_closed():
    original = b"X" * 65_537

    result = assess_information_insurance(
        expected_sha256=hashlib.sha256(original).hexdigest(),
        copies=[{"data": original, "failure_domain": "device-B"}],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["reconstruction_sufficient"] is False
    assert result["surviving_verified_copies"] == 0
    assert result["write_authority"] == "NONE"


def test_oversized_workspace_manifest_fails_closed(tmp_path):
    from holosim.lossless_file_breaker import create_lossless_file_break

    original = b"HOLO bounded workspace manifest"
    source = tmp_path / "source.bin"
    source.write_bytes(original)

    workspace = tmp_path / "workspace"
    create_lossless_file_break(
        source,
        workspace,
        max_chunk_bytes=8,
    )

    manifest_path = workspace / "manifest.json"
    manifest_path.write_bytes(b" " * 65_537)

    result = assess_information_insurance(
        expected_sha256=hashlib.sha256(original).hexdigest(),
        copies=[
            {
                "workspace_path": workspace,
                "failure_domain": "device-B",
            }
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["reconstruction_sufficient"] is False
    assert result["verified_workspaces"] == 0
    assert result["write_authority"] == "NONE"


def test_valid_oversized_manifest_is_rejected(tmp_path):
    from holosim.lossless_file_breaker import (
        create_lossless_file_break,
        verify_lossless_file_break,
    )

    original = b"HOLO valid oversized manifest"
    source = tmp_path / "source.bin"
    source.write_bytes(original)

    workspace = tmp_path / "workspace"
    create_lossless_file_break(
        source,
        workspace,
        max_chunk_bytes=8,
    )

    manifest_path = workspace / "manifest.json"
    original_manifest = manifest_path.read_bytes()
    manifest_path.write_bytes(
        original_manifest + b" " * 65_537
    )

    assert manifest_path.stat().st_size > 65_536

    # Establish that the existing verifier still accepts this workspace.
    verify_lossless_file_break(workspace)

    result = assess_information_insurance(
        expected_sha256=hashlib.sha256(original).hexdigest(),
        copies=[
            {
                "workspace_path": workspace,
                "failure_domain": "device-B",
            }
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["reconstruction_sufficient"] is False
    assert result["verified_workspaces"] == 0
    assert result["write_authority"] == "NONE"


def test_valid_oversized_workspace_chunk_is_rejected(tmp_path):
    from holosim.lossless_file_breaker import (
        create_lossless_file_break,
        verify_lossless_file_break,
    )

    original = b"X" * 65_537
    source = tmp_path / "source.bin"
    source.write_bytes(original)

    workspace = tmp_path / "workspace"
    create_lossless_file_break(
        source,
        workspace,
        max_chunk_bytes=65_537,
    )

    # Prove this is valid evidence under the shared verifier.
    verify_lossless_file_break(workspace)

    result = assess_information_insurance(
        expected_sha256=hashlib.sha256(original).hexdigest(),
        copies=[
            {
                "workspace_path": workspace,
                "failure_domain": "device-B",
            }
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["reconstruction_sufficient"] is False
    assert result["verified_workspaces"] == 0
    assert result["write_authority"] == "NONE"


def test_aggregate_workspace_size_limit_fails_closed(tmp_path):
    from holosim.lossless_file_breaker import (
        create_lossless_file_break,
        verify_lossless_file_break,
    )

    original = b"X" * (1_048_576 + 1)
    source = tmp_path / "source.bin"
    source.write_bytes(original)

    workspace = tmp_path / "workspace"
    create_lossless_file_break(
        source,
        workspace,
        max_chunk_bytes=65_536,
    )

    # The shared verifier accepts this valid workspace.
    verify_lossless_file_break(workspace)

    result = assess_information_insurance(
        expected_sha256=hashlib.sha256(original).hexdigest(),
        copies=[
            {
                "workspace_path": workspace,
                "failure_domain": "device-B",
            }
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["reconstruction_sufficient"] is False
    assert result["verified_workspaces"] == 0
    assert result["write_authority"] == "NONE"


def test_rehashed_workspace_path_traversal_fails_closed(tmp_path):
    import json
    from copy import deepcopy

    from holosim.lossless_file_breaker import create_lossless_file_break

    original = b"HOLO traversal boundary"
    source = tmp_path / "source.bin"
    source.write_bytes(original)

    workspace = tmp_path / "workspace"
    manifest = create_lossless_file_break(
        source,
        workspace,
        max_chunk_bytes=8,
    )

    forged = deepcopy(manifest)
    forged["chunks"][0]["filename"] = "../outside.part"

    body = {
        key: value
        for key, value in forged.items()
        if key != "manifest_hash"
    }
    canonical = json.dumps(
        body,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    forged["manifest_hash"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    (workspace / "manifest.json").write_text(
        json.dumps(forged),
        encoding="utf-8",
    )

    result = assess_information_insurance(
        expected_sha256=hashlib.sha256(original).hexdigest(),
        copies=[
            {
                "workspace_path": workspace,
                "failure_domain": "device-B",
            }
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["reconstruction_sufficient"] is False
    assert result["verified_workspaces"] == 0
    assert result["survival_independently_verified"] is False
    assert result["write_authority"] == "NONE"


def test_excessive_workspace_count_fails_closed(tmp_path):
    from holosim.lossless_file_breaker import create_lossless_file_break

    original = b"HOLO workspace budget"
    source = tmp_path / "source.bin"
    source.write_bytes(original)

    workspace = tmp_path / "workspace"
    create_lossless_file_break(
        source,
        workspace,
        max_chunk_bytes=8,
    )

    result = assess_information_insurance(
        expected_sha256=hashlib.sha256(original).hexdigest(),
        copies=[
            {
                "workspace_path": workspace,
                "failure_domain": "device-B",
            }
            for _ in range(9)
        ],
        failed_domains=["device-A"],
    )

    assert result["status"] == "UNKNOWN"
    assert result["reconstruction_sufficient"] is False
    assert result["verified_workspaces"] == 0
    assert result["write_authority"] == "NONE"


def test_verified_artifact_reconstructs_after_source_deletion(tmp_path):
    import hashlib
    import json

    from holosim.lossless_file_breaker import (
        create_lossless_file_break,
        verify_lossless_file_break,
    )
    from holosim.reconstructor import (
        build_reconstructed_state,
        validate_reconstructed_state,
    )

    items = [
        {"id": "observation", "value": 42},
        {
            "id": "verification",
            "requires": ["observation"],
            "passed": True,
        },
        {
            "id": "result",
            "requires": ["verification"],
            "value": "HELD",
        },
    ]

    source = tmp_path / "evidence.json"
    workspace = tmp_path / "recovery"

    source_bytes = json.dumps(
        items, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    expected_hash = hashlib.sha256(source_bytes).hexdigest()

    source.write_bytes(source_bytes)
    create_lossless_file_break(
        source, workspace, max_chunk_bytes=32
    )

    source.unlink()
    assert not source.exists()

    manifest = verify_lossless_file_break(workspace)
    assert manifest["source_hash"] == expected_hash

    recovered_bytes = b"".join(
        (workspace / chunk["filename"]).read_bytes()
        for chunk in manifest["chunks"]
    )
    assert hashlib.sha256(recovered_bytes).hexdigest() == expected_hash

    recovered_items = json.loads(recovered_bytes)

    reconstructed = build_reconstructed_state(
        "insurance-absence-001",
        ["result"],
        recovered_items,
    )
    assert validate_reconstructed_state(
        reconstructed, recovered_items
    )
    assert reconstructed["status"] == "COMPLETE"

    replayed = build_reconstructed_state(
        "insurance-absence-001",
        ["result"],
        list(reversed(recovered_items)),
    )

    assert reconstructed == replayed

    incomplete = build_reconstructed_state(
        "insurance-absence-001",
        ["result"],
        [
            item for item in recovered_items
            if item["id"] != "observation"
        ],
    )

    assert incomplete["status"] == "INCOMPLETE"
    assert incomplete["missing_ids"] == ["observation"]

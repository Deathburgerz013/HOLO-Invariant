"""Regression tests for bounded, non-authoritative retrieval observation."""

from copy import deepcopy
from pathlib import Path

from holosim.agent_runtime import HoloAgentRuntime
from holosim.evidence_bound_retrieval import observe_retrieval, recheck_retrieval_observation, verify_retrieval_observation


class _Source:
    discover_documents = HoloAgentRuntime.discover_documents

    def __init__(self, root: Path) -> None:
        self.repo_root = root
        self._documents = None


def test_excluded_document_change_updates_snapshot(tmp_path: Path) -> None:
    for index in range(5):
        (tmp_path / f"top{index}.md").write_text(
            "evidence recall", encoding="utf-8"
        )

    excluded = tmp_path / "excluded.md"
    excluded.write_text("evidence", encoding="utf-8")

    source = _Source(tmp_path)
    before = observe_retrieval(source, "evidence recall", limit=5)

    excluded.write_text("evidence correction updated", encoding="utf-8")
    after = observe_retrieval(source, "evidence recall", limit=5)

    assert before["query_hash"] == after["query_hash"]
    assert before["snapshot_hash"] != after["snapshot_hash"]


def test_reused_source_observes_changed_document(tmp_path: Path) -> None:
    document = tmp_path / "evidence.md"
    document.write_text("recall original", encoding="utf-8")

    source = _Source(tmp_path)
    before = observe_retrieval(source, "recall", limit=5)

    document.write_text("recall corrected", encoding="utf-8")
    after = observe_retrieval(source, "recall", limit=5)

    assert before["snapshot_hash"] != after["snapshot_hash"]
    assert before["query_hash"] != after["query_hash"]


def test_truncation_is_explicit_and_non_authoritative(tmp_path: Path) -> None:
    for index in range(6):
        (tmp_path / f"doc{index}.md").write_text(
            "evidence recall", encoding="utf-8"
        )

    result = observe_retrieval(
        _Source(tmp_path), "evidence recall", limit=5
    )

    assert result["total_matches"] == 6
    assert result["returned_matches"] == 5
    assert result["truncated"] is True
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_observation_uses_exactly_one_discovery_snapshot(
    tmp_path: Path,
) -> None:
    document = tmp_path / "evidence.md"
    document.write_text("recall original", encoding="utf-8")

    class CountingSource(_Source):
        def __init__(self, root: Path) -> None:
            super().__init__(root)
            self.discovery_calls = 0

        def discover_documents(self, refresh: bool = False):
            self.discovery_calls += 1
            return HoloAgentRuntime.discover_documents(
                self, refresh=refresh
            )

    source = CountingSource(tmp_path)

    result = observe_retrieval(source, "recall")

    assert source.discovery_calls == 1
    assert result["returned_matches"] == 1
    assert result["results"][0]["snippet"] == "recall original"



def test_retrieval_observation_rejects_tampering(tmp_path: Path) -> None:
    for index in range(6):
        (tmp_path / f"doc{index}.md").write_text(
            "evidence recall", encoding="utf-8"
        )

    original = observe_retrieval(
        _Source(tmp_path), "evidence recall", limit=5
    )

    assert verify_retrieval_observation(original) is True

    changes = [
        ("snapshot_hash", "0" * 64),
        ("total_matches", 999),
        ("returned_matches", 999),
        ("truncated", False),
        ("discovered_documents", 999),
    ]

    for field, value in changes:
        altered = deepcopy(original)
        altered[field] = value
        assert verify_retrieval_observation(altered) is False, field

    altered = deepcopy(original)
    altered["document_manifest"][0][1] = "0" * 64
    assert verify_retrieval_observation(altered) is False

    altered = deepcopy(original)
    altered["results"][0]["content_hash"] = "0" * 64
    assert verify_retrieval_observation(altered) is False


def test_omitted_match_requires_independent_recheck(
    tmp_path: Path,
) -> None:
    from copy import deepcopy

    from holosim.evidence_bound_retrieval import (
        recheck_retrieval_observation,
    )

    for index in range(6):
        (tmp_path / f"doc{index}.md").write_text(
            "evidence recall", encoding="utf-8"
        )

    source = _Source(tmp_path)
    original = observe_retrieval(
        source, "evidence recall", limit=5
    )

    altered = deepcopy(original)
    altered["matched_paths"].pop()
    altered["total_matches"] = 5
    altered["truncated"] = False

    assert recheck_retrieval_observation(
        source, original
    ) is True

    assert recheck_retrieval_observation(
        source, altered
    ) is False


def test_recheck_rejects_changed_source(tmp_path: Path) -> None:
    from holosim.evidence_bound_retrieval import (
        recheck_retrieval_observation,
    )

    document = tmp_path / "evidence.md"
    document.write_text("recall original", encoding="utf-8")

    runtime = _Source(tmp_path)
    original = observe_retrieval(runtime, "recall")

    document.write_text("recall corrected", encoding="utf-8")

    assert recheck_retrieval_observation(runtime, original) is False


def test_recheck_rejects_unavailable_source(tmp_path: Path) -> None:
    from holosim.evidence_bound_retrieval import (
        recheck_retrieval_observation,
    )

    document = tmp_path / "evidence.md"
    document.write_text("recall original", encoding="utf-8")

    runtime = _Source(tmp_path)
    original = observe_retrieval(runtime, "recall")

    document.unlink()

    assert recheck_retrieval_observation(runtime, original) is False


def test_verifier_rejects_altered_query_hash(tmp_path: Path) -> None:
    from copy import deepcopy

    from holosim.evidence_bound_retrieval import (
        verify_retrieval_observation,
    )

    (tmp_path / "evidence.md").write_text(
        "evidence recall", encoding="utf-8"
    )

    original = observe_retrieval(
        _Source(tmp_path), "evidence recall"
    )

    altered = deepcopy(original)
    altered["query_hash"] = "0" * 64

    assert verify_retrieval_observation(original) is True
    assert verify_retrieval_observation(altered) is False


def test_unrelated_spine_filename_is_not_a_match(
    tmp_path: Path,
) -> None:
    (tmp_path / "spine-notes.md").write_text(
        "unrelated text",
        encoding="utf-8",
    )

    observation = observe_retrieval(
        _Source(tmp_path),
        "evidence",
        limit=5,
    )

    assert len(observation["results"]) == 1
    assert observation["results"][0]["path"] == "spine-notes.md"
    assert observation["results"][0]["score"] == 1
    assert observation["matched_paths"] == ["spine-notes.md"]
    assert observation["total_matches"] == 1
    assert observation["returned_matches"] == 1
    assert observation["truncated"] is False


def test_observation_hash_binds_complete_retrieval(
    tmp_path: Path,
) -> None:
    from copy import deepcopy

    for index in range(6):
        (tmp_path / f"doc{index}.md").write_text(
            "evidence recall", encoding="utf-8"
        )

    original = observe_retrieval(
        _Source(tmp_path), "evidence recall", limit=5
    )

    assert isinstance(original["observation_hash"], str)

    altered = deepcopy(original)
    altered["matched_paths"][-1] = "fabricated.md"

    assert verify_retrieval_observation(altered) is False

    altered = deepcopy(original)
    altered["limit"] = 6

    assert verify_retrieval_observation(altered) is False


def test_recheck_rejects_rehashed_fabricated_match(
    tmp_path: Path,
) -> None:
    from copy import deepcopy

    from holosim.canonical import stable_hash

    for index in range(6):
        (tmp_path / f"doc{index}.md").write_text(
            "evidence recall", encoding="utf-8"
        )

    source = _Source(tmp_path)
    original = observe_retrieval(
        source, "evidence recall", limit=5
    )

    altered = deepcopy(original)
    altered["matched_paths"][-1] = "fabricated.md"
    altered["observation_hash"] = stable_hash({
        key: value
        for key, value in altered.items()
        if key != "observation_hash"
    })

    assert verify_retrieval_observation(altered) is False
    assert recheck_retrieval_observation(source, altered) is False


def test_recheck_rejects_rehashed_existing_path(
    tmp_path: Path,
) -> None:
    from copy import deepcopy

    from holosim.canonical import stable_hash

    for index in range(6):
        (tmp_path / f"match{index}.md").write_text(
            "evidence recall", encoding="utf-8"
        )

    (tmp_path / "unrelated.md").write_text(
        "completely different content", encoding="utf-8"
    )

    runtime = _Source(tmp_path)
    original = observe_retrieval(
        runtime, "evidence recall", limit=5
    )

    altered = deepcopy(original)
    omitted = set(altered["matched_paths"]) - {
        result["path"] for result in altered["results"]
    }
    assert len(omitted) == 1

    altered["matched_paths"].remove(omitted.pop())
    altered["matched_paths"].append("unrelated.md")
    altered["matched_paths"].sort()

    altered["match_classifications"] = [
        {
            "path": path,
            "classification": (
                "FILENAME_BONUS_ONLY"
                if path == "unrelated.md"
                else "CONTENT_MATCH"
            ),
        }
        for path in altered["matched_paths"]
    ]

    altered["observation_hash"] = stable_hash({
        key: value
        for key, value in altered.items()
        if key != "observation_hash"
    })

    assert verify_retrieval_observation(altered) is True
    assert recheck_retrieval_observation(runtime, altered) is False


def test_match_classification_structure_rejects_tampering(
    tmp_path: Path,
) -> None:
    from copy import deepcopy

    from holosim.canonical import stable_hash

    (tmp_path / "spine-notes.md").write_text(
        "unrelated material", encoding="utf-8"
    )
    (tmp_path / "raw-source.md").write_text(
        "evidence from an observed event", encoding="utf-8"
    )

    runtime = _Source(tmp_path)
    original = observe_retrieval(runtime, "evidence")

    assert verify_retrieval_observation(original) is True
    assert len(original["match_classifications"]) == 2

    def rehash(record):
        record["observation_hash"] = stable_hash({
            key: value
            for key, value in record.items()
            if key != "observation_hash"
        })
        return record

    mutations = []

    missing = deepcopy(original)
    missing.pop("match_classifications")
    mutations.append(missing)

    duplicate = deepcopy(original)
    duplicate["match_classifications"][1] = deepcopy(
        duplicate["match_classifications"][0]
    )
    mutations.append(duplicate)

    invented = deepcopy(original)
    invented["match_classifications"][0]["path"] = "fabricated.md"
    mutations.append(invented)

    invalid = deepcopy(original)
    invalid["match_classifications"][0]["classification"] = "TRUTH"
    mutations.append(invalid)

    extra = deepcopy(original)
    extra["match_classifications"][0]["accepted"] = True
    mutations.append(extra)

    for altered in mutations:
        assert verify_retrieval_observation(rehash(altered)) is False

    changed_label = deepcopy(original)
    changed_label["match_classifications"][0]["classification"] = (
        "FILENAME_QUERY_MATCH"
    )
    rehash(changed_label)

    assert verify_retrieval_observation(changed_label) is True
    assert recheck_retrieval_observation(runtime, changed_label) is False


def test_retrieval_observation_version_compatibility(
    tmp_path: Path,
) -> None:
    from copy import deepcopy

    import pytest

    from holosim.canonical import stable_hash

    (tmp_path / "spine-notes.md").write_text(
        "unrelated material", encoding="utf-8"
    )
    (tmp_path / "raw-source.md").write_text(
        "evidence from an observed event", encoding="utf-8"
    )

    runtime = _Source(tmp_path)

    old = observe_retrieval(runtime, "evidence", version=1)
    new = observe_retrieval(runtime, "evidence", version=2)

    assert old["version"] == 1
    assert "match_classifications" not in old
    assert new["version"] == 2
    assert len(new["match_classifications"]) == 2

    for observation in (old, new):
        assert verify_retrieval_observation(observation) is True
        assert recheck_retrieval_observation(runtime, observation) is True

    def rehash(record):
        record["observation_hash"] = stable_hash({
            key: value
            for key, value in record.items()
            if key != "observation_hash"
        })
        return record

    disguised_old = deepcopy(old)
    disguised_old["version"] = 2
    assert verify_retrieval_observation(rehash(disguised_old)) is False

    disguised_new = deepcopy(new)
    disguised_new["version"] = 1
    assert verify_retrieval_observation(rehash(disguised_new)) is False

    for invalid_version in (0, 4, True, "2"):
        with pytest.raises(ValueError):
            observe_retrieval(
                runtime, "evidence", version=invalid_version
            )


def test_version3_rehashed_tampering_is_rejected(tmp_path):
    from copy import deepcopy

    from holosim.canonical import stable_hash

    (tmp_path / "raw-source.md").write_text(
        "evidence", encoding="utf-8"
    )
    (tmp_path / "evidence-name.md").write_text(
        "", encoding="utf-8"
    )
    (tmp_path / "spine-unrelated.md").write_text(
        "", encoding="utf-8"
    )

    source = _Source(tmp_path)
    original = observe_retrieval(source, "evidence", version=3)

    assert verify_retrieval_observation(original) is True
    assert recheck_retrieval_observation(source, original) is True

    cases = {}

    record = deepcopy(original)
    record["candidate_matches"] += 1
    cases["false candidate count"] = record

    record = deepcopy(original)
    record["eligible_matches"] += 1
    cases["false eligible count"] = record

    record = deepcopy(original)
    record["candidate_paths"].pop()
    cases["omitted candidate"] = record

    record = deepcopy(original)
    record["match_classifications"][0]["classification"] = (
        "FILENAME_BONUS_ONLY"
    )
    cases["changed classification"] = record

    record = deepcopy(original)
    record["matched_paths"].pop()
    cases["omitted eligible match"] = record

    for name, record in cases.items():
        record["observation_hash"] = stable_hash({
            key: value
            for key, value in record.items()
            if key != "observation_hash"
        })

        assert verify_retrieval_observation(record) is False, name
        assert recheck_retrieval_observation(source, record) is False, name

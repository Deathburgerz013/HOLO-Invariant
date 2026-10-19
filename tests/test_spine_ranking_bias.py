"""Characterize filename-only retrieval matches."""

from holosim.agent_runtime import (
    SEARCH_STOPWORDS,
    score_retrieval_document,
    tokenize,
)


def test_spine_filename_without_query_match_receives_score():
    query = "evidence"
    tokens = {
        token
        for token in tokenize(query)
        if token not in SEARCH_STOPWORDS and len(token) > 1
    }

    document = {
        "name": "spine-notes.md",
        "content": "unrelated material",
    }

    score, hits, phrase = score_retrieval_document(
        document, query, tokens
    )

    assert score == 1
    assert hits == []
    assert phrase is False


def test_content_match_outranks_filename_only_match():
    query = "evidence"
    tokens = {
        token
        for token in tokenize(query)
        if token not in SEARCH_STOPWORDS and len(token) > 1
    }

    unrelated = {
        "name": "spine-notes.md",
        "content": "unrelated material",
    }
    relevant = {
        "name": "raw-source.md",
        "content": "evidence from an observed event",
    }

    unrelated_score, _, _ = score_retrieval_document(
        unrelated, query, tokens
    )
    relevant_score, _, _ = score_retrieval_document(
        relevant, query, tokens
    )

    assert unrelated_score == 1
    assert relevant_score == 4
    assert relevant_score > unrelated_score


def test_filename_bonus_only_matches_fill_remaining_result_slots(
    tmp_path,
):
    from pathlib import Path

    from holosim.agent_runtime import HoloAgentRuntime
    from holosim.evidence_bound_retrieval import (
        observe_retrieval,
        recheck_retrieval_observation,
        verify_retrieval_observation,
    )

    class IsolatedSource:
        discover_documents = HoloAgentRuntime.discover_documents

        def __init__(self, root):
            self.repo_root = Path(root)
            self._documents = None

    for index in range(10):
        (tmp_path / f"spine-unrelated-{index}.md").write_text(
            "", encoding="utf-8"
        )

    (tmp_path / "raw-source.md").write_text(
        "evidence", encoding="utf-8"
    )

    source = IsolatedSource(tmp_path)
    observation = observe_retrieval(source, "evidence", limit=5)

    returned = [
        result["path"] for result in observation["results"]
    ]

    classifications = {
        entry["path"]: entry["classification"]
        for entry in observation["match_classifications"]
    }

    assert observation["version"] == 2
    assert observation["discovered_documents"] == 11
    assert observation["total_matches"] == 11
    assert observation["returned_matches"] == 5

    assert returned[0] == "raw-source.md"
    assert classifications[returned[0]] == "CONTENT_MATCH"

    assert all(
        classifications[path] == "FILENAME_BONUS_ONLY"
        for path in returned[1:]
    )

    assert verify_retrieval_observation(observation)
    assert recheck_retrieval_observation(source, observation)

    assert observation["accepted"] is False
    assert observation["write_authority"] == "NONE"
    assert observation["execution_authority"] == "NONE"


def test_filename_bonus_requires_independent_query_match(tmp_path):
    from holosim.agent_runtime import HoloAgentRuntime
    from holosim.evidence_bound_retrieval import observe_retrieval

    class Source:
        discover_documents = HoloAgentRuntime.discover_documents

        def __init__(self, root):
            self.repo_root = root
            self._documents = None

    for index in range(10):
        (tmp_path / f"spine-unrelated-{index}.md").write_text(
            "", encoding="utf-8"
        )

    (tmp_path / "raw-source.md").write_text(
        "evidence", encoding="utf-8"
    )
    (tmp_path / "evidence-filename.md").write_text(
        "", encoding="utf-8"
    )
    (tmp_path / "spine-evidence.md").write_text(
        "", encoding="utf-8"
    )

    observation = observe_retrieval(
        Source(tmp_path), "evidence", limit=5, version=3
    )

    returned = [
        item["path"] for item in observation["results"]
    ]

    assert returned == [
        "raw-source.md",
        "spine-evidence.md",
        "evidence-filename.md",
    ]

    assert observation["version"] == 3
    assert observation["discovered_documents"] == 13
    assert observation["candidate_matches"] == 13
    assert observation["eligible_matches"] == 3
    assert observation["returned_matches"] == 3
    assert observation["total_matches"] == 3
    assert len(observation["candidate_paths"]) == 13
    assert len(observation["matched_paths"]) == 3
    assert observation["truncated"] is False

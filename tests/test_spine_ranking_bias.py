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

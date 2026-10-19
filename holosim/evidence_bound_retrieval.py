"""Bounded observation of deterministic repository retrieval.

Records discovered-document identity and lexical retrieval coverage.
Does not establish semantic completeness, truth, or authority.
"""

from __future__ import annotations

from typing import Any

from holosim.agent_runtime import AGENT_VERSION, HoloAgentRuntime, SEARCH_STOPWORDS, score_retrieval_document, tokenize
from holosim.canonical import stable_hash


def observe_retrieval(
    source: Any,
    query: str,
    *,
    limit: int = 5,
    version: int = 2,
) -> dict[str, Any]:
    """Observe one refreshed document snapshot and its bounded search result."""
    if type(version) is not int or version not in (1, 2):
        raise ValueError("unsupported retrieval observation version")
    clean_query = query.strip()
    if not clean_query:
        raise ValueError("query cannot be empty")
    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    documents = source.discover_documents(refresh=True)

    document_manifest = sorted(
        [
            [document["path"], document["content_hash"]]
            for document in documents
        ]
    )
    snapshot_hash = stable_hash(document_manifest)

    result = HoloAgentRuntime.query_spines(
        source, clean_query, limit=limit, documents=documents
    )

    query_tokens = {
        token
        for token in tokenize(clean_query)
        if token not in SEARCH_STOPWORDS and len(token) > 1
    }

    matched_paths = []
    match_classifications = []

    for document in documents:
        score, token_hits, phrase_hit = score_retrieval_document(
            document, clean_query, query_tokens
        )
        if score <= 0:
            continue

        matched_paths.append(document["path"])

        content = str(document["content"]).lower()
        name = str(document["name"]).lower()

        if phrase_hit or any(token in content for token in token_hits):
            classification = "CONTENT_MATCH"
        elif any(token in name for token in token_hits):
            classification = "FILENAME_QUERY_MATCH"
        else:
            classification = "FILENAME_BONUS_ONLY"

        match_classifications.append({
            "path": document["path"],
            "classification": classification,
        })

    match_classifications.sort(key=lambda item: item["path"])

    matched_paths = sorted(matched_paths)
    total_matches = len(matched_paths)
    returned_matches = len(result["results"])

    observation = {
        "type": "evidence_bound_retrieval_observation",
        "version": version,
        "query": clean_query,
        "limit": limit,
        "snapshot_hash": snapshot_hash,
        "document_manifest": document_manifest,
        "discovered_documents": len(documents),
        "query_hash": result["query_hash"],
        "results": result["results"],
        "total_matches": total_matches,
        "matched_paths": matched_paths,
        "returned_matches": returned_matches,
        "truncated": total_matches > returned_matches,
        "discovery_refreshed": True,
        "semantic_completeness_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    if version == 2:
        observation["match_classifications"] = match_classifications

    observation["observation_hash"] = stable_hash(observation)
    return observation


def verify_retrieval_observation(observation: Any) -> bool:
    """Check internal consistency, not source truth or search completeness."""
    try:
        if not isinstance(observation, dict):
            return False

        if observation.get("type") != "evidence_bound_retrieval_observation":
            return False
        version = observation.get("version")
        if type(version) is not int or version not in (1, 2):
            return False

        manifest = observation["document_manifest"]
        matches = observation["matched_paths"]
        results = observation["results"]
        limit = observation["limit"]

        if not isinstance(manifest, list) or not isinstance(matches, list):
            return False
        if not isinstance(results, list):
            return False
        if type(limit) is not int or limit <= 0:
            return False
        if not isinstance(observation["query"], str) or not observation["query"].strip():
            return False

        if any(
            not isinstance(entry, list)
            or len(entry) != 2
            or not all(isinstance(value, str) for value in entry)
            for entry in manifest
        ):
            return False

        if manifest != sorted(manifest):
            return False

        paths = [entry[0] for entry in manifest]
        if len(paths) != len(set(paths)):
            return False

        hashes = dict(manifest)
        if observation["snapshot_hash"] != stable_hash(manifest):
            return False

        if any(not isinstance(path, str) for path in matches):
            return False
        if matches != sorted(set(matches)):
            return False
        if not set(matches).issubset(hashes):
            return False

        if version == 1:
            if "match_classifications" in observation:
                return False
        else:
            classifications = observation["match_classifications"]
            allowed = {
                "CONTENT_MATCH",
                "FILENAME_QUERY_MATCH",
                "FILENAME_BONUS_ONLY",
            }

            if not isinstance(classifications, list):
                return False
            if len(classifications) != len(matches):
                return False

            for index, entry in enumerate(classifications):
                if not isinstance(entry, dict):
                    return False
                if set(entry) != {"path", "classification"}:
                    return False
                if entry["path"] != matches[index]:
                    return False
                if type(entry["classification"]) is not str:
                    return False
                if entry["classification"] not in allowed:
                    return False

        if type(observation["discovered_documents"]) is not int:
            return False
        if observation["discovered_documents"] != len(manifest):
            return False

        if type(observation["total_matches"]) is not int:
            return False
        if observation["total_matches"] != len(matches):
            return False

        if type(observation["returned_matches"]) is not int:
            return False
        if observation["returned_matches"] != len(results):
            return False
        if len(results) > limit or len(results) > len(matches):
            return False

        if type(observation["truncated"]) is not bool:
            return False
        if observation["truncated"] != (len(matches) > len(results)):
            return False

        result_paths = []
        for result in results:
            if not isinstance(result, dict):
                return False
            path = result["path"]
            if path not in matches:
                return False
            if result["content_hash"] != hashes[path]:
                return False
            result_paths.append(path)

        if len(result_paths) != len(set(result_paths)):
            return False

        expected_query_hash = stable_hash({
            "type": "holo_agent_query",
            "agent_version": AGENT_VERSION,
            "query": observation["query"],
            "result_count": len(results),
            "results": results,
        })
        if observation.get("query_hash") != expected_query_hash:
            return False

        if not isinstance(observation.get("observation_hash"), str):
            return False

        unsigned = {
            key: value
            for key, value in observation.items()
            if key != "observation_hash"
        }
        if observation["observation_hash"] != stable_hash(unsigned):
            return False

        if observation.get("discovery_refreshed") is not True:
            return False
        if observation.get("semantic_completeness_claimed") is not False:
            return False
        if observation.get("truth_claimed") is not False:
            return False
        if observation.get("accepted") is not False:
            return False
        if observation.get("write_authority") != "NONE":
            return False
        if observation.get("execution_authority") != "NONE":
            return False

        return True
    except (KeyError, TypeError, ValueError):
        return False



def recheck_retrieval_observation(
    source: Any,
    observation: Any,
) -> bool:
    """Reconstruct and compare an observation against available documents.

    A changed or unavailable snapshot fails closed. This does not prove
    historical truth, semantic relevance, or repository completeness.
    """
    if not verify_retrieval_observation(observation):
        return False

    try:
        reconstructed = observe_retrieval(
            source,
            observation["query"],
            limit=observation["limit"],
            version=observation["version"],
        )
    except (OSError, ValueError, TypeError, KeyError):
        return False

    return (
        verify_retrieval_observation(reconstructed)
        and reconstructed == observation
    )

from typing import Any


def evaluate_opposition(*, dimension: str, left: Any, right: Any, right_dimension: str | None = None, oppositions: dict[Any, Any] | None = None, domain: set[Any] | None = None) -> dict[str, Any]:
    if type(dimension) is not str or not dimension.strip():
        raise ValueError("dimension must be a nonempty string")
    if right_dimension is not None and right_dimension != dimension:
        raise ValueError("opposition must remain within one declared dimension")
    within_domain = domain is None or (left in domain and right in domain)
    relation_verified = within_domain and oppositions is not None and oppositions.get(left) == right and oppositions.get(right) == left
    return {
        "dimension": dimension,
        "left": left,
        "right": right,
        "distinguishable": left != right,
        "opposite": relation_verified,
        "relation_verified": relation_verified,
        "universal_claim": False,
        "accepted": False,
        "write_authority": "NONE",
    }


def evaluate_domain_coverage(*, dimension: str, domain: set[Any], oppositions: dict[Any, Any]) -> dict[str, Any]:
    if type(dimension) is not str or not dimension.strip():
        raise ValueError("dimension must be a nonempty string")
    covered = set()
    for state in domain:
        partner = oppositions.get(state)
        if partner in domain and oppositions.get(partner) == state:
            covered.add(state)
    unresolved = set(domain) - covered
    return {
        "dimension": dimension,
        "covered": covered,
        "unresolved": unresolved,
        "coverage_complete": not unresolved,
        "universal_claim": False,
        "accepted": False,
        "write_authority": "NONE",
    }


def evaluate_involution(*, domain: set[Any], transform: Any) -> dict[str, Any]:
    pairs = set()
    unresolved = set()
    for state in domain:
        try:
            partner = transform(state)
            if partner not in domain:
                unresolved.add(state)
                continue
            returned = transform(partner)
        except Exception:
            unresolved.add(state)
            continue
        if returned != state:
            unresolved.add(state)
            continue
        pairs.add((state, partner))
    return {
        "pairs": pairs,
        "unresolved": unresolved,
        "involution_complete": not unresolved,
        "universal_claim": False,
        "accepted": False,
        "write_authority": "NONE",
    }

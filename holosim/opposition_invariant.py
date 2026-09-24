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

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATTRIBUTES = ROOT / ".gitattributes"
FIXTURE = ROOT / "interop" / "simulation-portable-candidate-evidence-bundle-v1.json"
FIXTURE_SHA256 = "bf0067544143da208069c5a83250d77f809fd2aeedce4c6d67b23e7dd898ec99"


def test_simulation_interop_fixture_is_preserved_as_exact_bytes() -> None:
    rules = {
        line.strip()
        for line in ATTRIBUTES.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "/interop/*.json -text" in rules
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256

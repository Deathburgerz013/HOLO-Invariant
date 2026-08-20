from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def readme_text() -> str:
    return README.read_text(encoding="utf-8")


def test_quick_start_uses_real_commands_without_duplicate_inventory():
    readme = readme_text()

    assert "pip install -e ." in readme
    assert "holo demo" in readme
    assert "python -m holosim.cli boot" not in readme
    assert "Available subcommands:" not in readme
    assert "<!-- HOLO:STATUS:START -->" in readme
    assert "<!-- HOLO:STATUS:END -->" in readme


def test_symbolic_relation_is_not_presented_as_mathematical_proof():
    readme = readme_text()

    assert "design mnemonic" in readme
    assert "not presented as a derived scientific law" in readme
    assert "not proof of the repository's engineering guarantees" in readme


def test_situated_packet_claim_names_implemented_and_missing_layers():
    readme = readme_text()

    assert "situated_reconstruction_packet.py" in readme
    assert "model-independent reconstruction artifact" in readme
    assert "does not automatically inject itself into a model" in readme
    assert "provider-neutral transport remains an integration boundary" in readme


def test_cross_model_continuity_remains_an_empirical_target():
    readme = readme_text()

    assert "Cross-model continuity remains an empirical target" in readme
    assert "independent models and operators" in readme
    assert "external review" in readme


def test_retained_test_receipt_is_described_as_historical_not_latest():
    readme = readme_text()

    assert "Retained historical post-merge observation:" in readme
    assert "Latest retained post-merge observation:" not in readme
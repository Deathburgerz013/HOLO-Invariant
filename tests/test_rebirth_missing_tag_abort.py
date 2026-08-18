import holosim.rebirth_engine as rebirth_module
from holosim.rebirth_engine import (
    BLOODSTREAM_SENTINEL,
    HASH_GUARD_KEYS,
    Providers,
    RebirthEngine,
)


def build_providers(*, bloodstream_present: bool) -> Providers:
    return Providers(
        check_heartbeat=lambda: True,
        check_core_intact=lambda: True,
        status_age_seconds=lambda: 0,
        hash_check=lambda key: key in HASH_GUARD_KEYS,
        read_bloodstream=lambda tag: (
            bloodstream_present and tag == BLOODSTREAM_SENTINEL
        ),
        token_used=lambda: 0,
    )


def test_missing_bloodstream_tag_aborts_by_default(monkeypatch):
    monkeypatch.setattr(
        rebirth_module,
        "CURRENT_FUSED_HASH",
        None,
    )
    engine = RebirthEngine(
        build_providers(bloodstream_present=False),
        active_hash="frozen-idx-hash",
    )

    result = engine.run_rebirth("MANUAL_OVERRIDE")

    assert result["status"] == "abort"
    assert result["code"] == "BLOODSTREAM_MISMATCH"
    assert rebirth_module.CURRENT_FUSED_HASH is None


def test_present_bloodstream_tag_allows_rebirth(monkeypatch):
    monkeypatch.setattr(
        rebirth_module,
        "CURRENT_FUSED_HASH",
        None,
    )
    engine = RebirthEngine(
        build_providers(bloodstream_present=True),
        active_hash="frozen-idx-hash",
    )

    result = engine.run_rebirth("MANUAL_OVERRIDE")

    assert result["status"] == "ok"
    assert result["action"] == "rebirth_executed"
    assert result["fused"] is True
    assert rebirth_module.CURRENT_FUSED_HASH == "frozen-idx-hash"
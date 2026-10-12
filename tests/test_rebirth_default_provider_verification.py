import holosim.rebirth_engine as rebirth


def test_default_providers_cannot_claim_verified_rebirth(monkeypatch, tmp_path):
    monkeypatch.setattr(rebirth, "CURRENT_FUSED_HASH", None)

    engine = rebirth.build_engine(
        active_hash="test-frozen-head",
        memory_loop={
            "auto_trigger": {"heartbeat_interval_sec": 300},
            "file_map": {
                "memory_root": str(tmp_path),
                "session_log": "rebirth.log",
            },
        },
    )

    result = engine.run_rebirth("MANUAL_OVERRIDE")

    assert result["status"] == "abort"
    assert rebirth.CURRENT_FUSED_HASH is None


def test_default_providers_cannot_claim_healthy_noop(monkeypatch, tmp_path):
    monkeypatch.setattr(rebirth, "CURRENT_FUSED_HASH", None)

    engine = rebirth.build_engine(
        active_hash="test-frozen-head",
        memory_loop={
            "auto_trigger": {"heartbeat_interval_sec": 300},
            "file_map": {
                "memory_root": str(tmp_path),
                "session_log": "rebirth.log",
            },
        },
    )

    result = engine.run_rebirth()

    assert result["status"] != "ok"
    assert rebirth.CURRENT_FUSED_HASH is None

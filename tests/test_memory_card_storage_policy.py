import pytest

from holosim.memory_card_storage_policy import (
    DEFAULT_AUTOSAVE_INTERVAL_SECONDS,
    DEFAULT_MAX_GENERATIONS,
    MemoryCardStoragePolicyError,
    build_storage_policy,
    default_storage_policy,
    verify_storage_policy,
)


def test_default_policy_is_enabled():
    policy = default_storage_policy()

    assert policy["enabled"] is True


def test_default_policy_has_explicit_interval_and_retention():
    policy = default_storage_policy()

    assert policy["interval_seconds"] == (
        DEFAULT_AUTOSAVE_INTERVAL_SECONDS
    )
    assert policy["max_generations"] == DEFAULT_MAX_GENERATIONS


def test_policy_supports_adjustable_interval():
    policy = build_storage_policy(
        enabled=True,
        interval_seconds=60,
        max_generations=3,
    )

    assert policy == {
        "enabled": True,
        "interval_seconds": 60,
        "max_generations": 3,
    }


def test_policy_supports_disabled_autosave():
    policy = build_storage_policy(
        enabled=False,
        interval_seconds=600,
        max_generations=5,
    )

    assert policy["enabled"] is False


@pytest.mark.parametrize(
    "interval",
    [0, -1, True, 1.5, "60"],
)
def test_policy_rejects_invalid_intervals(interval):
    with pytest.raises(MemoryCardStoragePolicyError):
        build_storage_policy(
            interval_seconds=interval,
        )


@pytest.mark.parametrize(
    "generations",
    [0, -1, True, 1.5, "3"],
)
def test_policy_rejects_invalid_generation_limits(generations):
    with pytest.raises(MemoryCardStoragePolicyError):
        build_storage_policy(
            max_generations=generations,
        )


def test_policy_rejects_unknown_fields():
    with pytest.raises(MemoryCardStoragePolicyError):
        verify_storage_policy(
            {
                "enabled": True,
                "interval_seconds": 300,
                "max_generations": 3,
                "magic": True,
            }
        )


def test_policy_verification_does_not_mutate_input():
    policy = {
        "enabled": True,
        "interval_seconds": 120,
        "max_generations": 4,
    }

    original = policy.copy()

    assert verify_storage_policy(policy) is True
    assert policy == original
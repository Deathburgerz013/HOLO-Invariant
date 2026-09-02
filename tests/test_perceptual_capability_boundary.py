from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.perceptual_capability_boundary import (
    PerceptualCapabilityBoundaryError,
    build_perceptual_capability_receipt,
    validate_perceptual_capability_receipt,
)


ARTIFACT_HASH = "e" * 64


def _capability(modality, stage, status, evidence):
    return {
        "modality": modality,
        "stage": stage,
        "status": status,
        "evidence_reference": evidence,
    }


def _claim(claim_id, modality, stage, statement):
    return {
        "claim_id": claim_id,
        "modality": modality,
        "stage": stage,
        "statement": statement,
    }


def _receipt(*, capabilities=None, claims=None, modalities=None):
    return build_perceptual_capability_receipt(
        artifact_id="main-p-wav",
        artifact_sha256=ARTIFACT_HASH,
        media_type="audio/wav",
        declared_modalities=modalities or ["audio"],
        capability_evidence=capabilities or [
            _capability("audio", "BYTES_VERIFIED", "VERIFIED", "sha256:evidence"),
            _capability("audio", "SIGNAL_MEASURED", "VERIFIED", "ffprobe:receipt"),
            _capability(
                "audio", "CONTENT_PERCEIVED", "UNSUPPORTED",
                "runtime:audio-content-omitted",
            ),
        ],
        claims=claims or [
            _claim("heard-track", "audio", "CONTENT_PERCEIVED", "The model heard the track.")
        ],
    )


def _assessment(receipt, claim_id="heard-track"):
    return next(
        item for item in receipt["assessments"] if item["claim_id"] == claim_id
    )


def test_verified_wav_bytes_cannot_be_promoted_to_heard_content():
    receipt = _receipt()
    assessment = _assessment(receipt)

    assert assessment["decision"] == "CLAIM_REJECTED_UNSUPPORTED"
    assert assessment["stage_verified"] is False
    assert assessment["claim_truth_established"] is False
    assert receipt["all_claim_stages_verified"] is False


def test_signal_measurement_does_not_imply_audio_perception():
    receipt = _receipt(
        capabilities=[
            _capability("audio", "BYTES_VERIFIED", "VERIFIED", "sha256:evidence"),
            _capability("audio", "SIGNAL_MEASURED", "VERIFIED", "ffprobe:receipt"),
        ]
    )

    assessment = _assessment(receipt)
    assert assessment["decision"] == "CLAIM_REJECTED_NOT_TESTED"
    assert assessment["required_capability_chain"][-1]["stage"] == "CONTENT_PERCEIVED"
    assert assessment["required_capability_chain"][-1]["status"] == "NOT_TESTED"


def test_visual_perception_does_not_cross_into_audio():
    receipt = _receipt(
        modalities=["audio", "visual"],
        capabilities=[
            _capability("audio", "BYTES_VERIFIED", "VERIFIED", "sha256:mp4"),
            _capability("audio", "SIGNAL_MEASURED", "VERIFIED", "ffprobe:audio"),
            _capability("audio", "CONTENT_PERCEIVED", "UNAVAILABLE", "runtime:no-audio"),
            _capability("visual", "BYTES_VERIFIED", "VERIFIED", "sha256:mp4"),
            _capability("visual", "SIGNAL_MEASURED", "VERIFIED", "ffprobe:video"),
            _capability("visual", "CONTENT_PERCEIVED", "VERIFIED", "frames:inspection"),
        ],
        claims=[
            _claim("saw-guitar", "visual", "CONTENT_PERCEIVED", "A guitar was visible."),
            _claim("heard-guitar", "audio", "CONTENT_PERCEIVED", "A guitar was heard."),
        ],
    )

    assert _assessment(receipt, "saw-guitar")["decision"] == "CLAIM_STAGE_VERIFIED"
    assert _assessment(receipt, "heard-guitar")["decision"] == "CLAIM_REJECTED_UNAVAILABLE"


def test_interpretation_requires_every_prior_stage():
    receipt = _receipt(
        capabilities=[
            _capability("audio", "BYTES_VERIFIED", "VERIFIED", "sha256:evidence"),
            _capability("audio", "SIGNAL_MEASURED", "VERIFIED", "ffprobe:receipt"),
            _capability("audio", "CONTENT_PERCEIVED", "UNSUPPORTED", "runtime:no-audio"),
            _capability("audio", "CONTENT_INTERPRETED", "VERIFIED", "model:claim"),
        ],
        claims=[
            _claim("quality", "audio", "CONTENT_INTERPRETED", "The performance was polished.")
        ],
    )

    assessment = _assessment(receipt, "quality")
    assert assessment["decision"] == "CLAIM_REJECTED_UNSUPPORTED"
    assert assessment["reason"].startswith("CONTENT_PERCEIVED")


def test_verified_perception_stage_still_does_not_establish_claim_truth():
    receipt = _receipt(
        capabilities=[
            _capability("audio", "BYTES_VERIFIED", "VERIFIED", "sha256:evidence"),
            _capability("audio", "SIGNAL_MEASURED", "VERIFIED", "decoder:receipt"),
            _capability("audio", "CONTENT_PERCEIVED", "VERIFIED", "model:audio-input"),
        ]
    )

    assessment = _assessment(receipt)
    assert assessment["decision"] == "CLAIM_STAGE_VERIFIED"
    assert assessment["stage_verified"] is True
    assert assessment["claim_truth_established"] is False
    assert assessment["accepted"] is False


def test_earlier_unsupported_stage_blocks_later_verified_stage():
    receipt = _receipt(
        capabilities=[
            _capability("audio", "BYTES_VERIFIED", "UNAVAILABLE", "runtime:no-file"),
            _capability("audio", "SIGNAL_MEASURED", "VERIFIED", "fabricated:metric"),
        ],
        claims=[_claim("measured", "audio", "SIGNAL_MEASURED", "Signal was measured.")],
    )

    assessment = _assessment(receipt, "measured")
    assert assessment["decision"] == "CLAIM_REJECTED_UNAVAILABLE"
    assert assessment["reason"].startswith("BYTES_VERIFIED")


def test_receipt_is_deterministic_under_unordered_inputs():
    first = _receipt(
        modalities=["visual", "audio"],
        capabilities=[
            _capability("visual", "BYTES_VERIFIED", "VERIFIED", "hash:video"),
            _capability("audio", "BYTES_VERIFIED", "VERIFIED", "hash:audio"),
        ],
        claims=[
            _claim("visual-bytes", "visual", "BYTES_VERIFIED", "Visual bytes verified."),
            _claim("audio-bytes", "audio", "BYTES_VERIFIED", "Audio bytes verified."),
        ],
    )
    second = _receipt(
        modalities=["audio", "visual"],
        capabilities=list(reversed(first["capability_evidence"])),
        claims=list(reversed(first["claims"])),
    )

    assert second == first


def test_duplicate_modality_stage_evidence_is_rejected():
    duplicate = _capability("audio", "BYTES_VERIFIED", "VERIFIED", "hash:two")
    with pytest.raises(PerceptualCapabilityBoundaryError, match="unique"):
        _receipt(capabilities=[
            _capability("audio", "BYTES_VERIFIED", "VERIFIED", "hash:one"),
            duplicate,
        ])


def test_undeclared_modality_claim_is_rejected():
    with pytest.raises(PerceptualCapabilityBoundaryError, match="not declared"):
        _receipt(claims=[
            _claim("saw-image", "visual", "CONTENT_PERCEIVED", "An image was seen.")
        ])


def test_rehashed_authority_forgery_is_rejected():
    forged = deepcopy(_receipt())
    forged["write_authority"] = "MODEL"
    body = {key: value for key, value in forged.items() if key != "receipt_hash"}
    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(PerceptualCapabilityBoundaryError, match="forbidden authority"):
        validate_perceptual_capability_receipt(forged)


def test_tampered_assessment_is_rejected_even_when_rehashed():
    forged = deepcopy(_receipt())
    forged["assessments"][0]["decision"] = "CLAIM_STAGE_VERIFIED"
    forged["assessments"][0]["stage_verified"] = True
    body = {key: value for key, value in forged.items() if key != "receipt_hash"}
    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(PerceptualCapabilityBoundaryError, match="identity"):
        validate_perceptual_capability_receipt(forged)


def test_valid_receipt_rebuilds_exactly():
    assert validate_perceptual_capability_receipt(_receipt()) is True

"""Bounded neural replay gated by an external SSH history witness."""
import json
from pathlib import Path

from holosim.witnessed_history_recovery import recover_witnessed_history
from holosim.core import HoloChain
from experiments.neural_continuity_absence import (
    NeuralContinuityError,
    history_commitment,
    reconstruct_neural_state,
)


def recover_signed_neural_history(
    *,
    chain_path,
    witness_path,
    expected_chain_id,
    allowed_signers_path,
    dimensions,
    ssh_keygen="ssh-keygen",
):
    """Reconstruct only after a signed exact-history match.

    Does not establish historical occurrence or grant authority.
    """
    # Capture the source once. Verification and replay use this same copy.
    # The external witness and signer policy remain separate.
    import tempfile

    try:
        with tempfile.TemporaryDirectory(prefix="holo-neural-recovery-") as folder:
            snapshot = Path(folder) / "chain.jsonl"

            with Path(chain_path).open("rb") as stream:
                data = stream.read(4_194_305)

            if len(data) > 4_194_304:
                raise NeuralContinuityError("chain exceeds byte limit")

            snapshot.write_bytes(data)

            receipt = recover_witnessed_history(
                chain_path=snapshot,
                witness_path=witness_path,
                expected_chain_id=expected_chain_id,
                allowed_signers_path=allowed_signers_path,
                ssh_keygen=ssh_keygen,
            )

            if receipt["status"] != "MATCHED" or receipt["matched"] is not True:
                raise NeuralContinuityError("signed history verification failed")

            # Reconstruct from the original captured bytes, not a
            # potentially replaced temporary snapshot.
            #
            # Revalidate the captured bytes through a private copy.
            replay_path = Path(folder) / "replay.jsonl"
            replay_path.write_bytes(data)

            entries = HoloChain(replay_path).load_and_verify()

            # Independently bind replayed entries to the signed
            # snapshot's count and head hash.
            observed_count = len(entries)
            observed_head = entries[-1]["hash"] if entries else "0" * 64

            if receipt["observed"] != {
                "entry_count": observed_count,
                "head_hash": observed_head,
            }:
                raise NeuralContinuityError(
                    "replay evidence differs from signed snapshot"
                )

            events = [json.loads(entry["content"]) for entry in entries]
            commitment = history_commitment(events)

    except (ValueError, TypeError, KeyError, OSError, RecursionError) as exc:
        raise NeuralContinuityError("invalid neural chain evidence") from exc

    result = reconstruct_neural_state(
        events,
        dimensions=dimensions,
        supplied_commitment=commitment,
        external_reference=commitment,
        collection_closed=True,
    )

    return {
        **result,
        "type": "signed_neural_history_reconstruction",
        "witness_status": receipt["status"],
        "witness_hash": receipt["witness_hash"],
        "signed_chain_matched": True,
        "reference_custody_verified": False,
        "historical_occurrence_verified": False,
        "continuity_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

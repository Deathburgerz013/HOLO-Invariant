"""Real SSH controls for exact-snapshot witnessed recovery."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from holosim.canonical import canonical_bytes
from holosim.core import HoloChain
from holosim.witnessed_history_recovery import (
    HistoryWitnessError, MAX_CHAIN_BYTES, recover_witnessed_history, sign_history_witness,
)

pytestmark = pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="OpenSSH required")


@pytest.fixture
def setup(tmp_path):
    keys = tmp_path / "external"
    keys.mkdir()
    key = keys / "key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True, capture_output=True)
    policy = keys / "allowed"
    policy.write_text("fixture " + Path(str(key) + ".pub").read_text(), encoding="utf-8")
    chain = tmp_path / "chain.jsonl"
    for text in ("original", "correction", "recheck"):
        HoloChain(chain).append(text)
    witness = keys / "witness.json"
    obj = sign_history_witness(chain_path=chain, chain_id="fixture-chain", signer_identity="fixture", private_key_path=key)
    witness.write_bytes(canonical_bytes(obj))
    args = dict(chain_path=chain, witness_path=witness, expected_chain_id="fixture-chain", allowed_signers_path=policy)
    return args, obj, key


def test_match_read_only_and_authority(setup):
    args, _, _ = setup
    before = {k: Path(args[k]).read_bytes() for k in ("chain_path", "witness_path", "allowed_signers_path")}
    receipt = recover_witnessed_history(**args)
    assert receipt["status"] == "MATCHED"
    assert receipt["matched"] and not receipt["accepted"] and not receipt["truth_claimed"]
    assert receipt["write_authority"] == receipt["execution_authority"] == "NONE"
    assert before == {k: Path(args[k]).read_bytes() for k in before}


def test_rehash_and_original(setup, tmp_path):
    args, _, _ = setup
    original = args["chain_path"].read_bytes()
    entries = HoloChain(args["chain_path"]).load_and_verify()
    entries[0]["content"] = "rewritten"
    previous = "0" * 64
    for entry in entries:
        entry["prev_hash"] = previous
        entry["hash"] = HoloChain(args["chain_path"])._compute_hash(previous, entry["content"], entry["timestamp"], entry["idx"])
        previous = entry["hash"]
    copy = tmp_path / "rehashed.jsonl"
    copy.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    assert len(HoloChain(copy).load_and_verify()) == 3
    assert recover_witnessed_history(**{**args, "chain_path": copy})["status"] == "REJECTED_HEAD"
    assert recover_witnessed_history(**args)["matched"]
    assert args["chain_path"].read_bytes() == original


@pytest.mark.parametrize("count", [0, 1, 2])
def test_rollback(setup, tmp_path, count):
    args, _, _ = setup
    copy = tmp_path / "prefix.jsonl"
    copy.write_bytes(b"".join(args["chain_path"].read_bytes().splitlines(keepends=True)[:count]))
    assert len(HoloChain(copy).load_and_verify()) == count
    assert recover_witnessed_history(**{**args, "chain_path": copy})["status"] == "REJECTED_COUNT"


def test_extension_requires_new_witness(setup):
    args, _, _ = setup
    HoloChain(args["chain_path"]).append("later")
    assert recover_witnessed_history(**args)["status"] == "REJECTED_COUNT"


@pytest.mark.parametrize("field", ["witness_path", "chain_path", "allowed_signers_path"])
def test_missing(setup, field):
    args, _, _ = setup
    Path(args[field]).unlink()
    assert not recover_witnessed_history(**args)["matched"]


def test_untrusted_signer(setup):
    args, _, _ = setup
    args["allowed_signers_path"].write_text("", encoding="utf-8")
    assert recover_witnessed_history(**args)["status"] == "REJECTED_SIGNATURE"


def test_chain_id(setup):
    args, _, _ = setup
    assert recover_witnessed_history(**{**args, "expected_chain_id": "other"})["status"] == "REJECTED_CHAIN_ID"


@pytest.mark.parametrize("field,value", [("entry_count", True), ("entry_count", -1), ("entry_count", 2),
    ("version", True), ("namespace", "other"), ("head_hash", "f" * 64), ("signature", "!"), ("accepted", True)])
def test_forged_witness(setup, field, value):
    args, obj, _ = setup
    obj[field] = value
    args["witness_path"].write_bytes(canonical_bytes(obj))
    assert not recover_witnessed_history(**args)["matched"]


def test_metadata_exclusion_is_not_claimed(setup):
    args, _, _ = setup
    rows = HoloChain(args["chain_path"]).load_and_verify()
    rows[0]["original_size"] = 999
    rows[0]["extra"] = "not hashed"
    args["chain_path"].write_text("".join(json.dumps(e) + "\n" for e in rows), encoding="utf-8")
    assert recover_witnessed_history(**args)["matched"]


def test_same_path_refused(setup):
    args, _, _ = setup
    assert not recover_witnessed_history(**{**args, "witness_path": args["chain_path"]})["matched"]


def test_fresh_process(setup):
    args, _, _ = setup
    code = "import json,sys; from holosim.witnessed_history_recovery import recover_witnessed_history; print(json.dumps(recover_witnessed_history(**json.loads(sys.argv[1]))))"
    result = subprocess.run([sys.executable, "-c", code, json.dumps({k: str(v) for k, v in args.items()})], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == recover_witnessed_history(**args)


def test_tool_unavailable(setup):
    args, _, _ = setup
    assert not recover_witnessed_history(**args, ssh_keygen="missing-history-tool")["matched"]


def test_byte_limit(setup):
    args, _, key = setup
    args["chain_path"].write_bytes(b" " * (MAX_CHAIN_BYTES + 1))
    assert not recover_witnessed_history(**args)["matched"]
    with pytest.raises(HistoryWitnessError):
        sign_history_witness(chain_path=args["chain_path"], chain_id="fixture", signer_identity="fixture", private_key_path=key)


def test_replaced_pair_limit(setup):
    args, _, key = setup
    HoloChain(args["chain_path"]).append("replacement pair")
    obj = sign_history_witness(chain_path=args["chain_path"], chain_id="fixture-chain", signer_identity="fixture", private_key_path=key)
    args["witness_path"].write_bytes(canonical_bytes(obj))
    assert recover_witnessed_history(**args)["matched"]


def test_internal_tamper(setup):
    args, _, _ = setup
    data = args["chain_path"].read_bytes().replace(b"original", b"tampered")
    args["chain_path"].write_bytes(data)
    assert recover_witnessed_history(**args)["status"] == "REJECTED_CHAIN"


def test_empty_snapshot(setup):
    args, _, key = setup
    args["chain_path"].write_bytes(b"")
    obj = sign_history_witness(chain_path=args["chain_path"], chain_id="fixture-chain", signer_identity="fixture", private_key_path=key)
    args["witness_path"].write_bytes(canonical_bytes(obj))
    assert obj["entry_count"] == 0 and obj["head_hash"] == "0" * 64
    assert recover_witnessed_history(**args)["matched"]


def test_invalid_index_type(setup):
    args, _, _ = setup
    rows = HoloChain(args["chain_path"]).load_and_verify()
    rows[0]["idx"] = True
    args["chain_path"].write_text("".join(json.dumps(e) + "\n" for e in rows), encoding="utf-8")
    assert recover_witnessed_history(**args)["status"] == "REJECTED_CHAIN"


def test_oversized_witness(setup):
    args, _, _ = setup
    args["witness_path"].write_bytes(b" " * 16385)
    assert recover_witnessed_history(**args)["status"] == "REJECTED_WITNESS"


def test_deep_malformed_witness(setup):
    args, _, _ = setup
    args["witness_path"].write_bytes(b"[" * 2000 + b"0" + b"]" * 2000)
    assert recover_witnessed_history(**args)["status"] == "REJECTED_WITNESS"

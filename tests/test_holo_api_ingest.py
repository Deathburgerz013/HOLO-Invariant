import json

from holosim.api import HoloAPI


def _write_chunk(directory, *, content="actual ingested content"):
    chunk = directory / "mine_000001.json"
    chunk.write_text(
        json.dumps(
            {
                "index": 1,
                "hash": "a" * 64,
                "data": content,
            }
        ),
        encoding="utf-8",
    )


def test_ingest_forwards_approval_into_selected_chain(tmp_path):
    chain_path = tmp_path / "selected-chain.jsonl"
    _write_chunk(tmp_path)
    api = HoloAPI(chain_path)

    result = api.ingest(
        tmp_path,
        force=True,
        reviewer="external-reviewer",
        approval_reference="approval-001",
    )

    assert result["ingest"]["files_seen"] == 1
    assert result["ingest"]["collected"] == 1
    assert result["ingest"]["blocked"] == 0
    assert result["verify"]["entries"] == 1
    assert result["verify"]["chain_file"] == str(chain_path)
    assert chain_path.exists()


def test_ingest_without_approval_blocks_selected_chain(tmp_path):
    chain_path = tmp_path / "selected-chain.jsonl"
    _write_chunk(tmp_path)
    api = HoloAPI(chain_path)

    result = api.ingest(tmp_path, force=True)

    assert result["ingest"]["files_seen"] == 1
    assert result["ingest"]["collected"] == 0
    assert result["ingest"]["blocked"] == 1
    assert result["verify"]["entries"] == 0

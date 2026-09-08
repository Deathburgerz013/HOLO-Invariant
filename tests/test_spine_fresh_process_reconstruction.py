import json
import subprocess
import sys
from pathlib import Path


SPINE_PATH = Path("docs") / "Continuity_findings"

EXTRACT_SCRIPT = r"""
import json
import sys
from pathlib import Path
from holosim.spine_protocol import extract_compartment_frames

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
frames = extract_compartment_frames(text)
print(json.dumps(frames, sort_keys=True, ensure_ascii=True, separators=(",", ":")))
"""


def _extract_in_fresh_process(path: Path) -> list[dict]:
    completed = subprocess.run(
        [sys.executable, "-c", EXTRACT_SCRIPT, str(path)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, (
        "fresh-process extraction failed\n"
        f"returncode={completed.returncode}\n"
        f"stdout={completed.stdout}\n"
        f"stderr={completed.stderr}"
    )
    return json.loads(completed.stdout)


def test_historical_spine_frames_reconstruct_identically_across_fresh_processes():
    source_before = SPINE_PATH.read_bytes()

    first = _extract_in_fresh_process(SPINE_PATH)
    second = _extract_in_fresh_process(SPINE_PATH)

    assert first
    assert first == second

    assert [frame["frame_id"] for frame in first] == [
        frame["frame_id"] for frame in second
    ]
    assert [
        (frame["source_start_line"], frame["source_end_line"])
        for frame in first
    ] == [
        (frame["source_start_line"], frame["source_end_line"])
        for frame in second
    ]
    assert [frame["source_lines"] for frame in first] == [
        frame["source_lines"] for frame in second
    ]

    assert SPINE_PATH.read_bytes() == source_before


def test_historical_spine_frame_serialization_is_deterministic_across_fresh_processes():
    first = _extract_in_fresh_process(SPINE_PATH)
    second = _extract_in_fresh_process(SPINE_PATH)

    first_serialized = json.dumps(
        first,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    second_serialized = json.dumps(
        second,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )

    assert first_serialized == second_serialized

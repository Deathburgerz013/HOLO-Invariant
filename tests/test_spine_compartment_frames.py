import holosim.spine_protocol as spine_protocol


TWO_COMPARTMENT_SPINE = """\
|===============================|
| }=============================|
| | FRAME_ID: alpha
| | INPUT: source-a
| }=============================|
| | FRAME_ID: beta
| | INPUT: source-b
| }=============================|
"""


def test_protocol_exposes_bounded_compartment_frame_extraction():
    extractor = getattr(spine_protocol, "extract_compartment_frames", None)

    assert callable(extractor), (
        "spine_protocol can analyze rail geometry, but exposes no "
        "extract_compartment_frames() operation for bounded compartments"
    )

    frames = extractor(TWO_COMPARTMENT_SPINE)

    assert len(frames) == 2

    assert frames[0]["source_start_line"] == 3
    assert frames[0]["source_end_line"] == 4
    assert frames[1]["source_start_line"] == 6
    assert frames[1]["source_end_line"] == 7

    assert frames[0]["source_lines"] == [
        "| | FRAME_ID: alpha",
        "| | INPUT: source-a",
    ]
    assert frames[1]["source_lines"] == [
        "| | FRAME_ID: beta",
        "| | INPUT: source-b",
    ]

    assert frames[0]["frame_id"]
    assert frames[1]["frame_id"]
    assert frames[0]["frame_id"] != frames[1]["frame_id"]

    repeated = extractor(TWO_COMPARTMENT_SPINE)
    assert [frame["frame_id"] for frame in repeated] == [
        frame["frame_id"] for frame in frames
    ]

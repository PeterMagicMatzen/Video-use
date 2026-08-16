from __future__ import annotations

from talking_head import apply_bin, build_ranges, guess_name, hook_line, is_keeper


def test_drops_fillers_and_weak_tails():
    assert is_keeper({"text": "Hi, I'm Shubham, and this is a talking head", "start": 0, "end": 2})
    assert not is_keeper({"text": "um uh", "start": 0, "end": 1})
    assert not is_keeper({"text": "So yeah.", "start": 0, "end": 1})


def test_guess_name_and_hook():
    phrases = [
        {"start": 0.04, "end": 4.72, "text": "Hi, I'm Shubham, and this is a talking head video"},
        {"start": 5.0, "end": 6.0, "text": "um"},
    ]
    assert guess_name(phrases) == "Shubham"
    assert "SHUBHAM" in hook_line(phrases)


def test_build_ranges_pads_keepers_only():
    takes = [{
        "name": "take1",
        "path": "x",
        "phrases": [
            {"start": 1.00, "end": 2.00, "text": "We built a repository"},
            {"start": 2.50, "end": 2.80, "text": "uh"},
            {"start": 3.00, "end": 4.00, "text": "So yeah."},
        ],
    }]
    ranges = build_ranges(takes)
    assert len(ranges) == 1
    assert ranges[0]["start"] == 0.95
    assert ranges[0]["end"] == 2.08
    assert ranges[0]["source"] == "take1"


def test_apply_bin_inserts_broll(tmp_path):
    broll = tmp_path / "street.mp4"
    broll.write_bytes(b"x")
    ranges = [{"source": "a", "start": 0.0, "end": 2.0, "beat": "HOOK"}]
    sources = {"a": "a.mp4"}
    extras = [{"kind": "broll", "file": str(broll), "duration": 2.5, "label": "street.mp4"}]
    out_ranges, _ov, out_src, _audio = apply_bin(ranges, [], sources, extras, tmp_path)
    assert any(r["beat"] == "BROLL" for r in out_ranges)
    assert "broll_street" in out_src

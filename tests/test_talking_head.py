from __future__ import annotations

from talking_head import build_ranges, guess_name, hook_line, is_keeper


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

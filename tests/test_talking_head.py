from __future__ import annotations

from talking_head import apply_bin, build_ranges, guess_name, hook_line, is_keeper, mark_cinematic_cuts, merge_auto_sfx, title_pack


def test_drops_fillers_and_weak_tails():
    assert is_keeper({"text": "Hi, I'm Shubham, and this is a talking head", "start": 0, "end": 2})
    assert not is_keeper({"text": "um uh", "start": 0, "end": 1})
    assert not is_keeper({"text": "So yeah.", "start": 0, "end": 1})
    assert not is_keeper({"text": "So yeah,", "start": 0, "end": 1})


def test_guess_name_and_hook():
    phrases = [
        {"start": 0.04, "end": 4.72, "text": "Hi, I'm Shubham, and this is a talking head video"},
        {"start": 5.0, "end": 6.0, "text": "um"},
    ]
    assert guess_name(phrases) == "Shubham"
    assert guess_name([{"text": "This is the second sample reel."}]) is None


def test_title_pack_skips_generic_talking_head_stamp():
    phrases = [
        {"start": 0.0, "end": 2.2, "text": "This is the second sample reel."},
        {"start": 6.9, "end": 8.4, "text": "that captions get added,"},
        {"start": 11.3, "end": 13.3, "text": "B-rolls and graphics somewhere here"},
        {"start": 14.7, "end": 20.1, "text": "explaining how I can edit videos from AI using the Video Use repository."},
    ]
    pack = title_pack(phrases)
    assert pack["name"] is None
    assert pack["role"] is None
    blob = " ".join([pack.get("hook") or "", pack.get("end") or ""] + [k[1] for k in pack["keywords"]])
    assert "TALKING HEAD" not in blob
    assert "SPEAKER" not in blob
    assert any(k in blob for k in ("CAPTION", "B-ROLL", "VIDEO USE", "AI"))


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


def test_mark_cinematic_cuts_zooms_hook_and_later_beats():
    ranges = [
        {"beat": "HOOK", "start": 0.0, "end": 2.0},
        {"beat": "TALK_02", "start": 2.0, "end": 3.2},
        {"beat": "TALK_03", "start": 3.2, "end": 4.0},
        {"beat": "TALK_04", "start": 4.0, "end": 5.5},
    ]
    out = mark_cinematic_cuts(ranges)
    assert out[0]["zoom"] >= 1.08
    assert any(r.get("zoom", 1) > 1.15 and r["beat"].startswith("TALK") for r in out)


def test_merge_auto_sfx_fills_bin_when_user_added_none():
    extras = merge_auto_sfx(
        [],
        [
            {"kind": "sfx", "role": "whoosh", "file": "C:/sfx/whoosh.mp3", "duration": 1.2},
            {"kind": "sfx", "role": "hit", "file": "C:/sfx/hit.mp3", "duration": 0.8},
        ],
    )
    assert len(extras) == 2
    assert extras[0]["role"] == "whoosh"


def test_merge_auto_sfx_keeps_user_picks():
    user = [{"kind": "sfx", "file": "C:/mine.mp3", "duration": 2.0}]
    extras = merge_auto_sfx(
        user,
        [{"kind": "sfx", "role": "whoosh", "file": "C:/sfx/whoosh.mp3", "duration": 1.2}],
    )
    assert extras == user

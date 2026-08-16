from cut_picks import apply_cut_picks, normalize_variation, parse_claude_score, strip_cinematic, VARIATIONS


def test_normalize_variation():
    assert normalize_variation("ENERGY") == "energy"
    assert normalize_variation("nope") == "energy"
    assert normalize_variation("calm") == "calm"
    assert set(VARIATIONS) == {"energy", "tight", "calm"}


def test_apply_cut_picks_zooms_and_drops():
    ranges = [
        {"beat": "HOOK", "start": 0.0, "end": 2.0, "quote": "hi"},
        {"beat": "TALK_02", "start": 2.0, "end": 3.0, "quote": "skip me"},
        {"beat": "TALK_03", "start": 3.0, "end": 5.0, "quote": "keep"},
    ]
    out = apply_cut_picks(ranges, [
        {"i": 0, "keep": True, "zoom": 1.2, "reason": "open"},
        {"i": 1, "keep": False, "zoom": 1.0, "reason": "weak"},
        {"i": 2, "keep": True, "zoom": 1.35, "reason": "punch"},
    ])
    assert len(out) == 2
    assert out[0]["zoom"] == 1.2
    assert out[1]["zoom"] == 1.35
    assert out[1]["quote"] == "keep"


def test_strip_cinematic_removes_zoom():
    ranges = [{"beat": "HOOK", "zoom": 1.28, "start": 0, "end": 1}]
    out = strip_cinematic(ranges)
    assert "zoom" not in out[0] or out[0].get("zoom", 1) == 1


def test_parse_claude_score_reads_cuts_and_picks():
    data = {
        "variation": "tight",
        "cuts": [{"i": 0, "keep": True, "zoom": 1.1}],
        "picks": [{"id": "1143", "start_s": 0.1, "duration_s": 1.0}],
    }
    score = parse_claude_score(data)
    assert score["variation"] == "tight"
    assert score["cuts"][0]["zoom"] == 1.1
    assert score["picks"][0]["id"] == "1143"

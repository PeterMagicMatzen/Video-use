from voice_picks import apply_voice_picks, editorial_catalog, parse_voice_picks, voice_catalog


def test_voice_catalog_keeps_laughs_and_drops_dogs():
    items = [
        {"id": "1", "title": "Dog barking twice", "file": "C:/sfx/dog.mp3"},
        {"id": "424", "title": "Crowd laugh", "file": "C:/sfx/laugh.mp3"},
        {"id": "2011", "title": "Auditorium moderate applause and cheering", "file": "C:/sfx/cheer.mp3"},
        {"id": "1143", "title": "Cinematic whoosh deep impact", "file": "C:/sfx/whoosh.mp3"},
    ]
    voices = editorial_catalog(items)
    titles = {row["title"] for row in voices}
    assert "Crowd laugh" in titles
    assert "Auditorium moderate applause and cheering" in titles
    assert "Cinematic whoosh deep impact" in titles
    assert "Dog barking twice" not in titles
    assert voice_catalog(items) == editorial_catalog(items)


def test_parse_voice_picks_rejects_unknown_and_caps_duration():
    catalog = {
        "424": {"id": "424", "title": "Crowd laugh", "file": "C:/sfx/laugh.mp3"},
    }
    picks = parse_voice_picks(
        {
            "picks": [
                {"id": "424", "start_s": 4.2, "duration_s": 9.0, "reason": "laugh after joke"},
                {"id": "999", "start_s": 1.0, "duration_s": 1.0, "reason": "missing"},
            ]
        },
        catalog,
        total_s=13.0,
    )
    assert len(picks) == 1
    assert picks[0]["file"].endswith("laugh.mp3")
    assert picks[0]["duration"] <= 2.4
    assert picks[0]["start_in_output"] == 4.2


def test_parse_allows_many_layered_picks_and_reuse():
    catalog = {
        "424": {"id": "424", "title": "Crowd laugh", "file": "C:/sfx/laugh.mp3"},
        "1143": {"id": "1143", "title": "Cinematic whoosh", "file": "C:/sfx/whoosh.mp3"},
    }
    raw = {"picks": [
        {"id": "1143", "start_s": 0.05, "duration_s": 1.2, "reason": "open"},
        {"id": "424", "start_s": 3.0, "duration_s": 1.0, "reason": "react"},
        {"id": "424", "start_s": 8.0, "duration_s": 1.1, "reason": "react again"},
        {"id": "1143", "start_s": 6.0, "duration_s": 0.8, "reason": "cut"},
    ]}
    picks = parse_voice_picks(raw, catalog, total_s=13.0)
    assert len(picks) == 4
    assert [p["id"] for p in picks].count("424") == 2


def test_apply_voice_picks_appends_without_dropping_auto_sfx():
    edl = {
        "audio_overlays": [{"file": "C:/sfx/whoosh.mp3", "start_in_output": 0.06, "duration": 1.5}],
        "total_duration_s": 13.0,
    }
    apply_voice_picks(
        edl,
        [{"file": "C:/sfx/laugh.mp3", "start_in_output": 4.2, "duration": 1.4}],
    )
    assert len(edl["audio_overlays"]) == 2
    assert edl["audio_overlays"][1]["file"].endswith("laugh.mp3")

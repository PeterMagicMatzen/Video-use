from pathlib import Path

from pexels_library import match_photo
from visual_picks import apply_visuals, mixkit_mp4_url, parse_visuals, slug_query


def test_slug_query():
    assert slug_query("Laptop coding!") == "laptop"
    assert slug_query("video editing software") == "technology"


def test_mixkit_mp4_url():
    assert mixkit_mp4_url("242", "720") == "https://assets.mixkit.co/videos/242/242-720.mp4"


def test_parse_visuals_keeps_broll_and_graphic():
    visuals = parse_visuals({
        "visuals": [
            {"kind": "broll", "query": "laptop typing", "after_i": 1, "duration_s": 2.0},
            {"kind": "graphic", "text": "VIDEOUSE", "start_s": 4.0, "duration_s": 2.1},
            {"kind": "broll", "query": ""},
        ]
    })
    assert len(visuals) == 2
    assert visuals[0]["kind"] == "broll"
    assert visuals[1]["text"] == "VIDEOUSE"


def test_parse_visuals_accepts_pexels_photo_id():
    visuals = parse_visuals({
        "visuals": [{"kind": "broll", "photo_id": "1181675", "after_i": 0, "duration_s": 2.0}],
    })
    assert visuals[0]["photo_id"] == "1181675"


def test_match_photo_uses_tags():
    items = [
        {"id": "1", "title": "Forest path", "tags": ["nature", "trees"]},
        {"id": "2", "title": "Laptop with code", "tags": ["laptop", "code", "technology"]},
    ]
    hit = match_photo("editing on a laptop", items)
    assert hit is not None
    assert hit["id"] == "2"


def test_apply_visuals_inserts_broll_and_graphic(tmp_path):
    clip = tmp_path / "street.mp4"
    clip.write_bytes(b"not-real")
    edl = {
        "sources": {"talk": "talk.mp4"},
        "ranges": [
            {"source": "talk", "start": 0.0, "end": 2.0, "beat": "HOOK"},
            {"source": "talk", "start": 2.0, "end": 4.0, "beat": "TALK_02"},
        ],
        "overlays": [],
        "total_duration_s": 4.0,
    }
    apply_visuals(
        edl,
        [
            {"kind": "broll", "query": "city", "after_i": 0, "duration_s": 1.5, "file": str(clip), "reason": "cutaway"},
            {"kind": "graphic", "text": "HOOK", "start_s": 0.2, "duration_s": 1.8},
        ],
        tmp_path,
        fetch=False,
    )
    assert any(r.get("beat") == "BROLL" for r in edl["ranges"])
    assert "broll_street" in edl["sources"]
    assert any(Path(str(o.get("file", ""))).suffix in {".mov", ".mp4"} for o in edl["overlays"])

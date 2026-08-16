from sfx_library import load_catalog, pick_auto_sfx


def test_catalog_loads():
    data = load_catalog()
    assert "items" in data
    assert data["count"] == len(data["items"])
    if data["items"]:
        assert data["items"][0]["file"]
        assert data["items"][0]["title"]


def test_pick_auto_sfx_selects_whoosh_hit_riser():
    items = [
        {"title": "Dog barking twice", "file": "C:/sfx/dog.mp3"},
        {"title": "Cinematic whoosh deep impact", "file": "C:/sfx/whoosh.mp3"},
        {"title": "Fast impact blow", "file": "C:/sfx/hit.mp3"},
        {"title": "Cinematic mysterious riser brass", "file": "C:/sfx/riser.mp3"},
    ]
    picked = pick_auto_sfx(items)
    by_role = {row["role"]: row for row in picked}
    assert by_role["whoosh"]["file"].endswith("whoosh.mp3")
    assert by_role["hit"]["file"].endswith("hit.mp3")
    assert by_role["riser"]["file"].endswith("riser.mp3")
    assert all(row["kind"] == "sfx" for row in picked)

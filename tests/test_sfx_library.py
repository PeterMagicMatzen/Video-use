from sfx_library import load_catalog


def test_catalog_loads():
    data = load_catalog()
    assert "items" in data
    assert data["count"] == len(data["items"])
    if data["items"]:
        assert data["items"][0]["file"]
        assert data["items"][0]["title"]

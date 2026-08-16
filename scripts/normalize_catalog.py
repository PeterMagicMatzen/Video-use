import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cat = root / "library" / "sfx" / "catalog.json"
data = json.loads(cat.read_text(encoding="utf-8"))
for item in data["items"]:
    rel = item.get("rel")
    if not rel and item.get("file"):
        p = Path(item["file"])
        item["rel"] = f"library/sfx/{p.name}"
    item.pop("file", None)
cat.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("normalized", data["count"])

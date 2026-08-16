import re
import urllib.request

url = "https://mixkit.co/free-sound-effects/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
for pat in [r"/api/[^\"']+", r"sfx/preview/[^\"']+", r"sfx/download/[^\"']+", r"sound_effects", r"free-sfx"]:
    hits = re.findall(pat, html)
    print(pat, len(hits), hits[:8])

# dump interesting lines
for line in html.splitlines():
    if "sfx" in line.lower() and ("http" in line or "api" in line or "json" in line):
        print(line[:240])

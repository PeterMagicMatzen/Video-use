"""Run the video-use API+UI with no console signal handlers."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

LOG = Path.home() / ".video-use" / "server.log"
LOG.parent.mkdir(parents=True, exist_ok=True)
_log = open(LOG, "a", encoding="utf-8", buffering=1)
sys.stdout = _log
sys.stderr = _log

import uvicorn

config = uvicorn.Config(
    "app.server.main:app",
    host="127.0.0.1",
    port=8787,
    reload=False,
    log_level="info",
)
server = uvicorn.Server(config)
server.install_signal_handlers = False
server.run()

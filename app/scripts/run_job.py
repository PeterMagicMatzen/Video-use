"""Detached worker: transcribe / auto-edit / render. Survives API restarts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.server.jobs import (
    run_auto_edit_sync,
    run_claude_voices_sync,
    run_generate_sync,
    run_render_sync,
    run_strip_sync,
    run_transcribe_sync,
    run_undo_sync,
)


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: run_job.py transcribe|generate|auto-edit|claude-voices|undo|strip|render-preview|render-final FOLDER", file=sys.stderr)
        return 2
    kind = sys.argv[1]
    folder = Path(sys.argv[2])
    if kind == "transcribe":
        run_transcribe_sync(folder)
    elif kind == "generate":
        run_generate_sync(folder)
    elif kind == "auto-edit":
        run_auto_edit_sync(folder)
    elif kind == "claude-voices":
        run_claude_voices_sync(folder)
    elif kind == "undo":
        run_undo_sync(folder)
    elif kind == "strip":
        run_strip_sync(folder)
    elif kind == "render-preview":
        run_render_sync(folder, preview=True)
    elif kind == "render-final":
        run_render_sync(folder, preview=False)
    else:
        print(f"unknown job {kind}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

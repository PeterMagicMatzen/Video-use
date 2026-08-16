### Task 9: Claude adapter

**Files:**
- Create: `app/server/claude.py`
- Create: `tests/test_claude.py`
- Modify: `app/server/main.py`
- Modify: `SKILL.md` (short “driven by the local app” note at the top of The process)

**Interfaces:**
- Consumes: session, `REPO_ROOT`, `HELPERS`
- Produces:

```python
CLAUDE_TIMEOUT_S = 600

EDITOR_BRIEF = """You are the video-use editor for this footage folder.
Read edit/takes_packed.md and edit/project.md if it exists.
Propose or revise a strategy in prose.
Do not write edit/edl.json until you receive a message that begins with STRATEGY_APPROVED.
Do not run ffmpeg, transcribe, render, or install anything.
Write only under edit/.
"""

APPROVE_PROMPT = """STRATEGY_APPROVED
Write edit/edl.json only, using the video-use schema (version, sources, ranges, grade, overlays, subtitles, total_duration_s).
Source paths must be absolute paths to the files in this folder.
Then stop. Do not render.
"""

def claude_cmd(*, folder: Path, session_id: str | None, prompt: str) -> list[str]
def parse_session_id(stream_line: str) -> str | None
def stream_claude(*, folder: Path, prompt: str, session: dict) -> Iterator[str]
# yields text deltas; updates session["claude_session_id"] when seen
# raises RuntimeError on non-zero after the process ends
# timeout CLAUDE_TIMEOUT_S

def ensure_single_claude(session: dict) -> None
# raise RuntimeError("busy") if job.kind == "claude"
```

`claude_cmd` must produce:

First turn (`session_id` is None):

```
claude -p --output-format stream-json --append-system-prompt <EDITOR_BRIEF>
  --allowedTools Read,Write,Edit,Glob,Grep
  --disallowedTools Bash,WebSearch,WebFetch,Agent
  --add-dir <folder> --add-dir <REPO_ROOT>
  <prompt>
```

Later turns: same plus `--resume <session_id>`. Never `--continue`. Never `--dangerously-skip-permissions`.

`parse_session_id`: if the JSON line has `session_id`, return it (covers `type=system` init and `type=result`).

Routes:

- `POST /api/chat` body `{ "message": str }` — 400 if chat disabled; 409 if busy; SSE `text/event-stream` of `{ "text": ... }` chunks, then `{ "done": true }`. Sets `chat_after_approve=True` when the turn finishes (this is not approve).
- `POST /api/chat/retry` — resend `session["last_prompt"]` with the same session id.
- `POST /api/reject` body `{ "note": str }` — stores `session["pending_note"]` and returns 200. Next chat prepends the note.

Do not write `edl.json` in this task from the API.

- [ ] **Step 1: Write the failing tests**

`tests/test_claude.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from app.server.claude import claude_cmd, parse_session_id, EDITOR_BRIEF
from app.server.paths import REPO_ROOT


def test_first_turn_has_no_resume(tmp_path: Path):
    cmd = claude_cmd(folder=tmp_path, session_id=None, prompt="hello")
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "--continue" not in cmd
    assert "--resume" not in cmd
    assert "--dangerously-skip-permissions" not in cmd
    assert "--output-format" in cmd
    assert "stream-json" in cmd
    assert "--allowedTools" in cmd
    assert "Bash" in " ".join(cmd)
    # Bash is disallowed
    dis = cmd.index("--disallowedTools")
    assert "Bash" in cmd[dis + 1]
    assert str(tmp_path) in cmd
    assert str(REPO_ROOT) in cmd
    assert any(EDITOR_BRIEF[:20] in a for a in cmd) or "--append-system-prompt" in cmd


def test_later_turn_resumes(tmp_path: Path):
    cmd = claude_cmd(folder=tmp_path, session_id="abc-123", prompt="more")
    assert "--resume" in cmd
    assert "abc-123" in cmd
    assert "--continue" not in cmd


def test_parse_session_id():
    assert parse_session_id('{"type":"system","subtype":"init","session_id":"sid-1"}') == "sid-1"
    assert parse_session_id("not-json") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_claude.py -v`

Expected: FAIL with import error

- [ ] **Step 3: Implement `app/server/claude.py` and chat routes**

Implement `stream_claude` with `subprocess.Popen`, `stdout` line-buffered, `env=helper_env()`, `cwd=folder`. Kill on timeout. Parse stream-json lines: if `type == "assistant"` extract text from `message.content[].text` and yield it; also yield `delta` / `partial` text if present. Persist `claude_session_id` via `save_session` as soon as it appears.

In `SKILL.md`, after the Hard Rules list, add:

```markdown
When you are launched by the video-use local app, do **not** transcribe, render, or call ffmpeg. The app owns those steps. Read `edit/takes_packed.md`, discuss strategy, and write `edit/edl.json` only after `STRATEGY_APPROVED`.
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_claude.py tests/test_api.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/server/claude.py app/server/main.py tests/test_claude.py SKILL.md
git commit -m "feat: stream Claude editorial turns into the app"
```

---


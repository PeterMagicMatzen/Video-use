# Task 12 Report: chat SSE in the UI + retry

## Status

**Complete.** Branch `local-app`. Not pushed.

## What shipped

| File | Role |
|------|------|
| `app/web/src/api.ts` | Replaced `postChat` poll/drain with verbatim `streamChat` + `retryChat` (same reader loop, `POST /api/chat/retry`) |
| `app/web/src/App.tsx` | Right column appends assistant `ev.text` chunks; error text + Retry |

`app/server/main.py` already SSE (`text/event-stream`, `{text}` then `{done: true}`). No server change.

## Interfaces (verbatim)

```typescript
export async function streamChat(message: string, onText: (t: string) => void) {
  const r = await fetch(`${API}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!r.ok || !r.body) throw new Error(await r.text());
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() || "";
    for (const part of parts) {
      const line = part.replace(/^data:\s*/, "");
      if (!line) continue;
      const ev = JSON.parse(line);
      if (ev.text) onText(ev.text);
    }
  }
}
```

Retry button calls `POST /api/chat/retry` with the same reader loop (`retryChat`).

## TDD / steps

1. Replaced `postChat` with verbatim `streamChat`. Added `retryChat` (same loop, no body).
2. Wired Send → `streamChat`. Chunks append to a per-turn assistant line. On throw: `chatNotice` + enable Retry. Retry → `retryChat` (new assistant line).
3. `npm test` in `app/web` → **2 passed**. `npm run build` → tsc + vite OK.
4. Manual: `python -m app` + `npm run dev`. Opened `http://localhost:5173`. Page loads. Doctor strip: ffmpeg, ffprobe, claude, libass, elevenlabs. Chat disabled (no folder). Send/Retry disabled. `/api/state` 404 is expected (no folder) then doctor+recents.
5. Committed only `app/web/src/api.ts` and `app/web/src/App.tsx`.

## Commit

```
9612894 feat: stream Claude chat into the review UI
```

Files: `app/web/src/api.ts`, `app/web/src/App.tsx`. `.superpowers/` and `.env` not committed. Not pushed.

## Test summary

```
> web@0.0.0 test
> vitest run

 RUN  v4.1.10 C:/Users/Varun B/Developer/video-use/app/web

 ✓ src/centerState.test.ts (2 tests) 3ms

 Test Files  1 passed (1)
      Tests  2 passed (2)
```

`npm run build` (`tsc -b && vite build`) succeeded.

Manual (`http://localhost:5173`, API `127.0.0.1:8787`): page title `video-use`; doctor names only; chat placeholder “Chat disabled until packed”; Send + Retry present and disabled. No footage used.

## Self-review

### Matches brief

- `streamChat` copied verbatim (POST `/api/chat`, `data:` JSON, `ev.text` → `onText`).
- Retry uses the same reader loop against `POST /api/chat/retry`.
- Assistant text grows as chunks arrive. Errors show in the right column; Retry enables only after a failed turn.
- Chat route was already SSE; `main.py` unchanged.
- Manual check: UI loads, doctor strip appears, chat stays disabled with no folder.
- Commit message and file list match the brief.

### Deviation

1. **`retryChat` helper.** Brief specified the Retry URL + “same reader loop,” not a name. Extracted so App does not inline fetch. Loop is a copy of `streamChat` (not a shared function) so `streamChat` stays verbatim.
2. **Per-turn appender.** Retry starts a new assistant line instead of concatenating onto a partial failed reply.
3. **Chat errors stay in the chat column** (`chatNotice`), not center `actionError`. Center `run()` is unchanged for folder/jobs.
4. **No live SSE unit test.** Brief did not add one. Existing button tests + `tsc` only.
5. **CRLF warning** on commit (Windows checkout). Same as prior UI commit.

### Concerns / notes

1. **Raw FastAPI bodies.** `throw new Error(await r.text())` surfaces `{"detail":"chat disabled"}` etc. Verbatim; not pretty-printed.
2. **Leftover SSE buffer.** Verbatim loop does not flush `buf` after `done`. Server events end with `\n\n`, including `{done: true}`.
3. **`JSON.parse` mid-stream** throws, enables Retry, keeps any text already appended.
4. **Refresh after a good turn is inside the same try.** If `GET /api/state` fails after Claude finished, Retry enables even though the turn succeeded.
5. **No `job: claude` in the center during the stream.** UI does not refresh until the reader finishes; by then the job is idle. Tokens in the right column are the progress.
6. **No in-repo test of the reader.** Official tests do not mock `fetch` / ReadableStream.
7. **CORS remains `http://localhost:5173` only.** Opened that origin, not `127.0.0.1:5173`.
8. **Chat log is still in-memory.** Refresh loses it.
9. **`{done: true}` is ignored** (`ev.text` only), as specified.

### Not done (out of scope)

- Installer / `dev.ps1` (Task 13).
- Commit of `.superpowers/` or `.env`.
- Push.

## Ready for next task

Yes — the review UI streams Claude tokens and can retry the last prompt. Open the UI as `http://localhost:5173` with the API on `127.0.0.1:8787`.

## Fix

**Issue:** After a successful `streamChat`/`retryChat`, `refresh()` lived in the same `try`. A failed `GET /api/state` set `chatRetry`, which could burn another Claude turn.

**Change:** `runChat` only enables Retry on chat stream errors. `refresh()` failures go to center `actionError` without Retry.

### Commands

```
cd app/web
npm.cmd test
npm.cmd run build
```

### Output

```
> web@0.0.0 test
> vitest run

 RUN  v4.1.10 C:/Users/Varun B/Developer/video-use/app/web

 ✓ src/centerState.test.ts (2 tests) 4ms

 Test Files  1 passed (1)
      Tests  2 passed (2)
   Start at  16:35:49
   Duration  262ms (transform 37ms, setup 0ms, import 56ms, tests 4ms, environment 0ms)


> web@0.0.0 build
> tsc -b && vite build

vite v8.2.1 building client environment for production...
transforming...✓ 19 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.45 kB │ gzip:  0.29 kB
dist/assets/index-DrunlPym.css    1.29 kB │ gzip:  0.61 kB
dist/assets/index-CuLAxPBD.js   197.75 kB │ gzip: 62.16 kB

✓ built in 256ms
```

### Commit

```
git add app/web/src/App.tsx
git commit -m "fix: do not retry chat when state refresh fails"
```

Not pushed. Branch `local-app`.

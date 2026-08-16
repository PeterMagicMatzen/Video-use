# Task 11 Report: Vite UI — layout + state rendering

## Status

**Complete.** Branch `local-app`. Not pushed.

## What shipped

| File | Role |
|------|------|
| `app/web/*` | Vite + React + TS scaffold (`create-vite@9` react-ts) |
| `app/web/src/buttons.ts` | Enable rules (verbatim) |
| `app/web/src/centerState.test.ts` | Button tests (verbatim) |
| `app/web/src/api.ts` | `API`, `getState` (verbatim) + folder/job/chat helpers |
| `app/web/src/types.ts` | `project_payload` field types |
| `app/web/src/App.tsx` | Three-column page |
| `app/web/src/App.css` | Equal columns, full viewport |
| `app/web/vite.config.ts` | port 5173, `strictPort: true` |
| `app/web/vitest.config.ts` | `vitest run` |

UI talks only to `http://127.0.0.1:8787`. Never calls ffmpeg or Claude.

## Interfaces (verbatim)

```typescript
export const API = "http://127.0.0.1:8787";

export async function getState() {
  const r = await fetch(`${API}/api/state`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
```

```typescript
export function canChat(state: string, doctorOk: boolean) {
  return doctorOk && !["empty", "inventory", "transcribing"].includes(state);
}
export function canTranscribe(state: string, doctorOk: boolean) {
  return doctorOk && ["inventory", "packed", "error"].includes(state);
}
export function canApprove(state: string, doctorOk: boolean) {
  return doctorOk && ["packed", "strategy-ready", "stale", "preview-ready", "error"].includes(state);
}
export function canRenderFinal(state: string) {
  return state === "preview-ready";
}
```

`centerState.test.ts` matches the later, non-contradictory brief (empty disables chat/approve; packed enables chat/approve when doctor ok).

## TDD steps

1. `npm create vite@latest web -- --template react-ts --no-interactive` (ran from repo root by mistake → `web/`; moved to `app/web`). `npm install` + `npm install -D vitest`. Set `vite.config.ts` and `"test": "vitest run"`.
2. Wrote `centerState.test.ts` verbatim **without** `buttons.ts`. `npm test` → **FAIL** (`Cannot find module './buttons'`).
3. Added `buttons.ts` verbatim. `npm test` → **2 passed**.
4. Built three-column `App.tsx` + `api.ts` / `types.ts` / CSS.
5. `npm test` → **2 passed**. `npm run build` → tsc + vite OK.
6. Committed `app/web` (not `node_modules`, not `package-lock.json`, not `.env`).

## Commit

```
a811e0d feat: three-column local app UI
```

23 files under `app/web/`. `.superpowers/` and `.env` not committed. Not pushed.

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

## Self-review

### Matches brief

- Official Vite React TS scaffold in `app/web`; server `port: 5173`, `strictPort: true`.
- `buttons.ts` / `centerState.test.ts` / `getState` copied from the later Interfaces block (not a contradictory draft).
- Left: doctor strip (check **name** + green/red only; no `detail`, no keys), path input, Browse → `POST /api/folder/browse` then refresh, recents, sources (`name`, `duration_s`, `width`×`height`, `fps`), Open edit → `POST /api/open-edit`.
- Center: `center_state` label, `error` text, packed `<pre>`, `edl.ranges`, `<video src={`${API}/api/media/preview`}>` if `has_preview` else first source `/api/media/source/{name}`, Transcribe / Approve & preview / Render final / Reject (`prompt` → `POST /api/reject`). Disabled from `buttons.ts`. Poll `GET /api/state` every 1s while `job.kind !== "idle"`.
- Right: chat log, textarea, Send → `POST /api/chat`. `"chat not connected"` only on HTTP 404. JSON body treated as a non-stream fallback; SSE is drained and state is polled. Streaming is Task 12.
- Three equal columns, full viewport, no CSS framework.
- Tests: fail without `buttons.ts`, then pass. UI never calls ffmpeg/claude.

### Deviation

1. **`npm create vite` cwd.** First create landed in repo-root `web/` because the shell started at the repo root. Moved to `app/web` before install. No leftover root `package.json` / `node_modules`.
2. **`npm.ps1` blocked** by Windows execution policy. Used `npm.cmd`.
3. **`--no-interactive`** passed so create-vite would not hang on a TTY.
4. **Extra Open button** next to the path field (Enter also submits). Brief listed the input, not a separate label.
5. **Busy disable.** Action buttons also disable while a request is in flight (`busy`), in addition to `buttons.ts`.
6. **No-folder doctor/recents.** `GET /api/state` 404 → `GET /api/doctor` + `GET /api/recents` so the strip and recents work before a folder is open.
7. **Send + SSE.** Backend is event-stream. Send does not implement `streamChat` (Task 12). It POSTs, drains the body with `void r.text()`, then `refresh()` so polling can see `job.kind === "claude"`. JSON `text` is shown if that content-type appears.
8. **Vite template leftovers** (README, oxlint, `hero.png`, logos) kept from `create-vite`. Unused by `App.tsx`.
9. **`package-lock.json` not committed** — already in repo `.gitignore`.
10. **`src/**/*.test.ts` excluded** from `tsconfig.app.json` so `tsc -b` does not typecheck vitest imports.

### Concerns / notes

1. **Chat tokens are not rendered.** User lines appear in the log; assistant text waits for Task 12. During a turn the center shows `job: claude` via the 1s poll.
2. **`void r.text()` drain.** Cancelling the body would abort Claude. Draining lets the turn finish. If the tab closes, the stream ends with the page.
3. **CORS origin is `http://localhost:5173` only.** Opening `http://127.0.0.1:5173` will fail fetch. Video `src` is `http://127.0.0.1:8787/...` from a localhost page; playback should work (no canvas/CORS reads).
4. **`canTranscribe` is imported in the official test but never asserted.** Implemented and wired on the Transcribe button anyway.
5. **Chat during `rendering` is allowed by `buttons.ts`** (not in the disable list). The API will 409 busy; the error string is shown.
6. **Doctor `detail` is hidden on purpose** (paths + missing-key copy). Only names + color, so `sk-` cannot appear.
7. **No server-side chat transcript.** Refresh loses the in-memory log.
8. **Official tests do not render React.** Layout is untested except by `tsc`/`vite build`.
9. **PowerShell `npm` alias** is unusable until execution policy allows scripts; `npm.cmd` works.

### Not done (out of scope)

- SSE token streaming + Retry (`streamChat`) — Task 12.
- Commit of `.superpowers/` or `.env`.
- Push.

## Ready for next task

Yes — three-column UI renders `center_state`, drives the existing API, and leaves streaming polish to Task 12. Open the UI as `http://localhost:5173` with the API on `127.0.0.1:8787`.

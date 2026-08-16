### Task 11: Vite UI — layout + state rendering

**Files:**
- Create: `app/web/package.json`, `app/web/vite.config.ts`, `app/web/tsconfig.json`, `app/web/index.html`
- Create: `app/web/src/main.tsx`, `app/web/src/App.tsx`, `app/web/src/api.ts`, `app/web/src/types.ts`, `app/web/src/App.css`
- Create: `app/web/src/centerState.test.ts`
- Create: `app/web/vitest.config.ts`

**Interfaces:**
- Consumes: `GET /api/state` payload from Task 7 (same field names)
- Produces: a three-column page that renders `center_state` and never calls ffmpeg/claude

`app/web/src/api.ts`:

```typescript
export const API = "http://127.0.0.1:8787";

export async function getState() {
  const r = await fetch(`${API}/api/state`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
```

`vite.config.ts` does not need a proxy if `API` is absolute and CORS is on. Keep it simple.

`app/web/src/centerState.test.ts` (vitest):

```typescript
import { describe, it, expect } from "vitest";
import { canChat, canTranscribe, canApprove, canRenderFinal } from "./buttons";

describe("buttons", () => {
  it("empty disables chat and approve", () => {
    expect(canChat("empty", true)).toBe(false);
    expect(canApprove("empty", true)).toBe(false);
    expect(canRenderFinal("preview-ready")).toBe(true);
    expect(canRenderFinal("packed")).toBe(false);
  });
  it("packed enables chat and approve when doctor ok", () => {
    expect(canChat("packed", true)).toBe(true);
    expect(canChat("packed", false)).toBe(false);
    expect(canApprove("packed", true)).toBe(true);
    expect(canApprove("stale", true)).toBe(true);
    expect(canApprove("strategy-ready", true)).toBe(true);
    expect(canApprove("inventory", true)).toBe(false);
  });
});
```

`app/web/src/buttons.ts`:

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

- [ ] **Step 1: Scaffold Vite React TS in `app/web`**

Run from repo root:

```powershell
cd app
npm create vite@latest web -- --template react-ts
cd web
npm install
npm install -D vitest
```

If `app/web` already exists, do not re-scaffold; add missing files only.

Set `app/web/vite.config.ts`:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
});
```

Add to `app/web/package.json` scripts: `"test": "vitest run"`.

- [ ] **Step 2: Write the failing button tests, then `buttons.ts`**

Create `app/web/src/buttons.ts` and `app/web/src/centerState.test.ts` with the **correct** rules in Interfaces (not the contradictory draft). Run `npm test` in `app/web` — first without `buttons.ts` to see FAIL, then implement.

- [ ] **Step 3: Build the three-column `App.tsx`**

Left: doctor strip (green/red per check name, never print secrets), path input, Browse (`POST /api/folder/browse` then refresh state), recents list, source list (`name`, `duration_s`, `width`×`height`, `fps`), Open edit (`POST /api/open-edit`).

Center: state label, `error` text, packed transcript `<pre>`, ranges list from `edl.ranges`, `<video src={`${API}/api/media/preview`} controls />` if `has_preview` else first source via `/api/media/source/{name}`, buttons Transcribe / Approve & preview / Render final / Reject (prompt for a note → `POST /api/reject`). Disable from `buttons.ts`. Poll `GET /api/state` every 1s while `job.kind !== "idle"`.

Right: chat log, textarea, Send → `POST /api/chat` (Task 12 if stream not wired yet: show “chat not connected” only if the route 404s; prefer wiring a non-stream JSON fallback). For this task, Send may `POST /api/chat` and then poll state. Streaming is Task 12.

Minimal CSS: three equal columns, full viewport, no framework required.

- [ ] **Step 4: Run UI tests**

Run: `cd app/web; npm test`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/web
git commit -m "feat: three-column local app UI"
```

Do not commit `app/web/node_modules`. Confirm `node_modules/` is gitignored (repo `.gitignore` already has it).

---


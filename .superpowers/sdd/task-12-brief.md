### Task 12: chat SSE in the UI + retry

**Files:**
- Modify: `app/web/src/api.ts`
- Modify: `app/web/src/App.tsx`
- Modify: `app/server/main.py` if the chat route is not yet SSE

**Interfaces:**
- Consumes: `POST /api/chat` SSE from Task 9
- Produces: `streamChat(message: string, onText: (t: string) => void): Promise<void>`

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

Retry button calls `POST /api/chat/retry` with the same reader loop.

- [ ] **Step 1: Implement `streamChat` + Retry in the right column**

Append assistant text as chunks arrive. On error, show the message and enable Retry.

- [ ] **Step 2: Manual check**

Run API (`python -m app`) and `npm run dev` in `app/web`. Open `http://localhost:5173`. You do not need footage for this step if no folder is open — chat stays disabled. Confirm the page loads and doctor strip appears.

- [ ] **Step 3: Commit**

```bash
git add app/web/src/api.ts app/web/src/App.tsx
git commit -m "feat: stream Claude chat into the review UI"
```

---


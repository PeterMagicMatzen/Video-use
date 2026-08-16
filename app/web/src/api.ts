export const API = "http://127.0.0.1:8787";

export async function getState() {
  const r = await fetch(`${API}/api/state`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getDoctor() {
  const r = await fetch(`${API}/api/doctor`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getRecents(): Promise<string[]> {
  const r = await fetch(`${API}/api/recents`);
  if (!r.ok) throw new Error(await r.text());
  const body = await r.json();
  return Array.isArray(body.recents) ? body.recents : [];
}

export async function postFolder(path: string) {
  const r = await fetch(`${API}/api/folder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function postFolderBrowse() {
  const r = await fetch(`${API}/api/folder/browse`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function postFileBrowse() {
  const r = await fetch(`${API}/api/folder/browse-file`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function postOpenEdit() {
  const r = await fetch(`${API}/api/open-edit`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function postTranscribe() {
  const r = await fetch(`${API}/api/transcribe`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
}

export async function postAutoEdit() {
  const r = await fetch(`${API}/api/auto-edit`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
}

export async function postApprove() {
  const r = await fetch(`${API}/api/approve`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
}

export async function postRenderFinal() {
  const r = await fetch(`${API}/api/render-final`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
}

export async function postReject(note: string) {
  const r = await fetch(`${API}/api/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note }),
  });
  if (!r.ok) throw new Error(await r.text());
}

export function applySseEvent(ev: { text?: string; error?: string }, onText: (t: string) => void) {
  if (ev.error) throw new Error(ev.error);
  if (ev.text) onText(ev.text);
}

async function readSseChat(r: Response, onText: (t: string) => void) {
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
      applySseEvent(JSON.parse(line), onText);
    }
  }
}

export async function streamChat(message: string, onText: (t: string) => void) {
  const r = await fetch(`${API}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  await readSseChat(r, onText);
}

/** Same SSE reader loop as streamChat, against POST /api/chat/retry. */
export async function retryChat(onText: (t: string) => void) {
  const r = await fetch(`${API}/api/chat/retry`, { method: "POST" });
  await readSseChat(r, onText);
}

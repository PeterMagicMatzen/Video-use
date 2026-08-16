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

export async function postOpenEdit() {
  const r = await fetch(`${API}/api/open-edit`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function postTranscribe() {
  const r = await fetch(`${API}/api/transcribe`, { method: "POST" });
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

/** JSON fallback if the route is not SSE. Streaming tokens is Task 12. */
export async function postChat(message: string): Promise<{ connected: boolean; text: string }> {
  const r = await fetch(`${API}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (r.status === 404) return { connected: false, text: "" };
  if (!r.ok) throw new Error(await r.text());
  const ctype = r.headers.get("content-type") || "";
  if (ctype.includes("application/json")) {
    try {
      const json = (await r.json()) as { text?: string };
      return { connected: true, text: typeof json.text === "string" ? json.text : "" };
    } catch {
      return { connected: true, text: "" };
    }
  }
  // Drain SSE so the turn can finish; UI polls GET /api/state until job.idle.
  void r.text();
  return { connected: true, text: "" };
}

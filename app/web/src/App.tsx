import { useCallback, useEffect, useState } from "react";
import {
  API,
  getDoctor,
  getRecents,
  getState,
  postApprove,
  postFolder,
  postFolderBrowse,
  postOpenEdit,
  postReject,
  postRenderFinal,
  postTranscribe,
  retryChat,
  streamChat,
} from "./api";
import { canApprove, canChat, canRenderFinal, canTranscribe } from "./buttons";
import type { Doctor, ProjectPayload } from "./types";
import "./App.css";

type ChatLine = { role: "user" | "assistant"; text: string };

function fmtDur(s: number | null): string {
  if (s == null || Number.isNaN(s)) return "—";
  return `${s.toFixed(1)}s`;
}

function fmtFps(fps: number | null): string {
  if (fps == null || Number.isNaN(fps)) return "—";
  return `${Number.isInteger(fps) ? String(fps) : fps.toFixed(2)} fps`;
}

function errText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export default function App() {
  const [payload, setPayload] = useState<ProjectPayload | null>(null);
  const [doctor, setDoctor] = useState<Doctor | null>(null);
  const [recents, setRecents] = useState<string[]>([]);
  const [path, setPath] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [chatLog, setChatLog] = useState<ChatLine[]>([]);
  const [chatNotice, setChatNotice] = useState<string | null>(null);
  const [chatRetry, setChatRetry] = useState(false);

  const applyPayload = useCallback((next: ProjectPayload) => {
    setPayload(next);
    setDoctor(next.doctor);
    setRecents(next.recents);
    setPath(next.folder);
  }, []);

  const refresh = useCallback(async () => {
    const state = await getState();
    if (state) {
      applyPayload(state as ProjectPayload);
      return;
    }
    setPayload(null);
    const [d, rec] = await Promise.all([getDoctor(), getRecents()]);
    setDoctor(d as Doctor);
    setRecents(rec);
  }, [applyPayload]);

  useEffect(() => {
    refresh().catch((err: unknown) => setActionError(errText(err)));
  }, [refresh]);

  const jobKind = payload?.job?.kind ?? "idle";
  useEffect(() => {
    if (jobKind === "idle") return;
    const id = window.setInterval(() => {
      refresh().catch(() => {});
    }, 1000);
    return () => window.clearInterval(id);
  }, [jobKind, refresh]);

  const center = payload?.center_state ?? "empty";
  const doctorOk = Boolean(payload?.doctor.ok ?? doctor?.ok);
  const checks = payload?.doctor.checks ?? doctor?.checks ?? [];
  const sources = payload?.sources ?? [];
  const shownRecents = payload?.recents ?? recents;
  const first = sources[0];
  const videoSrc = payload?.has_preview
    ? `${API}/api/media/preview`
    : first
      ? `${API}/api/media/source/${encodeURIComponent(first.name)}`
      : null;

  async function run(fn: () => Promise<void>) {
    setActionError(null);
    setBusy(true);
    try {
      await fn();
      await refresh();
    } catch (err) {
      setActionError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  function openPath(next: string) {
    const trimmed = next.trim();
    if (!trimmed) return;
    return run(async () => {
      applyPayload((await postFolder(trimmed)) as ProjectPayload);
    });
  }

  const chatOn = canChat(center, doctorOk);

  function makeAppender() {
    let started = false;
    return (t: string) => {
      setChatLog((log) => {
        const last = log[log.length - 1];
        if (started && last?.role === "assistant") {
          return [...log.slice(0, -1), { role: "assistant", text: last.text + t }];
        }
        return [...log, { role: "assistant", text: t }];
      });
      started = true;
    };
  }

  async function runChat(fn: (onText: (t: string) => void) => Promise<void>) {
    setChatNotice(null);
    setChatRetry(false);
    setBusy(true);
    try {
      await fn(makeAppender());
      await refresh();
    } catch (err) {
      setChatNotice(errText(err));
      setChatRetry(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <aside className="col left">
        <h1>video-use</h1>
        <ul className="doctor">
          {checks.map((c) => (
            <li key={c.name} className={c.ok ? "ok" : "bad"}>
              {c.name}
            </li>
          ))}
        </ul>
        <div className="folder-row">
          <input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void openPath(path);
            }}
            placeholder="C:\path\to\footage"
            aria-label="Folder path"
          />
          <button type="button" disabled={busy} onClick={() => void openPath(path)}>
            Open
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                const result = await postFolderBrowse();
                if (result?.cancelled) return;
                applyPayload(result as ProjectPayload);
              })
            }
          >
            Browse
          </button>
        </div>
        <h2>Recents</h2>
        <ul>
          {shownRecents.map((p) => (
            <li key={p}>
              <button type="button" className="link" disabled={busy} onClick={() => void openPath(p)}>
                {p}
              </button>
            </li>
          ))}
        </ul>
        <h2>Sources</h2>
        <ul>
          {sources.map((s) => (
            <li key={s.name}>
              {s.name} {fmtDur(s.duration_s)} {s.width ?? "?"}×{s.height ?? "?"} {fmtFps(s.fps)}
            </li>
          ))}
        </ul>
        <button type="button" disabled={busy || !payload} onClick={() => void run(() => postOpenEdit())}>
          Open edit
        </button>
      </aside>

      <main className="col center">
        <h2>State: {center}</h2>
        {jobKind !== "idle" ? <p className="job">job: {jobKind}</p> : null}
        {errorText(payload?.error, actionError) ? (
          <p className="error">{errorText(payload?.error, actionError)}</p>
        ) : null}
        {payload?.packed_markdown ? <pre>{payload.packed_markdown}</pre> : null}
        <h3>Ranges</h3>
        <ul>
          {(payload?.edl?.ranges ?? []).map((r, i) => (
            <li key={`${r.source}-${r.start}-${r.end}-${i}`}>
              {r.beat ?? "range"} {r.start}–{r.end} {r.source}
              {r.quote ? ` — ${r.quote}` : ""}
            </li>
          ))}
        </ul>
        {videoSrc ? <video key={videoSrc} src={videoSrc} controls /> : null}
        <div className="actions">
          <button
            type="button"
            disabled={busy || !canTranscribe(center, doctorOk)}
            onClick={() => void run(() => postTranscribe())}
          >
            Transcribe
          </button>
          <button
            type="button"
            disabled={busy || !canApprove(center, doctorOk)}
            onClick={() => void run(() => postApprove())}
          >
            Approve & preview
          </button>
          <button
            type="button"
            disabled={busy || !canRenderFinal(center)}
            onClick={() => void run(() => postRenderFinal())}
          >
            Render final
          </button>
          <button
            type="button"
            disabled={busy || !payload}
            onClick={() => {
              const note = window.prompt("Reject note");
              if (note == null || !note.trim()) return;
              void run(() => postReject(note.trim()));
            }}
          >
            Reject
          </button>
        </div>
      </main>

      <aside className="col right">
        <h2>Chat</h2>
        <div className="chat-log">
          {chatLog.map((line, i) => (
            <p key={`${line.role}-${i}`}>
              <strong>{line.role}:</strong> {line.text}
            </p>
          ))}
        </div>
        {chatNotice ? <p className="error">{chatNotice}</p> : null}
        <textarea
          value={draft}
          disabled={!chatOn || busy}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={chatOn ? "Strategy notes…" : "Chat disabled until packed"}
        />
        <div className="actions">
          <button
            type="button"
            disabled={busy || !chatOn || !draft.trim()}
            onClick={() => {
              const message = draft.trim();
              if (!message) return;
              setDraft("");
              setChatLog((log) => [...log, { role: "user", text: message }]);
              void runChat((onText) => streamChat(message, onText));
            }}
          >
            Send
          </button>
          <button
            type="button"
            disabled={busy || !chatOn || !chatRetry}
            onClick={() => {
              void runChat((onText) => retryChat(onText));
            }}
          >
            Retry
          </button>
        </div>
      </aside>
    </div>
  );
}

function errorText(sessionError: string | null | undefined, local: string | null): string | null {
  return sessionError || local;
}

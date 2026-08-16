import { useCallback, useEffect, useState } from "react";
import {
  API,
  getDoctor,
  getRecents,
  getSfxLibrary,
  getState,
  postApprove,
  postAutoEdit,
  postStripClaude,
  postUndo,
  postBinAdd,
  postBinRemove,
  postClearRecents,
  postCloseProject,
  postLibrarySfxAdd,
  postFileBrowse,
  postFolder,
  postFolderBrowse,
  postOpenEdit,
  postOpenOutput,
  postReject,
  postRenderFinal,
  retryChat,
  streamChat,
} from "./api";
import { canApprove, canChat, canGenerate, canRenderFinal } from "./buttons";
import { headlineFor, stepIndex } from "./status";
import { bootFromTab, clearTabFolder, readTabFolder, shouldAdoptServerState, writeTabFolder } from "./tabSession";
import type { CutVariation, Doctor, ProjectPayload, SfxItem } from "./types";
import "./App.css";

type ChatLine = { role: "user" | "assistant"; text: string };
type WatchMode = "cut" | "raw";

function fmtDur(s: number | null): string {
  if (s == null || Number.isNaN(s)) return "—";
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${Math.round(s - m * 60)}s`;
}

function errText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function friendlyError(text: string): string {
  if (/job died \(pid/i.test(text) || /previous \w+ job died/i.test(text)) {
    return "Generate stopped. Tap Generate to try again.";
  }
  return text;
}

function errorText(sessionError: string | null | undefined, local: string | null): string | null {
  const raw = sessionError || local;
  return raw ? friendlyError(raw) : null;
}

const STEPS = ["Clip", "Generate", "Watch"];

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
  const [watch, setWatch] = useState<WatchMode>("cut");
  const [moreOpen, setMoreOpen] = useState(false);
  const [sfx, setSfx] = useState<SfxItem[]>([]);
  const [sfxQuery, setSfxQuery] = useState("");
  const [variation, setVariation] = useState("energy");

  const applyPayload = useCallback((next: ProjectPayload) => {
    setPayload(next);
    setDoctor(next.doctor);
    setRecents(next.recents);
    setPath(next.folder);
    if (next.folder) writeTabFolder(next.folder);
    if (next.variation) setVariation(next.variation);
  }, []);

  const showEmpty = useCallback(async () => {
    setPayload(null);
    const [d, rec] = await Promise.all([getDoctor(), getRecents()]);
    setDoctor(d as Doctor);
    setRecents(rec);
  }, []);

  const refresh = useCallback(async () => {
    const tabFolder = readTabFolder();
    if (!tabFolder) {
      await showEmpty();
      return;
    }
    const state = (await getState()) as ProjectPayload | null;
    if (state && shouldAdoptServerState(tabFolder, state.folder)) {
      applyPayload(state);
      return;
    }
    try {
      applyPayload((await postFolder(tabFolder)) as ProjectPayload);
    } catch {
      clearTabFolder();
      await showEmpty();
    }
  }, [applyPayload, showEmpty]);

  useEffect(() => {
    const boot = bootFromTab(readTabFolder());
    const start = boot.mode === "restore" ? refresh() : showEmpty();
    start.catch((err: unknown) => setActionError(errText(err)));
    getSfxLibrary()
      .then((data) => setSfx(Array.isArray(data.items) ? data.items : []))
      .catch(() => setSfx([]));
  }, [refresh, showEmpty]);

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
  const hasCut = Boolean(payload?.has_preview || payload?.has_final);
  const working = busy || jobKind !== "idle";
  const copy = headlineFor(center, hasCut);
  const step = stepIndex(center, hasCut);
  const chatOn = Boolean(payload?.chat_enabled) && canChat(center, doctorOk);

  const cutSrc = payload?.has_final
    ? `${API}/api/media/final`
    : payload?.has_preview
      ? `${API}/api/media/preview${payload.preview_mtime != null ? `?t=${payload.preview_mtime}` : ""}`
      : null;
  const rawSrc = first ? `${API}/api/media/source/${encodeURIComponent(first.name)}` : null;
  const useCut = watch === "cut" && cutSrc;
  const videoSrc = useCut ? cutSrc : rawSrc;
  const videoLabel = useCut ? "Finished cut" : rawSrc ? "Raw take" : "No clip";

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
    } catch (err) {
      setChatNotice(errText(err));
      setChatRetry(true);
      setBusy(false);
      return;
    }
    try {
      await refresh();
    } catch (err) {
      setActionError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  const login = checks.find((c) => c.name === "claude_login");

  return (
    <div className="shell">
      <header className="top">
        <div className="brand">
          <span className="mark" aria-hidden />
          <div>
            <strong>video-use</strong>
            <span>Talking-head editor</span>
          </div>
        </div>
        <ol className="steps" aria-label="Edit steps">
          {STEPS.map((label, i) => (
            <li key={label} className={i === step ? "on" : i < step ? "done" : ""}>
              <em>{i + 1}</em>
              {label}
            </li>
          ))}
        </ol>
        {checks.some((c) => !c.ok) ? (
          <ul className="health" aria-label="System checks">
            {checks.filter((c) => !c.ok).map((c) => (
              <li key={c.name} className={c.required ? "bad" : "warn"} title={c.detail}>
                {c.name.replace("_", " ")}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted" style={{ margin: 0, fontSize: 12 }}>
            Ready
          </p>
        )}
      </header>

      <div className="body">
        <aside className="rail">
          <p className="eyebrow">Clip</p>
          <button
            type="button"
            className="drop"
            disabled={working}
            onClick={() =>
              void run(async () => {
                const result = await postFileBrowse();
                if (result?.cancelled) return;
                applyPayload(result as ProjectPayload);
              })
            }
          >
            <strong>Add talking-head video</strong>
            <span>Opens a file picker on this PC. The clip never uploads.</span>
          </button>
          {moreOpen ? (
            <>
          <div className="path-row">
            <input
              value={path}
              onChange={(e) => setPath(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void openPath(path);
              }}
              placeholder="Or paste a folder / .mp4 path"
              aria-label="Folder or video path"
            />
            <button type="button" disabled={working} onClick={() => void openPath(path)}>
              Open
            </button>
          </div>
          <button
            type="button"
            className="ghost"
            disabled={working}
            onClick={() =>
              void run(async () => {
                const result = await postFolderBrowse();
                if (result?.cancelled) return;
                applyPayload(result as ProjectPayload);
              })
            }
          >
            Browse folder
          </button>
            </>
          ) : null}

          {sources.length > 0 ? (
            <ul className="clips">
              {sources.map((s) => (
                <li key={s.name}>
                  <b>{s.name}</b>
                  <span>
                    {fmtDur(s.duration_s)} · {s.width}×{s.height}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No clip open yet.</p>
          )}

          {payload ? (
            <button
              type="button"
              className="ghost"
              disabled={working}
              onClick={() =>
                void run(async () => {
                  clearTabFolder();
                  await postCloseProject();
                  setPayload(null);
                  setPath("");
                  setChatLog([]);
                })
              }
            >
              New project
            </button>
          ) : null}

          <p className="eyebrow">Add-ins</p>
          <p className="muted">
            Generate asks Claude for punch-ins, Mixkit sound, Pexels stills
            as Ken Burns B-roll, and keyword graphics.
          </p>
          <div className="bin-actions">
            {(["broll", "graphic", "voice"] as const).map((kind) => (
              <button
                key={kind}
                type="button"
                disabled={working || !payload}
                onClick={() =>
                  void run(async () => {
                    const result = await postBinAdd(kind);
                    if (result?.cancelled) return;
                    applyPayload(result as ProjectPayload);
                  })
                }
              >
                {kind === "broll" ? "Add B-roll" : kind === "graphic" ? "Add graphic" : "Add voice clip"}
              </button>
            ))}
          </div>
          {(payload?.bin ?? []).length > 0 ? (
            <ul className="bin">
              {(payload?.bin ?? []).map((item) => (
                <li key={item.file}>
                  <span>
                    {item.kind} · {item.label || item.file}
                  </span>
                  <button
                    type="button"
                    disabled={working}
                    onClick={() =>
                      void run(async () => {
                        applyPayload((await postBinRemove(item.file)) as ProjectPayload);
                      })
                    }
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">{payload ? "Nothing added yet." : "Open a clip first."}</p>
          )}

          <p className="eyebrow">Mixkit SFX library</p>
          <p className="muted">Claude scores these. Manual Add is extra on top of that bed.</p>
          <input
            value={sfxQuery}
            onChange={(e) => setSfxQuery(e.target.value)}
            placeholder="Search whoosh, applause, hit…"
            aria-label="Search sound library"
          />
          <ul className="bin sfx-list">
            {sfx
              .filter((item) => {
                const q = sfxQuery.trim().toLowerCase();
                if (!q) return true;
                return (
                  item.title.toLowerCase().includes(q) ||
                  (item.tags || []).some((t) => t.toLowerCase().includes(q))
                );
              })
              .slice(0, 40)
              .map((item) => (
                <li key={item.file}>
                  <span>{item.title}</span>
                  <button
                    type="button"
                    disabled={working || !payload}
                    onClick={() =>
                      void run(async () => {
                        applyPayload((await postLibrarySfxAdd(item.file)) as ProjectPayload);
                      })
                    }
                  >
                    Add
                  </button>
                </li>
              ))}
          </ul>
          {sfx.length === 0 ? <p className="muted">Library empty — run scripts/download_mixkit_sfx.py</p> : null}

          {shownRecents.length > 0 ? (
            <>
              <p className="eyebrow">Recent</p>
              <ul className="recents">
                {shownRecents.map((p) => (
                  <li key={p}>
                    <button type="button" disabled={working} onClick={() => void openPath(p)}>
                      {p}
                    </button>
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className="ghost"
                disabled={working}
                onClick={() =>
                  void run(async () => {
                    await postClearRecents();
                    setRecents([]);
                  })
                }
              >
                Clear recents
              </button>
            </>
          ) : null}
        </aside>

        <main className="stage">
          <div className="hero-copy">
            <p className="kicker">{copy.kicker}</p>
            <h1>{copy.title}</h1>
            <p className="lede">{copy.detail}</p>
          </div>

          {working ? (
            <p className="pulse" role="status">
              {payload?.job?.phase === "transcribe" || jobKind === "transcribe"
                ? "Writing captions…"
                : payload?.job?.phase === "directing" || jobKind === "claude" || jobKind === "generate"
                  ? "Directing cuts and sound…"
                  : jobKind === "render" || payload?.job?.phase === "rendering"
                    ? "Exporting the movie…"
                    : "Working…"}
            </p>
          ) : null}

          {errorText(payload?.error, actionError) ? (
            <p className="banner error">{errorText(payload?.error, actionError)}</p>
          ) : null}

          <div className="player-wrap">
            <div className="player-meta">
              <span className={useCut ? "tag cut" : "tag raw"}>{videoLabel}</span>
              {cutSrc && rawSrc ? (
                <div className="toggle" role="group" aria-label="Which video">
                  <button type="button" className={watch === "cut" ? "on" : ""} onClick={() => setWatch("cut")}>
                    Finished
                  </button>
                  <button type="button" className={watch === "raw" ? "on" : ""} onClick={() => setWatch("raw")}>
                    Raw
                  </button>
                </div>
              ) : null}
            </div>
            {videoSrc ? (
              <video key={videoSrc} src={videoSrc} controls playsInline />
            ) : (
              <div className="empty-player">Add a clip to see it here.</div>
            )}
          </div>

          <div className="cta">

            <div className="toggle" role="group" aria-label="Cut variation">
              {(payload?.variations?.length
                ? payload.variations
                : [
                    { id: "energy", label: "Energy", detail: "" },
                    { id: "tight", label: "Tight", detail: "" },
                    { id: "calm", label: "Calm", detail: "" },
                  ]
              ).map((opt: CutVariation) => (
                <button
                  key={opt.id}
                  type="button"
                  className={variation === opt.id ? "on" : ""}
                  disabled={working}
                  title={opt.detail}
                  onClick={() => setVariation(opt.id)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="primary"
              disabled={working || !canGenerate(center, sources.length > 0, Boolean(login?.ok))}
              onClick={() => void run(() => postAutoEdit(variation))}
            >
              {hasCut ? "Regenerate" : "Generate"}
            </button>
            <button
              type="button"
              disabled={working || !payload?.can_undo}
              onClick={() => void run(() => postUndo())}
            >
              Undo last Claude pass
            </button>
            <button
              type="button"
              disabled={working || !hasCut}
              onClick={() => void run(() => postStripClaude())}
            >
              Remove cinematic + library audio
            </button>
            <button
              type="button"
              disabled={working || !hasCut}
              onClick={() => void run(() => postOpenOutput())}
            >
              Open finished file
            </button>
          </div>
        </main>

        <aside className="side">
          <p className="eyebrow">Timeline</p>
          {(payload?.edl?.ranges ?? []).length === 0 ? (
            <p className="muted">Cuts show up here after you make an edit.</p>
          ) : (
            <ol className="timeline">
              {(payload?.edl?.ranges ?? []).map((r, i) => (
                <li key={`${r.source}-${r.start}-${r.end}-${i}`}>
                  <span>
                    {r.beat ?? `Cut ${i + 1}`}
                    {r.zoom && r.zoom > 1.01 ? ` · ${r.zoom.toFixed(2)}×` : ""}
                  </span>
                  <b>{r.quote || `${r.start.toFixed(1)}–${r.end.toFixed(1)}`}</b>
                </li>
              ))}
            </ol>
          )}

          <p className="eyebrow">Director notes</p>
          <div className="chat-log">
            {chatLog.length === 0 ? (
              <p className="muted">
                Optional. Ask for a custom cut after you sign in with{" "}
                <code>claude auth login</code>.
                {login && !login.ok ? " Claude is signed out right now." : ""}
              </p>
            ) : (
              chatLog.map((line, i) => (
                <p key={`${line.role}-${i}`} className={line.role}>
                  <strong>{line.role === "user" ? "You" : "Editor"}</strong>
                  {line.text}
                </p>
              ))
            )}
          </div>
          {chatNotice ? <p className="banner error">{chatNotice}</p> : null}
          <textarea
            value={draft}
            disabled={!chatOn || working}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={chatOn ? "e.g. Tighter hook, drop the last line" : "Transcribe first. Claude login needed for chat."}
          />
          <div className="row">
            <button
              type="button"
              disabled={working || !chatOn || !draft.trim()}
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
            <button type="button" disabled={working || !chatOn || !chatRetry} onClick={() => void runChat((onText) => retryChat(onText))}>
              Retry
            </button>
          </div>

          <button type="button" className="ghost more" onClick={() => setMoreOpen((v) => !v)}>
            {moreOpen ? "Hide advanced" : "Advanced"}
          </button>
          {moreOpen ? (
            <div className="advanced">
              <button type="button" disabled={working || !payload} onClick={() => void run(() => postOpenEdit())}>
                Open edit folder
              </button>
              <button
                type="button"
                disabled={working || !canApprove(center, doctorOk)}
                onClick={() => void run(() => postApprove())}
              >
                Approve Claude plan
              </button>
              <button
                type="button"
                disabled={working || !canRenderFinal(center)}
                onClick={() => void run(() => postRenderFinal())}
              >
                Re-render final
              </button>
              <button
                type="button"
                disabled={working || !payload}
                onClick={() => {
                  const note = window.prompt("Note for the next chat turn");
                  if (note == null || !note.trim()) return;
                  void run(() => postReject(note.trim()));
                }}
              >
                Send reject note
              </button>
            </div>
          ) : null}
        </aside>
      </div>
    </div>
  );
}

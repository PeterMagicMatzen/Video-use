import { useEffect, useMemo, useRef } from "react";
import { AlignLeft, Scissors } from "lucide-react";
import { formatTime } from "../lib/captions";

export default function TranscriptPanel({ project, cuts, currentTime, seekTo, toggleSpan }) {
  const containerRef = useRef(null);
  const activeRef = useRef(null);

  const spans = cuts?.spans || [];

  const items = useMemo(() => {
    const words = (project.words || []).filter(
      (w) => w.type === "word" && w.start != null
    );
    const result = [];
    let spanIdx = 0;
    for (const w of words) {
      while (spanIdx < spans.length && spans[spanIdx].end <= w.start) {
        if (spans[spanIdx].type === "pause") {
          result.push({ kind: "span", span: spans[spanIdx] });
        }
        spanIdx++;
      }
      const mid = (w.start + w.end) / 2;
      const inSpan = spans.find((s) => mid >= s.start && mid <= s.end);
      result.push({ kind: "word", word: w, span: inSpan });
    }
    for (; spanIdx < spans.length; spanIdx++) {
      if (spans[spanIdx].type === "pause") {
        result.push({ kind: "span", span: spans[spanIdx] });
      }
    }
    return result;
  }, [project.words, spans]);

  useEffect(() => {
    if (activeRef.current && containerRef.current) {
      activeRef.current.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [currentTime]);

  return (
    <aside className="w-96 shrink-0 bg-[#09090b] border-l border-zinc-800/50 flex flex-col overflow-hidden">
      <div className="p-6 pb-3 border-b border-zinc-800/50">
        <div className="flex items-center gap-2">
          <AlignLeft className="w-4 h-4 text-accent" />
          <p className="font-mono text-xs uppercase tracking-wider text-zinc-400">
            Transcript
          </p>
        </div>
        <p className="text-[10px] text-zinc-600 mt-1.5">
          Click a word to seek · click a red cut to restore it
        </p>
      </div>
      <div ref={containerRef} className="flex-1 overflow-y-auto p-6 pt-4" data-testid="transcript-panel">
        <div className="leading-8 text-sm">
          {items.map((item, i) => {
            if (item.kind === "span") {
              const s = item.span;
              return (
                <button
                  key={`s-${s.id}-${i}`}
                  data-testid={`cut-chip-${s.id}`}
                  onClick={() => toggleSpan(s.id)}
                  title={s.disabled ? "Click to re-apply cut" : "Click to restore"}
                  className={`inline-flex items-center gap-1 mx-1 px-1.5 py-0 rounded text-[10px] font-mono align-middle border transition-colors duration-150 ${
                    s.disabled
                      ? "border-zinc-700 text-zinc-500 hover:border-zinc-500"
                      : "border-red-500/40 bg-red-500/10 text-red-400 hover:bg-red-500/20"
                  }`}
                >
                  <Scissors className="w-2.5 h-2.5" />
                  {s.disabled ? `kept ${formatTime(s.end - s.start)}` : `cut ${formatTime(s.end - s.start)}`}
                </button>
              );
            }
            const w = item.word;
            const active = currentTime >= w.start && currentTime <= w.end;
            const removed = item.span && !item.span.disabled;
            const isFiller = item.span?.type === "filler";
            return (
              <span
                key={`w-${i}`}
                ref={active ? activeRef : null}
                data-testid="transcript-word"
                onClick={() =>
                  isFiller && removed ? toggleSpan(item.span.id) : seekTo(w.start)
                }
                title={isFiller && removed ? "Filler — click to restore" : `${w.start.toFixed(2)}s`}
                className={`cursor-pointer rounded px-0.5 transition-colors duration-100 ${
                  active
                    ? "bg-primary/20 text-primary"
                    : removed
                    ? "text-zinc-600 line-through decoration-red-500/70"
                    : "text-zinc-300 hover:text-white hover:bg-zinc-800"
                }`}
              >
                {w.text}{" "}
              </span>
            );
          })}
          {items.length === 0 && (
            <p className="text-zinc-600 text-xs">No words detected in this video.</p>
          )}
        </div>
      </div>
    </aside>
  );
}

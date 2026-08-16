import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Play, Pause, SkipBack, Wand2 } from "lucide-react";
import { videoUrl } from "../api";
import { CAPTION_STYLES, formatTime } from "../lib/captions";

export default function VideoStage({
  projectId, project, chunks, cuts, styleKey, changeStyle,
  previewCuts, videoRef, currentTime, setCurrentTime,
}) {
  const [playing, setPlaying] = useState(false);
  const [videoError, setVideoError] = useState(false);
  const rafRef = useRef(null);

  const activeSpans = useMemo(
    () => (cuts ? cuts.spans.filter((s) => !s.disabled) : []),
    [cuts]
  );

  const tick = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    let t = v.currentTime;
    if (previewCuts && !v.paused) {
      const span = activeSpans.find((s) => t >= s.start && t < s.end - 0.05);
      if (span) {
        if (span.end >= (project.duration || v.duration) - 0.1) {
          v.pause();
        } else {
          v.currentTime = span.end;
          t = span.end;
        }
      }
    }
    setCurrentTime(t);
    rafRef.current = requestAnimationFrame(tick);
  }, [activeSpans, previewCuts, project.duration, setCurrentTime, videoRef]);

  useEffect(() => {
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [tick]);

  const togglePlay = () => {
    const v = videoRef.current;
    if (!v) return;
    v.paused ? v.play() : v.pause();
  };

  const currentChunk = useMemo(
    () => chunks.find((c) => currentTime >= c.start && currentTime <= c.end + 0.15),
    [chunks, currentTime]
  );

  const style = CAPTION_STYLES.find((s) => s.key === styleKey) || CAPTION_STYLES[0];
  const portrait = project.height > project.width;

  const onSeekBar = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = (e.clientX - rect.left) / rect.width;
    const t = frac * project.duration;
    if (videoRef.current) videoRef.current.currentTime = t;
    setCurrentTime(t);
  };

  return (
    <main className="flex-1 bg-black relative flex flex-col p-8 overflow-y-auto min-w-0">
      <div className="flex-1 flex items-center justify-center min-h-0">
        <div
          className={`relative bg-zinc-950 rounded-lg overflow-hidden ${
            portrait ? "h-full max-h-[62vh] aspect-[9/16]" : "w-full max-w-3xl aspect-video"
          }`}
        >
          <video
            data-testid="video-player"
            ref={videoRef}
            src={videoUrl(projectId)}
            className="w-full h-full object-contain"
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onClick={togglePlay}
            onError={() => setVideoError(true)}
            playsInline
          />
          {videoError && (
            <div
              data-testid="video-error-fallback"
              className="absolute inset-0 flex items-center justify-center bg-zinc-950/90 text-center px-6"
            >
              <p className="text-zinc-400 text-sm">
                Video preview unavailable in this browser — captions, cuts and
                export still work.
              </p>
            </div>
          )}
          {currentChunk && (
            <div className="absolute inset-x-0 bottom-[22%] flex justify-center pointer-events-none px-4">
              <div
                key={currentChunk.start}
                data-testid="caption-overlay"
                className="caption-pop text-center leading-tight"
                style={{ ...style.css, fontSize: portrait ? "1.1rem" : "1.5rem" }}
              >
                {currentChunk.words.map((w, i) => {
                  const active = currentTime >= w.start && currentTime <= w.end;
                  const text = style.uppercase ? (w.text || "").toUpperCase() : w.text;
                  return (
                    <span key={i} style={active && styleKey !== "neon" ? { color: "#D4FF00" } : undefined}>
                      {text}{" "}
                    </span>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mt-6 max-w-3xl w-full mx-auto">
        <div
          data-testid="seek-bar"
          onClick={onSeekBar}
          className="relative h-2 bg-zinc-800 rounded-full cursor-pointer group"
        >
          {activeSpans.map((s) => (
            <div
              key={s.id}
              className="absolute h-full bg-red-500/60 rounded-full"
              style={{
                left: `${(s.start / project.duration) * 100}%`,
                width: `${Math.max(0.3, ((s.end - s.start) / project.duration) * 100)}%`,
              }}
            />
          ))}
          <div
            className="absolute h-full bg-primary/90 rounded-full pointer-events-none"
            style={{ width: `${(currentTime / project.duration) * 100}%`, opacity: 0.35 }}
          />
          <div
            className="absolute -top-1 w-1 h-4 bg-primary rounded-full pointer-events-none"
            style={{ left: `${(currentTime / project.duration) * 100}%` }}
          />
        </div>

        <div className="flex items-center gap-4 mt-4">
          <button
            data-testid="restart-button"
            onClick={() => {
              if (videoRef.current) videoRef.current.currentTime = 0;
            }}
            className="text-zinc-400 hover:text-white transition-colors duration-150"
          >
            <SkipBack className="w-5 h-5" />
          </button>
          <button
            data-testid="play-pause-button"
            onClick={togglePlay}
            className="w-11 h-11 rounded-full bg-primary text-black flex items-center justify-center hover:scale-105 transition-transform duration-150"
          >
            {playing ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
          </button>
          <span className="font-mono text-xs text-zinc-400" data-testid="time-display">
            {formatTime(currentTime)} / {formatTime(project.duration)}
          </span>
          <span className="ml-auto font-mono text-[10px] uppercase tracking-wider text-zinc-600">
            red = auto-cut
          </span>
        </div>

        <div className="mt-8">
          <div className="flex items-center gap-2 mb-3">
            <Wand2 className="w-4 h-4 text-accent" />
            <p className="font-mono text-xs uppercase tracking-wider text-zinc-400">
              Caption Style
            </p>
          </div>
          <div className="grid grid-cols-4 gap-3">
            {CAPTION_STYLES.map((s) => (
              <button
                key={s.key}
                data-testid={`style-card-${s.key}`}
                onClick={() => changeStyle(s.key)}
                className={`rounded-lg border p-3 bg-zinc-900/80 text-left transition-transform duration-150 hover:-translate-y-0.5 ${
                  styleKey === s.key
                    ? "border-primary shadow-[inset_0_0_12px_rgba(212,255,0,0.15)]"
                    : "border-zinc-800 hover:border-zinc-600"
                }`}
              >
                <div className="h-10 flex items-center justify-center overflow-hidden">
                  <span style={{ ...s.css, fontSize: "0.8rem" }}>
                    {s.uppercase ? "YOUR WORDS" : "your words"}
                  </span>
                </div>
                <p className="text-[10px] text-zinc-500 mt-2">{s.name}</p>
              </button>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}

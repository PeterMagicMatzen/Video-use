import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Clapperboard, Scissors, Download, Loader2, RotateCcw, CheckCircle2,
} from "lucide-react";
import { api, downloadUrl } from "../api";
import { formatTime } from "../lib/captions";

export default function LeftRail({
  project, cuts, styleKey, previewCuts, setPreviewCuts, updateCuts, onReset,
}) {
  const [threshold, setThreshold] = useState(cuts?.settings?.pause_threshold ?? 0.8);
  const [fillers, setFillers] = useState(cuts?.settings?.remove_fillers ?? true);
  const [burnCaptions, setBurnCaptions] = useState(true);
  const [exportState, setExportState] = useState(project.export || { status: "idle" });
  const debounceRef = useRef(null);
  const pollRef = useRef(null);

  useEffect(() => () => clearInterval(pollRef.current), []);

  const onThreshold = (val) => {
    setThreshold(val);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      updateCuts({ pause_threshold: val, remove_fillers: fillers, disabled: [] });
    }, 350);
  };

  const onFillers = (val) => {
    setFillers(val);
    updateCuts({ pause_threshold: threshold, remove_fillers: val, disabled: [] });
  };

  const startExport = useCallback(async () => {
    try {
      await api.post(`/projects/${project.id}/export`, {
        caption_style: styleKey,
        burn_captions: burnCaptions,
      });
      setExportState({ status: "processing", progress: 0 });
      pollRef.current = setInterval(async () => {
        const { data } = await api.get(`/projects/${project.id}`);
        setExportState(data.export);
        if (data.export.status === "done") {
          clearInterval(pollRef.current);
          toast.success("Export ready!");
        } else if (data.export.status === "error") {
          clearInterval(pollRef.current);
          toast.error(`Export failed: ${data.export.error}`);
        }
      }, 2000);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Export failed to start");
    }
  }, [project.id, styleKey, burnCaptions]);

  const exporting = exportState.status === "processing";

  return (
    <aside className="w-72 shrink-0 bg-[#09090b] border-r border-zinc-800/50 p-6 flex flex-col gap-6 overflow-y-auto">
      <div>
        <div className="flex items-center gap-2">
          <Clapperboard className="w-5 h-5 text-primary" />
          <span className="font-heading text-xl font-bold tracking-tight">ClipCut</span>
        </div>
        <button
          data-testid="new-project-button"
          onClick={onReset}
          className="mt-3 flex items-center gap-1.5 text-xs text-zinc-500 hover:text-white transition-colors duration-150"
        >
          <RotateCcw className="w-3 h-3" /> New project
        </button>
      </div>

      <div className="border border-zinc-800 rounded-lg p-4">
        <p className="font-mono text-xs uppercase tracking-wider text-zinc-400 mb-2">Source</p>
        <p className="text-sm font-medium truncate" title={project.filename}>{project.filename}</p>
        <p className="font-mono text-xs text-zinc-500 mt-1">
          {formatTime(project.duration)} · {project.width}×{project.height}
        </p>
      </div>

      <div className="border border-zinc-800 rounded-lg p-4 flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <Scissors className="w-4 h-4 text-accent" />
          <p className="font-mono text-xs uppercase tracking-wider text-zinc-400">Auto-Cut</p>
        </div>
        <div>
          <div className="flex justify-between mb-2">
            <span className="text-xs text-zinc-400">Pause sensitivity</span>
            <span className="font-mono text-xs text-primary">{Number(threshold).toFixed(1)}s</span>
          </div>
          <input
            data-testid="auto-cut-slider"
            type="range" min="0.4" max="2.0" step="0.1"
            value={threshold}
            onChange={(e) => onThreshold(parseFloat(e.target.value))}
          />
          <p className="text-[10px] text-zinc-600 mt-1">Pauses longer than this get cut</p>
        </div>
        <ToggleRow
          testId="filler-toggle"
          label="Remove filler words"
          hint="um, uh, hmm..."
          checked={fillers}
          onChange={onFillers}
        />
        <ToggleRow
          testId="preview-cuts-toggle"
          label="Preview cuts in player"
          hint="skips removed parts"
          checked={previewCuts}
          onChange={setPreviewCuts}
        />
        {cuts && (
          <div className="flex gap-3 pt-1 border-t border-zinc-800">
            <Stat label="Kept" value={formatTime(cuts.kept_duration)} color="text-primary" testId="kept-duration" />
            <Stat label="Removed" value={formatTime(cuts.removed_duration)} color="text-red-400" testId="removed-duration" />
            <Stat label="Cuts" value={cuts.spans.filter((s) => !s.disabled).length} color="text-accent" testId="cut-count" />
          </div>
        )}
      </div>

      <div className="border border-zinc-800 rounded-lg p-4 flex flex-col gap-3 mt-auto">
        <p className="font-mono text-xs uppercase tracking-wider text-zinc-400">Export</p>
        <ToggleRow
          testId="burn-captions-toggle"
          label="Burn captions"
          hint={`style: ${styleKey}`}
          checked={burnCaptions}
          onChange={setBurnCaptions}
        />
        {exporting && (
          <div data-testid="export-progress">
            <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-[width] duration-500"
                style={{ width: `${exportState.progress || 0}%` }}
              />
            </div>
            <p className="font-mono text-[10px] text-zinc-500 mt-1">
              rendering {exportState.progress || 0}%
            </p>
          </div>
        )}
        {exportState.status === "done" ? (
          <a
            data-testid="download-button"
            href={downloadUrl(project.id)}
            className="flex items-center justify-center gap-2 bg-primary text-black font-heading font-bold text-sm rounded-full py-2.5 hover:scale-[1.03] transition-transform duration-150"
          >
            <CheckCircle2 className="w-4 h-4" /> Download MP4
          </a>
        ) : (
          <button
            data-testid="export-button"
            onClick={startExport}
            disabled={exporting}
            className="flex items-center justify-center gap-2 bg-primary text-black font-heading font-bold text-sm rounded-full py-2.5 hover:scale-[1.03] transition-transform duration-150 disabled:opacity-50 disabled:hover:scale-100"
          >
            {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            {exporting ? "Rendering..." : "Export Video"}
          </button>
        )}
        {exportState.status === "done" && (
          <button
            data-testid="re-export-button"
            onClick={startExport}
            className="text-xs text-zinc-500 hover:text-white transition-colors duration-150"
          >
            Re-export with current settings
          </button>
        )}
      </div>
    </aside>
  );
}

function ToggleRow({ label, hint, checked, onChange, testId }) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <p className="text-xs text-zinc-300">{label}</p>
        <p className="text-[10px] text-zinc-600">{hint}</p>
      </div>
      <button
        data-testid={testId}
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`w-9 h-5 rounded-full relative transition-colors duration-200 ${
          checked ? "bg-primary" : "bg-zinc-700"
        }`}
      >
        <span
          className={`absolute top-0.5 w-4 h-4 rounded-full bg-black transition-transform duration-200 ${
            checked ? "translate-x-[18px]" : "translate-x-0.5"
          }`}
        />
      </button>
    </div>
  );
}

function Stat({ label, value, color, testId }) {
  return (
    <div data-testid={testId}>
      <p className={`font-mono text-xs ${color}`}>{value}</p>
      <p className="text-[10px] text-zinc-600">{label}</p>
    </div>
  );
}

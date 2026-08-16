import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "../api";
import { buildChunks } from "../lib/captions";
import LeftRail from "../components/LeftRail";
import VideoStage from "../components/VideoStage";
import TranscriptPanel from "../components/TranscriptPanel";

export default function Editor({ projectId, onReset }) {
  const [project, setProject] = useState(null);
  const [cuts, setCuts] = useState(null);
  const [styleKey, setStyleKey] = useState("bold");
  const [previewCuts, setPreviewCuts] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const videoRef = useRef(null);

  useEffect(() => {
    api.get(`/projects/${projectId}`).then(({ data }) => {
      setProject(data);
      setCuts(data.cuts);
      setStyleKey(data.caption_style || "bold");
    });
  }, [projectId]);

  const chunks = useMemo(
    () => (project ? buildChunks(project.words) : []),
    [project]
  );

  const updateCuts = useCallback(
    async (settings) => {
      try {
        const { data } = await api.post(`/projects/${projectId}/cuts`, settings);
        setCuts(data);
      } catch {
        toast.error("Failed to update cuts");
      }
    },
    [projectId]
  );

  const toggleSpan = useCallback(
    (spanId) => {
      if (!cuts) return;
      const disabled = new Set(cuts.settings.disabled || []);
      disabled.has(spanId) ? disabled.delete(spanId) : disabled.add(spanId);
      updateCuts({ ...cuts.settings, disabled: [...disabled] });
    },
    [cuts, updateCuts]
  );

  const seekTo = useCallback((t) => {
    if (videoRef.current) {
      videoRef.current.currentTime = t;
      setCurrentTime(t);
    }
  }, []);

  const changeStyle = useCallback(
    (key) => {
      setStyleKey(key);
      api.post(`/projects/${projectId}/style`, { caption_style: key }).catch(() => {});
    },
    [projectId]
  );

  if (!project) {
    return (
      <div className="h-full flex items-center justify-center text-zinc-500 font-mono text-sm">
        loading project...
      </div>
    );
  }

  return (
    <div className="h-full w-full flex overflow-hidden" data-testid="editor-layout">
      <LeftRail
        project={project}
        cuts={cuts}
        styleKey={styleKey}
        previewCuts={previewCuts}
        setPreviewCuts={setPreviewCuts}
        updateCuts={updateCuts}
        onReset={onReset}
      />
      <VideoStage
        projectId={projectId}
        project={project}
        chunks={chunks}
        cuts={cuts}
        styleKey={styleKey}
        changeStyle={changeStyle}
        previewCuts={previewCuts}
        videoRef={videoRef}
        currentTime={currentTime}
        setCurrentTime={setCurrentTime}
      />
      <TranscriptPanel
        project={project}
        cuts={cuts}
        currentTime={currentTime}
        seekTo={seekTo}
        toggleSpan={toggleSpan}
      />
    </div>
  );
}

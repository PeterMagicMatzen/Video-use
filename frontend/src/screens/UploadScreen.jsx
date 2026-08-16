import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { Clapperboard, UploadCloud, Loader2, AudioLines } from "lucide-react";
import { uploadVideo, api } from "../api";

export default function UploadScreen({ onReady }) {
  const [phase, setPhase] = useState("idle"); // idle | uploading | transcribing
  const [progress, setProgress] = useState(0);
  const [dragOver, setDragOver] = useState(false);
  const [fileName, setFileName] = useState("");
  const inputRef = useRef(null);

  const pollUntilReady = useCallback(
    async (pid) => {
      setPhase("transcribing");
      for (let attempts = 0; attempts < 240; attempts++) {
        await new Promise((r) => setTimeout(r, 2500));
        const { data } = await api.get(`/projects/${pid}`);
        if (data.status === "ready") {
          onReady(pid);
          return;
        }
        if (data.status === "error") {
          toast.error(`Transcription failed: ${data.error}`);
          setPhase("idle");
          return;
        }
      }
      toast.error("Transcription timed out — please try again");
      setPhase("idle");
    },
    [onReady]
  );

  const handleFile = useCallback(
    async (file) => {
      if (!file) return;
      if (!/\.(mp4|mov|m4v|webm|mkv|avi)$/i.test(file.name)) {
        toast.error("Please upload a video file (mp4, mov, webm...)");
        return;
      }
      setFileName(file.name);
      setPhase("uploading");
      setProgress(0);
      try {
        const pid = await uploadVideo(file, setProgress);
        await pollUntilReady(pid);
      } catch (e) {
        toast.error(e?.response?.data?.detail || "Upload failed");
        setPhase("idle");
      }
    },
    [pollUntilReady]
  );

  return (
    <div className="h-full flex flex-col items-center justify-center px-6">
      <div className="w-full max-w-2xl fade-up">
        <div className="flex items-center gap-3 mb-2">
          <Clapperboard className="w-7 h-7 text-primary" />
          <h1 className="font-heading text-4xl sm:text-5xl tracking-tighter font-bold">
            ClipCut
          </h1>
        </div>
        <p className="text-zinc-400 text-sm mb-10">
          Upload a talking video. Get instant captions, silence &amp; filler
          cuts, and a social-ready export.
        </p>

        {phase === "idle" && (
          <div
            data-testid="upload-dropzone"
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              handleFile(e.dataTransfer.files?.[0]);
            }}
            className={`cursor-pointer border-2 border-dashed rounded-xl p-16 flex flex-col items-center gap-4 transition-colors duration-200 ${
              dragOver
                ? "border-primary bg-primary/5"
                : "border-zinc-700 hover:border-primary hover:bg-primary/5"
            }`}
          >
            <UploadCloud className="w-12 h-12 text-primary" />
            <div className="text-center">
              <p className="font-heading text-lg font-semibold">
                Drop your video here
              </p>
              <p className="text-zinc-500 text-sm mt-1">
                or click to browse — MP4, MOV, WEBM
              </p>
            </div>
            <input
              ref={inputRef}
              data-testid="upload-file-input"
              type="file"
              accept="video/*,.mp4,.mov,.m4v,.webm,.mkv,.avi"
              className="hidden"
              onChange={(e) => handleFile(e.target.files?.[0])}
            />
          </div>
        )}

        {phase === "uploading" && (
          <div className="border border-zinc-800 rounded-xl p-10" data-testid="upload-progress-panel">
            <div className="flex items-center gap-3 mb-4">
              <Loader2 className="w-5 h-5 text-primary animate-spin" />
              <p className="font-heading font-semibold">Uploading {fileName}</p>
            </div>
            <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-[width] duration-200"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="font-mono text-xs text-zinc-500 mt-2">{progress}%</p>
          </div>
        )}

        {phase === "transcribing" && (
          <div className="border border-zinc-800 rounded-xl p-10" data-testid="transcribing-panel">
            <div className="flex items-center gap-3">
              <span className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center pulse-ring">
                <AudioLines className="w-5 h-5 text-primary" />
              </span>
              <div>
                <p className="font-heading font-semibold">
                  Transcribing with ElevenLabs Scribe
                </p>
                <p className="text-zinc-500 text-sm">
                  Word-level timestamps incoming — this takes a moment...
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

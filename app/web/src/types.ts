export type CenterState =
  | "empty"
  | "inventory"
  | "transcribing"
  | "packed"
  | "strategy-ready"
  | "rendering"
  | "preview-ready"
  | "stale"
  | "error";

export type DoctorCheck = {
  name: string;
  ok: boolean;
  detail: string;
  required: boolean;
};

export type Doctor = {
  ok: boolean;
  checks: DoctorCheck[];
};

export type Source = {
  name: string;
  path: string;
  duration_s: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  error: string | null;
};

export type EdlRange = {
  source: string;
  start: number;
  end: number;
  beat?: string;
  quote?: string;
  reason?: string;
};

export type Edl = {
  version?: number;
  sources?: Record<string, string>;
  ranges?: EdlRange[];
  grade?: string;
  overlays?: unknown[];
  subtitles?: string;
  total_duration_s?: number;
};

export type Job = {
  kind: string;
  pid: number | null;
  started_at: string | null;
  output: string | null;
  log: string | null;
};

export type ProjectPayload = {
  folder: string;
  doctor: Doctor;
  sources: Source[];
  recents: string[];
  center_state: CenterState;
  error: string | null;
  packed_markdown: string | null;
  edl: Edl | null;
  has_preview: boolean;
  preview_mtime: number | null;
  has_final: boolean;
  chat_enabled: boolean;
  job: Job;
  stale: boolean;
};

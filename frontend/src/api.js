import axios from "axios";

const BASE = process.env.REACT_APP_BACKEND_URL;
export const API = `${BASE}/api`;

export const api = axios.create({ baseURL: API });

export const videoUrl = (pid) => `${API}/projects/${pid}/video`;
export const exportVideoUrl = (pid, bust) =>
  `${API}/projects/${pid}/export/video${bust ? `?t=${bust}` : ""}`;
export const downloadUrl = (pid) => `${API}/projects/${pid}/export/download`;
export const thumbUrl = (pid) => `${API}/projects/${pid}/thumbnail`;

const CHUNK_SIZE = 5 * 1024 * 1024;

export async function uploadVideo(file, onProgress) {
  const { data } = await api.post("/projects/upload/init", {
    filename: file.name,
    size: file.size,
  });
  const pid = data.project_id;
  const total = Math.ceil(file.size / CHUNK_SIZE);
  for (let i = 0; i < total; i++) {
    const blob = file.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE);
    const form = new FormData();
    form.append("index", i);
    form.append("chunk", blob, "chunk");
    await api.post(`/projects/${pid}/upload/chunk`, form);
    onProgress(Math.round(((i + 1) / total) * 100));
  }
  await api.post(`/projects/${pid}/upload/complete`);
  return pid;
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

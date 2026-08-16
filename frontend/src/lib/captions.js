const PUNCT = new Set([".", ",", "!", "?", ";", ":"]);

export function buildChunks(words, maxWords = 3) {
  const items = (words || []).filter(
    (w) => w.type === "word" && w.start != null
  );
  const chunks = [];
  let current = [];
  for (const w of items) {
    const text = (w.text || "").trim();
    if (!text) continue;
    current.push(w);
    if (current.length >= maxWords || PUNCT.has(text[text.length - 1])) {
      chunks.push(current);
      current = [];
    }
  }
  if (current.length) chunks.push(current);
  return chunks.map((c) => ({
    start: c[0].start,
    end: c[c.length - 1].end,
    words: c,
  }));
}

export const CAPTION_STYLES = [
  {
    key: "bold",
    name: "Bold Classic",
    uppercase: true,
    css: {
      fontFamily: "'Outfit', sans-serif",
      fontWeight: 800,
      color: "#fff",
      textShadow:
        "-2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000, 0 3px 6px rgba(0,0,0,0.6)",
    },
  },
  {
    key: "neon",
    name: "Cyber Neon",
    uppercase: true,
    css: {
      fontFamily: "'Outfit', sans-serif",
      fontWeight: 800,
      color: "#D4FF00",
      textShadow:
        "-2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000, 0 0 18px rgba(212,255,0,0.45)",
    },
  },
  {
    key: "boxed",
    name: "Boxed",
    uppercase: true,
    css: {
      fontFamily: "'Outfit', sans-serif",
      fontWeight: 700,
      color: "#fff",
      background: "rgba(0,0,0,0.85)",
      padding: "2px 10px",
      borderRadius: "4px",
    },
  },
  {
    key: "minimal",
    name: "Minimal",
    uppercase: false,
    css: {
      fontFamily: "'Inter', sans-serif",
      fontWeight: 500,
      color: "#fff",
      textShadow: "0 1px 3px rgba(0,0,0,0.9), 0 0 8px rgba(0,0,0,0.5)",
    },
  },
];

export function formatTime(s) {
  if (!s || isNaN(s)) s = 0;
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  const ms = Math.floor((s % 1) * 10);
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}.${ms}`;
}

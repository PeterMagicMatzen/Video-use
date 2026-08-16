export function headlineFor(state: string, hasCut: boolean): { kicker: string; title: string; detail: string } {
  if (hasCut && (state === "preview-ready" || state === "stale")) {
    return {
      kicker: "Ready",
      title: "Your cut is done",
      detail: "This is the edited video, not the raw take. Open it if the player still looks uncut.",
    };
  }
  switch (state) {
    case "empty":
      return {
        kicker: "Step 1",
        title: "Add a talking-head clip",
        detail: "Nothing uploads. A file picker opens on this PC — it may hide behind the browser.",
      };
    case "inventory":
      return {
        kicker: "Step 2",
        title: "Transcribe the take",
        detail: "Reads the words so we can cut on speech, not guess.",
      };
    case "transcribing":
      return { kicker: "Working", title: "Listening to the take…", detail: "ElevenLabs Scribe is running. Stay on this page." };
    case "packed":
    case "strategy-ready":
      return {
        kicker: "Step 3",
        title: "Generate the cut",
        detail: "One tap. Captions, cinematic cuts, and a Mixkit score — directed by Claude.",
      };
    case "rendering":
      return {
        kicker: "Working",
        title: "Cutting the film…",
        detail: "ffmpeg is writing the movie. Wait for the player to switch to “Finished cut”.",
      };
    case "preview-ready":
      return { kicker: "Ready", title: "Your cut is done", detail: "Play it here or open the file on your Desktop." };
    case "stale":
      return { kicker: "Update", title: "The plan changed", detail: "Run Make professional edit again to rebuild the movie." };
    case "error":
      return { kicker: "Needs a look", title: "Something stopped", detail: "Read the message below. Transcribe or the cut may already be usable." };
    default:
      return { kicker: "video-use", title: "Talking-head editor", detail: "" };
  }
}

export function stepIndex(state: string, hasCut: boolean): number {
  if (state === "empty") return 0;
  if (hasCut || state === "preview-ready") return 2;
  return 1;
}

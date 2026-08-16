export function canChat(state: string, doctorOk: boolean) {
  return doctorOk && !["empty", "inventory", "transcribing"].includes(state);
}
export function canTranscribe(state: string, doctorOk: boolean) {
  return doctorOk && ["inventory", "packed", "error"].includes(state);
}
export function canApprove(state: string, doctorOk: boolean) {
  return doctorOk && ["packed", "strategy-ready", "stale", "preview-ready", "error"].includes(state);
}
export function canRenderFinal(state: string) {
  return state === "preview-ready";
}

export function canAutoEdit(state: string, packed: boolean, claudeOk = true) {
  return claudeOk && packed && !["empty", "inventory", "transcribing", "rendering"].includes(state);
}

export function canAutoVoices(state: string, packed: boolean, claudeOk: boolean) {
  return claudeOk && canAutoEdit(state, packed);
}

export function canGenerate(state: string, hasClip: boolean, claudeOk: boolean) {
  return hasClip && claudeOk && !["transcribing", "rendering"].includes(state);
}

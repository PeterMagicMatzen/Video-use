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

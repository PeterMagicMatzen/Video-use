import { describe, it, expect } from "vitest";
import { canChat, canTranscribe, canApprove, canRenderFinal, canAutoEdit, canAutoVoices, canGenerate } from "./buttons";

describe("buttons", () => {
  it("empty disables chat and approve", () => {
    expect(canChat("empty", true)).toBe(false);
    expect(canApprove("empty", true)).toBe(false);
    expect(canRenderFinal("preview-ready")).toBe(true);
    expect(canRenderFinal("packed")).toBe(false);
  });
  it("packed enables chat and approve when doctor ok", () => {
    expect(canChat("packed", true)).toBe(true);
    expect(canChat("packed", false)).toBe(false);
    expect(canApprove("packed", true)).toBe(true);
    expect(canApprove("stale", true)).toBe(true);
    expect(canApprove("strategy-ready", true)).toBe(true);
    expect(canApprove("inventory", true)).toBe(false);
  });
  it("auto-edit works once packed, without Claude login", () => {
    expect(canAutoEdit("packed", true)).toBe(true);
    expect(canAutoEdit("packed", true, false)).toBe(false);
    expect(canAutoEdit("inventory", false)).toBe(false);
    expect(canAutoEdit("rendering", true)).toBe(false);
  });
  it("Claude voice pick needs packed transcript and login", () => {
    expect(canAutoVoices("packed", true, true)).toBe(true);
    expect(canAutoVoices("packed", true, false)).toBe(false);
    expect(canAutoVoices("inventory", false, true)).toBe(false);
  });
  it("Generate works from a clip even before captions", () => {
    expect(canGenerate("inventory", true, true)).toBe(true);
    expect(canGenerate("packed", true, true)).toBe(true);
    expect(canGenerate("rendering", true, true)).toBe(false);
    expect(canGenerate("inventory", true, false)).toBe(false);
  });
});

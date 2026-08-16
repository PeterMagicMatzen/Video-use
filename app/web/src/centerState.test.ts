import { describe, it, expect } from "vitest";
import { canChat, canTranscribe, canApprove, canRenderFinal } from "./buttons";

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
});

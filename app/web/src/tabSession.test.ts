import { describe, expect, it } from "vitest";
import { bootFromTab, shouldAdoptServerState } from "./tabSession";

describe("bootFromTab", () => {
  it("starts empty in a new tab even if the server still has a project", () => {
    expect(bootFromTab(null)).toEqual({ mode: "empty" });
    expect(bootFromTab("")).toEqual({ mode: "empty" });
    expect(bootFromTab("   ")).toEqual({ mode: "empty" });
  });

  it("restores only the folder this tab opened", () => {
    expect(bootFromTab("C:\\\\Users\\\\me\\\\clip")).toEqual({
      mode: "restore",
      folder: "C:\\\\Users\\\\me\\\\clip",
    });
  });
});

describe("shouldAdoptServerState", () => {
  it("does not show another tab's project", () => {
    expect(shouldAdoptServerState(null, "C:\\\\old-project")).toBe(false);
    expect(shouldAdoptServerState("C:\\\\mine", "C:\\\\old-project")).toBe(false);
  });

  it("keeps this tab's project after refresh", () => {
    expect(shouldAdoptServerState("C:\\\\mine", "C:\\\\mine")).toBe(true);
  });
});

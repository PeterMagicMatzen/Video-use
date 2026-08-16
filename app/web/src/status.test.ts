import { describe, expect, it } from "vitest";
import { headlineFor, stepIndex } from "./status";

describe("status copy", () => {
  it("treats a finished cut as the last step", () => {
    expect(stepIndex("preview-ready", true)).toBe(3);
    expect(headlineFor("preview-ready", true).title).toMatch(/cut is done/i);
  });
  it("asks for a clip when empty", () => {
    expect(stepIndex("empty", false)).toBe(0);
    expect(headlineFor("empty", false).title).toMatch(/talking-head/i);
  });
});

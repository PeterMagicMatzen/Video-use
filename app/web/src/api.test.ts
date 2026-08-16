import { describe, expect, it } from "vitest";
import { applySseEvent } from "./api";

describe("applySseEvent", () => {
  it("throws the error message so Retry can arm", () => {
    expect(() => applySseEvent({ error: "claude failed" }, () => {})).toThrow("claude failed");
  });

  it("forwards text chunks", () => {
    const chunks: string[] = [];
    applySseEvent({ text: "hi" }, (t) => chunks.push(t));
    expect(chunks).toEqual(["hi"]);
  });
});

import { describe, it, expect } from "vitest";
import { matchesLine } from "./filter";
import { messages } from "./i18n";
import type { Line } from "./types";
const line = (code: string, classification = "external") =>
  ({ code, classification }) as Line;
describe("service filtering", () => {
  it("retains a single physical bus under either combined line", () => {
    const bus = { lines: [line("1"), line("4")] };
    expect(matchesLine(bus, "1")).toBe(true);
    expect(matchesLine(bus, "4")).toBe(true);
    expect(matchesLine(bus, "2")).toBe(false);
  });
  it("shows all services under all lines", () =>
    expect(matchesLine({ lines: [] }, "all")).toBe(true));
  it("groups campus services independently", () => {
    expect(matchesLine({ lines: [line("R", "campus")] }, "campus")).toBe(true);
    expect(matchesLine({ lines: [line("1")] }, "campus")).toBe(false);
  });
  it("has matching translation keys", () =>
    expect(Object.keys(messages.en).sort()).toEqual(
      Object.keys(messages.tr).sort(),
    ));
  it("distinguishes stale and offline labels", () => {
    expect(messages.en.live).not.toEqual(messages.en.stale);
    expect(messages.tr.offline).toBe("Çevrimdışı");
  });
});

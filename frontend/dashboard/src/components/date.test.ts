import { describe, expect, it } from "vitest";

import { formatSingaporeDateTime } from "./date";

describe("formatSingaporeDateTime", () => {
  it("formats ISO timestamps in Singapore time", () => {
    expect(formatSingaporeDateTime("2026-07-09T10:16:22+00:00")).toBe(
      "Jul 9, 2026, 18:16 SGT",
    );
  });

  it("can include seconds for live snapshot timestamps", () => {
    expect(formatSingaporeDateTime("2026-07-09T10:16:22+00:00", { seconds: true })).toBe(
      "Jul 9, 2026, 18:16:22 SGT",
    );
  });

  it("keeps date-only values as friendly dates", () => {
    expect(formatSingaporeDateTime("2026-07-10")).toBe("10 Jul 2026");
  });

  it("returns original text for invalid timestamps", () => {
    expect(formatSingaporeDateTime("not-a-date")).toBe("not-a-date");
  });
});

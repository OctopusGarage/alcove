import { describe, expect, it } from "vitest";
import { dashboardResultClickMetadata } from "./events";

describe("dashboard events", () => {
  it("builds privacy-safe metadata for opened search results", () => {
    const metadata = dashboardResultClickMetadata({
      type: "pin",
      title: "  Private Result Title  ",
      text: "private body must not be copied",
      href: "/pins",
    });

    expect(metadata).toEqual({
      type: "pin",
      href: "/pins",
      title_length: "Private Result Title".length,
    });
    expect(JSON.stringify(metadata)).not.toContain("Private Result Title");
    expect(JSON.stringify(metadata)).not.toContain("private body");
  });
});

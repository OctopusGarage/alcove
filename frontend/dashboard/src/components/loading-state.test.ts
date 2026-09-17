import { describe, expect, it } from "vitest";
import { renderLoadingState } from "./loading-state";

describe("dashboard loading state", () => {
  it("renders visible shell copy while the snapshot is loading", () => {
    const html = renderLoadingState();

    expect(html).toContain("Alcove Console");
    expect(html).toContain("Loading local snapshot");
  });
});

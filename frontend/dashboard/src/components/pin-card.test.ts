import { describe, expect, it } from "vitest";
import { renderMarkdown } from "./pin-card";

describe("pin markdown rendering", () => {
  it("renders links and fenced code blocks as separate readable blocks", () => {
    const html = renderMarkdown(
      "Project: https://example.com\n\n```bash\necho \\\"hello\\\"\n```",
      "Example",
      "example-pin",
    );

    expect(html).toContain('<a href="https://example.com"');
    expect(html).toContain("<pre");
    expect(html).toContain("echo \\&quot;hello\\&quot;");
    expect(html).toContain('data-copy-target="pin-code-example-pin-0"');
    expect(html).toContain('id="pin-code-example-pin-0"');
    expect(html).not.toContain("https://example.com%5Cn%5Cn");
  });

  it("escapes markup inside code and inline content", () => {
    const html = renderMarkdown(
      "Use `<script>alert(1)</script>`\n\n```bash\necho '<unsafe>'\n```",
      "Example",
      "example-pin",
    );

    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(html).toContain("echo &#039;&lt;unsafe&gt;&#039;");
    expect(html).not.toContain("<script>");
  });
});

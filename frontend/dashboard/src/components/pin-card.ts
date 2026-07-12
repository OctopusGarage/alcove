import type { ThemePin } from "../snapshot";
import { formatSingaporeDateTime } from "./date";
import { escapeHtml } from "./text";

interface PinCardOptions {
  compact?: boolean;
}

export function pinCard(pin: ThemePin, options: PinCardOptions = {}): string {
  const tags = pin.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("");
  const refs = Array.from(new Set([...pin.resources, ...pin.source_refs].filter(Boolean)));
  const refsHtml = refs.map((ref) => `<code>${escapeHtml(ref)}</code>`).join("");
  const body = options.compact
    ? `<p class="pin-excerpt">${escapeHtml(pin.raw_excerpt || pin.content.slice(0, 220))}</p>`
    : `<div class="markdown-body">${renderMarkdown(pin.content, pin.title)}</div>`;
  const refsBlock = refs.length
    ? `
      <details class="refs" open>
        <summary>Sources and links <span>${refs.length}</span></summary>
        <div>${refsHtml}</div>
      </details>`
    : "";
  const anchor = options.compact ? "" : ` id="pin-${escapeHtml(pin.kind)}" tabindex="-1"`;
  return `
    <article${anchor} class="pin-card ${pin.kind}${options.compact ? " compact-card" : ""}" data-kind="${escapeHtml(pin.kind)}">
      <div class="pin-topline">
        <div class="pin-meta"><span>${escapeHtml(pin.kind)}</span><span>${escapeHtml(pin.priority)}</span></div>
        <small>${escapeHtml(formatSingaporeDateTime(pin.updated_at))}</small>
      </div>
      <h2 class="pin-title">${escapeHtml(pin.title)}</h2>
      <p class="pin-summary">${escapeHtml(pin.summary)}</p>
      <div class="tags">${tags}</div>
      ${body}
      ${refsBlock}
    </article>
  `;
}

function renderMarkdown(markdown: string, title: string): string {
  const lines = stripDuplicateTitle(markdown, title).split("\n");
  const html: string[] = [];
  let paragraph: string[] = [];
  let list: string[] = [];
  let table: string[] = [];
  let code: string[] = [];
  let inCode = false;

  const flushParagraph = () => {
    if (!paragraph.length) return;
    html.push(`<p>${inlineMarkdown(paragraph.join(" "))}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    if (!list.length) return;
    html.push(`<ul>${list.map((item) => `<li>${inlineMarkdown(item)}</li>`).join("")}</ul>`);
    list = [];
  };
  const flushTable = () => {
    if (!table.length) return;
    html.push(renderTable(table));
    table = [];
  };
  const flushBlocks = () => {
    flushParagraph();
    flushList();
    flushTable();
  };

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    const trimmed = line.trim();
    if (trimmed.startsWith("```")) {
      if (inCode) {
        html.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
        code = [];
        inCode = false;
      } else {
        flushBlocks();
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      code.push(line);
      continue;
    }
    if (!trimmed) {
      flushBlocks();
      continue;
    }
    const heading = /^(#{2,4})\s+(.+)$/.exec(trimmed);
    if (heading) {
      flushBlocks();
      const level = heading[1].length + 1;
      html.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }
    if (/^\|.+\|$/.test(trimmed)) {
      flushParagraph();
      flushList();
      table.push(trimmed);
      continue;
    }
    const bullet = /^[-*]\s+(.+)$/.exec(trimmed);
    if (bullet) {
      flushParagraph();
      flushTable();
      list.push(bullet[1]);
      continue;
    }
    flushList();
    flushTable();
    paragraph.push(trimmed);
  }
  if (inCode) {
    html.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
  }
  flushBlocks();
  return html.join("");
}

function stripDuplicateTitle(markdown: string, title: string): string {
  const lines = markdown.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
  const firstContent = lines.findIndex((line) => line.trim());
  if (firstContent < 0) return "";
  const first = lines[firstContent].trim();
  if (first === `# ${title}`) {
    return lines.slice(firstContent + 1).join("\n").trim();
  }
  return markdown.trim();
}

function renderTable(lines: string[]): string {
  const rows = lines
    .filter((line) => !/^\|\s*-+/.test(line))
    .map((line) =>
      line
        .split("|")
        .slice(1, -1)
        .map((cell) => cell.trim()),
    )
    .filter((row) => row.length);
  if (!rows.length) return "";
  const [head, ...body] = rows;
  return `
    <div class="table-scroll">
      <table>
        <thead><tr>${head.map((cell) => `<th>${inlineMarkdown(cell)}</th>`).join("")}</tr></thead>
        <tbody>${body
          .map((row) => `<tr>${row.map((cell) => `<td>${inlineMarkdown(cell)}</td>`).join("")}</tr>`)
          .join("")}</tbody>
      </table>
    </div>`;
}

function inlineMarkdown(value: string): string {
  const links: string[] = [];
  let html = escapeHtml(value).replace(
    /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
    (_match, label: string, url: string) => {
      const token = `@@ALCOVE_LINK_${links.length}@@`;
      links.push(
        `<a href="${url}" target="_blank" rel="noreferrer">${label}</a>`,
      );
      return token;
    },
  );
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(
    /(https?:\/\/[^\s<]+)/g,
    '<a href="$1" target="_blank" rel="noreferrer">$1</a>',
  );
  links.forEach((link, index) => {
    html = html.replace(`@@ALCOVE_LINK_${index}@@`, link);
  });
  return html;
}

# Personal Pin Markdown Rendering

## Goal

Make personal Pins readable and useful in the Dashboard, especially for command references such as CLIProxyAPI. Markdown links, headings, paragraphs, lists, tables, inline code, and fenced code blocks must preserve their intended structure instead of collapsing into one malformed paragraph.

## Scope

- Store the CLIProxyAPI reference as valid Markdown with fenced shell code blocks.
- Keep the current Pin file format and support existing plain-text and imported Pins.
- Render Markdown content in the Pin view with explicit structure and safe escaping.
- Keep long commands inside horizontally scrollable code blocks so cards remain stable.
- Add copy actions for fenced code blocks where the browser supports the Clipboard API.
- Preserve all active personal Pins in the Pins route, including directly created Pins and imported Pins.

## Design

The snapshot remains the source of truth. The backend continues to provide the raw Pin content and metadata. The frontend owns presentation: it parses the supported Markdown subset into escaped HTML, recognizing fenced code blocks before inline link processing. Code blocks are rendered as separate `pre` regions with a copy control; normal links open in a new tab with safe `rel` attributes. Unsupported Markdown is shown as escaped text rather than interpreted as HTML.

The Pins page keeps the existing card layout and visual language. Each card has a clear title, summary, tags, and a readable content region. Code blocks use a compact utility treatment, preserve line breaks, and scroll horizontally. Tables remain scrollable on narrow screens. Existing imported Pins continue to render without requiring migration.

## Acceptance Criteria

1. The CLIProxyAPI Pin displays the project URL as a link, not as a link containing newline escapes.
2. Each shell example displays as a separate multi-line code block with preserved backslashes and JSON.
3. Paragraphs, headings, lists, inline code, and tables remain visually separated.
4. Long content does not overflow the card or resize surrounding layout unexpectedly.
5. Existing imported Markdown Pins and plain-text Pins continue to render.
6. Copying a code block copies only that block's source text and does not navigate the page.
7. Backend and frontend regression tests cover the content shape and rendered behavior.

## Verification

- Run the focused backend and frontend tests.
- Build the dashboard frontend and rebuild the local Dashboard snapshot.
- Inspect the actual `/alcove/dashboard/#/pins` page and verify the CLIProxyAPI Pin visually at desktop and narrow widths.
- Run the full test suites before completion.

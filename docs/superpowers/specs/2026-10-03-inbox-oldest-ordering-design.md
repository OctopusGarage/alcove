# Inbox Oldest-Item Ordering Design

## Problem

`alcove inbox peek` promises to return the oldest pending inbox item across all
platforms. Its current ordering logic only recognizes legacy item directories
whose names begin with `YYYYMMDD`. Current capture bundles instead use the
required stable naming scheme `<platform>-<stable-id>`. Those names all fall
through to a lexical fallback, so the selected item can be unrelated to capture
order.

## Ordering Semantics

“Oldest pending” means the item that entered the inbox earliest, not the item
whose source content was published earliest. Therefore the authoritative field
for current capture bundles is `capture.json.captured_at`.

The ordering key uses these sources in priority order:

1. A valid `capture.json.captured_at` timestamp, normalized to an aware UTC
   datetime.
2. A legacy `YYYYMMDD` directory-name prefix, interpreted as midnight UTC.
3. No inferred time for items without either source; these remain after dated
   items and use platform plus item name for deterministic ordering.

`published_at` is deliberately excluded. An old article captured today should
not jump ahead of content that has already been waiting in the inbox.
Filesystem creation and modification times are also excluded because copying,
restoring, editing, and synchronizing a workspace can change them.

## Implementation

Keep the behavior inside `InboxModule`, where inbox enumeration and ordering
already live. Replace the name-only sort key with a path-aware key that can read
the adjacent `capture.json` manifest.

Manifest parsing must be defensive:

- A missing manifest, malformed JSON, missing `captured_at`, or invalid
  timestamp must not make `peek` fail.
- `Z` and explicit UTC offsets must compare as the same kind of aware datetime.
- Invalid metadata falls through to the legacy directory-date behavior.
- The final platform/item-name components provide deterministic tie-breaking.

No bundle files, directory names, or CLI response schemas change.

## Tests

Add regression coverage at the real `InboxModule.peek()` seam:

1. Two stable-ID bundles on different platforms, with the lexically earlier
   name having the later `captured_at`; assert that the earlier capture wins.
2. Equivalent timestamps expressed with `Z` and an explicit offset; assert
   correct chronological comparison.
3. Malformed or missing capture metadata; assert that legacy `YYYYMMDD` naming
   still works and `peek` does not fail.
4. Preserve the existing cross-platform legacy-name test.

Verification includes the focused inbox tests, the complete test suite and
quality checks required by the repository, and the original real-workspace CLI
reproduction that compares `peek` with the minimum `captured_at` value.

## Non-goals

- Renaming existing inbox directories.
- Sorting by publication date.
- Persisting a separate queue or index.
- Changing archive, note, todo, or delete behavior.

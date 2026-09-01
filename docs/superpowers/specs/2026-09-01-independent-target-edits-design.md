# Independent Target Copy Editing

## Goal

Each archived target copy of one source message is an independent Web material. Editing one copy must update only its own text, HTML, tags, rating, rendered content, and Telegram target message. Existing single-target records and API callers remain usable.

## Data flow

`message_targets` is the target-copy identity. It stores target Telegram identifiers plus independent `original_text`, `original_html`, `rendered_text`, `rating`, and thumbnail path. `target_tags` stores tag associations keyed by `message_targets.id`. The parent `messages` row remains the source/queue record and compatibility projection for legacy callers.

When a target copy is requested, the API resolves `target_id` and loads that target's fields. Without `target_id`, it uses the parent row. A missing target ID is a 404 rather than silently editing another copy.

## API and rendering

`PATCH /messages/{id}` accepts `target_id` and optional `body`, `add_tags`, `remove_tag_names`, and `rating`. The edit service applies all requested changes to the selected target in one transaction, renders from that target's body and tags, persists the result, then edits exactly that Telegram message. Legacy requests without `target_id` retain the existing parent-row behavior.

`GET` responses expose target-copy records, including their independent content and tags. The existing top-level fields remain the compatibility projection when needed by current clients.

## Web interaction

The detail drawer selects a target copy when multiple copies exist. It displays that copy's rating, tags, body, and archive link. An edit control changes the selected body's text and provides save/cancel actions. Rating and tag controls submit the selected target ID. Switching targets discards unsaved body edits after an explicit reset through the cancel action; saved changes are reflected in the returned message.

## Compatibility and errors

The migration runs after existing migrations. Legacy databases without target tables continue to serialize and edit parent records. A target ID must belong to the requested parent message. Telegram edit failures do not leave a falsely updated rendered payload: database changes are committed only after the Telegram edit succeeds, while existing retry/error behavior remains unchanged.

## Tests

Add storage/service tests proving two target copies can have different body, tags, rating, and rendered text. Assert Telegram edits address the selected target only. Add API tests for target selection, independent response fields, invalid target ownership, and the body edit request. Run the full Python suite, Ruff, frontend lint, and frontend type/build checks.

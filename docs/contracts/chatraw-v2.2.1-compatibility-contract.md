# ChatRaw v2.2.1 Compatibility Contract

This is the protection baseline for the ChatRaw Server refactor. It records
what the classic `v2.2.1` application already exposes so later Server targets
can add authentication and modules without accidentally rewriting the classic
product.

The machine-readable source of truth is
`backend/contracts/chatraw-v2.2.1.json`. Automated tests verify it.

## Protected behavior

- Existing chat, document, model, settings, Skill, plugin, proxy, upload, and
  Hermes route paths remain available. New Server routes may be added.
- `/api/chat` and `/api/hermes/chat` keep their existing
  `text/event-stream` response media type with newline-delimited JSON records.
  They are not standard SSE and must not be converted during the Server v1
  refactor.
- `/api/upload/document` keeps its `application/x-ndjson` progress stream.
- The current SQLite tables and columns remain readable. Later migrations must
  be additive and preserve classic data.
- `window.ChatRawPlugin`, its existing namespaces, hooks, bundled plugin types,
  and bundled plugin hook declarations remain compatible.
- `backend/static/index.html` continues to use Alpine `app()` and the generated
  `app.min.js` and `styles.min.css` assets.
- `python main.py` and `backend.main:app` remain valid backend entry points.
- `DATA_DIR/chatraw.db`, `DATA_DIR/plugins`, and `DATA_DIR/skills` remain the
  persistent classic data locations inside a Server data copy.

## Intentional future changes that are not regressions

- Server business routes will require authentication.
- Member requests to management operations will return `403`.
- Secret values will be removed from browser responses.
- Unapproved generic proxy targets will be rejected.
- New Server database tables and nullable ownership columns may be added.
- The legacy ten-chat automatic deletion behavior will be removed.
- New module task streams will use real SSE on new versioned endpoints; this
  does not change the classic chat or Hermes streams.

Any other change to the machine-readable baseline requires an explicit product
decision and a reviewed contract update.

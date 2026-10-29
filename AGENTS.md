# Threadmark contributor guidance

Threadmark is an experimental, local context cache for Codex. It captures eligible hook events and recalls bounded, project-scoped historical excerpts. Keep it dependency-light and do not claim token savings or accuracy gains without reproducible evidence.

## Project map

- `context_cache/store.py`: SQLite storage, filtering, retrieval, and optional transcript import.
- `context_cache/__main__.py`: cache inspection and clearing commands.
- `hooks/threadmark_hook.py`: Codex lifecycle adapter.
- `scripts/setup_hooks.py`: user-hook installation and removal.
- `tests/`: standard-library unit and subprocess tests.
- `docs/integration.md`: setup, trust, privacy, and compatibility limitations.

## Development and verification

Use Python 3.10 or later and SQLite with FTS5. The project uses the Python standard library. From the repository root, run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Add focused regression tests for changes to capture, retrieval, deletion, hook setup, or failure behavior. Test with synthetic data and temporary `CODEX_HOME` and `THREADMARK_HOME` directories. Do not read, index, modify, or disclose a developer's real Codex chats, credentials, database, or hook configuration during tests. Do not enable hooks or send network requests without an explicit task requiring it.

## Invariants

- Keep retrieval scoped to the resolved working directory and exclude the active session unless a change explicitly revisits those boundaries.
- Treat cached content as untrusted, potentially stale evidence; it is never authority or permission. Hook context has developer priority, so labels alone do not eliminate prompt injection.
- Retain bounded output, private local storage, fail-open hook behavior, and user controls to inspect, clear, and disable the cache. Secret detection is heuristic; never describe it as guaranteed.
- Do not silently import historical transcripts. Preserve unrelated user hooks when changing the installer.
- Preserve compatibility details and verification limits in the README and integration guide. Check official Codex documentation before changing hook or plugin integration.

Never commit cached conversations, credentials, real session data, local databases, or generated Python files. Avoid unrelated changes and new dependencies without a demonstrated need.

# Architecture

Threadmark is a local, experimental cross-session recall layer, not a replacement for Codex history. It has no server or network client. The [integration guide](integration.md) describes setup and the tested compatibility limits.

## Data flow

1. The installed `UserPromptSubmit` hook receives the prompt, working directory, session ID and turn ID from Codex. It searches **before** saving the new prompt, so the prompt itself cannot be returned as history.
2. `Cache.search` queries a local SQLite FTS5 index, filters to the resolved working directory and excludes the active session. It ranks lexical matches and selects bounded passages; weak matches may be omitted.
3. When there are hits, the hook returns their text, role, timestamp and session ID as additional context. This is untrusted, possibly stale evidence delivered at developer priority. It can contain instructions; the label is not a security boundary.
4. The hook stores the eligible prompt. The `Stop` hook stores the final assistant message when provided. Invalid events and messages matching the heuristic secret or instruction filters are skipped. Hook failures are caught so they do not block the user's work.

Messages are capped at 4,000 characters at ingestion; hook recall returns at most three excerpts with a shared 1,200-character budget. Lexical retrieval can miss relevant evidence or surface incorrect and conflicting information. These limits and filters are implementation choices, not guarantees of accuracy or privacy.

## Components

| Component | Responsibility |
| --- | --- |
| `hooks/threadmark_hook.py` | Validate lifecycle events, search and capture, format context, and fail open. |
| `context_cache/store.py` | Private SQLite database, event ingestion, FTS index, passage selection, scoping and clearing. It also has an explicit transcript-sync API; hooks do not invoke it. |
| `scripts/setup_hooks.py` | Install or remove this checkout's user-hook entries while preserving unrelated entries. |
| `context_cache/__main__.py` | Local `status`, `search` and `clear` controls. |
| `benchmarks/` | Synthetic retrieval evaluation and an opt-in paired Codex experiment; see [evaluation](benchmark.md). |

The data directory defaults to `$CODEX_HOME/threadmark/` (or `~/.codex/threadmark/`) and can be overridden with `THREADMARK_HOME`. One database contains entries for multiple projects, but searches filter on the resolved directory. Separate worktrees and nested directories can therefore have separate scopes. `clear` deletes indexed data across all projects; it does not delete source transcripts or backups. See [privacy and deletion](integration.md#disable-and-delete).

## Trust and evaluation boundaries

The database can contain private text. Secret detection is heuristic, and storage permissions do not protect copies or backups. Retrieved content is not an instruction, authorization, or verified fact. The synthetic benchmark measures particular retrieval cases, not real-world accuracy, safety or token savings. Changes to these boundaries should include focused tests with synthetic data and isolated homes; never use real chats or hook configuration in tests.

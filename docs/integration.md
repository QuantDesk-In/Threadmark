# Codex integration

Threadmark is an early local plugin. It records eligible prompt and final-response text into a private SQLite index as you use Codex, and looks for relevant excerpts from other chats in the same working directory. Existing history is not imported automatically. Exact working-directory scoping avoids mixing projects, but worktrees and nested folders are separate scopes. Excerpts may be stale or contain misleading instructions; never treat them as authority. Secret screening is best-effort, not a privacy guarantee. Avoid enabling it for conversations that must not be retained.

## Installation

Requires Python 3.10 or later, SQLite FTS5, and a current Codex with lifecycle hooks. From the checked-out Threadmark directory, inspect the code and then install global user hooks:

```sh
python3 scripts/setup_hooks.py install
```

This adds only Threadmark entries to `$CODEX_HOME/hooks.json` (default `~/.codex/hooks.json`), preserving other hook definitions. Keep the checkout at the same path: the hook command points to this copy. Restart Codex, ensure `features.hooks = true` if disabled, then use `/hooks` in the Codex CLI to review and trust both Threadmark hooks. Hooks are skipped until trusted, and changes require another review. Managed policy can prohibit user hooks. This path was exercised with Codex CLI 0.165.0; manually installed plugin hooks were not discovered in our test of that version, so the user-level hooks are the supported installation here. Do not enable both plugin and user hooks at the same time.

Reviewing and trusting hooks opts into local retention of future messages. The default data location is `$CODEX_HOME/threadmark/cache.sqlite3`, or `~/.codex/threadmark/cache.sqlite3` if `CODEX_HOME` is unset. Set `THREADMARK_HOME` in the Codex process environment to select another data directory. The plugin makes no network requests. Retrieval sends selected historical excerpts back into the model context as developer context: the label that says they are untrusted mitigates but cannot eliminate prompt injection, so review the risk before enabling it.

## Inspect and clear

From the checked-out Threadmark directory, use the same `CODEX_HOME` and `THREADMARK_HOME` environment settings as your Codex process:

```sh
python3 -m context_cache status
python3 -m context_cache search "migration backup" --project /absolute/project/path
python3 -m context_cache clear
```

Search prints private cached excerpts to the terminal. `clear` removes indexed entries; it does not delete source chats.

## Disable and delete

Disable the hooks through `/hooks` or remove the installed entries from the same checkout:

```sh
python3 scripts/setup_hooks.py remove
```

The remove command removes only entries matching this checkout and leaves other hooks intact. If the checkout moves, run removal from its original path first.

Disabling prevents future hook runs but does not delete the database. To remove it, run `python3 -m context_cache clear` from the checkout. Clearing does not import old chats; later enabled hooks will collect new messages. If multiple Codex processes are running, stop or disable hooks in each before clearing. Backups and filesystem snapshots may retain older copies.

Sources: [Codex hooks](https://learn.chatgpt.com/docs/hooks), [plugin packaging](https://developers.openai.com/plugins/build/plugins), [Codex developer commands](https://learn.chatgpt.com/docs/developer-commands).

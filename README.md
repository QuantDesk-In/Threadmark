# Threadmark

Threadmark is an experimental, local context cache for Codex. After its hooks are installed and trusted, it saves selected new prompts and final responses and retrieves short, potentially relevant excerpts from earlier chats in the same working directory. It requires Python 3.10 or later and SQLite with FTS5; it makes no network calls.

**Status: prototype.** An isolated test on Codex CLI 0.165.0 captured two synthetic chats, and the second answer recalled a fact from the first. The test bypassed hook trust; normal interactive trust remains unverified. No study has established that Threadmark reduces token usage or improves accuracy. Recall adds tokens to a prompt and can make either measure worse.

## Install and use

See [installation and controls](docs/integration.md) for global user-hook setup, hook trust, inspection and deletion. The plugin marketplace path did not load hooks in our CLI 0.165.0 test. Threadmark starts collecting new conversations after it is enabled; it does not automatically import older chats. A new chat and a matching working directory are needed for recall. Hook support and script availability depend on the Codex client and execution host.

## How it works

On each prompt, Threadmark searches its local SQLite index using lexical matching, excludes the current session, and returns at most three excerpts with a combined limit of 1,200 characters. It then saves the prompt; the `Stop` hook saves the final response when available. Each item is capped at 4,000 characters. Projects are identified by their resolved working-directory path: separate worktrees or subdirectories may not share context, and chats using the same directory may share it. There is one local database across projects, but retrieval is scoped to that exact directory.

Retrieved text is historical evidence, not a verified fact or instruction. It can be stale, wrong, irrelevant, or malicious. Codex receives hook context at developer priority; labeling excerpts as untrusted does not eliminate prompt-injection risk. Review the implementation and use Threadmark only with chats whose contents you are comfortable storing and recalling.

## Privacy

Threadmark stores excerpts in a local SQLite database under `$CODEX_HOME/threadmark/` (or `~/.codex/threadmark/` by default). `THREADMARK_HOME` overrides the data directory. The database can contain private conversation text and persists until cleared. Newly created files use restrictive permissions, but filesystem security and backups remain the user's responsibility. Credential detection skips some likely secret-bearing messages; it is heuristic and **cannot guarantee secrets or sensitive data are excluded**. Disable the plugin for sensitive work. Clearing the cache does not delete Codex's own transcripts or backups.

## Development

```sh
python3 -m unittest discover -s tests -v
```

See the [architecture](docs/architecture.md) for the data flow and trust boundaries, and the [benchmark and paired experiment protocol](docs/benchmark.md) for measured synthetic retrieval results and end-to-end limitations.

See [contribution guidance](CONTRIBUTING.md) and [integration research](docs/research.md) for development conventions, official Codex interfaces, and their limitations.

Licensed under the [MIT License](LICENSE).

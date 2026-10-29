# Contributing

Threadmark is an experimental local Codex context cache. Issues and pull requests are welcome. Before starting a large change, describe the problem and proposed approach in an issue so maintainers can discuss its scope. For smaller fixes, a focused pull request is welcome.

## Set up and verify

Clone the repository and work from its root. Python 3.10 or later and SQLite with FTS5 are required; there are no third-party Python dependencies. Check your SQLite build and run the suite:

```sh
python3 -c "import sqlite3; c = sqlite3.connect(':memory:'); c.execute('CREATE VIRTUAL TABLE fts_check USING fts5(text)'); print('SQLite', sqlite3.sqlite_version, 'with FTS5')"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

If the first command fails with `no such module: fts5`, use a Python build linked to SQLite with FTS5 enabled. Tests use temporary directories and synthetic data; installing or trusting Codex hooks is not required. Do not point tests at real Codex homes, chats or databases.

For retrieval changes, also run the [synthetic evaluation](docs/benchmark.md); explain changes to results and their limits. The paired Codex experiment requires a separate isolated setup and authorization for any network use and costs. It is not part of the test suite.

## Make a contribution

- Keep changes focused and explain the user-facing problem, approach and verification in the pull request. Link the related issue when applicable.
- Add focused regression tests for capture, retrieval, deletion, hook installation and failure behavior. Cover project and session boundaries when affected.
- Use synthetic chat text and isolated temporary directories. Never include real conversations, credentials, local databases, or private paths in issues, pull requests, logs or fixtures.
- Update the relevant docs when behavior, setup, compatibility, privacy or evaluation changes. Do not claim token savings or accuracy gains without reproducible evidence.
- Read the [architecture](docs/architecture.md), [integration guide](docs/integration.md), and [project conventions](AGENTS.md) for the boundaries that changes must preserve.

Contributions are submitted under the project's [MIT license](LICENSE). Please report security concerns as described in [SECURITY.md](SECURITY.md), rather than posting sensitive details publicly.

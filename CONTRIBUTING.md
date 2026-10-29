# Contributing

Threadmark is an experimental local Codex context cache. Issues and pull requests are welcome. Before starting a large change, describe the problem and proposed approach in an issue so maintainers can discuss its scope.

Run the test suite from the repository root with Python 3.10 or later and SQLite FTS5:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Use synthetic chat text and isolated temporary directories for tests. Never include real conversations, credentials, local cache databases, or private paths in issues, pull requests, or fixtures. Changes to capture, retrieval, deletion, or hook installation should include focused tests for the affected behavior and failure cases.

Read [AGENTS.md](AGENTS.md) for project conventions and [the integration guide](docs/integration.md) for compatibility and privacy limitations. Contributions are submitted under the project's [MIT license](LICENSE).

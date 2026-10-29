# Open-source readiness research

Checked 2026-10-29. This is a comparison of public project documentation and GitHub guidance, not a product or performance ranking. Threadmark is a local Codex hook cache; the projects below have different architectures and intended uses.

## Comparable projects

- The [MCP reference memory server](https://github.com/modelcontextprotocol/servers/blob/main/src/memory/README.md) explains its data model, runtime requirements, setup options, storage location, concurrency behavior, and license. For Threadmark, an architecture and data-flow explanation plus explicit trust and storage boundaries provide the equivalent operational context.
- [Mem0](https://github.com/mem0ai/mem0) distinguishes deployment options and links to documentation, integrations, and its Apache-2.0 license. Threadmark should identify its prototype status and supported integration path without implying an equivalent production service.
- [Supermemory's contribution guide](https://github.com/supermemoryai/supermemory/blob/main/CONTRIBUTING.md) describes local setup, contribution workflow, and how contributions are licensed. A small project can give the same essentials with its standard-library test command, synthetic-data rule, and scope-specific review expectations.
- [Supermemory's README](https://github.com/supermemoryai/supermemory/blob/main/README.md) publishes benchmark claims alongside named benchmarks. Those are its authors' claims, not independent validation or measurements of Threadmark. Threadmark already documents synthetic retrieval results and a paired evaluation protocol in [benchmark.md](benchmark.md); reproducibility, denominators, and limitations are more useful than copying a leaderboard claim. No evidence currently establishes end-to-end token savings for Threadmark.

## Community and security basics

[GitHub's community profile guidance](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories) identifies a README, license, contribution guidelines, code of conduct, and issue templates as community-health materials. GitHub also recommends a security policy for reporting vulnerabilities. Templates are useful when they solicit reproduction steps, environment details, and privacy-safe synthetic examples; they do not replace active maintenance.

## Recommendations

1. Keep the license, prototype status, installation limitations, privacy warnings, and contribution instructions discoverable from the README. Check that published rights and reporting channels match maintainer intent rather than inventing support commitments.
2. Explain the capture-to-retrieval flow, project and session boundaries, deletion, and the untrusted-content boundary in an architecture document linked from the README.
3. Add lightweight issue and pull request prompts for reproducibility, tests, compatibility, and accidental disclosure of sensitive chat data. Add automated tests on supported Python versions if the repository can run them without real Codex data, hooks, or network access.
4. Preserve the existing synthetic benchmark and paired protocol; publish end-to-end figures only after a reproducible authorized run, including baseline, environment, failures, token accounting, and uncertainty. The synthetic scores are not an estimate of production accuracy or savings.

# Threadmark evaluation

## Design and limits

The evaluation separates deterministic evidence retrieval from paired agent outcomes. We chose real `Cache.ingest_event` and `Cache.search` against fresh temporary databases, rather than a simulated search or a live transcript corpus: this exercises production retrieval without private data or service access. A paired fresh-session experiment is needed to assess task success, safety and token use; retrieval scores alone cannot establish any savings. A live run is not authorized by this task's network, hook and cost constraints. The synthetic fixtures are deliberately small and do not represent a production distribution.

The v1 development and held-out evaluation cases are distinct. No retrieval parameters were tuned against the evaluation cases. Defaults match the hook: three results and 1,200 excerpt characters. Each case has its own temporary database and canonical project paths, synthetic session IDs and fixed timestamps. The fixture marks the exact passage that makes an eligible document useful; a retrieved document counts only when that passage is visible in its returned excerpt. An old conflicting fact is labeled non-useful; recency itself is not proof of truth. Duplicate useful documents count separately. Project and active-session documents are excluded from eligible evidence.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m benchmarks.retrieval --split dev
PYTHONDONTWRITEBYTECODE=1 python3 -m benchmarks.retrieval --split eval
```

Recall is useful returned excerpts divided by eligible useful documents, micro-averaged across the split. Precision is useful returned excerpts divided by all returned excerpts. A no-answer false positive is any returned excerpt in a query with zero eligible useful documents; its rate divides by such queries. Empty denominators are `null`. These measures treat a passage missing due to truncation as a miss, and irrelevant or stale excerpts as false positives. Output size is the sum of excerpt Unicode characters, excluding the hook wrapper and JSON escaping; it is not token usage. Median elapsed time covers `Cache.search` only, not ingestion, hook startup or model execution, and varies by machine.

## Results recorded 2026-10-29

With fixture 1.0.0 and default limits, the dev split returned 2/2 recall, 2/4 precision, and 1/1 no-answer false positives; 198 excerpt characters. The held-out split returned 4/7 recall, 4/10 precision, and 2/3 no-answer false positives; 1,552 excerpt characters and a median search time of approximately 0.085 ms on this run. The short identifier and paraphrase cases missed, the long message's useful passage was truncated, duplicates occupied slots, and an obsolete conflicting statement was also returned. Project and active-session evidence did not cross their boundaries. These are observations from nine held-out queries, not generalizable performance estimates.

Prioritize testing passage-centered snippets and selective abstention on development cases, then evaluate a new untouched holdout; investigate duplicate suppression and conflict provenance next. These are hypotheses for future changes, not measured improvements. Do not weaken project/session boundaries or assume timestamps resolve conflicts. Actual Codex task quality, safety, tokens, cached input, cost and latency remain unmeasured. API billing and subscription limits are separate observables.

See [interface research](benchmark-research.md) for verified local CLI capabilities and limitations.

## Paired Codex protocol

The four versioned cases in `benchmarks/paired_cases.json` cover an answer available only in synthetic history, a no-history file lookup, an obsolete conflicting claim, and an instruction-injection marker. Each arm recreates identical files at the same project path and gets fresh temporary `HOME`, `CODEX_HOME` and `THREADMARK_HOME`. The enabled arm seeds synthetic events and installs reviewed local Threadmark hooks in its temporary home; the disabled arm disables hooks. Both use fresh ephemeral sessions, the same fixed model, read-only sandbox, and the same prompt. Alternating arm order across repeats reduces order bias. Exact output matching is the automated correctness oracle; the injection marker is a narrow safety check, not a comprehensive safety assessment.

The harness does not invoke Codex without `--run`. Only after separately authorizing network access, any cost and isolated hook execution, provide a compatible isolated authentication method and run, for example:

```sh
python3 benchmarks/paired.py --run --model MODEL --repeats 2 --output paired-results.json
```

For an API-key provider, supply `OPENAI_API_KEY` through the environment; it is passed to the child but never included in results. Do not copy personal credentials or point the harness at a real Codex home. Authentication, hook execution and JSON event fields vary by Codex version. Verify the enabled hook actually ran using an appropriate isolated diagnostic before interpreting comparisons: installing a hook and bypassing trust do not demonstrate execution. The harness does not measure hook overhead separately. A result with absent usage remains unavailable, and observed tool-call counts include only recognized JSON event types. The report includes each run and enabled-minus-disabled paired deltas, with per-arm median, min, max and sample count; failed or malformed runs are excluded from metric aggregates and shown individually. Elapsed time includes the Codex process, not preparation. Output and input counters are reported independently; no character-to-token conversion or billing calculation is made. Inspect raw cases and validate the scoring and event schema for the tested CLI before drawing conclusions.

The included mock subprocess test verifies setup, alternating arms, usage parsing and failure handling without invoking Codex or a hook. It cannot establish actual retrieval injection, token reporting, task success, safety, hook overhead, billing or subscription impact. See `tests/test_paired_benchmark.py` for the executable mock.

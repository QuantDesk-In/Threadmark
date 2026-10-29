#!/usr/bin/env python3
"""Paired, isolated Codex experiment. No Codex is invoked without --run."""
import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from context_cache.store import Cache
from scripts.setup_hooks import update

CASES = Path(__file__).with_name('paired_cases.json')


def parse_events(output):
    """Use the final turn usage object; missing or malformed fields stay unavailable."""
    usage = None
    calls = 0
    malformed = 0
    completed = False
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            malformed += 1
            continue
        if not isinstance(event, dict):
            malformed += 1
            continue
        if event.get('type') == 'turn.completed':
            completed = True
            if isinstance(event.get('usage'), dict):
                usage = event['usage']
        item = event.get('item')
        if event.get('type') == 'item.completed' and isinstance(item, dict) and item.get('type') in ('command_execution', 'mcp_tool_call', 'web_search'):
            calls += 1
    def count(key):
        value = usage.get(key) if usage is not None else None
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
    input_tokens, output_tokens = count('input_tokens'), count('output_tokens')
    return {'input_tokens': input_tokens, 'cached_input_tokens': count('cached_input_tokens'),
            'output_tokens': output_tokens, 'total_tokens': input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None, 'tool_calls_observed': calls,
            'malformed_event_lines': malformed, 'turn_completed': completed}


def _safe_files(work, files):
    for name, contents in files.items():
        p = Path(name)
        if p.is_absolute() or '..' in p.parts:
            raise ValueError('fixture path must be relative and contained')
        target = work / p
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding='utf-8')


def run_one(case, enabled, root, model, executable, timeout, api_key=None):
    # Recreate the same absolute project path for each paired arm.
    work = root / 'project'
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    _safe_files(work, case['files'])
    home = root / ('enabled-home' if enabled else 'disabled-home')
    if home.exists():
        shutil.rmtree(home)
    codex_home = home / 'codex'
    threadmark_home = home / 'threadmark'
    codex_home.mkdir(parents=True)
    threadmark_home.mkdir()
    if enabled:
        cache = Cache(threadmark_home / 'cache.sqlite3')
        try:
            for i, text in enumerate(case['history']):
                cache.ingest_event(project=str(work), session_id='synthetic-history', turn_id=str(i),
                                   role='assistant', text=text, timestamp='2025-01-01T00:00:00+00:00')
        finally:
            cache.close()
        update('install', codex_home)
    result_file = home / 'answer.txt'
    env = {'PATH': os.environ.get('PATH', ''), 'HOME': str(home), 'CODEX_HOME': str(codex_home),
           'THREADMARK_HOME': str(threadmark_home), 'PYTHONDONTWRITEBYTECODE': '1'}
    if api_key:
        env['OPENAI_API_KEY'] = api_key
    cmd = [executable, 'exec', '--json', '--ephemeral', '--skip-git-repo-check', '--sandbox', 'read-only',
           '--model', model, '--cd', str(work), '--output-last-message', str(result_file)]
    if enabled:
        cmd += ['--enable', 'hooks', '--dangerously-bypass-hook-trust']
    else:
        cmd += ['--disable', 'hooks']
    cmd.append(case['prompt'])
    started = time.perf_counter()
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
        elapsed = time.perf_counter() - started
        answer = result_file.read_text(encoding='utf-8').strip() if result_file.exists() else None
        metrics = parse_events(proc.stdout)
        valid = proc.returncode == 0 and answer is not None and metrics['malformed_event_lines'] == 0 and metrics['turn_completed']
        return {'case': case['id'], 'enabled': enabled, 'status': 'ok' if valid else 'failed',
                'returncode': proc.returncode, 'answer': answer,
                'correct': answer == case['expected'] if valid else None,
                'safety_violation': case.get('forbidden') in answer if valid and case.get('forbidden') else (False if valid else None),
                'elapsed_seconds': elapsed, 'hook_overhead_seconds': None, **metrics}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'case': case['id'], 'enabled': enabled, 'status': 'failed', 'error': type(exc).__name__,
                'correct': None, 'safety_violation': None, 'elapsed_seconds': time.perf_counter() - started,
                'hook_overhead_seconds': None, 'input_tokens': None, 'cached_input_tokens': None,
                'output_tokens': None, 'total_tokens': None, 'tool_calls_observed': None, 'malformed_event_lines': None, 'turn_completed': False}


def summarize(rows):
    summaries = {}
    for enabled in (False, True):
        group = [r for r in rows if r['enabled'] == enabled]
        metrics = {}
        for name in ('input_tokens', 'cached_input_tokens', 'output_tokens', 'total_tokens', 'tool_calls_observed', 'elapsed_seconds'):
            values = [r[name] for r in group if r.get(name) is not None and r['status'] == 'ok']
            metrics[name] = {'n': len(values), 'median': statistics.median(values) if values else None,
                             'min': min(values) if values else None, 'max': max(values) if values else None}
        summaries['enabled' if enabled else 'disabled'] = {'runs': len(group), 'successful_runs': sum(r['status'] == 'ok' for r in group),
            'correct': sum(r['correct'] is True for r in group), 'safety_violations': sum(r['safety_violation'] is True for r in group),
            'metrics': metrics}
    return summaries


def run_suite(cases, executable, model, repeats=1, timeout=300, api_key=None):
    rows = []
    with tempfile.TemporaryDirectory(prefix='threadmark-paired-') as tmp:
        root = Path(tmp)
        for rep in range(repeats):
            for case in cases:
                # Alternation reduces systematic ordering bias; each run starts from the same files.
                for enabled in ((False, True) if rep % 2 == 0 else (True, False)):
                    row = run_one(case, enabled, root, model, executable, timeout, api_key)
                    row['repeat'] = rep + 1
                    rows.append(row)
    pairs = []
    for i in range(0, len(rows), 2):
        pair = rows[i:i + 2]
        disabled = next(r for r in pair if not r['enabled'])
        enabled = next(r for r in pair if r['enabled'])
        deltas = {}
        for key in ('input_tokens', 'cached_input_tokens', 'output_tokens', 'total_tokens', 'tool_calls_observed', 'elapsed_seconds'):
            a, b = disabled.get(key), enabled.get(key)
            deltas[key] = b - a if disabled['status'] == enabled['status'] == 'ok' and a is not None and b is not None else None
        pairs.append({'case': disabled['case'], 'repeat': disabled['repeat'], 'enabled_minus_disabled': deltas})
    return {'fixture_version': 1, 'model': model, 'repeats': repeats, 'runs': rows, 'paired_deltas': pairs, 'summary': summarize(rows),
            'limitations': ['Hook overhead is not separately observable.', 'Tool calls count only recognized completed JSONL events.',
                            'Token counters are provider-reported values, not estimates; absent fields are unavailable.',
                            'Subscription limits and billing are not measured.', 'Enabled-hook execution must be independently verified for the target Codex version.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Explicitly authorize invoking Codex and any associated network/charges')
    parser.add_argument('--model', required=True, help='Explicit fixed model')
    parser.add_argument('--codex', default='codex', help='Codex executable')
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--output', required=True, help='Destination for synthetic results JSON')
    args = parser.parse_args()
    if not args.run:
        parser.error('--run is required; real runs may use network and incur charges')
    if args.repeats < 1 or args.timeout < 1:
        parser.error('repeats and timeout must be positive')
    data = json.loads(CASES.read_text(encoding='utf-8'))
    result = run_suite(data['cases'], args.codex, args.model, args.repeats, args.timeout, os.environ.get('OPENAI_API_KEY'))
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return 0 if all(r['status'] == 'ok' for r in result['runs']) else 1


if __name__ == '__main__':
    sys.exit(main())

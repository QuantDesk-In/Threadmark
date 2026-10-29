import json
import os
from pathlib import Path
import tempfile
import unittest

from benchmarks.paired import parse_events, run_one, run_suite, _safe_files


class PairedBenchmarkTests(unittest.TestCase):
    def test_usage_and_tool_events_are_actual_values(self):
        events = '\n'.join(map(json.dumps, [
            {'type': 'item.completed', 'item': {'type': 'command_execution'}},
            {'type': 'turn.completed', 'usage': {'input_tokens': 27, 'cached_input_tokens': 8, 'output_tokens': 4}},
        ]))
        result = parse_events(events)
        self.assertEqual((result['input_tokens'], result['cached_input_tokens'], result['output_tokens']), (27, 8, 4))
        self.assertEqual(result['tool_calls_observed'], 1)
        self.assertEqual(parse_events('not json')['malformed_event_lines'], 1)
        self.assertIsNone(parse_events('{}')['input_tokens'])

    def test_fixture_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                _safe_files(Path(tmp), {'../outside': 'bad'})

    def test_mock_process_isolation_and_failures(self):
        case = {'id': 'sample', 'files': {'data.txt': 'same'}, 'history': ['synthetic prior context'],
                'prompt': 'example', 'expected': 'OK'}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            executable = root / 'fake-codex'
            executable.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
assert os.environ["HOME"] != str(pathlib.Path.home().parent)
assert pathlib.Path(os.environ["CODEX_HOME"]).parent == pathlib.Path(os.environ["HOME"])
assert pathlib.Path(os.environ["THREADMARK_HOME"]).parent == pathlib.Path(os.environ["HOME"])
assert pathlib.Path(args[args.index("--cd") + 1], "data.txt").read_text() == "same"
enabled = "--enable" in args
assert pathlib.Path(os.environ["CODEX_HOME"], "hooks.json").exists() == enabled
assert pathlib.Path(os.environ["THREADMARK_HOME"], "cache.sqlite3").exists() == enabled
pathlib.Path(args[args.index("--output-last-message") + 1]).write_text("OK")
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 12, "output_tokens": 3}}))
''', encoding='utf-8')
            executable.chmod(0o755)
            result = run_suite([case], str(executable), 'synthetic-model', repeats=2, timeout=10)
            self.assertEqual(len(result['runs']), 4)
            self.assertTrue(all(row['status'] == 'ok' and row['correct'] for row in result['runs']))
            self.assertTrue(all(row['cached_input_tokens'] is None for row in result['runs']))
            self.assertEqual(result['summary']['enabled']['metrics']['input_tokens']['median'], 12)
            row = run_one(case, False, root, 'synthetic-model', str(root / 'missing'), 5)
            self.assertEqual(row['status'], 'failed')
            self.assertIsNone(row['correct'])
            self.assertIsNone(row['input_tokens'])


if __name__ == '__main__':
    unittest.main()

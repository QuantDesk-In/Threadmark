import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / 'hooks' / 'threadmark_hook.py'


class HookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = {**os.environ, 'CODEX_HOME': self.temp.name}
        self.project = str(Path(self.temp.name) / 'project')

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, name, session, turn, **fields):
        event = dict(hook_event_name=name, cwd=self.project, session_id=session, turn_id=turn, **fields)
        process = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), text=True,
                                 capture_output=True, env=self.env, check=True)
        self.assertEqual(process.stderr, '')
        return json.loads(process.stdout) if process.stdout else None

    def test_cross_session_recall_and_clear(self):
        self.assertIsNone(self.invoke('UserPromptSubmit', 'first', 'one', prompt='Walnut migration requires a backup'))
        self.assertEqual(self.invoke('Stop', 'first', 'one', last_assistant_message='Walnut migration uses a snapshot'), {})
        self.assertIsNone(self.invoke('UserPromptSubmit', 'first', 'two', prompt='Walnut migration'))
        output = self.invoke('UserPromptSubmit', 'second', 'three', prompt='Walnut migration')
        context = output['hookSpecificOutput']['additionalContext']
        self.assertIn('untrusted', context)
        self.assertIn('Walnut migration', context)
        command = subprocess.run([sys.executable, '-m', 'context_cache', 'status'], cwd=ROOT, env=self.env, text=True, capture_output=True, check=True)
        self.assertGreater(json.loads(command.stdout)['messages'], 0)
        command = subprocess.run([sys.executable, '-m', 'context_cache', 'clear'], cwd=ROOT, env=self.env, text=True, capture_output=True, check=True)
        self.assertTrue(json.loads(command.stdout)['cleared'])
        self.assertIsNone(self.invoke('UserPromptSubmit', 'third', 'four', prompt='Walnut migration'))

    def test_bad_input_does_not_block_stop(self):
        result = subprocess.run([sys.executable, str(HOOK)], input='{"hook_event_name":"Stop"}', text=True,
                                capture_output=True, env=self.env, check=True)
        self.assertEqual(json.loads(result.stdout), {})


if __name__ == '__main__':
    unittest.main()

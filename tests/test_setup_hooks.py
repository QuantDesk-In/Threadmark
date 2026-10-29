import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'setup_hooks.py'

class SetupTests(unittest.TestCase):
    def test_install_remove_preserve_other_hooks_and_are_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'hooks.json'
            other = {'hooks': [{'type': 'command', 'command': 'other-command'}], 'matcher': 'x'}
            original = {'description': 'mine', 'hooks': {'Stop': [other], 'SessionStart': [other]}}
            file.write_text(json.dumps(original))
            def run(action):
                subprocess.run([sys.executable, str(SCRIPT), action, '--codex-home', temp], check=True, capture_output=True)
            run('install')
            first = json.loads(file.read_text())
            run('install')
            self.assertEqual(first, json.loads(file.read_text()))
            run('remove')
            self.assertEqual(original, json.loads(file.read_text()))
            run('remove')
            self.assertEqual(original, json.loads(file.read_text()))

    def test_invalid_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'hooks.json'
            file.write_text('{invalid')
            result = subprocess.run([sys.executable, str(SCRIPT), 'install', '--codex-home', temp], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(file.read_text(), '{invalid')

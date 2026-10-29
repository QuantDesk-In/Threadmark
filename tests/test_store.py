import json
import tempfile
import unittest
from pathlib import Path
from context_cache.store import Cache


def record(kind, payload, timestamp='2026-01-01T00:00:00Z'):
    return json.dumps({'type': kind, 'timestamp': timestamp, 'payload': payload}) + '\n'


def session(path, cwd, text, role='user'):
    path.write_text(record('session_meta', {'id': 'one', 'cwd': cwd}) + record('response_item', {'type': 'message', 'role': role, 'content': [{'type': 'input_text', 'text': text}]}))


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'sessions'
        self.root.mkdir()
        self.cache = Cache(self.base / 'private' / 'cache.sqlite3')

    def tearDown(self):
        self.cache.close()
        self.temp.cleanup()

    def test_indexes_and_finds_same_project_only(self):
        session(self.root / 'a.jsonl', '/projects/alpha', 'Using walnut database migration')
        session(self.root / 'b.jsonl', '/projects/beta', 'Using walnut database beta')
        self.cache.sync(self.root)
        hits = self.cache.search('walnut database', project='/projects/alpha')
        self.assertEqual(len(hits), 1)
        self.assertIn('migration', hits[0]['text'])

    def test_sync_removes_changed_and_deleted_content(self):
        path = self.root / 'a.jsonl'
        session(path, '/projects/alpha', 'walnut migration')
        self.cache.sync(self.root)
        session(path, '/projects/alpha', 'hazelnut changes')
        self.cache.sync(self.root)
        self.assertEqual(self.cache.search('walnut', project='/projects/alpha'), [])
        self.assertEqual(len(self.cache.search('hazelnut', project='/projects/alpha')), 1)
        path.unlink()
        self.cache.sync(self.root)
        self.assertEqual(self.cache.search('hazelnut', project='/projects/alpha'), [])

    def test_skips_credentials_and_non_message_records(self):
        path = self.root / 'a.jsonl'
        session(path, '/projects/alpha', 'api_key = sk-abcdefghijklmnopsecret')
        with path.open('a') as f:
            f.write(record('response_item', {'type': 'function_call_output', 'output': 'walnut secret'}))
        self.cache.sync(self.root)
        self.assertEqual(self.cache.search('secret', project='/projects/alpha'), [])
        self.assertEqual(self.cache.search('walnut', project='/projects/alpha'), [])

    def test_bounded_output_and_safe_query(self):
        session(self.root / 'a.jsonl', '/projects/alpha', 'walnut ' + 'long ' * 1000)
        self.cache.sync(self.root)
        hits = self.cache.search('"walnut" OR *', project='/projects/alpha', max_chars=80)
        self.assertEqual(len(hits), 1)
        self.assertLessEqual(len(hits[0]['text']), 80)

    def test_incomplete_json_is_ignored_then_recovered(self):
        path = self.root / 'a.jsonl'
        path.write_text(record('session_meta', {'id': 'one', 'cwd': '/projects/alpha'}) + '{')
        self.cache.sync(self.root)
        session(path, '/projects/alpha', 'walnut recovered')
        self.cache.sync(self.root)
        self.assertEqual(len(self.cache.search('walnut', project='/projects/alpha')), 1)

    def test_session_exclusion_and_clear(self):
        session(self.root / 'a.jsonl', '/projects/alpha', 'walnut migration')
        self.cache.sync(self.root)
        self.assertEqual(self.cache.search('walnut', project='/projects/alpha', exclude_session='one'), [])
        self.cache.clear()
        self.assertEqual(self.cache.search('walnut', project='/projects/alpha'), [])
        self.cache.sync(self.root)
        self.assertEqual(len(self.cache.search('walnut', project='/projects/alpha')), 1)

    def test_unrecognized_records_fail_closed(self):
        path = self.root / 'a.jsonl'
        path.write_text(record('session_meta', {'cwd': '/projects/alpha'}) + record('response_item', {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'walnut'}]}))
        self.cache.sync(self.root)
        self.assertEqual(self.cache.search('walnut', project='/projects/alpha'), [])

    def test_event_ingestion_deduplicates_and_excludes_active_session(self):
        kwargs = dict(project='/projects/alpha', session_id='session1', turn_id='turn1', role='user', text='walnut migration', timestamp='2026-01-01')
        self.assertTrue(self.cache.ingest_event(**kwargs))
        self.assertTrue(self.cache.ingest_event(**kwargs))
        self.assertEqual(len(self.cache.search('walnut', project='/projects/alpha')), 1)
        self.assertEqual(self.cache.search('walnut', project='/projects/alpha', exclude_session='session1'), [])
        self.assertEqual(self.cache.search('walnut', project='/projects/beta'), [])
        self.cache.clear()
        self.assertEqual(self.cache.search('walnut', project='/projects/alpha'), [])

    def test_event_rejects_credentials_and_invalid_metadata(self):
        kwargs = dict(project='/projects/alpha', session_id='session1', turn_id='turn1', role='user', text='password = supersecret', timestamp='2026-01-01')
        self.assertFalse(self.cache.ingest_event(**kwargs))
        self.assertEqual(self.cache.search('supersecret', project='/projects/alpha'), [])
        kwargs['text'] = 'walnut migration'
        kwargs['turn_id'] = ''
        self.assertFalse(self.cache.ingest_event(**kwargs))
        self.assertEqual(self.cache.search('walnut', project='/projects/alpha'), [])

    def test_multiword_query_requires_two_matching_terms(self):
        session(self.root / 'a.jsonl', '/projects/alpha', 'walnut passwordless profile')
        session(self.root / 'b.jsonl', '/projects/alpha', 'walnut unrelated history')
        self.cache.sync(self.root)
        hits = self.cache.search('walnut passwordless', project='/projects/alpha')
        self.assertEqual(len(hits), 1)
        self.assertIn('passwordless', hits[0]['text'])

    def test_event_skips_common_credential_formats(self):
        for n, value in enumerate((
            '{"api_key":"abc123"}',
            '{"password":"secret"}',
            "'client_secret': 'hidden'",
            'password: hunter2',
            'ACCESS_TOKEN=abcdef',
        )):
            with self.subTest(value=value):
                self.assertFalse(self.cache.ingest_event(project='/projects/alpha', session_id='s', turn_id=str(n), role='user', text=value))
        self.assertEqual(self.cache.search('abc123', project='/projects/alpha'), [])

    def test_existing_public_database_is_rejected(self):
        db = self.base / 'public.sqlite3'
        db.touch(mode=0o644)
        db.chmod(0o644)
        with self.assertRaises(PermissionError):
            Cache(db)

    def test_permissions(self):
        self.assertEqual((self.base / 'private').stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.base / 'private' / 'cache.sqlite3').stat().st_mode & 0o777, 0o600)

if __name__ == '__main__':
    unittest.main()

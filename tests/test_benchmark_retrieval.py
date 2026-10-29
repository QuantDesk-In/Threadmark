import json
import tempfile
import unittest
from pathlib import Path

from benchmarks.retrieval import run, summarize


class RetrievalBenchmarkTests(unittest.TestCase):
    def test_metrics_count_only_visible_useful_evidence_and_no_answer_hits(self):
        rows = [dict(eligible=2, useful=1, returned=2, excerpt_characters=10, search_ms=1),
                dict(eligible=0, useful=0, returned=1, excerpt_characters=5, search_ms=3),
                dict(eligible=0, useful=0, returned=0, excerpt_characters=0, search_ms=2)]
        result = summarize(rows)
        self.assertEqual(result['recall'], 0.5)
        self.assertEqual(result['precision'], 1 / 3)
        self.assertEqual(result['no_answer_false_positive_rate'], 0.5)
        self.assertEqual(result['median_search_ms'], 2)

    def test_project_and_active_session_excluded(self):
        cases = {row['id']: row for row in run()['cases']}
        self.assertEqual(cases['eval-project']['eligible'], 0)
        self.assertNotIn('d1', cases['eval-project']['returned_ids'])
        self.assertEqual(cases['eval-active']['returned'], 0)

    def test_bad_fixture_and_empty_split_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'fixture.json'
            path.write_text(json.dumps({'version': 'x', 'cases': []}))
            with self.assertRaises(ValueError):
                run(path)
            with self.assertRaises(ValueError):
                run(limit=0)


if __name__ == '__main__':
    unittest.main()

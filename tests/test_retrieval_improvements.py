import tempfile
import unittest
from pathlib import Path

from context_cache.store import Cache


class RetrievalImprovementsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cache = Cache(Path(self.temp.name) / 'cache.sqlite3')
        self.project = str(Path(self.temp.name) / 'project')

    def tearDown(self):
        self.cache.close()
        self.temp.cleanup()

    def add(self, text, session='past', project=None, timestamp='2025-01-01'):
        self.cache.ingest_event(project=project or self.project, session_id=session,
                                turn_id=session, role='assistant', text=text, timestamp=timestamp)

    def test_late_passage_is_visible_and_bounded(self):
        self.add('Background notes. ' * 120 + 'Orchid archive location is shelf nine. More context follows.')
        hit = self.cache.search('orchid archive location', project=self.project, max_chars=100)[0]
        self.assertIn('shelf nine', hit['text'])
        self.assertLessEqual(len(hit['text']), 100)
        self.assertTrue(hit['text'].startswith('…'))

    def test_partial_overlap_abstains(self):
        self.add('Maple release notes discuss a logo.')
        self.assertEqual(self.cache.search('maple release policy', project=self.project), [])

    def test_short_identifier_only_if_unambiguous(self):
        self.add('QX is the project identifier.')
        self.assertEqual(len(self.cache.search('QX', project=self.project)), 1)
        self.add('QX is another identifier.', session='second')
        self.add('QX is yet another identifier.', session='third')
        self.assertEqual(self.cache.search('QX', project=self.project), [])
        self.assertEqual(self.cache.search('is', project=self.project), [])

    def test_late_short_identifier_is_visible(self):
        self.add('Background notes. ' * 100 + 'QX identifies this project.')
        hit = self.cache.search('QX', project=self.project, max_chars=80)[0]
        self.assertIn('QX identifies', hit['text'])

    def test_conflicting_evidence_remains_available(self):
        self.add('Juniper queue capacity is five.', session='old', timestamp='2025-01-01')
        self.add('Juniper queue capacity is ten.', session='new', timestamp='2026-01-01')
        hits = self.cache.search('juniper queue capacity', project=self.project)
        self.assertEqual({hit['session_id'] for hit in hits}, {'old', 'new'})

    def test_boundaries_and_tiny_budget(self):
        self.add('Orchid archive location is elsewhere.', session='other', project=str(Path(self.temp.name) / 'other'))
        self.add('Orchid archive location is active.', session='active')
        self.assertEqual(self.cache.search('orchid archive location', project=self.project, exclude_session='active'), [])
        self.add('Start. ' * 100 + 'Orchid archive location is shelf nine.', session='past')
        hits = self.cache.search('orchid archive location', project=self.project, exclude_session='active', max_chars=1)
        self.assertLessEqual(sum(len(hit['text']) for hit in hits), 1)

    def test_scattered_matches_do_not_make_an_unanchored_excerpt(self):
        self.add('orchid ' + 'background ' * 80 + 'archive ' + 'background ' * 80 + 'location')
        self.assertEqual(self.cache.search('orchid archive location', project=self.project, max_chars=80), [])

    def test_too_small_budget_abstains_instead_of_returning_fragments(self):
        self.add('Orchid archive location is shelf nine.')
        self.assertEqual(self.cache.search('orchid archive location', project=self.project, max_chars=5), [])

    def test_small_budget_does_not_return_just_a_single_anchor(self):
        self.add('walnut ' + 'context ' * 20)
        self.assertEqual(self.cache.search('walnut', project=self.project, max_chars=10), [])

    def test_question_with_paraphrased_action_keeps_strong_overlap(self):
        self.add('Violet deployment rollback uses the previous image.')
        hits = self.cache.search('how is violet deployment reverted', project=self.project)
        self.assertEqual(len(hits), 1)
        self.assertIn('previous image', hits[0]['text'])


if __name__ == '__main__':
    unittest.main()

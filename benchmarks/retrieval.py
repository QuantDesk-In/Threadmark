"""Evaluate the production cache on versioned, isolated synthetic cases."""
from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

from context_cache.store import Cache

FIXTURE = Path(__file__).parent / 'fixtures' / 'retrieval-v1.json'


def summarize(rows):
    """Micro-average evidence recall/precision and no-answer query false positives."""
    eligible = sum(row['eligible'] for row in rows)
    returned = sum(row['returned'] for row in rows)
    useful = sum(row['useful'] for row in rows)
    no_answer = [row for row in rows if row['eligible'] == 0]
    return {
        'queries': len(rows), 'eligible_evidence': eligible, 'returned_excerpts': returned,
        'useful_excerpts': useful,
        'recall': useful / eligible if eligible else None,
        'precision': useful / returned if returned else None,
        'no_answer_queries': len(no_answer),
        'no_answer_false_positive_rate': (sum(r['returned'] > 0 for r in no_answer) / len(no_answer)
                                          if no_answer else None),
        'excerpt_characters': sum(r['excerpt_characters'] for r in rows),
        'median_search_ms': statistics.median(r['search_ms'] for r in rows) if rows else None,
    }


def run(fixture=FIXTURE, split='eval', limit=3, max_chars=1200):
    data = json.loads(Path(fixture).read_text(encoding='utf-8'))
    if limit <= 0 or max_chars <= 0:
        raise ValueError('limit and max_chars must be positive')
    rows = []
    with tempfile.TemporaryDirectory(prefix='threadmark-retrieval-') as tmp:
        base = Path(tmp)
        project = base / 'project'
        other = base / 'other'
        for case in data['cases']:
            if case['split'] != split:
                continue
            # Per-case fresh cache prevents cross-case contamination and never touches user data.
            cache = Cache(base / case['id'] / 'cache.sqlite3')
            try:
                documents = {}
                for document in case['documents']:
                    sid = document.get('session', document['id'])
                    path = other if document.get('project') == 'other' else project
                    text = document.get('prefix_repeat', '') * document.get('prefix_count', 0) + document['text']
                    if not cache.ingest_event(project=str(path), session_id=sid, turn_id=document['id'],
                                              role='assistant', text=text, timestamp=document.get('timestamp', '2026-01-01')):
                        raise ValueError('fixture document rejected: ' + case['id'] + '/' + document['id'])
                    if sid in documents:
                        raise ValueError('fixture session IDs must be unique per case')
                    documents[sid] = document
                eligible = sum(bool(d.get('answer')) and d.get('project') != 'other'
                               and d.get('session', d['id']) != 'active' for d in case['documents'])
                start = time.perf_counter()
                hits = cache.search(case['query'], project=str(project), exclude_session='active',
                                    limit=limit, max_chars=max_chars)
                duration = (time.perf_counter() - start) * 1000
                useful = sum(bool(documents[h['session_id']].get('answer')) and
                             documents[h['session_id']]['answer'] in h['text'] for h in hits)
                rows.append({'id': case['id'], 'eligible': eligible, 'returned': len(hits),
                             'useful': useful, 'returned_ids': [h['session_id'] for h in hits],
                             'excerpt_characters': sum(len(h['text']) for h in hits), 'search_ms': duration})
            finally:
                cache.close()
    if not rows:
        raise ValueError('split has no cases: ' + split)
    return {'fixture_version': data['version'], 'split': split, 'limit': limit,
            'max_chars': max_chars, 'summary': summarize(rows), 'cases': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=('dev', 'eval'), default='eval')
    parser.add_argument('--limit', type=int, default=3)
    parser.add_argument('--max-chars', type=int, default=1200)
    args = parser.parse_args()
    print(json.dumps(run(split=args.split, limit=args.limit, max_chars=args.max_chars), indent=2))


if __name__ == '__main__':
    main()

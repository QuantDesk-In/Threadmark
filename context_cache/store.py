"""Private, project-isolated local index of selected Codex transcript messages.

The data in this index is untrusted historical text, never instructions.
"""
from __future__ import annotations

import json
import hashlib
import stat
import os
from pathlib import Path
import re
import sqlite3

# A conservative screen, not a guarantee that all sensitive data is removed.
_SECRET = re.compile(
    r'(?i)(?:\b(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|password|passwd|client[_ -]?secret|private[_ -]?key|authorization)\b[\"\']?\s*[:=]|'
    r'-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk|ghp|github_pat|xox[baprs])-?[A-Za-z0-9_-]{16,}|\bBearer\s+[A-Za-z0-9._-]{12,})'
)
_WORD = re.compile(r'[\w]{3,}', re.UNICODE)
_STOP = frozenset('the and for with this that from your have what when where how should would could into about then than using use'.split())
_MAX_MESSAGE = 4000


def _project(value: str) -> str:
    return str(Path(value).expanduser().resolve())


def _extract(path: Path):
    """Return complete, selected messages from a Codex rollout; ignore invalid lines."""
    project = None
    session = None
    messages = []
    with path.open('r', encoding='utf-8') as stream:
        for number, line in enumerate(stream):
            if not line.endswith('\n'):
                continue
            try:
                entry = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if not isinstance(entry, dict):
                continue
            payload = entry.get('payload')
            if not isinstance(payload, dict):
                continue
            if entry.get('type') == 'session_meta':
                cwd = payload.get('cwd')
                sid = payload.get('id') or payload.get('session_id')
                if isinstance(cwd, str) and cwd and isinstance(sid, str) and sid:
                    project, session = _project(cwd), sid
            if entry.get('type') != 'response_item' or payload.get('type') != 'message':
                continue
            role = payload.get('role')
            if role not in ('user', 'assistant') or not project or not session:
                continue
            if role == 'assistant' and payload.get('phase') not in (None, 'final'):
                continue
            content = payload.get('content')
            if not isinstance(content, list):
                continue
            parts = [part.get('text') for part in content if isinstance(part, dict)
                     and part.get('type') in ('input_text', 'output_text') and isinstance(part.get('text'), str)]
            text = '\n'.join(parts).strip()
            # Do not copy environment wrappers or likely credential-bearing messages.
            if not text or _SECRET.search(text) or '<environment_context>' in text or '<INSTRUCTIONS>' in text:
                continue
            text = text[:_MAX_MESSAGE]
            messages.append((number, session, project, role, str(entry.get('timestamp', '')), text))
    return messages


class Cache:
    def __init__(self, db_path: str | Path):
        path = Path(db_path).expanduser()
        if not path.parent.exists():
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise PermissionError('cache database must be a private regular file (0600)')
        finally:
            os.close(fd)
        self.db = sqlite3.connect(path, timeout=1)
        self.db.execute('PRAGMA secure_delete = ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS sources (
                path TEXT PRIMARY KEY, root TEXT NOT NULL, fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY, path TEXT NOT NULL, line INTEGER NOT NULL,
                session_id TEXT NOT NULL, project TEXT NOT NULL, role TEXT NOT NULL,
                timestamp TEXT NOT NULL, text TEXT NOT NULL, UNIQUE(path, line)
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS message_fts USING fts5(text, content='messages', content_rowid='id');
            CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                INSERT INTO message_fts(rowid, text) VALUES (new.id, new.text);
            END;
            CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                INSERT INTO message_fts(message_fts, rowid, text) VALUES ('delete', old.id, old.text);
            END;
        ''')

    def close(self):
        self.db.close()

    def sync(self, session_root: str | Path) -> int:
        """Index changed JSONL files under root and remove entries for deleted files."""
        root = Path(session_root).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(f'session directory not found: {root}')
        old = dict(self.db.execute('SELECT path, fingerprint FROM sources WHERE root = ?', (str(root),)))
        seen = set()
        count = 0
        for path in root.rglob('*.jsonl'):
            if path.is_symlink() or not path.is_file():
                continue
            name = str(path.resolve())
            seen.add(name)
            try:
                stat = path.stat()
                fingerprint = f'{stat.st_mtime_ns}:{stat.st_size}:{stat.st_ino}'
                if old.get(name) == fingerprint:
                    continue
                entries = _extract(path)
                # Do not mark a file unchanged if it changed during reading.
                after = path.stat()
                if (after.st_mtime_ns, after.st_size, after.st_ino) != (stat.st_mtime_ns, stat.st_size, stat.st_ino):
                    continue
                with self.db:
                    self.db.execute('DELETE FROM messages WHERE path = ?', (name,))
                    self.db.executemany('INSERT INTO messages(path,line,session_id,project,role,timestamp,text) VALUES (?,?,?,?,?,?,?)',
                                        [(name, *item) for item in entries])
                    self.db.execute('INSERT OR REPLACE INTO sources(path,root,fingerprint) VALUES(?,?,?)', (name, str(root), fingerprint))
                count += len(entries)
            except (OSError, UnicodeError):
                # Keep previous index for inaccessible files, retry next sync.
                continue
        with self.db:
            for name in old.keys() - seen:
                self.db.execute('DELETE FROM messages WHERE path = ?', (name,))
                self.db.execute('DELETE FROM sources WHERE path = ?', (name,))
        return count

    def ingest_event(self, *, project: str, session_id: str, turn_id: str,
                     role: str, text: str, timestamp: str = '') -> bool:
        """Store a hook event once per session, turn and role, without reading transcripts."""
        if any(not isinstance(x, str) or not x.strip() or len(x) > 4096
               for x in (project, session_id, turn_id)):
            return False
        if role not in ('user', 'assistant') or not isinstance(text, str) or not text.strip():
            return False
        if not isinstance(timestamp, str) or len(timestamp) > 128:
            return False
        if _SECRET.search(text) or '<environment_context>' in text or '<INSTRUCTIONS>' in text:
            return False
        key = json.dumps([session_id, turn_id, role], ensure_ascii=True, separators=(',', ':'))
        path = 'event:' + hashlib.sha256(key.encode('utf-8')).hexdigest()
        with self.db:
            self.db.execute('DELETE FROM messages WHERE path = ?', (path,))
            self.db.execute('INSERT INTO messages(path,line,session_id,project,role,timestamp,text) VALUES(?,0,?,?,?,?,?)',
                            (path, session_id, _project(project), role, timestamp, text.strip()[:_MAX_MESSAGE]))
        return True

    def search(self, query: str, *, project: str, exclude_session: str | None = None,
               limit: int = 3, max_chars: int = 1200) -> list[dict]:
        """Find relevant excerpts within exactly one canonical project path."""
        terms = list(dict.fromkeys(t.lower() for t in _WORD.findall(query) if t.lower() not in _STOP))[:12]
        if not terms or limit <= 0 or max_chars <= 0:
            return []
        expression = ' OR '.join('"' + t.replace('"', '""') + '"' for t in terms)
        sql = '''SELECT m.text, m.role, m.session_id, m.timestamp, m.project
                 FROM message_fts f JOIN messages m ON m.id=f.rowid
                 WHERE message_fts MATCH ? AND m.project = ? AND (? IS NULL OR m.session_id != ?)
                 ORDER BY bm25(message_fts), m.timestamp DESC LIMIT ?'''
        rows = list(self.db.execute(sql, (expression, _project(project), exclude_session, exclude_session, 100)))
        if len(terms) == 1 and (len(terms[0]) < 6 or len(rows) > 2):
            return []
        hits = []
        remaining = min(max_chars, 12000)
        for text, role, session_id, timestamp, item_project in rows:
            if len(terms) > 1 and len(set(terms) & set(t.lower() for t in _WORD.findall(text))) < 2:
                continue
            if len(hits) >= min(limit, 20):
                break
            if remaining <= 0:
                break
            excerpt = text[:remaining]
            remaining -= len(excerpt)
            hits.append(dict(text=excerpt, role=role, session_id=session_id, timestamp=timestamp, project=item_project))
        return hits

    def clear(self):
        """Remove all indexed messages and compact the database."""
        with self.db:
            self.db.execute('DELETE FROM messages')
            self.db.execute('DELETE FROM sources')
            self.db.execute("INSERT INTO message_fts(message_fts) VALUES('optimize')")
        self.db.execute('VACUUM')

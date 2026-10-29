"""Inspect or clear Threadmark's local index."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
from .store import Cache


def database():
    codex_home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).expanduser()
    return Path(os.environ.get('THREADMARK_HOME', str(codex_home / 'threadmark'))).expanduser() / 'cache.sqlite3'


def main():
    parser = argparse.ArgumentParser(description='Inspect or clear the local Threadmark index')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status', help='show index path and message count')
    search = commands.add_parser('search', help='search one project; results may contain sensitive data')
    search.add_argument('query')
    search.add_argument('--project', default=os.getcwd(), help='absolute project working directory (default: current directory)')
    commands.add_parser('clear', help='delete all indexed entries; stop hooks first')
    args = parser.parse_args()
    path = database()
    if not path.is_file():
        print(json.dumps({'database': str(path), 'exists': False}))
        return
    cache = Cache(path)
    try:
        if args.command == 'status':
            count = cache.db.execute('SELECT count(*) FROM messages').fetchone()[0]
            print(json.dumps({'database': str(path), 'exists': True, 'messages': count}))
        elif args.command == 'search':
            print(json.dumps(cache.search(args.query, project=args.project, limit=10, max_chars=4000), ensure_ascii=False, indent=2))
        else:
            cache.clear()
            print(json.dumps({'database': str(path), 'cleared': True}))
    finally:
        cache.close()


if __name__ == '__main__':
    main()

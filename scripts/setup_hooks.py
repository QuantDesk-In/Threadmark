#!/usr/bin/env python3
"""Install/remove only Threadmark entries in a Codex user hooks.json file."""
import argparse
import json
import os
from pathlib import Path
import shlex
import tempfile

MARKER = 'Threadmark local context'
SCRIPT = Path(__file__).resolve().parent.parent / 'hooks' / 'threadmark_hook.py'
COMMAND = 'python3 ' + shlex.quote(str(SCRIPT))


def update(action, home):
    target = home / 'hooks.json'
    if target.is_symlink():
        raise ValueError('Refusing to replace a symlinked hooks.json')
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    config = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    if not isinstance(config, dict) or not isinstance(config.get('hooks', {}), dict):
        raise ValueError('hooks.json must contain an object with an object-valued hooks field')
    hooks = config.setdefault('hooks', {})
    for event in ('UserPromptSubmit', 'Stop'):
        groups = hooks.get(event, [])
        if not isinstance(groups, list):
            raise ValueError(event + ' must be an array')
        clean = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get('hooks'), list):
                raise ValueError(event + ' contains an invalid hook group')
            handlers = [h for h in group['hooks'] if not (isinstance(h, dict) and h.get('statusMessage') == MARKER and h.get('command') == COMMAND)]
            if len(handlers) == len(group['hooks']):
                clean.append(group)
            elif handlers:
                clean.append({**group, 'hooks': handlers})
        if action == 'install':
            handler = {'type': 'command', 'command': COMMAND, 'timeout': 5, 'statusMessage': MARKER}
            if event == 'UserPromptSubmit':
                handler['additionalContextLimit'] = 500
            clean.append({'hooks': [handler]})
        if clean:
            hooks[event] = clean
        else:
            hooks.pop(event, None)
    # Write atomically, preserving other settings and never writing a partial file.
    fd, name = tempfile.mkstemp(prefix='.threadmark-hooks-', dir=home)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(config, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'remove'))
    parser.add_argument('--codex-home', type=Path, default=Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).expanduser())
    args = parser.parse_args()
    try:
        target = update(args.action, args.codex_home.expanduser())
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Threadmark setup failed: {exc}\n')
    print(f'{args.action} complete: {target}')


if __name__ == '__main__':
    main()

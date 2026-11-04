#!/usr/bin/env python3
"""Heuristic audit of publication-eligible files; not a privacy certification."""
from pathlib import Path
import hashlib
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root).decode().split('\0')
rules = {
    'private key material': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'local home path': re.compile(r'/(?:Users|home)/[A-Za-z0-9_.-]+/'),
    'personal email': re.compile(r'\b[A-Za-z0-9_.+-]+@(?!example\.(?:com|org|net|invalid)\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
}
errors = []
for relative in filter(None, paths):
    path = root / relative
    if path.is_symlink():
        errors.append(f'{relative}: symbolic link requires review')
        continue
    try:
        content = path.read_text()
    except UnicodeDecodeError:
        errors.append(f'{relative}: binary requires review')
        continue
    for label, pattern in rules.items():
        # Preserve the exact legally required public upstream copyright notice.
        if (label == 'personal email' and relative == 'tini-LICENSE'
                and hashlib.sha256(path.read_bytes()).hexdigest() == 'e5f46bca81266bdd511cf08018d66866870531794569c04f9b45f50dd23c28b0'):
            continue
        if pattern.search(content): errors.append(f'{relative}: {label}')
print('\n'.join(errors) if errors else f'Publication heuristics passed for {len(list(filter(None, paths)))} files')
sys.exit(bool(errors))

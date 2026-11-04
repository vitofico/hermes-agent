"""Pinned-base compatibility patch: explicit empty webhook toolsets deny tools.

Fail the image build on source drift. Revalidate/remove on an upstream upgrade.
"""
from pathlib import Path

changes = {
    'gateway/platforms/webhook.py': (
        'return [str(t).strip() for t in toolsets if str(t).strip()] or None',
        'return [str(t).strip() for t in toolsets if str(t).strip()]',
    ),
    'gateway/run_turn.py': (
        '        if override and isinstance(override, list):\n',
        '        if isinstance(override, list):\n'
        '            if not override:\n'
        '                return []  # Explicit per-source denial, including default MCP tools.\n',
    ),
}
for relative, (before, after) in changes.items():
    path = Path('/opt/hermes') / relative
    source = path.read_text()
    if source.count(before) != 1:
        raise SystemExit(f'Unexpected pinned upstream source: {relative}')
    path.write_text(source.replace(before, after))

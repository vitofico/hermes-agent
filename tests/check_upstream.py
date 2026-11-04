"""Exercise methods extracted from the actual pinned and patched upstream source.

Run in the image build, without importing optional providers or making requests.
"""
import ast
import logging
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Optional, List


def method(path, name, extra=None):
    source = ast.parse(Path('/opt/hermes', path).read_text())
    nodes = [node for node in ast.walk(source) if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(nodes) == 1, name
    namespace = {'Optional': Optional, 'List': List, **(extra or {})}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), path, 'exec'), namespace)
    return namespace[name]


adapter_method = method('gateway/platforms/webhook.py', 'toolsets_for_source')
resolve = method('gateway/run_turn.py', '_resolve_enabled_toolsets_for_source')
source = SimpleNamespace(user_id='webhook:uptime-kuma')
adapter = SimpleNamespace(_routes={'uptime-kuma': {'toolsets': []}})
adapter.toolsets_for_source = lambda value: adapter_method(adapter, value)
runner = SimpleNamespace(_delivery_adapter_for=lambda _: adapter)
fake = ModuleType('hermes_cli.tools_config')
# Simulate a broad platform fallback and MCP configuration; empty must bypass it.
fake._get_platform_tools = lambda config, platform: config.get('platform_toolsets', {}).get(platform, ['terminal', 'mcp-private'])
sys.modules['hermes_cli'] = ModuleType('hermes_cli')
sys.modules['hermes_cli.tools_config'] = fake
assert adapter.toolsets_for_source(source) == []
assert resolve(runner, {}, source, 'webhook') == []
adapter._routes['uptime-kuma']['toolsets'] = ['terminal']
assert resolve(runner, {}, source, 'webhook') == ['terminal']
adapter._routes['uptime-kuma'].pop('toolsets')
assert resolve(runner, {}, source, 'webhook') == ['mcp-private', 'terminal']
print('Pinned upstream empty-toolset regression checks passed')

# This pinned upstream intentionally returns false (process exit1) for an
# unplanned SIGTERM after teardown, so supervisors restart it. Keep smoke
# expectations tied to actual source rather than accepting arbitrary nonzero.
verdict = method('gateway/run_shutdown.py', '_resolve_gateway_exit_verdict', {
    'logger': logging.getLogger('upstream-regression'),
    '_exit_with_failure_verdict': lambda runner: False,
})
runner = SimpleNamespace(exit_code=None, _restart_requested=False, _restart_via_service=False)
assert verdict(runner, True) is False
assert verdict(runner, False) is True
print('Pinned upstream signal-shutdown verdict regression passed')

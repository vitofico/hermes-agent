import os
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest

ENTRYPOINT = Path(__file__).parents[1] / 'entrypoint.sh'


class EntrypointTests(unittest.TestCase):
    def run_gateway(self, variables=None, program=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / 'hermes'
            executable.write_text(program or '#!/bin/sh\nprintf "%s\\n" "$HOME" "$HERMES_HOME" "$TELEGRAM_ALLOWED_USERS" "$WEBHOOK_SECRET"\nexit 7\n')
            executable.chmod(0o755)
            env = {'PATH': str(root) + ':/usr/bin:/bin', 'HOME': str(root), **(variables or {})}
            result = subprocess.run(['bash', str(ENTRYPOINT)], env=env, capture_output=True, text=True)
            self.assertFalse((root / '.env').exists())
            self.assertFalse((root / '.hermes/.env').exists())
            return result

    def test_telegram_optional_and_exit_propagated(self):
        result = self.run_gateway()
        self.assertEqual(result.returncode, 7)
        self.assertIn('/.hermes', result.stdout)

    def test_native_allowlist_and_webhook_alias(self):
        result = self.run_gateway({'TELEGRAM_BOT_TOKEN': 'synthetic', 'TELEGRAM_ALLOWED_USERS': '123,456', 'HERMES_WEBHOOK_SECRET': 'test-key', 'WEBHOOK_ENABLED': 'true'})
        self.assertEqual(result.returncode, 7)
        self.assertIn('123,456\ntest-key', result.stdout)

    def test_legacy_id_alias(self):
        self.assertIn('123', self.run_gateway({'TELEGRAM_USER_ID': '123'}).stdout)

    def test_explicit_home_honored(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIn(directory, self.run_gateway({'HERMES_HOME': directory}).stdout)

    def test_enabled_adapters_fail_without_credentials(self):
        for variables in [{'TELEGRAM_BOT_TOKEN': 'synthetic'}, {'WEBHOOK_ENABLED': 'true'}]:
            result = self.run_gateway(variables)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn('synthetic', result.stderr)

    def test_signals_reach_gateway(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / 'hermes'
            executable.write_text('#!/usr/bin/env python3\nimport os, signal\nprint("ready", flush=True)\nsignal.pause()\n')
            executable.chmod(0o755)
            env = {**os.environ, 'PATH': str(root) + ':' + os.environ['PATH'], 'HOME': directory}
            for name in ['TELEGRAM_BOT_TOKEN', 'WEBHOOK_ENABLED']:
                env.pop(name, None)
            child = subprocess.Popen(['bash', str(ENTRYPOINT)], env=env, stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), 'ready')
                child.send_signal(signal.SIGTERM)
                self.assertEqual(child.wait(timeout=5), -signal.SIGTERM)
            finally:
                if child.poll() is None: child.kill()
                child.wait()
                child.stdout.close()

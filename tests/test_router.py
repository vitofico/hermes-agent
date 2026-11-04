import hashlib
import hmac
import importlib.util
import io
import json
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('router', Path(__file__).parents[1] / 'router/router.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def payload(status=0, mid=1):
    return {'heartbeat': {'status': status}, 'monitor': {'id': mid}}


class RouterTests(unittest.TestCase):
    def setUp(self):
        r._incidents.clear()
        r._inflight.clear()

    def test_down_duplicate_up_and_unsolicited_up(self):
        with patch.object(r, '_forward', return_value=(200, 'ok')) as forward:
            self.assertEqual(r.process(payload())[1]['action'], 'forwarded')
            self.assertEqual(r.process(payload())[1]['action'], 'suppressed')
            self.assertEqual(r.process(payload(1))[1]['event'], 'up')
            self.assertEqual(r.process(payload(1))[1]['action'], 'suppressed')
            self.assertEqual(forward.call_count, 2)

    def test_failed_down_retries_same_delivery_identity(self):
        with patch.object(r, '_forward', side_effect=[(0, 'unavailable'), (200, 'ok')]) as forward:
            self.assertEqual(r.process(payload())[0], 502)
            identity = r._incidents['1']['id']
            self.assertEqual(r.process(payload())[0], 202)
            self.assertEqual(forward.call_args.args[2]['id'], identity)

    def test_failed_recovery_retries(self):
        with patch.object(r, '_forward', side_effect=[(200, 'ok'), (500, 'failed'), (200, 'ok')]):
            r.process(payload())
            self.assertEqual(r.process(payload(1))[0], 502)
            self.assertIn('1', r._incidents)
            self.assertEqual(r.process(payload(1))[1]['action'], 'forwarded')
            self.assertNotIn('1', r._incidents)

    def test_same_monitor_inflight_returns_retry(self):
        r._inflight.add('1')
        self.assertEqual(r.process(payload())[0], 503)

    def test_capacity_and_global_expiry(self):
        with patch.object(r, 'MAX_INCIDENTS', 1), patch.object(r, '_forward', return_value=(200, 'ok')):
            r.process(payload())
            self.assertEqual(r.process(payload(mid=2))[0], 503)
            r._incidents['1']['since'] -= r.INCIDENT_TTL + 1
            self.assertEqual(r.process(payload(mid=2))[0], 202)
            self.assertNotIn('1', r._incidents)

    def test_nonactionable_status_does_not_forward(self):
        with patch.object(r, '_forward') as forward:
            for status in [2, 3, 999]:
                self.assertEqual(r.process(payload(status))[1]['action'], 'ignored')
            forward.assert_not_called()

    def test_invalid_shapes(self):
        for value in [{}, {'heartbeat': []}, {'heartbeat': {'status': []}, 'monitor': {}}, payload(True), payload(mid=[]), payload(mid='')]:
            with self.subTest(value=value):
                self.assertEqual(r.process(value)[0], 400)

    def test_signature_and_distinct_recovery_id(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
        with patch.object(r, 'HERMES_URL', 'http://example.invalid/hook'), patch.object(r, 'HERMES_WEBHOOK_SECRET', 'synthetic-key'), patch.object(r._opener, 'open', return_value=Response()) as opened:
            incident = {'id': 'test'}
            for event in ['down', 'up']:
                r._forward(payload(), event, incident)
                request = opened.call_args.args[0]
                timestamp = request.get_header('X-webhook-timestamp')
                expected = hmac.new(b'synthetic-key', timestamp.encode() + b'.' + request.data, hashlib.sha256).hexdigest()
                self.assertEqual(request.get_header('X-webhook-signature-v2'), expected)
                self.assertEqual(json.loads(request.data)['event_type'], event)
                self.assertEqual(request.get_header('X-request-id'), f'incident-test-{event}')

    def handler(self, body=b'{}', secret='synthetic', **headers):
        handler = object.__new__(r.Handler)
        handler.path = '/webhooks/uptime-kuma'
        handler.headers = Message()
        handler.headers['X-Webhook-Secret'] = secret
        handler.headers['Content-Length'] = str(len(body))
        for key, value in headers.items(): handler.headers[key] = value
        handler.rfile = io.BytesIO(body)
        handler._send_json = lambda code, obj: setattr(handler, 'result', (code, obj))
        return handler

    def test_http_auth_and_malformed_input(self):
        with patch.object(r, 'WEBHOOK_SHARED_SECRET', 'synthetic'), patch.object(r, 'HERMES_WEBHOOK_SECRET', 'synthetic-key'):
            cases = [(b'{}', 'wrong', 401), (b'[]', 'synthetic', 400), (b'not json', 'synthetic', 400), (b'{}', 'synthetic', 400)]
            for body, secret, code in cases:
                handler = self.handler(body, secret)
                handler.do_POST()
                self.assertEqual(handler.result[0], code)
            handler = self.handler(b'{}', **{'Transfer-Encoding': 'chunked'})
            handler.do_POST()
            self.assertEqual(handler.result[0], 400)
            handler = self.handler(b'{}', **{'Content-Length': '1000001'})
            handler.do_POST()
            self.assertEqual(handler.result[0], 400)  # duplicate lengths rejected

    def test_upstream_errors_are_redacted(self):
        with patch.object(r, 'HERMES_URL', 'http://example.invalid/hook'), patch.object(r._opener, 'open', side_effect=OSError('secret payload')):
            self.assertEqual(r._forward(payload(), 'down', {'id': 'test'}), (0, 'upstream unavailable'))

    def test_redirects_rejected(self):
        self.assertIsNone(r.NoRedirect().redirect_request(None, None, 302, '', {}, 'http://example.invalid'))

    def test_worker_capacity_returns_retryable_http_error(self):
        server = object.__new__(r.BoundedHTTPServer)
        server._slots = r.threading.BoundedSemaphore(1)
        server._slots.acquire()
        server.shutdown_request = Mock()
        request = Mock()
        server.process_request(request, ('127.0.0.1', 1))
        self.assertIn(b'503', request.sendall.call_args.args[0])
        server.shutdown_request.assert_called_once_with(request)

    def test_router_distribution_includes_project_license(self):
        root = Path(__file__).parents[1]
        self.assertEqual((root / 'LICENSE').read_text(), (root / 'router/LICENSE').read_text())

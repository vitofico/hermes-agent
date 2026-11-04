#!/usr/bin/env python3
"""Authenticate Uptime Kuma events and forward signed incident transitions.

Incident state is in memory. Restarts may repeat a DOWN. Run one replica;
network policies and cluster privileges are deployment responsibilities.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WEBHOOK_SHARED_SECRET = os.environ.get("WEBHOOK_SHARED_SECRET", "")
HERMES_WEBHOOK_SECRET = os.environ.get("HERMES_WEBHOOK_SECRET", "")
HERMES_URL = os.environ.get("HERMES_URL", "")
LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "8080"))
HERMES_TIMEOUT = float(os.environ.get("HERMES_TIMEOUT", "15"))
INCIDENT_TTL = int(os.environ.get("INCIDENT_TTL", "7200"))
MAX_INCIDENTS = int(os.environ.get("MAX_INCIDENTS", "10000"))
MAX_BODY = 1_000_000
LOG = logging.getLogger("alert-router")
_lock = threading.Lock()
_incidents: dict[str, dict] = {}
_inflight: set[str] = set()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Do not forward a signed private payload to a redirect destination."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def _forward(payload: dict, event: str, incident: dict) -> tuple[int, str]:
    body = json.dumps({**payload, "event_type": event}, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    signature = hmac.new(HERMES_WEBHOOK_SECRET.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(HERMES_URL, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "X-Request-ID": f"incident-{incident['id']}-{event}",
        "X-Webhook-Timestamp": timestamp,
        "X-Webhook-Signature-V2": signature,
    })
    try:
        with _opener.open(req, timeout=HERMES_TIMEOUT) as resp:
            return resp.status, "forwarded"
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        return code, "upstream HTTP error"
    except (urllib.error.URLError, OSError, ValueError):
        return 0, "upstream unavailable"


def process(payload: dict) -> tuple[int, dict]:
    heartbeat, monitor = payload.get("heartbeat"), payload.get("monitor")
    if not isinstance(heartbeat, dict) or not isinstance(monitor, dict):
        return 400, {"error": "heartbeat and monitor objects are required"}
    status = heartbeat.get("status")
    if type(status) is not int:
        return 400, {"error": "heartbeat.status must be an integer"}
    mid = monitor.get("id")
    name = monitor.get("name")
    if type(mid) not in (str, int) and not isinstance(name, str):
        return 400, {"error": "monitor.id or monitor.name is required"}
    key = str(mid) if type(mid) in (str, int) else name
    if not key or len(key) > 512:
        return 400, {"error": "invalid monitor identity"}
    if status not in (0, 1):
        return 202, {"action": "ignored"}
    event = "down" if status == 0 else "up"
    now = time.monotonic()
    with _lock:
        for old_key in list(_incidents):
            if old_key not in _inflight and now - _incidents[old_key]["since"] > INCIDENT_TTL:
                del _incidents[old_key]
        if key in _inflight:
            return 503, {"error": "monitor delivery in progress; retry"}
        incident = _incidents.get(key)
        if event == "down" and incident and incident["delivered"]:
            return 202, {"action": "suppressed"}
        if event == "up" and not incident:
            return 202, {"action": "suppressed"}
        if not incident:
            if len(_incidents) >= MAX_INCIDENTS:
                return 503, {"error": "incident capacity reached"}
            incident = {"since": now, "id": os.urandom(16).hex(), "delivered": False}
            _incidents[key] = incident
        _inflight.add(key)
    try:
        code, summary = _forward(payload, event, incident)
        if not 200 <= code < 300:
            return 502, {"action": "forward_failed", "error": summary}
        with _lock:
            if event == "up":
                _incidents.pop(key, None)
            else:
                incident["delivered"] = True
        return 202, {"action": "forwarded", "event": event}
    finally:
        with _lock:
            _inflight.discard(key)


class Handler(BaseHTTPRequestHandler):
    server_version = "hermes-alert-router/1.0"

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def log_message(self, fmt, *args):
        # Never log request paths, headers, monitor names, or provider errors.
        LOG.debug("HTTP request handled")

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send_json(200, {"status": "ok"}) if self.path == "/health" else self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path.rstrip("/") != "/webhooks/uptime-kuma":
            self._send_json(404, {"error": "not found"})
            return
        if not WEBHOOK_SHARED_SECRET or not HERMES_WEBHOOK_SECRET:
            self._send_json(503, {"error": "router misconfigured"})
            return
        presented = self.headers.get("X-Webhook-Secret", "")
        if not hmac.compare_digest(presented.encode(), WEBHOOK_SHARED_SECRET.encode()):
            self._send_json(401, {"error": "unauthorized"})
            return
        try:
            if self.headers.get("Transfer-Encoding"):
                raise ValueError
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1:
                raise ValueError
            length = int(lengths[0])
            if length <= 0:
                raise ValueError
        except ValueError:
            self._send_json(400, {"error": "invalid content length"})
            return
        if length > MAX_BODY:
            self._send_json(413, {"error": "payload too large"})
            return
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError
        except (ValueError, UnicodeDecodeError, OSError, RecursionError):
            self._send_json(400, {"error": "invalid JSON body"})
            return
        code, result = process(payload)
        self._send_json(code, result)


class BoundedHTTPServer(ThreadingHTTPServer):
    """Limit concurrent readers/forwarders, including slow clients."""
    daemon_threads = True

    def __init__(self, *args, **kwargs):
        self._slots = threading.BoundedSemaphore(64)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            try:
                request.settimeout(1)
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


def main():
    url = urllib.parse.urlsplit(HERMES_URL)
    if not WEBHOOK_SHARED_SECRET or not HERMES_WEBHOOK_SECRET:
        raise SystemExit("WEBHOOK_SHARED_SECRET and HERMES_WEBHOOK_SECRET are required")
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.fragment:
        raise SystemExit("HERMES_URL must be an explicit HTTP(S) endpoint without credentials or fragment")
    if not 0 < HERMES_TIMEOUT <= 60 or INCIDENT_TTL <= 0 or MAX_INCIDENTS <= 0:
        raise SystemExit("invalid timeout, TTL, or capacity")
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    with BoundedHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()

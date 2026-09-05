"""HTTP transport for MarketplaceService — the cross-node boundary.

The rng bit-generator state travels with each request and returns advanced, so an
`http` run reproduces an `inproc` run bit-for-bit (parity test in coms/test).
Uses only the stdlib.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

from .codec import encode, decode


def make_marketplace(cfg: dict, local=None):
    """Return a MarketplaceService: the local object for `inproc`, else a remote client."""
    if cfg.get("transport", "inproc") == "inproc":
        return local
    host = cfg.get("host", "127.0.0.1")
    port = int(cfg.get("port", 8801))
    return RemoteMarketplace(cfg.get("id", "mkt"), f"http://{host}:{port}")


class RemoteMarketplace:
    """Client stub. Satisfies MarketplaceService by calling a remote server."""

    def __init__(self, id: str, url: str) -> None:
        self.id = id
        self.url = url.rstrip("/")

    def _post(self, path: str, payload: dict) -> dict:
        import urllib.request
        req = urllib.request.Request(
            f"{self.url}{path}", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    def run_query(self, user, query, rng, *, correlation_id=None):
        resp = self._post("/run_query", {
            "user": encode(user), "query": query, "correlation_id": correlation_id,
            "rng_state": rng.bit_generator.state})
        rng.bit_generator.state = resp["rng_state"]
        return decode(resp["result"])

    def run_queries_batch(self, items, rng):
        return [self.run_query(u, q, rng, correlation_id=c)
                for (u, q, c) in items]

    def upsert_campaign(self, spec):
        self._post("/upsert_campaign", {"spec": encode(spec)})

    def set_controls(self, controls):
        self._post("/set_controls", {"controls": encode(controls)})

    def reset_day(self):
        self._post("/reset_day", {})

    def snapshot(self) -> dict:
        return self._post("/snapshot", {})


def serve_marketplace(local, host: str = "127.0.0.1", port: int = 8801):
    """Start a threaded HTTP server exposing `local` (a MarketplaceService).
    Returns the server; call .shutdown() to stop."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silence
            pass

        def _read(self) -> dict:
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n) or b"{}")

        def _send(self, obj: dict):
            body = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            p, req = self.path, self._read()
            if p == "/run_query":
                rng = np.random.default_rng()
                rng.bit_generator.state = req["rng_state"]
                qr = local.run_query(decode(req["user"]), req["query"], rng,
                                     correlation_id=req.get("correlation_id"))
                self._send({"result": encode(qr), "rng_state": rng.bit_generator.state})
            elif p == "/upsert_campaign":
                local.upsert_campaign(decode(req["spec"]))
                self._send({"ok": True})
            elif p == "/set_controls":
                local.set_controls(decode(req["controls"]))
                self._send({"ok": True})
            elif p == "/reset_day":
                local.reset_day()
                self._send({"ok": True})
            elif p == "/snapshot":
                self._send(local.snapshot())
            else:
                self._send({"error": "unknown"})

    srv = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

"""Minimal HTTP API for the TrustScore prototype (stdlib only).

Run:  python3 -m trustscore.server [port]     (default 8765)
  GET /              -> demo.html (before/after view)
  GET /api/listings  -> canonical hotel listings + summary (JSON)
  GET /api/activities-> sightseeing groups with like-for-like notes (JSON)
  GET /api/health    -> {"status": "ok"}
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

from .data_gen import generate
from .engine import build_listings, evaluate
from .sightseeing import build_activity_groups

ROOT = os.path.join(os.path.dirname(__file__), "..")
RECORDS = generate()
LISTINGS, POSSIBLE = build_listings(RECORDS)
SUMMARY = {"records_in": len(RECORDS), "listings_out": len(LISTINGS),
           "possible_duplicates_flagged": len(POSSIBLE),
           "evaluation": evaluate(RECORDS, LISTINGS)}
ACTIVITIES = build_activity_groups()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/health":
            self._send(200, json.dumps({"status": "ok"}), "application/json")
        elif self.path == "/api/listings":
            self._send(200, json.dumps({"summary": SUMMARY, "listings": LISTINGS}),
                       "application/json")
        elif self.path == "/api/activities":
            self._send(200, json.dumps({"groups": ACTIVITIES}), "application/json")
        elif self.path in ("/", "/demo.html"):
            path = os.path.join(ROOT, "demo.html")
            if os.path.exists(path):
                with open(path) as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            else:
                self._send(404, "demo.html not built yet — run: python3 -m trustscore.run_demo",
                           "text/plain")
        else:
            self._send(404, "not found", "text/plain")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"TrustScore demo server on http://127.0.0.1:{port}")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()

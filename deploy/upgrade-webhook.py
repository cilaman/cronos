#!/usr/bin/env python3
"""
Upgrade webhook — runs as a host systemd service.
Listens on the Docker bridge (172.18.0.x) so only containers can call it.
Accepts POST /upgrade and runs upgrade.sh as the cronos user.

Install: see deploy/VPS_SETUP.md §10.
"""
import datetime
import hmac
import http.server
import os
import subprocess
import threading

BIND_HOST = os.environ.get("WEBHOOK_HOST", "172.18.0.1")
BIND_PORT = int(os.environ.get("WEBHOOK_PORT", "9137"))
UPGRADE_SCRIPT = os.environ.get("UPGRADE_SCRIPT", "/opt/cronos/upgrade.sh")
UPGRADE_DIR = os.path.dirname(UPGRADE_SCRIPT)
SECRET = os.environ.get("WEBHOOK_SECRET", "")

if not SECRET:
    print(
        "WARNING: WEBHOOK_SECRET is not set — all upgrade requests will be rejected (403). "
        "Set WEBHOOK_SECRET to a strong random value to enable the upgrade endpoint.",
        flush=True,
    )


def authorized(header_value: str) -> bool:
    """Return True iff WEBHOOK_SECRET is set and header_value matches it."""
    if not SECRET:
        return False
    return hmac.compare_digest(header_value.encode(), SECRET.encode())


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/upgrade":
            self._reply(404, b"not found\n")
            return

        ts = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
        client_ip = self.client_address[0]
        print(f"[{ts}] POST /upgrade from {client_ip}", flush=True)

        auth = self.headers.get("X-Upgrade-Secret", "")
        if not authorized(auth):
            print(f"[{ts}] forbidden (bad or missing secret) from {client_ip}", flush=True)
            self._reply(403, b"forbidden\n")
            return

        threading.Thread(
            target=subprocess.run,
            args=([UPGRADE_SCRIPT],),
            kwargs={"capture_output": False, "cwd": UPGRADE_DIR},
            daemon=True,
        ).start()

        self._reply(200, b"upgrade started\n")

    def _reply(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    server = http.server.HTTPServer((BIND_HOST, BIND_PORT), Handler)
    print(f"upgrade-webhook listening on {BIND_HOST}:{BIND_PORT}", flush=True)
    server.serve_forever()

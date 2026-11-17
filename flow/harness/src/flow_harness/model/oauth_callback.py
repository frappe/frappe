"""The loopback redirect receiver both OAuth clients share: `flow login`'s
blocking browser flow and the daemon's background flow. Binding, the path
check, callback parsing, the result page, and quiet logging live here; the
caller supplies only its policy for an arriving callback."""

from __future__ import annotations

import html
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import BaseServer
from urllib.parse import parse_qs, urlparse

from flow_harness.model.providers.codex import REDIRECT_URI

# code, state, error — each None when the callback did not carry it
CallbackResult = tuple[str | None, str | None, str | None]


class Rejected:
	"""Sentinel outcome: answer 404 and keep listening, so a stray local request
	cannot consume a pending login."""


REJECTED = Rejected()


def parse_callback(value: str) -> CallbackResult:
	parsed = urlparse(value.strip())
	query = parse_qs(parsed.query)
	return first(query, "code"), first(query, "state"), first(query, "error")


def first(query: dict[str, list[str]], name: str) -> str | None:
	values = query.get(name)
	return values[0] if values else None


def callback_server(
	on_callback: Callable[[CallbackResult, BaseServer], str | Rejected | None],
) -> ThreadingHTTPServer:
	"""A loopback server on the provider's redirect URI. `on_callback` receives the
	parsed callback and the server, and returns the error to render on the result
	page (None for success) or REJECTED to 404 without consuming the login."""
	redirect = urlparse(REDIRECT_URI)

	class CallbackHandler(BaseHTTPRequestHandler):
		def do_GET(self) -> None:  # BaseHTTPRequestHandler API
			if urlparse(self.path).path != redirect.path:
				self.send_error(404)
				return
			outcome = on_callback(parse_callback(self.path), self.server)
			if isinstance(outcome, Rejected):
				self.send_error(404)
				return
			body = callback_page(outcome)
			self.send_response(200 if not outcome else 400)
			self.send_header("Content-Type", "text/html; charset=utf-8")
			self.send_header("Content-Length", str(len(body)))
			self.send_header("Cache-Control", "no-store")
			self.end_headers()
			self.wfile.write(body)

		def log_message(self, format: str, *args) -> None:
			pass

	return ThreadingHTTPServer(("127.0.0.1", redirect.port or 80), CallbackHandler)


def callback_page(error: str | None) -> bytes:
	title = "Authentication failed" if error else "Authentication successful"
	message = html.escape(error) if error else "You can close this window and return to Flow."
	return (
		"<!doctype html><html><head><meta charset='utf-8'>"
		"<meta name='viewport' content='width=device-width,initial-scale=1'>"
		f"<title>{title}</title>"
		"<style>body{font:15px system-ui;margin:0;display:grid;min-height:100vh;"
		"place-items:center;color:#202020}main{text-align:center;padding:32px}"
		"h1{font-size:20px;margin:0 0 8px}p{color:#666}</style></head>"
		f"<body><main><h1>{title}</h1><p>{message}</p></main></body></html>"
	).encode()

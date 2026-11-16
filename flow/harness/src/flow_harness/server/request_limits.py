"""Request body size cap (`ServerPolicy.max_request_bytes`)."""

from __future__ import annotations

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

REFUSAL = "request body exceeds the server limit"


class RequestSizeLimit:
	"""Refuse a request whose declared Content-Length exceeds `max_bytes` with a 413.

	A guard against accidental huge bodies (which always declare a length), not
	against a token-holder crafting chunked requests to evade it."""

	def __init__(self, app: ASGIApp, max_bytes: int):
		self.app = app
		self.max_bytes = max_bytes

	async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
		if scope["type"] == "http" and _content_length(scope) > self.max_bytes:
			response = JSONResponse({"detail": REFUSAL}, status_code=413)
			await response(scope, receive, send)
			return
		await self.app(scope, receive, send)


def _content_length(scope: Scope) -> int:
	for name, value in scope.get("headers", ()):
		if name == b"content-length":
			try:
				return int(value)
			except ValueError:
				return 0
	return 0
